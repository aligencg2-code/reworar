# models/post.py — Planlanan gönderi ve medya ilişki modeli
import enum
from datetime import datetime
from sqlalchemy import (
    String, Integer, DateTime, Text, Enum, ForeignKey, JSON, Boolean
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class PostStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    SCHEDULED = "SCHEDULED"
    PUBLISHING = "PUBLISHING"
    PUBLISHED = "PUBLISHED"
    FAILED = "FAILED"


class MediaType(str, enum.Enum):
    PHOTO = "PHOTO"
    VIDEO = "VIDEO"
    STORY = "STORY"
    REELS = "REELS"
    CAROUSEL = "CAROUSEL"


class Post(Base):
    __tablename__ = "posts"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    account_id: Mapped[int] = mapped_column(
        ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False
    )
    caption: Mapped[str | None] = mapped_column(Text, nullable=True)
    media_type: Mapped[MediaType] = mapped_column(
        Enum(MediaType), default=MediaType.PHOTO
    )
    status: Mapped[PostStatus] = mapped_column(
        Enum(PostStatus), default=PostStatus.DRAFT
    )

    # Zamanlama
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Hashtag grubu
    hashtag_group_id: Mapped[int | None] = mapped_column(
        ForeignKey("hashtag_groups.id", ondelete="SET NULL"), nullable=True
    )

    # Konum
    location_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    location_name: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Instagram API yanıtı
    instagram_media_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    instagram_permalink: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Hata bilgisi
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)

    # Görsel ayarları
    aspect_ratio: Mapped[str] = mapped_column(String(10), default="1:1")
    auto_resize: Mapped[bool] = mapped_column(Boolean, default=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # İlişkiler
    account = relationship("Account", back_populates="posts")
    hashtag_group = relationship("HashtagGroup")
    media_items = relationship(
        "PostMedia", back_populates="post", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<Post {self.id} [{self.status.value}] @{self.scheduled_at}>"


class PostMedia(Base):
    """Bir gönderiye bağlı medya dosyaları (carousel desteği)."""
    __tablename__ = "post_media"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    post_id: Mapped[int] = mapped_column(
        ForeignKey("posts.id", ondelete="CASCADE"), nullable=False
    )
    media_id: Mapped[int] = mapped_column(
        ForeignKey("media_files.id", ondelete="CASCADE"), nullable=False
    )
    position: Mapped[int] = mapped_column(Integer, default=0)  # carousel sırası

    post = relationship("Post", back_populates="media_items")
    media = relationship("Media")
