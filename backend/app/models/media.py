# models/media.py — Medya dosya modeli
import enum
from datetime import datetime
from sqlalchemy import String, Integer, DateTime, Text, Enum, ForeignKey, BigInteger
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class MediaFileType(str, enum.Enum):
    PHOTO = "PHOTO"
    VIDEO = "VIDEO"
    REELS = "REELS"
    PROFILE = "PROFILE"


class Media(Base):
    __tablename__ = "media_files"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    account_id: Mapped[int | None] = mapped_column(
        ForeignKey("accounts.id", ondelete="SET NULL"), nullable=True
    )
    filename: Mapped[str] = mapped_column(String(500), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(500), nullable=False)
    file_path: Mapped[str] = mapped_column(Text, nullable=False)
    thumbnail_path: Mapped[str | None] = mapped_column(Text, nullable=True)

    media_type: Mapped[MediaFileType] = mapped_column(
        Enum(MediaFileType), default=MediaFileType.PHOTO
    )
    folder: Mapped[str] = mapped_column(String(255), default="default")
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)

    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    file_size: Mapped[int] = mapped_column(BigInteger, default=0)
    duration: Mapped[int | None] = mapped_column(Integer, nullable=True)  # video saniye

    # İndirilen içerik için
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_username: Mapped[str | None] = mapped_column(String(100), nullable=True)

    is_used: Mapped[bool] = mapped_column(default=False)
    use_count: Mapped[int] = mapped_column(Integer, default=0)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # İlişkiler
    account = relationship("Account", back_populates="media_files")

    def __repr__(self):
        return f"<Media {self.filename} ({self.media_type.value})>"
