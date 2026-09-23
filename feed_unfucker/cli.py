"""The fu command. Every fixed step of a run is one subcommand, so any coding agent can call it."""

import argparse
import json
import os
import shutil
import sys
from datetime import timedelta
from pathlib import Path

from . import digest as digest_mod
from . import labels, mail, outbox, state, store
from .config import REPO_ROOT, load_config, set_env_value
from .ingest import IngestError, ingest
from .render import subject as render_subject

PLAYWRIGHT_MCP = "@playwright/mcp@latest"
MIN_HOURS_BETWEEN_READS = 20


def _print_json(value):
    print(json.dumps(value, indent=2, ensure_ascii=False))


def _read_json(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise SystemExit(f"No such file: {path}")
    except json.JSONDecodeError as exc:
        raise SystemExit(f"{path} isn't valid JSON: {exc}")


def cmd_init(args, cfg):
    cfg.home.mkdir(parents=True, exist_ok=True)
    (cfg.home / "inbox").mkdir(exist_ok=True)
    env = cfg.home / "config.env"
    if not env.exists():
        shutil.copyfile(REPO_ROOT / "config.example.env", env)
        env.chmod(0o600)
        print(f"Created {env}. The user fills in their email settings there; don't read it back.")
    if not cfg.preferences_path.exists():
        shutil.copyfile(REPO_ROOT / "preferences.example.md", cfg.preferences_path)
        print(f"Created {cfg.preferences_path} from the example. The user edits it in plain English.")
    store.connect(cfg).close()
    print(f"State folder ready: {cfg.home}")


def cmd_doctor(args, cfg):
    ok = True

    def line(good, text):
        nonlocal ok
        ok = ok and good
        print(("ok    " if good else "todo  ") + text)

    line(sys.version_info >= (3, 9), f"Python {sys.version.split()[0]}")
    line(bool(shutil.which("npx")), "npx is installed (needed for the Playwright MCP server)")
    line(cfg.home.exists(), f"state folder {cfg.home}")
    line(cfg.preferences_path.exists(), f"preferences at {cfg.preferences_path}")
    line(bool(cfg.email_to), f"FU_EMAIL_TO is {'set' if cfg.email_to else 'missing'}")
    if cfg.email_ready():
        print("      email: ./fu sends it over SMTP (digest --send)")
    else:
        print("      email: your email tool sends it (digest --prepare, then ./fu sent)")
    print(f"      this machine: {machine_kind()}")
    print(f"      platforms to read: {', '.join(cfg.platforms) or 'none'}")
    print(f"      digest cadence: {cfg.cadence}" + (f", on {cfg.weekly_day}" if cfg.cadence == "weekly" else ""))
    if cfg.db_path.exists():
        conn = store.connect(cfg)
        last = conn.execute("SELECT started_at, platform, n_seen FROM runs ORDER BY id DESC LIMIT 1").fetchone()
        sent = conn.execute("SELECT sent_at, subject FROM digests ORDER BY id DESC LIMIT 1").fetchone()
        print(f"      last read: {dict(last) if last else 'never'}")
        print(f"      last email: {dict(sent) if sent else 'never'}")
    sys.exit(0 if ok else 1)


def machine_kind():
    """Whether a browser window can appear for the user here. Cloud containers can't show one."""
    if sys.platform in ("darwin", "win32"):
        return "the user's computer"
    if os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"):
        return "the user's computer (Linux desktop)"
    return "no screen: probably a cloud machine, so the user's Chrome can't be reached from here"


def cmd_config(args, cfg):
    """Set one value in state/config.env without printing the file."""
    if not args.key.startswith("FU_") and args.key != "PLAYWRIGHT_MCP_EXTENSION_TOKEN":
        raise SystemExit("Only FU_* settings and PLAYWRIGHT_MCP_EXTENSION_TOKEN can be set here.")
    if args.key == "FU_SMTP_PASSWORD":
        raise SystemExit("The user sets FU_SMTP_PASSWORD themselves, in their own editor.")
    set_env_value(cfg.home / "config.env", args.key, args.value)
    print(f"Set {args.key}.")


def cmd_mcp(args, cfg):
    out = cfg.home / "inbox"
    base = ["npx", "-y", PLAYWRIGHT_MCP, "--output-dir", str(out)]
    if args.window:
        base += ["--user-data-dir", str(cfg.home / "browser-profile")]
    elif args.cloud:
        base += ["--headless", "--isolated", "--storage-state", str(cfg.home / "meta.storage-state.json")]
    else:
        base += ["--extension"]
    print("Playwright MCP server command for this machine:\n")
    print("  " + " ".join(base))
    print("\nClaude Code: the repo's .mcp.json already registers the --extension version.")
    print("  For a different version: claude mcp add --scope project playwright -- " + " ".join(base))
    print("\nCodex:")
    env = " --env PLAYWRIGHT_MCP_EXTENSION_TOKEN=<token>" if "--extension" in base else ""
    print(f"  codex mcp add playwright{env} -- " + " ".join(base))
    print("\nAny other agent: register an MCP server named playwright that runs the command above.")


def cmd_ingest(args, cfg):
    conn = store.connect(cfg)
    path = Path(args.file)
    try:
        summary = ingest(conn, cfg, _read_json(path), path.parent.resolve())
    except IngestError as exc:
        print("The posts file has problems. Fix them and run ingest again:\n" + str(exc), file=sys.stderr)
        sys.exit(2)
    _print_json(summary)


def cmd_pending(args, cfg):
    _print_json(labels.pending(store.connect(cfg), cfg, args.limit))


def cmd_label(args, cfg):
    conn = store.connect(cfg)
    try:
        _print_json(labels.apply_labels(conn, _read_json(args.file)))
    except labels.LabelError as exc:
        print("The labels file has problems. Fix them and run label again:\n" + str(exc), file=sys.stderr)
        sys.exit(2)


def cmd_can_read(args, cfg):
    """Guardrail against reading too often: one read per platform per MIN_HOURS_BETWEEN_READS."""
    if args.platform not in cfg.platforms:
        print(f"{args.platform} is not in FU_PLATFORMS ({', '.join(cfg.platforms) or 'none'}), so don't read it.")
        sys.exit(1)
    conn = store.connect(cfg)
    last = conn.execute("SELECT started_at FROM runs WHERE platform = ? ORDER BY started_at DESC LIMIT 1",
                        (args.platform,)).fetchone()
    if last:
        since = store.utcnow() - store.parse_iso(last["started_at"])
        if since < timedelta(hours=MIN_HOURS_BETWEEN_READS):
            print(f"{args.platform} was read {since.seconds // 3600}h ago. Don't read it again yet.")
            sys.exit(1)
    print(f"ok to read {args.platform}")


def cmd_due(args, cfg):
    due = digest_mod.is_due(store.connect(cfg), cfg)
    print("due" if due else "not due")
    sys.exit(0 if due else 1)


def cmd_digest(args, cfg):
    conn = store.connect(cfg)
    d = digest_mod.build(conn, cfg)
    if args.prepare:
        path = outbox.prepare(conn, cfg, d)
        print(f"Subject: {render_subject(d)}")
        print(f"{len(d.friends)} friends, {d.n_posts} posts, {d.posts_read} posts read this period.")
        if d.waiting_for_label:
            print(f"Warning: {d.waiting_for_label} posts have no label yet and were not included. Run ./fu pending.")
        print(f"Ready to send: {path}")
        print("Send it with your email tool: to, subject, html_body as the HTML body, text_body as the plain-text body.")
        print(f"Then run: ./fu sent {path.stem}")
        return
    if d.broke and not args.preview:
        reason = "no posts were read since the last email. The browser may be logged out, or the page may have changed."
        msg, subject = mail.build_broke_message(cfg, reason, d.period_end)
    else:
        msg, subject = mail.build_digest_message(cfg, d)

    cfg.outbox_dir.mkdir(parents=True, exist_ok=True)
    stamp = d.period_end.strftime("%Y-%m-%d")
    eml = cfg.outbox_dir / f"{stamp}.eml"
    eml.write_bytes(bytes(msg))
    if args.preview:
        from . import render

        page = render.render_html(d, lambda im: str(cfg.home / im["file"]) if im.get("file") else None, cfg.tz)
        preview = Path(args.preview)
        preview.write_text(page, encoding="utf-8")
        print(f"Preview written to {preview}")

    print(f"Subject: {subject}")
    print(f"{len(d.friends)} friends, {d.n_posts} posts, {d.posts_read} posts read this period. Saved as {eml}")
    if d.waiting_for_label:
        print(f"Warning: {d.waiting_for_label} posts have no label yet and were not included. Run ./fu pending.")
    if args.send and d.broke:
        recent = conn.execute("SELECT 1 FROM digests WHERE kind = 'alert' AND sent_at > ?",
                              (store.iso(d.period_end - timedelta(days=3)),)).fetchone()
        if recent:
            print("Not sent: a 'something broke' note already went out in the last 3 days.")
            return
    if args.send:
        mail.send(cfg, msg)
        if d.broke:
            conn.execute("INSERT INTO digests (sent_at, kind, n_posts, n_friends, subject) VALUES (?, 'alert', 0, 0, ?)",
                         (store.iso(d.period_end), subject))
            conn.commit()
        else:
            digest_mod.mark_sent(conn, d, subject)
        print(f"Sent to {cfg.email_to}.")
    else:
        print("Not sent (add --send to send it).")


def cmd_sent(args, cfg):
    info = outbox.mark_sent(store.connect(cfg), args.email_id)
    print(f"Recorded as sent: {info['subject']}")


def cmd_alert(args, cfg):
    if args.prepare:
        path = outbox.prepare_alert(store.connect(cfg), cfg, args.reason, store.utcnow())
        print(f"Ready to send: {path}\nSend it with your email tool, then run: ./fu sent {path.stem}")
        return
    msg, subject = mail.build_broke_message(cfg, args.reason, store.utcnow())
    if args.send:
        mail.send(cfg, msg)
        conn = store.connect(cfg)
        conn.execute("INSERT INTO digests (sent_at, kind, n_posts, n_friends, subject) VALUES (?, 'alert', 0, 0, ?)",
                     (store.iso(store.utcnow()), subject))
        conn.commit()
        print(f"Sent a 'something broke' note to {cfg.email_to}.")
    else:
        print(msg.get_body(("plain",)).get_content())
        print("Not sent (add --send to send it).")


def cmd_status(args, cfg):
    conn = store.connect(cfg)
    counts = {r[0] or "waiting": r[1] for r in conn.execute("SELECT decision, COUNT(*) FROM posts WHERE digested_at IS NULL GROUP BY decision")}
    runs = [dict(r) for r in conn.execute("SELECT started_at, platform, n_seen, n_new, note FROM runs ORDER BY id DESC LIMIT 5")]
    sent = [dict(r) for r in conn.execute("SELECT sent_at, kind, n_posts, subject FROM digests ORDER BY id DESC LIMIT 3")]
    _print_json({"not_yet_emailed": counts, "recent_reads": runs, "recent_emails": sent,
                 "digest_due": digest_mod.is_due(conn, cfg)})


def cmd_prune(args, cfg):
    conn = store.connect(cfg)
    cutoff = store.iso(store.utcnow() - timedelta(days=args.days))
    removed = state.prune(conn, cfg, cutoff)
    print(f"Removed the text and photos of {removed} posts emailed or left out before {cutoff}. Their ids are kept so they never repeat.")


def cmd_state(args, cfg):
    conn = store.connect(cfg)
    if args.action == "export":
        data = state.export_state(conn, cfg)
        Path(args.file).write_text(json.dumps(data, indent=1), encoding="utf-8")
        print(f"Wrote {len(data['keys'])} seen-post keys and {len(data['recent'])} recent sends to {args.file}")
    else:
        n = state.import_state(conn, cfg, _read_json(args.file))
        print(f"Imported {n} seen-post keys.")


def cmd_demo(args, cfg):
    from . import demo

    demo.run(args.out, send=args.send, cfg=cfg)


def main(argv=None):
    parser = argparse.ArgumentParser(prog="fu", description="Feed Unfucker: the fixed steps of a digest run.")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("init", help="create the state folder, config.env and preferences.md")
    sub.add_parser("doctor", help="check setup (never prints secrets)")
    p = sub.add_parser("mcp", help="print the Playwright MCP command for this machine")
    which = p.add_mutually_exclusive_group()
    which.add_argument("--window", action="store_true", help="its own browser window with a saved login, instead of the user's Chrome")
    which.add_argument("--cloud", action="store_true", help="headless, using a saved login file")

    p = sub.add_parser("ingest", help="store posts the agent read (see docs/formats.md)")
    p.add_argument("file")
    p = sub.add_parser("pending", help="print posts that need a label, with preferences.md")
    p.add_argument("--limit", type=int)
    p = sub.add_parser("label", help="store the agent's labels (see docs/formats.md)")
    p.add_argument("file")

    p = sub.add_parser("can-read", help="exit 0 if it's ok to read this platform now (at most once a day)")
    p.add_argument("platform", choices=["facebook", "instagram"])
    sub.add_parser("due", help="exit 0 if a digest should go out now")
    p = sub.add_parser("digest", help="build the digest email")
    how = p.add_mutually_exclusive_group()
    how.add_argument("--send", action="store_true", help="send it over SMTP (needs the FU_SMTP_* settings)")
    how.add_argument("--prepare", action="store_true", help="write it as JSON for the agent's email tool to send")
    p.add_argument("--preview", metavar="HTML_FILE", help="also write an HTML preview to open in a browser")
    p = sub.add_parser("alert", help="email a 'something broke' note")
    p.add_argument("--reason", required=True)
    how = p.add_mutually_exclusive_group()
    how.add_argument("--send", action="store_true", help="send it over SMTP")
    how.add_argument("--prepare", action="store_true", help="write it as JSON for the agent's email tool to send")
    p = sub.add_parser("sent", help="record that the agent sent a prepared email")
    p.add_argument("email_id", help="the name printed by --prepare, like 2026-09-27-0730")
    p = sub.add_parser("config", help="set one value in state/config.env")
    p.add_argument("action", choices=["set"])
    p.add_argument("key")
    p.add_argument("value")

    sub.add_parser("status", help="what's stored, recent reads and emails")
    p = sub.add_parser("prune", help="forget the content of old posts, keep their ids")
    p.add_argument("--days", type=int, default=30)
    p = sub.add_parser("state", help="export or import the small state a cloud run must keep")
    p.add_argument("action", choices=["export", "import"])
    p.add_argument("file")

    p = sub.add_parser("demo", help="build a sample digest from made-up friends, no account needed")
    p.add_argument("--out", default=str(REPO_ROOT / "state" / "demo"), help="folder for the demo's files")
    p.add_argument("--send", action="store_true", help="email the sample digest to yourself")

    args = parser.parse_args(argv)
    cfg = load_config()
    globals()["cmd_" + args.command.replace("-", "_")](args, cfg)
