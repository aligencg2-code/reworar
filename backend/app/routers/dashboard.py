# routers/dashboard.py — Dashboard istatistik ve yönetim
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import get_db
from app.models.account import Account
from app.models.post import Post, PostStatus
from app.models.media import Media
from app.models.message import Message
from app.models.log import ActivityLog
from app.models.user import User
from app.routers.auth import get_current_user
from app.services.backup_service import backup_service

router = APIRouter(prefix="/api/dashboard", tags=["Dashboard"])


@router.get("/stats")
async def get_stats(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Dashboard genel istatistikleri."""
    total_accounts = db.query(Account).count()
    active_accounts = db.query(Account).filter(Account.is_active == True).count()

    today = datetime.utcnow().replace(hour=0, minute=0, second=0)
    posts_today = db.query(Post).filter(
        Post.published_at >= today,
        Post.status == PostStatus.PUBLISHED,
    ).count()

    scheduled_posts = db.query(Post).filter(
        Post.status == PostStatus.SCHEDULED
    ).count()

    total_media = db.query(Media).count()
    unread_messages = db.query(Message).filter(
        Message.is_incoming == True,
        Message.is_read == False,
    ).count()

    failed_posts = db.query(Post).filter(
        Post.status == PostStatus.FAILED,
        Post.created_at >= today - timedelta(days=7),
    ).count()

    return {
        "total_accounts": total_accounts,
        "active_accounts": active_accounts,
        "posts_today": posts_today,
        "scheduled_posts": scheduled_posts,
        "total_media": total_media,
        "unread_messages": unread_messages,
        "failed_posts_week": failed_posts,
    }


@router.get("/activity")
async def get_recent_activity(
    limit: int = 20,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Son aktiviteler."""
    logs = (
        db.query(ActivityLog)
        .order_by(ActivityLog.created_at.desc())
        .limit(limit)
        .all()
    )
    return {
        "activities": [
            {
                "id": log.id,
                "level": log.level.value.lower(),
                "category": log.category.value.lower(),
                "action": log.action,
                "details": log.details,
                "created_at": log.created_at.isoformat(),
            }
            for log in logs
        ]
    }


@router.get("/backups")
async def list_backups(user: User = Depends(get_current_user)):
    """Yedekleme listesi."""
    return {"backups": backup_service.list_backups()}


@router.post("/backups/create")
async def create_backup(user: User = Depends(get_current_user)):
    """Manuel yedekleme oluşturur."""
    path = backup_service.create_backup()
    if not path:
        return {"message": "Yedekleme oluşturulamadı", "success": False}
    return {"message": "Yedekleme oluşturuldu", "path": path, "success": True}


# ─── Bot Kontrolü ──────────────────────────────────────
from app.services.autobot_service import autobot_service


@router.post("/bot/start")
async def bot_start(user: User = Depends(get_current_user)):
    """Otomatik paylaşım botunu başlatır."""
    return autobot_service.start()


@router.post("/bot/stop")
async def bot_stop(user: User = Depends(get_current_user)):
    """Otomatik paylaşım botunu durdurur."""
    return autobot_service.stop()


@router.get("/bot/status")
async def bot_status(user: User = Depends(get_current_user)):
    """Bot durumunu döner."""
    return autobot_service.status()
