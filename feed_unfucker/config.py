"""Settings, read from state/config.env and environment variables.

Environment variables win over the file, so a cloud job can pass secrets
without writing them to disk.
"""

import os
from dataclasses import dataclass
from pathlib import Path
from zoneinfo import ZoneInfo

REPO_ROOT = Path(__file__).resolve().parent.parent

DEFAULTS = {
    "FU_CADENCE": "weekly",
    "FU_WEEKLY_DAY": "sunday",
    "FU_SMTP_PORT": "465",
    "FU_TIMEZONE": "",
    "FU_PLATFORMS": "facebook,instagram",
}

WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]


def home_dir():
    return Path(os.environ.get("FU_HOME") or REPO_ROOT / "state").expanduser().resolve()


def read_env_file(path):
    values = {}
    if not path.exists():
        return values
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        values[key.strip()] = value
    return values


@dataclass
class Config:
    home: Path
    preferences_path: Path
    cadence: str
    weekly_day: str
    timezone: str
    smtp_host: str
    smtp_port: int
    smtp_user: str
    smtp_password: str
    email_to: str
    email_from: str
    platforms: tuple = ("facebook", "instagram")

    @property
    def db_path(self):
        return self.home / "feed.sqlite"

    @property
    def images_dir(self):
        return self.home / "images"

    @property
    def outbox_dir(self):
        return self.home / "outbox"

    @property
    def tz(self):
        if self.timezone:
            return ZoneInfo(self.timezone)
        return None  # the machine's local time

    @property
    def cadence_days(self):
        return 1 if self.cadence == "daily" else 7

    def email_ready(self):
        return bool(self.smtp_host and self.smtp_user and self.smtp_password and self.email_to)


def load_config(home=None):
    home = Path(home).resolve() if home else home_dir()
    values = dict(DEFAULTS)
    values.update(read_env_file(home / "config.env"))
    values.update({k: v for k, v in os.environ.items() if k.startswith("FU_")})

    cadence = values.get("FU_CADENCE", "weekly").lower()
    if cadence not in ("daily", "weekly"):
        raise SystemExit(f"FU_CADENCE must be daily or weekly, not {cadence!r}")
    weekly_day = values.get("FU_WEEKLY_DAY", "sunday").lower()
    if weekly_day not in WEEKDAYS:
        raise SystemExit(f"FU_WEEKLY_DAY must be a day name like sunday, not {weekly_day!r}")

    user = values.get("FU_SMTP_USER", "")
    prefs = values.get("FU_PREFERENCES") or str(REPO_ROOT / "preferences.md")
    return Config(
        home=home,
        preferences_path=Path(prefs).expanduser(),
        cadence=cadence,
        weekly_day=weekly_day,
        timezone=values.get("FU_TIMEZONE", ""),
        smtp_host=values.get("FU_SMTP_HOST", ""),
        smtp_port=int(values.get("FU_SMTP_PORT") or 465),
        smtp_user=user,
        smtp_password=values.get("FU_SMTP_PASSWORD", ""),
        email_to=values.get("FU_EMAIL_TO") or user,
        email_from=values.get("FU_EMAIL_FROM") or user,
        platforms=tuple(p.strip().lower() for p in values.get("FU_PLATFORMS", "").split(",") if p.strip()),
    )
