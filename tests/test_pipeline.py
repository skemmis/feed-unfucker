import email
import email.policy
import io
import json
import shutil
import tempfile
import unittest
from contextlib import redirect_stdout
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

from feed_unfucker import digest, labels, mail, outbox, render, state, store
from feed_unfucker.config import REPO_ROOT, load_config, read_env_file, set_env_value
from feed_unfucker.filters import left_out_sentence
from feed_unfucker.ingest import IngestError, ingest, normalize_link, validate


def fake_fetch(image, dest_stem, base_dir):
    dest = dest_stem.with_suffix(".png")
    dest.write_bytes(b"\x89PNG fake")
    return dest


def post(author, text="", **extra):
    return {"author": author, "author_kind": "person", "text": text,
            "posted_at": store.iso(store.utcnow() - timedelta(hours=extra.pop("hours", 5))), **extra}


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        home = Path(self.tmp.name)
        self.cfg = replace(load_config(home), preferences_path=home / "preferences.md",
                           smtp_host="", smtp_user="", smtp_password="", email_to="me@example.com",
                           email_from="me@example.com", cadence="weekly", timezone="UTC")
        self.conn = store.connect(self.cfg)

    def tearDown(self):
        self.conn.close()
        self.tmp.cleanup()

    def ingest(self, posts, platform="facebook"):
        return ingest(self.conn, self.cfg, {"platform": platform, "posts": posts}, Path(self.tmp.name), fetch=fake_fetch)

    def label_all(self, mapping, prefs=None):
        items = []
        for p in labels.pending(self.conn, self.cfg)["posts"]:
            choice = mapping[p["author"]] if isinstance(mapping.get(p["author"]), dict) else {"label": mapping.get(p["author"], "life_update")}
            items.append({"id": p["id"], **choice})
        doc = {"labels": items}
        if prefs is not None:
            doc["preferences"] = prefs
        return labels.apply_labels(self.conn, doc)


class IngestTests(Base):
    def test_validation_lists_every_problem(self):
        with self.assertRaises(IngestError) as ctx:
            validate({"platform": "myspace", "posts": [{"author": ""}, {"author": "A", "is_reshare": "yes"}]})
        msg = str(ctx.exception)
        self.assertIn("platform must be", msg)
        self.assertIn("posts[0]: author is required", msg)
        self.assertIn("posts[1]: is_reshare must be true or false", msg)

    def test_repeats_are_spotted_by_link_and_by_text(self):
        first = self.ingest([post("Jen Park", "Moved house!", link="https://www.facebook.com/jen/posts/1?__cft__[0]=x")])
        self.assertEqual(first["new"], 1)
        again = self.ingest([
            post("Jen Park", "Moved house!", link="https://m.facebook.com/jen/posts/1?__tn__=y"),
            post("Jen Park", "moved   house!"),
        ])
        self.assertEqual((again["new"], again["repeats"]), (0, 2))

    def test_normalize_link_keeps_meaningful_params(self):
        self.assertEqual(
            normalize_link("https://www.facebook.com/permalink.php?story_fbid=42&id=7&__cft__[0]=abc&mibextid=z"),
            "https://facebook.com/permalink.php?id=7&story_fbid=42",
        )

    def test_stage1_drops_ads_suggestions_pages_and_bare_reshares(self):
        s = self.ingest([
            post("Brand", "Buy", is_sponsored=True),
            post("Page", "Look", is_suggested=True),
            {"author": "News Co", "author_kind": "page", "text": "Headline"},
            post("Tom", "", is_reshare=True, reshared_from="Viral"),
            post("Tom", "This made me think of you all", is_reshare=True, reshared_from="Viral"),
            post("Ana", "", images=[{"url": "https://example.com/a.jpg", "alt": "beach"}]),
        ])
        self.assertEqual(s["dropped"], {"sponsored": 1, "suggested": 1, "page": 1, "reshare": 1})
        self.assertEqual(s["waiting_for_label"], 2)

    def test_images_are_saved_under_the_post(self):
        self.ingest([post("Ana", "Beach day", images=[{"url": "https://example.com/a.jpg", "alt": "beach"}])])
        row = self.conn.execute("SELECT id, images FROM posts").fetchone()
        images = json.loads(row["images"])
        self.assertEqual(images[0]["alt"], "beach")
        self.assertTrue((self.cfg.home / images[0]["file"]).exists())
        self.assertIn(row["id"], images[0]["file"])

    def test_failed_image_keeps_a_placeholder(self):
        def broken(image, dest_stem, base_dir):
            raise OSError("expired link")
        ingest(self.conn, self.cfg, {"platform": "instagram", "posts": [
            post("Ana", "", images=[{"url": "https://example.com/a.jpg"}])]}, Path(self.tmp.name), fetch=broken)
        row = self.conn.execute("SELECT images, decision FROM posts").fetchone()
        self.assertEqual(json.loads(row["images"]), [{"file": None, "alt": "", "url": "https://example.com/a.jpg"}])
        self.assertIsNone(row["decision"])  # still a photo post, so it waits for a label


