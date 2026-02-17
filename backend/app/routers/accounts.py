# routers/accounts.py — Hesap yönetimi endpoint'leri
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.database import get_db
from app.models.account import Account
from app.routers.auth import get_current_user
from app.models.user import User
from app.utils.rate_limiter import rate_limiter

router = APIRouter(prefix="/api/accounts", tags=["Hesap Yönetimi"])


class AccountUpdate(BaseModel):
    daily_post_limit: int | None = None
    is_active: bool | None = None
    auto_publish: bool | None = None
    photo_percentage: int | None = None
    video_percentage: int | None = None
    story_percentage: int | None = None
    reels_percentage: int | None = None
    posting_mode: str | None = None
    loop_mode: str | None = None
    proxy_url: str | None = None


class AccountResponse(BaseModel):
    id: int
    instagram_id: str
    username: str
    full_name: str | None
    profile_picture_url: str | None
    followers_count: int
    following_count: int
    media_count: int
    daily_post_limit: int
    is_active: bool
    auto_publish: bool
    photo_percentage: int
    video_percentage: int
    story_percentage: int
    reels_percentage: int
    posting_mode: str
    loop_mode: str
    token_status: str
    api_calls_remaining: int

    class Config:
        from_attributes = True


@router.get("")
async def list_accounts(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Tüm Instagram hesaplarını listeler."""
    accounts = db.query(Account).order_by(Account.created_at.desc()).all()
    result = []
    for acc in accounts:
        result.append({
            "id": acc.id,
            "instagram_id": acc.instagram_id or "",
            "username": acc.username,
            "full_name": acc.full_name,
            "profile_picture_url": acc.profile_picture_url,
            "biography": acc.biography,
            "followers_count": acc.followers_count,
            "following_count": acc.following_count,
            "media_count": acc.media_count,
            "daily_post_limit": acc.daily_post_limit,
            "is_active": acc.is_active,
            "auto_publish": acc.auto_publish,
            "photo_percentage": acc.photo_percentage,
            "video_percentage": acc.video_percentage,
            "story_percentage": acc.story_percentage,
            "reels_percentage": acc.reels_percentage,
            "posting_mode": acc.posting_mode,
            "loop_mode": acc.loop_mode,
            "proxy_url": acc.proxy_url,
            # Web otomasyon alanları
            "session_valid": acc.session_valid if acc.session_valid is not None else False,
            "last_login_at": acc.last_login_at.isoformat() if acc.last_login_at else None,
            "login_method": acc.login_method or "password",
            "account_status": acc.account_status or "unknown",
        })
    return result


@router.get("/{account_id}")
async def get_account(
    account_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Hesap detayı."""
    account = db.query(Account).filter(Account.id == account_id).first()
    if not account:
        raise HTTPException(status_code=404, detail="Hesap bulunamadı")
    return account


@router.put("/{account_id}")
async def update_account(
    account_id: int,
    data: AccountUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Hesap ayarlarını günceller."""
    account = db.query(Account).filter(Account.id == account_id).first()
    if not account:
        raise HTTPException(status_code=404, detail="Hesap bulunamadı")

    update_data = data.model_dump(exclude_unset=True)

    # Yüzde toplamı kontrolü
    percentages = {
        "photo_percentage": account.photo_percentage,
        "video_percentage": account.video_percentage,
        "story_percentage": account.story_percentage,
        "reels_percentage": account.reels_percentage,
    }
    percentages.update(
        {k: v for k, v in update_data.items() if k.endswith("_percentage")}
    )
    total = sum(percentages.values())
    if total != 100 and any(k.endswith("_percentage") for k in update_data):
        raise HTTPException(
            status_code=400,
            detail=f"Paylaşım yüzdeleri toplamı 100 olmalı (şu an: {total})"
        )

    for key, value in update_data.items():
        setattr(account, key, value)

    db.commit()
    return {"message": "Hesap güncellendi", "account_id": account_id}


@router.delete("/{account_id}")
async def delete_account(
    account_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Hesabı sistemden kaldırır."""
    account = db.query(Account).filter(Account.id == account_id).first()
    if not account:
        raise HTTPException(status_code=404, detail="Hesap bulunamadı")

    db.delete(account)
    db.commit()
    return {"message": f"@{account.username} hesabı silindi"}
