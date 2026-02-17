# routers/profiles.py — Profil düzenleme ve yönetim endpoint'leri
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.database import get_db
from app.models.user import User
from app.models.account import Account
from app.routers.auth import get_current_user
from app.services.profile_bot_service import profile_bot_service

router = APIRouter(prefix="/api/profiles", tags=["Profil Yönetimi"])


class ProfileUpdateRequest(BaseModel):
    full_name: str | None = None
    biography: str | None = None
    daily_post_limit: int | None = None
    auto_publish: bool | None = None
    photo_percentage: int | None = None
    video_percentage: int | None = None
    story_percentage: int | None = None
    reels_percentage: int | None = None
    posting_mode: str | None = None
    proxy_url: str | None = None


@router.get("/all")
async def get_all_profiles(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Tüm hesapların profil özetini getirir."""
    return await profile_bot_service.get_all_profiles_summary(db)


@router.get("/{account_id}")
async def get_profile(
    account_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Tek bir hesabın Instagram profilini çeker."""
    try:
        return await profile_bot_service.get_profile_info(db, account_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/{account_id}")
async def update_profile(
    account_id: int,
    data: ProfileUpdateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Hesap ayarlarını günceller."""
    account = db.query(Account).filter(Account.id == account_id).first()
    if not account:
        raise HTTPException(status_code=404, detail="Hesap bulunamadı")

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(account, key, value)

    db.commit()
    return {"message": f"@{account.username} güncellendi"}


@router.post("/refresh-all")
async def refresh_all(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Tüm hesapların profillerini Instagram'dan yeniler."""
    background_tasks.add_task(profile_bot_service.refresh_all_profiles, db)
    return {"message": "Tüm profiller yenileniyor..."}


@router.post("/{account_id}/refresh")
async def refresh_single(
    account_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Tek bir hesabın profilini Instagram'dan yeniler."""
    try:
        profile = await profile_bot_service.get_profile_info(db, account_id)
        return profile
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
