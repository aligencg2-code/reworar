# routers/logs.py — Aktivite log endpoint'leri
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.database import get_db
from app.models.log import ActivityLog, LogLevel, LogCategory
from app.models.account import Account
from app.models.user import User
from app.routers.auth import get_current_user

router = APIRouter(prefix="/api/logs", tags=["Aktivite Logları"])


@router.get("")
async def get_logs(
    account_id: int | None = None,
    category: str | None = None,
    level: str | None = None,
    limit: int = 100,
    offset: int = 0,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Aktivite loglarını listeler."""
    query = db.query(ActivityLog)

    if account_id:
        query = query.filter(ActivityLog.account_id == account_id)
    if category:
        try:
            query = query.filter(ActivityLog.category == LogCategory(category))
        except ValueError:
            pass
    if level:
        try:
            query = query.filter(ActivityLog.level == LogLevel(level))
        except ValueError:
            pass

    total = query.count()
    items = query.order_by(desc(ActivityLog.created_at)).offset(offset).limit(limit).all()

    # Hesap username'leri
    account_ids = set(l.account_id for l in items if l.account_id)
    accounts = {
        a.id: a.username
        for a in db.query(Account).filter(Account.id.in_(account_ids)).all()
    } if account_ids else {}

    return {
        "total": total,
        "items": [
            {
                "id": l.id,
                "level": l.level.value if l.level else "INFO",
                "category": l.category.value if l.category else "SYSTEM",
                "account_id": l.account_id,
                "account_username": accounts.get(l.account_id),
                "action": l.action,
                "details": l.details,
                "created_at": l.created_at.isoformat(),
            }
            for l in items
        ],
    }


@router.delete("")
async def clear_logs(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Tüm logları siler."""
    count = db.query(ActivityLog).delete()
    db.commit()
    return {"message": f"{count} log silindi"}
