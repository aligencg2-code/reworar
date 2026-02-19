# config.py — Merkezi konfigürasyon dosyası
import os
import sys
from pathlib import Path
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

# PyInstaller ile paketlenmişse veri dizinini kullanıcı klasörüne yönlendir
# (C:\Program Files\ yazılamaz, %LOCALAPPDATA%\Instabot kullan)
if getattr(sys, 'frozen', False):
    _appdata = os.environ.get("LOCALAPPDATA", os.path.expanduser("~"))
    DATA_DIR = Path(_appdata) / "Instabot"
else:
    DATA_DIR = Path(os.environ.get("DATA_DIR", str(BASE_DIR)))


class Settings(BaseSettings):
    """Uygulama ayarları — .env dosyasından okunur."""

    # --- Uygulama ---
    APP_NAME: str = "Instabot"
    APP_VERSION: str = "1.2.7"
    APP_DEBUG: bool = True
    SECRET_KEY: str = "change-me-in-production-use-openssl-rand-hex-32"

    # --- Veritabanı ---
    DATABASE_URL: str = os.environ.get(
        "DATABASE_URL",
        f"sqlite:///{DATA_DIR / 'demet.db'}"
    )

    # --- Instagram Graph API ---
    INSTAGRAM_API_BASE: str = "https://graph.instagram.com/v21.0"
    FACEBOOK_GRAPH_API_BASE: str = "https://graph.facebook.com/v21.0"
    FACEBOOK_APP_ID: str = ""
    FACEBOOK_APP_SECRET: str = ""
    FACEBOOK_REDIRECT_URI: str = "http://localhost:8000/api/auth/callback"

    # --- JWT ---
    JWT_SECRET_KEY: str = "jwt-secret-change-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 1440  # 24 saat

    # --- Token Şifreleme ---
    ENCRYPTION_KEY: str = ""  # Fernet key, boşsa otomatik üretilir

    # --- Redis ---
    REDIS_URL: str = "redis://localhost:6379/0"

    # --- Medya ---
    UPLOAD_DIR: Path = DATA_DIR / "uploads"
    MAX_UPLOAD_SIZE_MB: int = 100
    THUMBNAIL_SIZE: tuple = (300, 300)
    ALLOWED_IMAGE_TYPES: list = ["image/jpeg", "image/png", "image/webp"]
    ALLOWED_VIDEO_TYPES: list = ["video/mp4", "video/quicktime"]

    # --- Sessions ---
    SESSIONS_DIR: Path = DATA_DIR / "sessions"

    # --- Zamanlayıcı ---
    SCHEDULER_CHECK_INTERVAL: int = 30  # saniye

    # --- Rate Limiting ---
    API_CALLS_PER_HOUR: int = 200  # hesap başına
    API_CALLS_PER_DAY: int = 4800

    # --- Yedekleme ---
    BACKUP_DIR: Path = DATA_DIR / "backups"
    BACKUP_RETENTION_DAYS: int = 7

    # --- Log ---
    LOG_DIR: Path = DATA_DIR / "logs"
    LOG_LEVEL: str = "INFO"

    # --- CORS / Frontend ---
    FRONTEND_URL: str = os.environ.get("FRONTEND_URL", "http://localhost:3000")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


settings = Settings()

# Gerekli dizinleri oluştur
for directory in [settings.UPLOAD_DIR, settings.BACKUP_DIR, settings.LOG_DIR, settings.SESSIONS_DIR]:
    directory.mkdir(parents=True, exist_ok=True)

for sub in ["photos", "videos", "stories", "reels", "thumbnails", "downloads"]:
    (settings.UPLOAD_DIR / sub).mkdir(parents=True, exist_ok=True)

