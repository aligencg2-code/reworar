# main.py — FastAPI ana uygulama giriş noktası
from pathlib import Path
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
    captions, locations, logs, update_server,
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
    "http://localhost:3001",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:3001",
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
app.include_router(captions.router)
app.include_router(locations.router)
app.include_router(logs.router)
app.include_router(update_server.router)


# ─── Lisans API ────────────────────────────────────────
@app.get("/api/license/status")
async def license_status():
    try:
        from app.license import verify_license, get_hwid
        result = verify_license()
        result["hwid"] = get_hwid()
        return result
    except Exception as e:
        return {"valid": False, "error": str(e)}


@app.post("/api/license/activate")
async def license_activate(data: dict):
    try:
        from app.license import activate_license
        return activate_license(data.get("key", ""))
    except Exception as e:
        return {"valid": False, "error": str(e)}


# ─── Health & Root ────────────────────────────────────
@app.get("/health")
async def health():
    return {"status": "ok"}


# ─── Statik Frontend (EXE modu) ────────────────────────
_FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend_dist"

if _FRONTEND_DIR.exists():
    from fastapi.responses import FileResponse

    # Next.js static assets
    app.mount(
        "/_next",
        StaticFiles(directory=str(_FRONTEND_DIR / "_next")),
        name="next_static",
    )

    # Catch-all: serve frontend pages
    @app.get("/{path:path}")
    async def serve_frontend(path: str):
        """SPA fallback — frontend sayfalarını serve et."""
        file_path = _FRONTEND_DIR / path
        if file_path.is_file():
            return FileResponse(file_path)
        # Try with .html extension
        html_path = _FRONTEND_DIR / f"{path}.html"
        if html_path.is_file():
            return FileResponse(html_path)
        # Try directory/index.html
        index_path = _FRONTEND_DIR / path / "index.html"
        if index_path.is_file():
            return FileResponse(index_path)
        # Fallback to root
        root_index = _FRONTEND_DIR / "index.html"
        if root_index.is_file():
            return FileResponse(root_index)
        return {"error": "not found"}

else:
    @app.get("/")
    async def root():
        return {
            "name": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "status": "running",
            "docs": "/docs",
        }
