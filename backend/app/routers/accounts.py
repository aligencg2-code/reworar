# routers/accounts.py — Hesap yönetimi endpoint'leri
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from pathlib import Path
import subprocess, os

from app.database import get_db
from app.models.account import Account
from app.routers.auth import get_current_user
from app.models.user import User
from app.utils.rate_limiter import rate_limiter
from app.config import settings, DATA_DIR

router = APIRouter(prefix="/api/accounts", tags=["Hesap Yönetimi"])

# ─── Hesap dosya/klasör yardımcıları ───

ACCOUNT_FILES = {
    "BioTexts": {"filename": "BioTexts.txt", "description": "Hesaba özel bio yazıları"},
    "BioLinks": {"filename": "BioLinks.txt", "description": "Hesaba özel bio linkleri"},
    "Usernames": {"filename": "Usernames.txt", "description": "Hesaba özel kullanıcı adları"},
}


def _get_account_dir(username: str) -> Path:
    """Hesaba ait klasör yolunu döner, yoksa oluşturur."""
    account_dir = DATA_DIR / "accounts" / username
    account_dir.mkdir(parents=True, exist_ok=True)
    return account_dir


class AccountUpdate(BaseModel):
    daily_post_limit: int | None = None
    posts_per_session: int | None = None
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
    posts_per_session: int
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
            "posts_per_session": getattr(acc, 'posts_per_session', 1) or 1,
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


# ─── Hesap Dosya Yönetimi ───


class FileContent(BaseModel):
    content: str


