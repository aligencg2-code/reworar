# models/log.py — Aktivite log modeli
import enum
from datetime import datetime
from sqlalchemy import String, Integer, DateTime, Text, Enum, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class LogLevel(str, enum.Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class LogCategory(str, enum.Enum):
    AUTH = "AUTH"
    POST = "POST"
    MEDIA = "MEDIA"
    MESSAGE = "MESSAGE"
    DOWNLOAD = "DOWNLOAD"
    SCHEDULER = "SCHEDULER"
    API = "API"
    SYSTEM = "SYSTEM"


class ActivityLog(Base):
    __tablename__ = "activity_logs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    level: Mapped[LogLevel] = mapped_column(Enum(LogLevel), default=LogLevel.INFO)
    category: Mapped[LogCategory] = mapped_column(
        Enum(LogCategory), default=LogCategory.SYSTEM
    )
    account_id: Mapped[int | None] = mapped_column(
        ForeignKey("accounts.id", ondelete="SET NULL"), nullable=True
    )
    action: Mapped[str] = mapped_column(String(255), nullable=False)
    details: Mapped[str | None] = mapped_column(Text, nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(50), nullable=True)
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<Log [{self.level.value}] {self.category.value}: {self.action}>"