class LabelTests(Base):
    def test_defaults_and_overrides(self):
        self.ingest([post("A", "new job"), post("B", "vote!"), post("C", "football photo")])
        self.label_all({"A": {"label": "life_update"}, "B": {"label": "opinion"},
                        "C": {"label": "photos", "decision": "leave_out"}})
        rows = {r["author"]: (r["decision"], r["left_out_reason"]) for r in self.conn.execute("SELECT * FROM posts")}
        self.assertEqual(rows, {"A": ("keep", None), "B": ("leave_out", "opinion"), "C": ("leave_out", "preference")})

    def test_bad_labels_change_nothing(self):
        self.ingest([post("A", "hi")])
        pid = labels.pending(self.conn, self.cfg)["posts"][0]["id"]
        with self.assertRaises(labels.LabelError):
            labels.apply_labels(self.conn, {"labels": [{"id": pid, "label": "life_update"}, {"id": "nope", "label": "vibes"}]})
        self.assertEqual(len(labels.pending(self.conn, self.cfg)["posts"]), 1)


class DigestTests(Base):
    def test_close_friends_first_then_most_recent(self):
        self.ingest([post("Zed Old", "a", hours=2), post("Jen Park", "b", hours=50), post("Amy New", "c", hours=1)])
        self.label_all({}, prefs={"close_friends": ["Jen"], "max_per_person_per_week": None})
        d = digest.build(self.conn, self.cfg)
        self.assertEqual([f.name for f in d.friends], ["Jen Park", "Amy New", "Zed Old"])
        self.assertEqual(render.subject(d), "Your friends this week: Jen, Amy and Zed")
        self.assertEqual(render.opening_line(d), "3 friends shared 3 things this week.")

    def test_everyday_cap_weekly_cap_and_pinning(self):
        self.ingest([post("Dan", f"thought {i}", hours=i + 1) for i in range(3)]
                    + [post("Maya", f"photo {i}", hours=i + 1) for i in range(3)])
        todo = labels.pending(self.conn, self.cfg)["posts"]
        items = [{"id": p["id"], "label": "everyday"} for p in todo if p["author"] == "Dan"]
        maya = [p for p in todo if p["author"] == "Maya"]
        items += [{"id": p["id"], "label": "photos", "pinned": p["text"] == "photo 2"} for p in maya]
        labels.apply_labels(self.conn, {"preferences": {"close_friends": [], "max_per_person_per_week": 1}, "labels": items})
        d = digest.build(self.conn, self.cfg)
        by_name = {f.name: [p.text for p in f.posts] for f in d.friends}
        self.assertEqual(by_name["Dan"], ["thought 0"])
        self.assertEqual(sorted(by_name["Maya"]), ["photo 0", "photo 2"])  # the pinned one doesn't count
        self.assertEqual(d.left_out["cap"], 3)

    def test_weekly_cap_counts_earlier_digests(self):
        self.ingest([post("Dan", "first")])
        self.label_all({}, prefs={"close_friends": [], "max_per_person_per_week": 1})
        d = digest.build(self.conn, self.cfg)
        digest.mark_sent(self.conn, d, render.subject(d))
        self.ingest([post("Dan", "second")])
        self.label_all({})
        self.assertEqual(digest.build(self.conn, self.cfg).friends, [])

    def test_sent_posts_and_left_out_counts_do_not_repeat(self):
        self.ingest([post("A", "hello"), post("B", "vote!")])
        self.label_all({"B": {"label": "opinion"}})
        d = digest.build(self.conn, self.cfg)
        self.assertEqual(left_out_sentence(d.left_out), "Left out: 1 political or outrage post.")
        digest.mark_sent(self.conn, d, render.subject(d))
        again = digest.build(self.conn, self.cfg)
        self.assertEqual((again.n_posts, sum(again.left_out.values())), (0, 0))

    def test_no_reads_means_broke(self):
        d = digest.build(self.conn, self.cfg)
        self.assertTrue(d.broke)
        self.ingest([])
        self.assertTrue(digest.build(self.conn, self.cfg).broke)
        self.ingest([post("A", "hi")])
        self.assertFalse(digest.build(self.conn, self.cfg).broke)

    def test_due(self):
        cfg = replace(self.cfg, cadence="weekly", weekly_day="sunday")
        sunday = datetime(2026, 9, 27, 8, tzinfo=timezone.utc)
        self.assertTrue(digest.is_due(self.conn, cfg, sunday))
        self.assertFalse(digest.is_due(self.conn, cfg, sunday - timedelta(days=1)))
        self.conn.execute("INSERT INTO digests (sent_at, kind, n_posts, n_friends, subject) VALUES (?, 'digest', 1, 1, 's')",
                          (store.iso(sunday),))
        self.assertFalse(digest.is_due(self.conn, cfg, sunday + timedelta(hours=3)))
        self.assertFalse(digest.is_due(self.conn, cfg, sunday + timedelta(days=3)))
        # Asleep all next Sunday: catches up on Monday.
        self.assertTrue(digest.is_due(self.conn, cfg, sunday + timedelta(days=8)))
        daily = replace(cfg, cadence="daily")
        self.assertTrue(digest.is_due(self.conn, daily, sunday + timedelta(days=1)))


