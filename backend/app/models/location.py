# models/location.py — Konum yönetimi modeli
from datetime import datetime
from sqlalchemy import String, Integer, DateTime, Text, Boolean
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class Location(Base):
    """Paylaşım için Instagram konum listeleri."""
    __tablename__ = "locations"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    instagram_location_pk: Mapped[str | None] = mapped_column(String(100), nullable=True)
    lat: Mapped[str | None] = mapped_column(String(50), nullable=True)
    lng: Mapped[str | None] = mapped_column(String(50), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<Location {self.name} ({self.city})>"