@router.get("/{account_id}/files")
async def list_account_files(
    account_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Hesaba ait dosyaların durumunu döner."""
    account = db.query(Account).filter(Account.id == account_id).first()
    if not account:
        raise HTTPException(status_code=404, detail="Hesap bulunamadı")

    account_dir = _get_account_dir(account.username)
    files = []
    for key, info in ACCOUNT_FILES.items():
        filepath = account_dir / info["filename"]
        exists = filepath.exists()
        line_count = 0
        if exists:
            try:
                line_count = len(
                    [l for l in filepath.read_text(encoding="utf-8").splitlines() if l.strip()]
                )
            except Exception:
                pass
        files.append({
            "key": key,
            "filename": info["filename"],
            "description": info["description"],
            "exists": exists,
            "line_count": line_count,
        })
    return {"files": files, "folder_path": str(account_dir)}


@router.get("/{account_id}/files/{file_key}")
async def get_account_file(
    account_id: int,
    file_key: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Hesap dosyasının içeriğini okur."""
    if file_key not in ACCOUNT_FILES:
        raise HTTPException(status_code=400, detail="Geçersiz dosya türü")

    account = db.query(Account).filter(Account.id == account_id).first()
    if not account:
        raise HTTPException(status_code=404, detail="Hesap bulunamadı")

    filepath = _get_account_dir(account.username) / ACCOUNT_FILES[file_key]["filename"]
    if not filepath.exists():
        return {"content": "", "exists": False}

    content = filepath.read_text(encoding="utf-8")
    return {"content": content, "exists": True}


@router.put("/{account_id}/files/{file_key}")
async def update_account_file(
    account_id: int,
    file_key: str,
    data: FileContent,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Hesap dosyasını günceller / oluşturur."""
    if file_key not in ACCOUNT_FILES:
        raise HTTPException(status_code=400, detail="Geçersiz dosya türü")

    account = db.query(Account).filter(Account.id == account_id).first()
    if not account:
        raise HTTPException(status_code=404, detail="Hesap bulunamadı")

    filepath = _get_account_dir(account.username) / ACCOUNT_FILES[file_key]["filename"]
    filepath.write_text(data.content, encoding="utf-8")

    line_count = len([l for l in data.content.splitlines() if l.strip()])
    return {"message": f"{ACCOUNT_FILES[file_key]['filename']} kaydedildi", "line_count": line_count}


@router.post("/{account_id}/open-folder")
async def open_account_folder(
    account_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Hesabın klasörünü Windows Explorer'da açar."""
    account = db.query(Account).filter(Account.id == account_id).first()
    if not account:
        raise HTTPException(status_code=404, detail="Hesap bulunamadı")

    account_dir = _get_account_dir(account.username)
    try:
        subprocess.Popen(["explorer", str(account_dir)])
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Klasör açılamadı: {e}")

    return {"message": f"Klasör açıldı: {account_dir}", "path": str(account_dir)}


@router.get("/{account_id}/media")
async def list_account_media(
    account_id: int,
    media_type: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Hesaba ait medya dosyalarını listeler."""
    from app.models.media import Media, MediaFileType

    account = db.query(Account).filter(Account.id == account_id).first()
    if not account:
        raise HTTPException(status_code=404, detail="Hesap bulunamadı")

    query = db.query(Media).filter(
        (Media.account_id == account_id) | (Media.folder == account.username)
    )
    if media_type:
        try:
            query = query.filter(Media.media_type == MediaFileType(media_type.upper()))
        except ValueError:
            pass

    items = query.order_by(Media.created_at.desc()).limit(200).all()

    # Sayılar
    counts = {}
    for mt in MediaFileType:
        c = db.query(Media).filter(
            (Media.account_id == account_id) | (Media.folder == account.username),
            Media.media_type == mt,
        ).count()
        counts[mt.value.lower()] = c

    total = sum(counts.values())

    def _url(m):
        if m.file_path:
            try:
                rel = os.path.relpath(m.file_path, str(settings.UPLOAD_DIR)).replace("\\", "/")
                return f"/uploads/{rel}"
            except ValueError:
                pass
        return f"/uploads/{m.media_type.value.lower()}s/{m.filename}"

    return {
        "total": total,
        "counts": counts,
        "items": [
            {
                "id": m.id,
                "filename": m.filename,
                "original_filename": m.original_filename,
                "media_type": m.media_type.value.lower(),
                "folder": m.folder,
                "thumbnail_url": f"/uploads/thumbnails/{os.path.basename(m.thumbnail_path)}"
                    if m.thumbnail_path else None,
                "file_url": _url(m),
                "created_at": m.created_at.isoformat(),
            }
            for m in items
        ],
    }


# ─── Tarayıcı ile giriş ───

@router.post("/login-browser")
async def login_browser(
    data: dict,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Tarayıcı ile Instagram girişi — Playwright penceresi açar."""
    account_id = data.get("account_id")
    if not account_id:
        raise HTTPException(status_code=400, detail="account_id gerekli")

    account = db.query(Account).filter(Account.id == account_id).first()
    if not account:
        raise HTTPException(status_code=404, detail="Hesap bulunamadı")

    from app.services.browser_login_service import browser_login
    result = await browser_login(account.id, account.username, account.proxy_url)

    if result.get("success"):
        account.session_valid = True
        db.commit()

    return result


# ─── Öne Çıkarılanlar (Highlights) ───

@router.get("/{account_id}/highlights")
async def list_highlights(
    account_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Hesabın öne çıkarılan listesini getirir."""
    account = db.query(Account).filter(Account.id == account_id).first()
    if not account:
        raise HTTPException(status_code=404, detail="Hesap bulunamadı")

    try:
        from instagrapi import Client
        from app.utils.encryption import decrypt_token

        cl = Client()
        cl.delay_range = [1, 3]
        if account.proxy_url:
            try:
                cl.set_proxy(account.proxy_url)
            except Exception:
                pass

        session_file = settings.SESSIONS_DIR / f"{account.username}.json"
        if session_file.exists():
            cl.load_settings(session_file)
            password = ""
            if account.password_encrypted:
                try:
                    password = decrypt_token(account.password_encrypted)
                except Exception:
                    pass
            if password:
                cl.login(account.username, password)
            else:
                cl.get_timeline_feed()
        else:
            raise HTTPException(status_code=400, detail="Önce giriş yapılmalı")

        user_id = cl.user_id
        highlights = cl.user_highlights(user_id)

        return {
            "highlights": [
                {
                    "pk": str(h.pk),
                    "title": h.title,
                    "cover_url": str(h.cover_media.thumbnail_url) if h.cover_media else None,
                    "items_count": h.media_count or 0,
                    "created_at": h.created_at.isoformat() if h.created_at else None,
                }
                for h in highlights
            ]
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)[:200])


@router.post("/{account_id}/highlights")
async def create_highlight(
    account_id: int,
    data: dict,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Yeni öne çıkarılan oluşturur (story media ID'lerinden)."""
    account = db.query(Account).filter(Account.id == account_id).first()
    if not account:
        raise HTTPException(status_code=404, detail="Hesap bulunamadı")

    title = data.get("title", "Öne Çıkan")
    story_ids = data.get("story_ids", [])

    if not story_ids:
        raise HTTPException(status_code=400, detail="En az 1 story gerekli")

    try:
        from instagrapi import Client
        from app.utils.encryption import decrypt_token

        cl = Client()
        cl.delay_range = [1, 3]
        if account.proxy_url:
            try:
                cl.set_proxy(account.proxy_url)
            except Exception:
                pass

        session_file = settings.SESSIONS_DIR / f"{account.username}.json"
        if session_file.exists():
            cl.load_settings(session_file)
            password = ""
            if account.password_encrypted:
                try:
                    password = decrypt_token(account.password_encrypted)
                except Exception:
                    pass
            if password:
                cl.login(account.username, password)
            else:
                cl.get_timeline_feed()

        result = cl.highlight_create(title, story_ids)
        return {
            "success": True,
            "highlight_pk": str(result.pk),
            "message": f"'{title}' öne çıkarılanı oluşturuldu",
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)[:200])


@router.delete("/{account_id}/highlights/{highlight_pk}")
async def delete_highlight(
    account_id: int,
    highlight_pk: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Öne çıkarılan siler."""
    account = db.query(Account).filter(Account.id == account_id).first()
    if not account:
        raise HTTPException(status_code=404, detail="Hesap bulunamadı")

    try:
        from instagrapi import Client
        from app.utils.encryption import decrypt_token

        cl = Client()
        cl.delay_range = [1, 3]
        if account.proxy_url:
            try:
                cl.set_proxy(account.proxy_url)
            except Exception:
                pass

        session_file = settings.SESSIONS_DIR / f"{account.username}.json"
        if session_file.exists():
            cl.load_settings(session_file)
            password = ""
            if account.password_encrypted:
                try:
                    password = decrypt_token(account.password_encrypted)
                except Exception:
                    pass
            if password:
                cl.login(account.username, password)
            else:
                cl.get_timeline_feed()

        cl.highlight_delete(highlight_pk)
        return {"success": True, "message": "Öne çıkarılan silindi"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)[:200])

