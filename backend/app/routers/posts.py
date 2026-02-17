# routers/posts.py — Gönderi planlama ve yönetimi
from datetime import datetime, date
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.database import get_db
from app.models.post import Post, PostStatus, MediaType
from app.models.user import User
from app.routers.auth import get_current_user
from app.services.scheduler_service import scheduler_service

router = APIRouter(prefix="/api/posts", tags=["Gönderi Yönetimi"])


class PostCreate(BaseModel):
    account_id: int
    caption: str | None = None
    media_type: str = "photo"
    scheduled_at: datetime | None = None
    hashtag_group_id: int | None = None
    location_name: str | None = None
    aspect_ratio: str = "1:1"
    auto_resize: bool = True
    media_ids: list[int] = []
    status: str = "draft"


class PostUpdate(BaseModel):
    caption: str | None = None
    scheduled_at: datetime | None = None
    hashtag_group_id: int | None = None
    location_name: str | None = None
    aspect_ratio: str | None = None
    status: str | None = None
    media_ids: list[int] | None = None


@router.post("")
async def create_post(
    data: PostCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Yeni gönderi oluşturur (taslak veya planlı)."""
    media_type_map = {
        "photo": MediaType.PHOTO,
        "video": MediaType.VIDEO,
        "story": MediaType.STORY,
        "reels": MediaType.REELS,
        "carousel": MediaType.CAROUSEL,
    }
    status_map = {
        "draft": PostStatus.DRAFT,
        "scheduled": PostStatus.SCHEDULED,
    }

    post = Post(
        account_id=data.account_id,
        caption=data.caption,
        media_type=media_type_map.get(data.media_type, MediaType.PHOTO),
        status=status_map.get(data.status, PostStatus.DRAFT),
        scheduled_at=data.scheduled_at,
        hashtag_group_id=data.hashtag_group_id,
        location_name=data.location_name,
        aspect_ratio=data.aspect_ratio,
        auto_resize=data.auto_resize,
    )
    db.add(post)
    db.flush()

    # Medya dosyalarını bağla
    if data.media_ids:
        from app.models.post import PostMedia
        for i, mid in enumerate(data.media_ids):
            pm = PostMedia(post_id=post.id, media_id=mid, position=i)
            db.add(pm)

    db.commit()
    return {"message": "Gönderi oluşturuldu", "post_id": post.id}


@router.get("")
async def list_posts(
    status: str | None = None,
    account_id: int | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Gönderi listesi (filtreli)."""
    query = db.query(Post)

    if status:
        query = query.filter(Post.status == PostStatus(status))
    if account_id:
        query = query.filter(Post.account_id == account_id)
    if date_from:
        query = query.filter(Post.scheduled_at >= datetime.combine(date_from, datetime.min.time()))
    if date_to:
        query = query.filter(Post.scheduled_at <= datetime.combine(date_to, datetime.max.time()))

    total = query.count()
    posts = query.order_by(Post.scheduled_at.desc()).offset(offset).limit(limit).all()

    return {
        "total": total,
        "posts": [
            {
                "id": p.id,
                "account_id": p.account_id,
                "caption": p.caption,
                "media_type": p.media_type.value.lower(),
                "status": p.status.value.lower(),
                "scheduled_at": p.scheduled_at.isoformat() if p.scheduled_at else None,
                "published_at": p.published_at.isoformat() if p.published_at else None,
                "error_message": p.error_message,
                "aspect_ratio": p.aspect_ratio,
                "media_count": len(p.media_items),
            }
            for p in posts
        ],
    }


@router.get("/calendar")
async def calendar_view(
    month: int,
    year: int,
    account_id: int | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Takvim görünümü verisi — ay bazlı."""
    from calendar import monthrange
    _, last_day = monthrange(year, month)
    start = datetime(year, month, 1)
    end = datetime(year, month, last_day, 23, 59, 59)

    query = db.query(Post).filter(
        Post.scheduled_at >= start,
        Post.scheduled_at <= end,
    )
    if account_id:
        query = query.filter(Post.account_id == account_id)

    posts = query.order_by(Post.scheduled_at).all()

    # Gün bazlı grupla
    calendar_data = {}
    for p in posts:
        day = p.scheduled_at.day
        if day not in calendar_data:
            calendar_data[day] = []
        calendar_data[day].append({
            "id": p.id,
            "caption": (p.caption or "")[:50],
            "media_type": p.media_type.value.lower(),
            "status": p.status.value.lower(),
            "time": p.scheduled_at.strftime("%H:%M"),
        })

    return {"year": year, "month": month, "days": calendar_data}


@router.put("/{post_id}")
async def update_post(
    post_id: int,
    data: PostUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Gönderiyi düzenler."""
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Gönderi bulunamadı")

    if post.status == PostStatus.PUBLISHED:
        raise HTTPException(status_code=400, detail="Yayınlanmış gönderi düzenlenemez")

    update_data = data.model_dump(exclude_unset=True)

    if "status" in update_data:
        update_data["status"] = PostStatus(update_data["status"])
    if "media_ids" in update_data:
        media_ids = update_data.pop("media_ids")
        from app.models.post import PostMedia
        # Mevcut medya bağlantılarını sil
        db.query(PostMedia).filter(PostMedia.post_id == post_id).delete()
        for i, mid in enumerate(media_ids):
            db.add(PostMedia(post_id=post_id, media_id=mid, position=i))

    for key, value in update_data.items():
        setattr(post, key, value)

    db.commit()
    return {"message": "Gönderi güncellendi"}


@router.delete("/{post_id}")
async def delete_post(
    post_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Gönderiyi siler."""
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Gönderi bulunamadı")
    db.delete(post)
    db.commit()
    return {"message": "Gönderi silindi"}


@router.post("/{post_id}/publish")
async def publish_now(
    post_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Gönderiyi anında yayınlar."""
    try:
        post = db.query(Post).filter(Post.id == post_id).first()
        if not post:
            raise HTTPException(status_code=404, detail="Gönderi bulunamadı")

        if post.status == PostStatus.PUBLISHED:
            raise HTTPException(status_code=400, detail="Gönderi zaten yayınlanmış")

        # Yayınlama statusunu hemen güncelle
        post.status = PostStatus.PUBLISHING
        db.commit()

        # Arka planda yayınla — thread ile
        import threading
        t = threading.Thread(
            target=_publish_in_thread,
            args=(post_id,),
            daemon=True,
            name=f"publish-{post_id}",
        )
        t.start()
        return {"message": "Yayınlama başlatıldı", "post_id": post_id}
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Yayınlama hatası: {str(e)}")


def _publish_in_thread(post_id: int):
    """Thread'de gönderi yayınlar (kendi event loop ve DB session'ı ile)."""
    import asyncio
    import logging

    logger = logging.getLogger("demet")
    logger.info(f"🚀 Yayınlama thread başlatıldı: Post #{post_id}")

    from app.database import SessionLocal
    db = SessionLocal()
    try:
        post = db.query(Post).filter(Post.id == post_id).first()
        if not post:
            logger.error(f"❌ Post #{post_id} bulunamadı")
            return

        # Yeni event loop oluştur (bu thread için)
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(scheduler_service.publish_post(db, post))
            logger.info(f"✅ Post #{post_id} yayınlama tamamlandı")
        finally:
            loop.close()
    except Exception as e:
        logger.error(f"❌ Yayınlama hatası Post #{post_id}: {e}")
        try:
            post = db.query(Post).filter(Post.id == post_id).first()
            if post and post.status != PostStatus.PUBLISHED:
                post.status = PostStatus.FAILED
                post.error_message = str(e)[:500]
                db.commit()
        except Exception:
            pass
    finally:
        db.close()

