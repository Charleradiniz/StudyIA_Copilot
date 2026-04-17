import os
from pathlib import Path


def load_env_file(env_path: Path) -> None:
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()

        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")

        if key:
            os.environ.setdefault(key, value)


def get_bool_env(name: str, default: bool) -> bool:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default

    return raw_value.strip().lower() in {"1", "true", "yes", "on"}


BASE_DIR = Path(__file__).resolve().parents[1]
PROJECT_DIR = BASE_DIR.parent
load_env_file(BASE_DIR / ".env")

STORAGE_ROOT = Path(os.getenv("STORAGE_ROOT", str(PROJECT_DIR / "storage")))
PDF_STORAGE_PROVIDER = os.getenv("PDF_STORAGE_PROVIDER", "local").strip().lower() or "local"
PDF_STORAGE_DIR = os.getenv(
    "PDF_STORAGE_DIR",
    os.getenv("UPLOAD_DIR", str(STORAGE_ROOT / "pdfs")),
)
UPLOAD_DIR = PDF_STORAGE_DIR
DATA_DIR = os.getenv("DATA_DIR", str(STORAGE_ROOT / "indexes"))
DEFAULT_SQLITE_URL = f"sqlite:///{BASE_DIR / 'studycopilot.db'}"
DATABASE_URL = os.getenv("DATABASE_URL", DEFAULT_SQLITE_URL)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash-lite")
RAG_MODE = os.getenv("RAG_MODE", "full").strip().lower()
APP_NAME = os.getenv("APP_NAME", "StudyIA Copilot")
AUTH_SESSION_TTL_DAYS = int(os.getenv("AUTH_SESSION_TTL_DAYS", "30"))
AUTH_SESSION_COOKIE_NAME = (
    os.getenv("AUTH_SESSION_COOKIE_NAME", "studyiacopilot_session").strip()
    or "studyiacopilot_session"
)
AUTH_SESSION_COOKIE_DOMAIN = os.getenv("AUTH_SESSION_COOKIE_DOMAIN", "").strip() or None
AUTH_SESSION_COOKIE_PATH = os.getenv("AUTH_SESSION_COOKIE_PATH", "/").strip() or "/"
AUTH_SESSION_COOKIE_SAMESITE = os.getenv("AUTH_SESSION_COOKIE_SAMESITE", "lax").strip().lower()
if AUTH_SESSION_COOKIE_SAMESITE not in {"lax", "strict", "none"}:
    AUTH_SESSION_COOKIE_SAMESITE = "lax"
AUTH_SESSION_COOKIE_SECURE = get_bool_env(
    "AUTH_SESSION_COOKIE_SECURE",
    AUTH_SESSION_COOKIE_SAMESITE == "none",
)
PASSWORD_RESET_TOKEN_TTL_MINUTES = int(
    os.getenv("PASSWORD_RESET_TOKEN_TTL_MINUTES", "60")
)
PASSWORD_RESET_URL_TEMPLATE = os.getenv("PASSWORD_RESET_URL_TEMPLATE", "").strip()

SMTP_HOST = os.getenv("SMTP_HOST", "").strip()
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USERNAME = os.getenv("SMTP_USERNAME", "").strip()
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_FROM_EMAIL = os.getenv("SMTP_FROM_EMAIL", "").strip()
SMTP_FROM_NAME = os.getenv("SMTP_FROM_NAME", APP_NAME).strip()
SMTP_USE_TLS = get_bool_env("SMTP_USE_TLS", True)
SMTP_USE_SSL = get_bool_env("SMTP_USE_SSL", False)

raw_cors_origins = os.getenv(
    "CORS_ORIGINS",
    "http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000,http://127.0.0.1:3000",
)
CORS_ORIGINS = [origin.strip() for origin in raw_cors_origins.split(",") if origin.strip()]
