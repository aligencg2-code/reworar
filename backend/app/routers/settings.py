# routers/settings.py — Sistem ayarları endpoint'leri
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.database import get_db
from app.models.settings import SystemSettings
from app.models.user import User
from app.routers.auth import get_current_user, require_admin

router = APIRouter(prefix="/api/settings", tags=["Sistem Ayarları"])


class SettingUpdate(BaseModel):
    key: str
    value: str
    description: str | None = None


class BulkSettings(BaseModel):
    settings: list[SettingUpdate]


@router.get("")
async def get_all_settings(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Tüm sistem ayarlarını döndürür."""
    settings = db.query(SystemSettings).all()
    return {
        "settings": {s.key: s.value for s in settings}
    }


@router.post("")
async def update_settings(
    data: BulkSettings,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    """Sistem ayarlarını toplu günceller (sadece admin)."""
    for item in data.settings:
        setting = db.query(SystemSettings).filter(
            SystemSettings.key == item.key
        ).first()
        if setting:
            setting.value = item.value
            if item.description:
                setting.description = item.description
        else:
            setting = SystemSettings(
                key=item.key,
                value=item.value,
                description=item.description,
            )
            db.add(setting)

    db.commit()
    return {"message": "Ayarlar güncellendi"}


@router.delete("/{key}")
async def delete_setting(
    key: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    """Bir ayarı siler."""
    setting = db.query(SystemSettings).filter(SystemSettings.key == key).first()
    if not setting:
        raise HTTPException(status_code=404, detail="Ayar bulunamadı")
    db.delete(setting)
    db.commit()
    return {"message": f"Ayar '{key}' silindi"}
