# routers/media.py — Medya yükleme ve yönetim endpoint'leri
import os
import shutil
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.database import get_db
from app.models.media import Media, MediaFileType
from app.models.user import User
from app.routers.auth import get_current_user
from app.services.media_service import media_service
from app.config import settings

router = APIRouter(prefix="/api/media", tags=["Medya Yönetimi"])


@router.post("/upload")
async def upload_media(
    files: list[UploadFile] = File(...),
    media_type: str = Form("photo"),
    folder: str = Form("default"),
    account_id: int | None = Form(None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Çoklu medya yükleme."""
    uploaded = []
    media_ids = []
    type_map = {
        "photo": MediaFileType.PHOTO,
        "video": MediaFileType.VIDEO,
        "reels": MediaFileType.REELS,
        "profile": MediaFileType.PROFILE,
        "PHOTO": MediaFileType.PHOTO,
        "VIDEO": MediaFileType.VIDEO,
        "REELS": MediaFileType.REELS,
        "PROFILE": MediaFileType.PROFILE,
    }

    for file in files:
        # Dosya boyutu kontrolü
        content = await file.read()
        size = len(content)
        if size > settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024:
            continue

        # Güvenli dosya adı
        filename = media_service.generate_filename(file.filename)
        file_path = media_service.get_upload_path(media_type, filename)
        file_path.parent.mkdir(parents=True, exist_ok=True)

        # Dosyayı kaydet
        with open(file_path, "wb") as f:
            f.write(content)

        # Metadata
        width, height = None, None
        thumbnail_path = None
        if media_type in ("photo", "profile"):
            try:
                width, height = media_service.get_image_dimensions(str(file_path))
                thumbnail_path = media_service.create_thumbnail(str(file_path))
            except Exception:
                pass

        media = Media(
            account_id=account_id,
            filename=filename,
            original_filename=file.filename,
            file_path=str(file_path),
            thumbnail_path=thumbnail_path,
            media_type=type_map.get(media_type, MediaFileType.PHOTO),
            folder=folder,
            mime_type=file.content_type or "application/octet-stream",
            width=width,
            height=height,
            file_size=size,
        )
        db.add(media)
        db.flush()  # ID'yi al
        uploaded.append(filename)
        media_ids.append(media.id)

    db.commit()
    return {"message": f"{len(uploaded)} dosya yüklendi", "files": uploaded, "media_ids": media_ids}


@router.get("")
async def list_media(
    media_type: str | None = None,
    folder: str | None = None,
    account_id: int | None = None,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Medya listesi (filtreli)."""
    query = db.query(Media)

    if media_type:
        mt_upper = media_type.upper()
        try:
            query = query.filter(Media.media_type == MediaFileType(mt_upper))
        except ValueError:
            pass
    if folder:
        query = query.filter(Media.folder == folder)
    if account_id:
        query = query.filter(Media.account_id == account_id)

    total = query.count()
    items = query.order_by(Media.created_at.desc()).offset(offset).limit(limit).all()

    # Medya türü sayıları
    counts = {}
    for mt in MediaFileType:
        count_query = db.query(Media).filter(Media.media_type == mt)
        if account_id:
            count_query = count_query.filter(Media.account_id == account_id)
        counts[mt.value.lower()] = count_query.count()

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
                "width": m.width,
                "height": m.height,
                "file_size": m.file_size,
                "thumbnail_url": f"/uploads/thumbnails/{os.path.basename(m.thumbnail_path)}"
                    if m.thumbnail_path else None,
                "file_url": f"/uploads/{m.media_type.value.lower()}s/{m.filename}",
                "created_at": m.created_at.isoformat(),
            }
            for m in items
        ],
    }


@router.post("/{media_id}/resize")
async def resize_media(
    media_id: int,
    aspect_ratio: str = "1:1",
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Medyayı boyutlandırır."""
    media = db.query(Media).filter(Media.id == media_id).first()
    if not media:
        raise HTTPException(status_code=404, detail="Medya bulunamadı")

    if media.media_type not in (MediaFileType.PHOTO, MediaFileType.PROFILE):
        raise HTTPException(status_code=400, detail="Sadece görseller boyutlandırılabilir")

    try:
        new_path = media_service.resize_image(media.file_path, aspect_ratio)
        w, h = media_service.get_image_dimensions(new_path)
        media.width = w
        media.height = h
        media.file_size = os.path.getsize(new_path)
        if new_path != media.file_path:
            media.file_path = new_path
        db.commit()
        return {"message": f"Görsel {aspect_ratio} olarak boyutlandırıldı"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{media_id}")
async def delete_media(
    media_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Medya dosyasını siler."""
    media = db.query(Media).filter(Media.id == media_id).first()
    if not media:
        raise HTTPException(status_code=404, detail="Medya bulunamadı")

    # Dosyayı diskten sil
    try:
        if os.path.exists(media.file_path):
            os.remove(media.file_path)
        if media.thumbnail_path and os.path.exists(media.thumbnail_path):
            os.remove(media.thumbnail_path)
    except Exception:
        pass

    db.delete(media)
    db.commit()
    return {"message": "Medya silindi"}
