# routers/hashtags.py — Hashtag grup yönetimi
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.database import get_db
from app.models.hashtag import HashtagGroup
from app.models.user import User
from app.routers.auth import get_current_user

router = APIRouter(prefix="/api/hashtags", tags=["Hashtag Yönetimi"])


class HashtagGroupCreate(BaseModel):
    name: str
    hashtags: list[str]
    account_id: int | None = None


class HashtagGroupUpdate(BaseModel):
    name: str | None = None
    hashtags: list[str] | None = None


@router.get("")
async def list_groups(
    account_id: int | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Hashtag gruplarını listeler."""
    query = db.query(HashtagGroup)
    if account_id:
        query = query.filter(
            (HashtagGroup.account_id == account_id)
            | (HashtagGroup.account_id == None)
        )
    groups = query.order_by(HashtagGroup.usage_count.desc()).all()
    return {
        "groups": [
            {
                "id": g.id,
                "name": g.name,
                "hashtags": g.hashtags,
                "hashtag_string": g.get_hashtag_string(),
                "account_id": g.account_id,
                "usage_count": g.usage_count,
            }
            for g in groups
        ]
    }


@router.post("")
async def create_group(
    data: HashtagGroupCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Yeni hashtag grubu oluşturur."""
    group = HashtagGroup(
        name=data.name,
        hashtags=data.hashtags,
        account_id=data.account_id,
    )
    db.add(group)
    db.commit()
    return {"message": "Hashtag grubu oluşturuldu", "group_id": group.id}


@router.put("/{group_id}")
async def update_group(
    group_id: int,
    data: HashtagGroupUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Hashtag grubunu günceller."""
    group = db.query(HashtagGroup).filter(HashtagGroup.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Grup bulunamadı")

    if data.name is not None:
        group.name = data.name
    if data.hashtags is not None:
        group.hashtags = data.hashtags

    db.commit()
    return {"message": "Grup güncellendi"}


@router.delete("/{group_id}")
async def delete_group(
    group_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Hashtag grubunu siler."""
    group = db.query(HashtagGroup).filter(HashtagGroup.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Grup bulunamadı")
    db.delete(group)
    db.commit()
    return {"message": "Grup silindi"}