class EmailTests(Base):
    def test_email_has_both_parts_inline_photos_and_no_counts(self):
        self.ingest([post("Ana <script>", "Beach & sun\n\nSecond para",
                          link="https://www.instagram.com/p/abc/",
                          images=[{"url": "https://example.com/a.jpg", "alt": "beach"}])], platform="instagram")
        self.label_all({"Ana <script>": {"label": "photos"}})
        msg, subject = mail.build_digest_message(self.cfg, digest.build(self.conn, self.cfg))
        parsed = email.message_from_bytes(bytes(msg), policy=email.policy.default)
        html_part = parsed.get_body(("html",)).get_content()
        self.assertIn("Ana &lt;script&gt;", html_part)
        self.assertIn("Beach &amp; sun</p>", html_part)
        self.assertIn("See it on Instagram", html_part)
        self.assertIn("alt='Photo shared by Ana &lt;script&gt;: beach'", html_part)
        cids = [p["Content-ID"] for p in parsed.walk() if p.get_content_maintype() == "image"]
        self.assertEqual(len(cids), 1)
        self.assertIn("cid:" + cids[0].strip("<>"), html_part)
        self.assertNotRegex(html_part.lower(), r"\blikes?\b|\bcomments?\b|followers?")
        self.assertIn("Beach & sun", parsed.get_body(("plain",)).get_content())

    def test_broke_note(self):
        msg, subject = mail.build_broke_message(self.cfg, "a login page appeared on facebook.com", store.utcnow())
        self.assertEqual(subject, "Feed Unfucker couldn't read your feed")
        self.assertIn("a login page appeared", msg.get_body(("plain",)).get_content())

    def test_send_refuses_without_settings(self):
        with self.assertRaises(SystemExit):
            mail.send(self.cfg, mail.build_broke_message(self.cfg, "x", store.utcnow())[0])


class OutboxTests(Base):
    def test_prepare_uses_remote_photos_and_sent_records_once(self):
        self.ingest([post("Ana", "Beach", images=[{"url": "https://scontent.example/a.jpg", "alt": "beach"},
                                                   {"path": "missing.png"}]),
                     post("Bo", "vote!")])
        self.label_all({"Bo": {"label": "opinion"}})
        path = outbox.prepare(self.conn, self.cfg, digest.build(self.conn, self.cfg))
        payload = json.loads(path.read_text())
        self.assertEqual(payload["to"], "me@example.com")
        self.assertIn("src='https://scontent.example/a.jpg'", payload["html_body"])
        self.assertNotIn("cid:", payload["html_body"])
        self.assertIn("1 more photo on Facebook", payload["html_body"])
        self.assertIn("Beach", payload["text_body"])
        # Not sent yet: the same posts are still waiting.
        self.assertEqual(digest.build(self.conn, self.cfg).n_posts, 1)
        outbox.mark_sent(self.conn, payload["id"])
        again = digest.build(self.conn, self.cfg)
        self.assertEqual((again.n_posts, sum(again.left_out.values())), (0, 0))
        with self.assertRaises(SystemExit):
            outbox.mark_sent(self.conn, payload["id"])

    def test_prepare_needs_an_address(self):
        with self.assertRaises(SystemExit):
            outbox.prepare(self.conn, replace(self.cfg, email_to=""), digest.build(self.conn, self.cfg))

    def test_broke_prepares_an_alert(self):
        path = outbox.prepare(self.conn, self.cfg, digest.build(self.conn, self.cfg))
        self.assertTrue(path.stem.endswith("-alert"))
        outbox.mark_sent(self.conn, path.stem)
        self.assertEqual(self.conn.execute("SELECT kind FROM digests").fetchone()[0], "alert")

    def test_set_env_value_keeps_other_lines(self):
        env = self.cfg.home / "config.env"
        env.write_text("# note\nFU_CADENCE=weekly\nFU_EMAIL_TO=old@example.com\n")
        set_env_value(env, "FU_EMAIL_TO", "new@example.com")
        set_env_value(env, "FU_TIMEZONE", "Europe/London")
        self.assertEqual(read_env_file(env), {"FU_CADENCE": "weekly", "FU_EMAIL_TO": "new@example.com",
                                              "FU_TIMEZONE": "Europe/London"})
        self.assertTrue(env.read_text().startswith("# note"))


