# routers/captions.py — Paylaşım yazısı CRUD endpoint'leri
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.database import get_db
from app.models.caption import Caption
from app.models.user import User
from app.routers.auth import get_current_user

router = APIRouter(prefix="/api/captions", tags=["Paylaşım Yazıları"])


class CaptionCreate(BaseModel):
    text: str
    display_order: int = 0


class CaptionUpdate(BaseModel):
    text: str | None = None
    display_order: int | None = None
    is_active: bool | None = None


class BulkCaptionImport(BaseModel):
    captions_text: str  # Her satır bir caption


@router.get("")
async def list_captions(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Tüm caption'ları listeler."""
    items = db.query(Caption).order_by(Caption.display_order, Caption.id).all()
    return {
        "total": len(items),
        "items": [
            {
                "id": c.id,
                "text": c.text,
                "display_order": c.display_order,
                "is_active": c.is_active,
                "use_count": c.use_count,
                "created_at": c.created_at.isoformat(),
            }
            for c in items
        ],
    }


@router.post("")
async def create_caption(
    data: CaptionCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Yeni caption ekler."""
    caption = Caption(text=data.text, display_order=data.display_order)
    db.add(caption)
    db.commit()
    return {"message": "Caption eklendi", "id": caption.id}


@router.post("/bulk-import")
async def bulk_import_captions(
    data: BulkCaptionImport,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Toplu caption import — her satır bir caption."""
    lines = [l.strip() for l in data.captions_text.strip().split("\n") if l.strip()]
    added = 0
    for i, text in enumerate(lines):
        caption = Caption(text=text, display_order=i)
        db.add(caption)
        added += 1
    db.commit()
    return {"message": f"{added} caption eklendi", "added": added}


@router.put("/{caption_id}")
async def update_caption(
    caption_id: int,
    data: CaptionUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Caption günceller."""
    caption = db.query(Caption).filter(Caption.id == caption_id).first()
    if not caption:
        raise HTTPException(status_code=404, detail="Caption bulunamadı")

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(caption, key, value)
    db.commit()
    return {"message": "Caption güncellendi"}


@router.delete("/{caption_id}")
async def delete_caption(
    caption_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Caption siler."""
    caption = db.query(Caption).filter(Caption.id == caption_id).first()
    if not caption:
        raise HTTPException(status_code=404, detail="Caption bulunamadı")
    db.delete(caption)
    db.commit()
    return {"message": "Caption silindi"}


@router.delete("")
async def delete_all_captions(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Tüm caption'ları siler."""
    count = db.query(Caption).delete()
    db.commit()
    return {"message": f"{count} caption silindi"}
