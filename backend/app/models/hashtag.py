# models/hashtag.py — Hashtag grup modeli
from datetime import datetime
from sqlalchemy import String, Integer, DateTime, JSON, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class HashtagGroup(Base):
    __tablename__ = "hashtag_groups"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    hashtags: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    account_id: Mapped[int | None] = mapped_column(
        ForeignKey("accounts.id", ondelete="SET NULL"), nullable=True
    )
    usage_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    def get_hashtag_string(self) -> str:
        """Hashtag listesini metin olarak döndürür."""
        return " ".join(f"#{tag.lstrip('#')}" for tag in self.hashtags)

    def __repr__(self):
        return f"<HashtagGroup '{self.name}' ({len(self.hashtags)} tags)>"