class StateTests(Base):
    def test_export_import_keeps_keys_and_caps_but_no_content(self):
        self.ingest([post("Dan", "secret words", link="https://facebook.com/dan/posts/1")])
        self.label_all({}, prefs={"close_friends": ["Dan"], "max_per_person_per_week": 1})
        d = digest.build(self.conn, self.cfg)
        digest.mark_sent(self.conn, d, render.subject(d))
        data = state.export_state(self.conn, self.cfg)
        self.assertNotIn("secret words", json.dumps(data))

        fresh = Base()
        fresh.setUp()
        try:
            state.import_state(fresh.conn, fresh.cfg, data)
            again = fresh.ingest([post("Dan", "secret words", link="https://facebook.com/dan/posts/1"), post("Dan", "new one")])
            self.assertEqual((again["new"], again["repeats"]), (1, 1))
            fresh.label_all({})
            self.assertEqual(digest.build(fresh.conn, fresh.cfg).friends, [])  # weekly cap carried over
        finally:
            fresh.tearDown()

    def test_settings_and_preferences_survive_a_fresh_machine(self):
        env = self.cfg.home / "config.env"
        set_env_value(env, "FU_EMAIL_TO", "me@example.com")
        set_env_value(env, "FU_CADENCE", "daily")
        set_env_value(env, "FU_SMTP_PASSWORD", "hunter2")
        self.cfg.preferences_path.write_text("Always show Dan.\n", encoding="utf-8")
        data = state.export_state(self.conn, self.cfg)
        self.assertNotIn("hunter2", json.dumps(data))

        fresh = Base()
        fresh.setUp()
        try:
            # A fresh machine starts from the examples, as ./fu init makes it.
            shutil.copyfile(REPO_ROOT / "config.example.env", fresh.cfg.home / "config.env")
            shutil.copyfile(REPO_ROOT / "preferences.example.md", fresh.cfg.preferences_path)
            set_env_value(fresh.cfg.home / "config.env", "FU_TIMEZONE", "Europe/London")
            data["settings"]["FU_TIMEZONE"] = "America/New_York"
            state.import_state(fresh.conn, fresh.cfg, data)
            got = read_env_file(fresh.cfg.home / "config.env")
            self.assertEqual((got["FU_EMAIL_TO"], got["FU_CADENCE"]), ("me@example.com", "daily"))
            self.assertEqual(got["FU_TIMEZONE"], "Europe/London")  # changed on this machine, so kept
            self.assertEqual(got["FU_SMTP_PASSWORD"], "")
            self.assertEqual(fresh.cfg.preferences_path.read_text(encoding="utf-8"), "Always show Dan.\n")
        finally:
            fresh.tearDown()

    def test_prune_forgets_content_keeps_keys(self):
        self.ingest([post("Ana", "hello", images=[{"url": "https://example.com/a.jpg"}])])
        self.label_all({})
        d = digest.build(self.conn, self.cfg)
        digest.mark_sent(self.conn, d, render.subject(d))
        n = state.prune(self.conn, self.cfg, store.iso(store.utcnow() + timedelta(seconds=1)))
        self.assertEqual(n, 1)
        row = self.conn.execute("SELECT text, images FROM posts").fetchone()
        self.assertEqual((row["text"], row["images"]), ("", "[]"))
        self.assertEqual(self.ingest([post("Ana", "hello")])["repeats"], 1)


class DemoTest(unittest.TestCase):
    def test_demo_runs(self):
        from feed_unfucker import demo
        with tempfile.TemporaryDirectory() as tmp:
            out = io.StringIO()
            with redirect_stdout(out):
                demo.run(Path(tmp) / "demo", cfg=load_config(tmp))
            self.assertIn("Subject: Your friends this week: Jen, Marcus and 4 others", out.getvalue())
            self.assertTrue((Path(tmp) / "demo" / "preview.html").exists())


if __name__ == "__main__":
    unittest.main()
