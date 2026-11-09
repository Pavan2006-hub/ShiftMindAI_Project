import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

INSTANCE_DIR = BASE_DIR / "instance"
DEFAULT_SECRET = "dev-only-change-this-secret"


def _env_bool(name, default="false"):
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "on"}


def _resolve_database_url():
    """Return an absolute database URL.

    A relative SQLite URL such as ``sqlite:///instance/shiftmind.db`` is resolved by
    Flask-SQLAlchemy *inside* the instance folder, which produces
    ``instance/instance/shiftmind.db`` and the error "unable to open database file".
    To avoid that, every relative SQLite path is placed in the instance folder.
    """
    default_path = (INSTANCE_DIR / "shiftmind.db").as_posix()
    url = os.getenv("DATABASE_URL", "").strip()

    if not url:
        return "sqlite:///" + default_path

    # Fix Render/Heroku postgres:// URLs for SQLAlchemy
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)

    if url.startswith("sqlite:///") and not url.startswith("sqlite:////"):
        relative = url[len("sqlite:///"):]

        if relative in ("", ":memory:"):
            return url

        # Windows absolute path such as sqlite:///C:/data/app.db
        if len(relative) > 1 and relative[1] == ":":
            return url

        relative = relative.replace("\\", "/")
        if relative.startswith("instance/"):
            relative = relative[len("instance/"):]

        return "sqlite:///" + (INSTANCE_DIR / relative).as_posix()

    return url


class BaseConfig:
    SECRET_KEY = os.getenv("SECRET_KEY", DEFAULT_SECRET)
    SQLALCHEMY_DATABASE_URI = _resolve_database_url()
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}
    MAX_CONTENT_LENGTH = int(os.getenv("MAX_CONTENT_LENGTH", 5 * 1024 * 1024))
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = _env_bool("COOKIE_SECURE")
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SAMESITE = "Lax"
    WTF_CSRF_ENABLED = True
    WTF_CSRF_TIME_LIMIT = None  # token lives as long as the session
    DEBUG = False
    TESTING = False
    HOST = os.getenv("HOST", "127.0.0.1")
    PORT = int(os.getenv("PORT", "5000"))

    ALLOW_PUBLIC_REGISTRATION = _env_bool("ALLOW_PUBLIC_REGISTRATION")

    # Groq (LLM)
    GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()
    GROQ_MODEL = os.getenv("GROQ_MODEL", "").strip() or "llama-3.3-70b-versatile"

    # Hindsight (long-term memory)
    HINDSIGHT_BASE_URL = (
        os.getenv("HINDSIGHT_BASE_URL", "").strip()
        or "https://api.hindsight.vectorize.io"
    ).rstrip("/")
    HINDSIGHT_API_KEY = os.getenv("HINDSIGHT_API_KEY", "").strip().strip('"').strip("'").replace("Bearer ", "").strip()
    HINDSIGHT_BANK_ID = os.getenv("HINDSIGHT_BANK_ID", "").strip() or "shiftmind"


class DevelopmentConfig(BaseConfig):
    DEBUG = _env_bool("FLASK_DEBUG")


class TestingConfig(BaseConfig):
    TESTING = True
    WTF_CSRF_ENABLED = False
    SQLALCHEMY_DATABASE_URI = "sqlite://"
    SQLALCHEMY_ENGINE_OPTIONS = {}
    SESSION_COOKIE_SECURE = False
    GROQ_API_KEY = ""
    HINDSIGHT_API_KEY = ""
    ALLOW_PUBLIC_REGISTRATION = True


class ProductionConfig(BaseConfig):
    DEBUG = False
    SESSION_COOKIE_SECURE = True
    REMEMBER_COOKIE_SECURE = True


def get_config():
    environment = os.getenv("FLASK_ENV", "development").lower()
    config_class = {
        "development": DevelopmentConfig,
        "testing": TestingConfig,
        "production": ProductionConfig,
    }.get(environment, DevelopmentConfig)

    if config_class is ProductionConfig and BaseConfig.SECRET_KEY == DEFAULT_SECRET:
        raise RuntimeError(
            "SECRET_KEY must be set in .env when FLASK_ENV=production."
        )

    return config_class
