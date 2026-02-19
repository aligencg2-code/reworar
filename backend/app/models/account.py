# models/account.py — Instagram hesap modeli
from datetime import datetime
from sqlalchemy import String, Boolean, Integer, DateTime, Text, Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base
import enum


class AccountStatus(str, enum.Enum):
    ACTIVE = "active"
    RESTRICTED = "restricted"
    ACTION_BLOCKED = "action_blocked"
    DISABLED = "disabled"
    CHECKPOINT = "checkpoint"
    UNKNOWN = "unknown"


class AppealStatus(str, enum.Enum):
    NONE = "none"
    PENDING = "pending"
    SUBMITTED = "submitted"
    APPROVED = "approved"
    REJECTED = "rejected"


class Account(Base):
    __tablename__ = "accounts"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    instagram_id: Mapped[str | None] = mapped_column(String(50), unique=True, nullable=True)
    username: Mapped[str] = mapped_column(String(100), nullable=False)
    full_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    profile_picture_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    biography: Mapped[str | None] = mapped_column(Text, nullable=True)
    followers_count: Mapped[int] = mapped_column(Integer, default=0)
    following_count: Mapped[int] = mapped_column(Integer, default=0)
    media_count: Mapped[int] = mapped_column(Integer, default=0)

    # Web otomasyon — şifre ve session
    password_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    email_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    email_password_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    session_cookies: Mapped[str | None] = mapped_column(Text, nullable=True)
    session_valid: Mapped[bool] = mapped_column(Boolean, default=False)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    two_factor_seed: Mapped[str | None] = mapped_column(String(100), nullable=True)
    login_method: Mapped[str] = mapped_column(String(50), default="password")

    # Eski Graph API alanları (uyumluluk)
    access_token_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    token_type: Mapped[str] = mapped_column(String(50), default="long_lived")
    token_expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Facebook sayfa bilgileri (uyumluluk)
    facebook_page_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    facebook_page_token_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Hesap durumu & itiraz
    account_status: Mapped[str] = mapped_column(
        String(50), default=AccountStatus.ACTIVE.value
    )
    appeal_status: Mapped[str] = mapped_column(
        String(50), default=AppealStatus.NONE.value
    )
    status_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_appeal_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Hesap ayarları
    daily_post_limit: Mapped[int] = mapped_column(Integer, default=10)
    posts_per_session: Mapped[int] = mapped_column(Integer, default=1)  # Her giriş başına paylaşım
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    auto_publish: Mapped[bool] = mapped_column(Boolean, default=False)

    # Paylaşım yüzdeleri
    photo_percentage: Mapped[int] = mapped_column(Integer, default=100)
    video_percentage: Mapped[int] = mapped_column(Integer, default=0)
    story_percentage: Mapped[int] = mapped_column(Integer, default=0)
    reels_percentage: Mapped[int] = mapped_column(Integer, default=0)

    # Medya işleme modu
    posting_mode: Mapped[str] = mapped_column(
        String(50), default="sequential"
    )  # sequential, random
    loop_mode: Mapped[str] = mapped_column(
        String(50), default="continue"
    )  # continue, reset

    # Proxy
    proxy_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Per-account izolasyon — her hesap kendi içerik kaynaklarını kullanır
    user_agent: Mapped[str | None] = mapped_column(String(500), nullable=True)  # Kalıcı UA
    selected_hashtag_group_id: Mapped[int | None] = mapped_column(Integer, nullable=True)  # Atanmış hashtag grubu
    selected_location_list: Mapped[str | None] = mapped_column(String(255), nullable=True)  # Atanmış konum listesi
    selected_media_list: Mapped[str | None] = mapped_column(String(255), nullable=True)  # Atanmış medya listesi/klasörü

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # İlişkiler
    posts = relationship("Post", back_populates="account", cascade="all, delete-orphan")
    media_files = relationship("Media", back_populates="account", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Account @{self.username}>"
