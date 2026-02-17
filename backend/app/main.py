# main.py — FastAPI ana uygulama giriş noktası
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.config import settings
from app.database import init_db, SessionLocal
from app.utils.logger import logger
from app.services.scheduler_service import scheduler_service
from app.services.backup_service import backup_service

# Router'ları import et
from app.routers import (
    auth, accounts, posts, media,
    messages, downloads, hashtags,
    dashboard, settings as settings_router,
    appeals, profiles, bulk_import,
)

# APScheduler — zamanlanmış görevler
scheduler = AsyncIOScheduler()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Uygulama yaşam döngüsü — başlatma ve durdurma."""
    # ─── Başlangıç ───
    logger.info(f"🚀 {settings.APP_NAME} v{settings.APP_VERSION} başlatılıyor...")
    init_db()
    logger.info("✅ Veritabanı tabloları oluşturuldu")

    # Admin kullanıcı yoksa oluştur
    _create_default_admin()

    # Zamanlanmış görevleri başlat
    scheduler.add_job(
        _run_scheduler,
        "interval",
        seconds=settings.SCHEDULER_CHECK_INTERVAL,
        id="post_scheduler",
        replace_existing=True,
    )
    scheduler.add_job(
        backup_service.create_backup,
        "cron",
        hour=3,
        minute=0,
        id="daily_backup",
        replace_existing=True,
    )
    scheduler.start()
    logger.info("⏰ Zamanlayıcı ve yedekleme görevleri başlatıldı")

    yield

    # ─── Kapanış ───
    scheduler.shutdown()
    logger.info("👋 Uygulama kapatıldı")


def _create_default_admin():
    """İlk çalışmada admin kullanıcı oluşturur."""
    from app.models.user import User, UserRole
    import bcrypt

    db = SessionLocal()
    try:
        existing = db.query(User).filter(User.role == UserRole.ADMIN).first()
        if not existing:
            hashed = bcrypt.hashpw("admin123".encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            admin = User(
                username="admin",
                email="admin@demet.local",
                password_hash=hashed,
                role=UserRole.ADMIN,
            )
            db.add(admin)
            db.commit()
            logger.info("🔑 Varsayılan admin kullanıcı oluşturuldu (admin/admin123)")
    finally:
        db.close()


async def _run_scheduler():
    """Zamanlanmış gönderileri kontrol eder."""
    db = SessionLocal()
    try:
        await scheduler_service.execute_scheduled_posts(db)
    except Exception as e:
        logger.error(f"Zamanlayıcı hatası: {e}")
    finally:
        db.close()


# ─── FastAPI Uygulaması ────────────────────────────────
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Instagram İçerik Planlama ve Mesaj Yönetim Sistemi",
    lifespan=lifespan,
)

# CORS
_cors_origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:45321",   # Electron desktop app
    "http://localhost:45321",
]
# Railway frontend URL (production)
if settings.FRONTEND_URL and settings.FRONTEND_URL not in _cors_origins:
    _cors_origins.append(settings.FRONTEND_URL)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Statik dosyalar (yüklenen medya)
app.mount(
    "/uploads",
    StaticFiles(directory=str(settings.UPLOAD_DIR)),
    name="uploads",
)

# Router'ları kaydet
app.include_router(auth.router)
app.include_router(accounts.router)
app.include_router(posts.router)
app.include_router(media.router)
app.include_router(messages.router)
app.include_router(downloads.router)
app.include_router(hashtags.router)
app.include_router(dashboard.router)
app.include_router(settings_router.router)
app.include_router(appeals.router)
app.include_router(profiles.router)
app.include_router(bulk_import.router)


@app.get("/")
async def root():
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "running",
        "docs": "/docs",
    }


@app.get("/health")
async def health():
    return {"status": "ok"}
