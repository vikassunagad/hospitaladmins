"""All settings in one place. Values come from the .env file (see .env.example)."""
import os
from pathlib import Path

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parents[2]
load_dotenv(ROOT_DIR / ".env")


def _bool(name, default):
    return os.getenv(name, str(default)).strip().lower() in ("1", "true", "yes", "on")


def _int(name, default):
    try:
        return int(os.getenv(name, default))
    except ValueError:
        return default


class Settings:
    APP_NAME = "Hospital Module - Central Emergency Control Room"
    SECRET_KEY = os.getenv("SECRET_KEY") or "dev-secret-change-me"
    DATABASE_URL = os.getenv("DATABASE_URL") or "sqlite:///" + (ROOT_DIR / "hospital.db").as_posix()
    HOSPITAL_CREDENTIALS = {
        number: (
            os.getenv("HOSPITAL%d_USERNAME" % number, "hospital%d" % number),
            os.getenv("HOSPITAL%d_PASSWORD" % number, "1234"),
        )
        for number in range(1, 13)
    }
    CONTROL_ROOM_BASE_URL = os.getenv("CONTROL_ROOM_BASE_URL", "").rstrip("/")
    CONTROL_ROOM_API_KEY = os.getenv("CONTROL_ROOM_API_KEY", "")
    MOCK_CONTROL_ROOM = _bool("MOCK_CONTROL_ROOM", True)
    AUTO_ACCEPT = _bool("AUTO_ACCEPT", True)

    # Hospital load thresholds (percent of all beds used = occupied + reserved)
    HIGH_LOAD_THRESHOLD = _int("HIGH_LOAD_THRESHOLD", 80)
    CRITICAL_LOAD_THRESHOLD = _int("CRITICAL_LOAD_THRESHOLD", 90)
    # Raise ICU / EMERGENCY capacity warning when free beds <= this number
    CAPACITY_WARNING_FREE = _int("CAPACITY_WARNING_FREE", 1)

    SESSION_HOURS = _int("SESSION_HOURS", 8)
    COOKIE_NAME = "hospital_session"
    PASSWORD_ITERATIONS = _int("PASSWORD_ITERATIONS", 200_000)


settings = Settings()
