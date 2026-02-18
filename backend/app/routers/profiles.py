# routers/profiles.py — Profil düzenleme ve yönetim endpoint'leri
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, UploadFile, File, Form
from sqlalchemy.orm import Session
from pydantic import BaseModel
import shutil, tempfile, os

from app.database import get_db
from app.models.user import User
from app.models.account import Account
from app.routers.auth import get_current_user
from app.services.profile_bot_service import profile_bot_service
from app.services.instagram_web import InstagramWebClient, InstagramWebError
from app.config import settings as app_settings

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


class InstagramProfileUpdate(BaseModel):
    """Instagram profil güncelleme — gerçek Instagram API üzerinden."""
    full_name: str | None = None
    biography: str | None = None
    external_url: str | None = None
    username: str | None = None


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
    """Hesap ayarlarını günceller (yerel DB)."""
    account = db.query(Account).filter(Account.id == account_id).first()
    if not account:
        raise HTTPException(status_code=404, detail="Hesap bulunamadı")

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(account, key, value)

    db.commit()
    return {"message": f"@{account.username} güncellendi"}


@router.post("/{account_id}/update-instagram")
async def update_instagram_profile(
    account_id: int,
    data: InstagramProfileUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Instagram profilini gerçek API ile günceller (bio, isim, link, kullanıcı adı)."""
    account = db.query(Account).filter(Account.id == account_id).first()
    if not account:
        raise HTTPException(status_code=404, detail="Hesap bulunamadı")

    if not account.session_cookies and not account.session_valid:
        raise HTTPException(status_code=400, detail="Önce giriş yapılmalı")

    # instagrapi client'ı session dosyasından yükle
    client = InstagramWebClient(proxy=account.proxy_url)

    try:
        await client.load_session_from_file(account.username)
    except InstagramWebError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Güncellenecek alanları hazırla
    update_fields = {}
    if data.full_name is not None:
        update_fields["full_name"] = data.full_name
    if data.biography is not None:
        update_fields["biography"] = data.biography
    if data.external_url is not None:
        update_fields["external_url"] = data.external_url
    if data.username is not None:
        update_fields["username"] = data.username

    if not update_fields:
        raise HTTPException(status_code=400, detail="Güncellenecek alan belirtilmedi")

    try:
        result = await client.update_profile(**update_fields)

        # Yerel DB'yi de güncelle
        if data.full_name is not None:
            account.full_name = data.full_name
        if data.biography is not None:
            account.biography = data.biography
        if data.username is not None:
            account.username = data.username
        db.commit()

        return {
            "success": True,
            "message": f"@{account.username} Instagram profili güncellendi",
            "updated_fields": list(update_fields.keys()),
        }
    except InstagramWebError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{account_id}/update-photo")
async def update_profile_photo(
    account_id: int,
    photo: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Instagram profil fotoğrafını değiştirir."""
    account = db.query(Account).filter(Account.id == account_id).first()
    if not account:
        raise HTTPException(status_code=404, detail="Hesap bulunamadı")

    if not account.session_cookies and not account.session_valid:
        raise HTTPException(status_code=400, detail="Önce giriş yapılmalı")

    # Dosyayı geçici konuma kaydet
    suffix = os.path.splitext(photo.filename)[1] or ".jpg"
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    try:
        shutil.copyfileobj(photo.file, tmp)
        tmp.close()

        # instagrapi client
        client = InstagramWebClient(proxy=account.proxy_url)
        await client.load_session_from_file(account.username)
        result = await client.update_profile_picture(tmp.name)

        return {
            "success": True,
            "message": f"@{account.username} profil fotoğrafı güncellendi",
        }
    except InstagramWebError as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        try:
            os.unlink(tmp.name)
        except OSError:
            pass


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

