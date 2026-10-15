import os
import secrets
import sys
from ipaddress import ip_network
from datetime import time
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from dotenv import load_dotenv

env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

_INSECURE_DEFAULTS = {
    "docuguard-default-dev-secret-key-change-in-production",
    "replace-with-a-secure-random-secret",
    "changeme",
    "secret",
}

ENVIRONMENT = os.getenv("ENVIRONMENT", "development").strip().lower()
IS_PRODUCTION = ENVIRONMENT in {"production", "prod"}

_raw_secret = os.getenv("JWT_SECRET_KEY", "").strip()
if not _raw_secret or _raw_secret in _INSECURE_DEFAULTS:
    if IS_PRODUCTION:
        print(
            "FATAL: JWT_SECRET_KEY must be set to a strong unique value in production.",
            file=sys.stderr,
        )
        sys.exit(1)
    # Ephemeral secret for local/dev only — tokens reset on process restart.
    _raw_secret = secrets.token_urlsafe(48)
    print(
        "WARNING: JWT_SECRET_KEY unset or insecure; using an ephemeral development secret.",
        file=sys.stderr,
    )

JWT_SECRET_KEY = _raw_secret
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "10080"))
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./docuguard.db")

# Comma-separated origins. Default keeps local Vite + API hosts.
_cors_raw = os.getenv(
    "CORS_ORIGINS",
    "http://127.0.0.1:5173,http://localhost:5173,http://127.0.0.1:8000,http://localhost:8000",
)
CORS_ORIGINS = [o.strip() for o in _cors_raw.split(",") if o.strip()]

MAX_UPLOAD_BYTES = int(os.getenv("MAX_UPLOAD_BYTES", str(15 * 1024 * 1024)))
MAX_PDF_PAGES = int(os.getenv("MAX_PDF_PAGES", "100"))

AUTH_RATE_LIMIT_PER_MINUTE = int(os.getenv("AUTH_RATE_LIMIT_PER_MINUTE", "20"))
UPLOAD_RATE_LIMIT_PER_MINUTE = int(os.getenv("UPLOAD_RATE_LIMIT_PER_MINUTE", "10"))
_trusted_proxy_cidrs = [
    cidr.strip()
    for cidr in os.getenv("TRUSTED_PROXY_CIDRS", "").split(",")
    if cidr.strip()
]
try:
    TRUSTED_PROXY_NETWORKS = tuple(
        ip_network(cidr, strict=False) for cidr in _trusted_proxy_cidrs
    )
except ValueError as exc:
    raise ValueError("TRUSTED_PROXY_CIDRS must contain valid IP networks.") from exc

# Minimum password length for new registrations (existing hashes still verify).
MIN_PASSWORD_LENGTH = int(os.getenv("MIN_PASSWORD_LENGTH", "8"))

APP_TIMEZONE = os.getenv("APP_TIMEZONE", "UTC").strip() or "UTC"
DEFAULT_DATE_ONLY_REMINDER_TIME = (
    os.getenv("DEFAULT_DATE_ONLY_REMINDER_TIME", "09:00").strip() or "09:00"
)
REMINDER_CHECK_INTERVAL_SECONDS = max(
    15, int(os.getenv("REMINDER_CHECK_INTERVAL_SECONDS", "60"))
)
ENABLE_REMINDER_SCHEDULER = (
    os.getenv("ENABLE_REMINDER_SCHEDULER", "true").strip().lower()
    in {"1", "true", "yes", "on"}
)

SMTP_HOST = os.getenv("SMTP_HOST", "").strip()
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USERNAME = os.getenv("SMTP_USERNAME", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_FROM = os.getenv("SMTP_FROM", "").strip()
SMTP_USE_TLS = os.getenv("SMTP_USE_TLS", "true").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}
SMTP_USE_SSL = os.getenv("SMTP_USE_SSL", "false").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}
SMTP_CONFIGURED = bool(
    SMTP_HOST
    and SMTP_FROM
    and (SMTP_USE_TLS != SMTP_USE_SSL)
    and bool(SMTP_USERNAME) == bool(SMTP_PASSWORD)
)

try:
    ZoneInfo(APP_TIMEZONE)
except (ZoneInfoNotFoundError, ValueError) as exc:
    raise ValueError("APP_TIMEZONE must be a valid IANA timezone.") from exc

try:
    default_reminder_time = time.fromisoformat(DEFAULT_DATE_ONLY_REMINDER_TIME)
except ValueError as exc:
    raise ValueError(
        "DEFAULT_DATE_ONLY_REMINDER_TIME must use HH:MM format."
    ) from exc
if default_reminder_time.strftime("%H:%M") != DEFAULT_DATE_ONLY_REMINDER_TIME:
    raise ValueError("DEFAULT_DATE_ONLY_REMINDER_TIME must use HH:MM format.")
