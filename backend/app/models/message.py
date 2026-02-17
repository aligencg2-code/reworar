# models/message.py — DM mesaj, şablon ve otomatik yanıt modelleri
from datetime import datetime
from sqlalchemy import (
    String, Integer, DateTime, Text, Boolean, ForeignKey, JSON
)
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    account_id: Mapped[int] = mapped_column(
        ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False
    )
    conversation_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    sender_id: Mapped[str] = mapped_column(String(100), nullable=False)
    sender_username: Mapped[str | None] = mapped_column(String(100), nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    is_incoming: Mapped[bool] = mapped_column(Boolean, default=True)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    auto_replied: Mapped[bool] = mapped_column(Boolean, default=False)
    tags: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        direction = "←" if self.is_incoming else "→"
        return f"<Message {direction} {self.sender_username}: {self.content[:30]}>"


class MessageTemplate(Base):
    """Hazır yanıt şablonları."""
    __tablename__ = "message_templates"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String(50), default="general")
    shortcut: Mapped[str | None] = mapped_column(String(20), nullable=True)
    use_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<Template '{self.name}'>"


class AutoReplyRule(Base):
    """Anahtar kelime bazlı otomatik yanıt kuralları."""
    __tablename__ = "auto_reply_rules"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    account_id: Mapped[int | None] = mapped_column(
        ForeignKey("accounts.id", ondelete="CASCADE"), nullable=True
    )
    keywords: Mapped[dict] = mapped_column(JSON, nullable=False)  # ["fiyat", "price"]
    response: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    match_type: Mapped[str] = mapped_column(
        String(20), default="contains"
    )  # contains, exact, starts_with
    priority: Mapped[int] = mapped_column(Integer, default=0)
    whatsapp_redirect: Mapped[str | None] = mapped_column(String(500), nullable=True)
    trigger_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<AutoReply keywords={self.keywords}>"
