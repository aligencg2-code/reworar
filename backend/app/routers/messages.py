# routers/messages.py — Mesaj ve DM yönetim endpoint'leri
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.database import get_db
from app.models.message import Message, MessageTemplate, AutoReplyRule
from app.models.user import User
from app.routers.auth import get_current_user
from app.services.message_service import message_service

router = APIRouter(prefix="/api/messages", tags=["Mesaj Yönetimi"])


# ─── Şemalar ───────────────────────────────────────────
class TemplateCreate(BaseModel):
    name: str
    content: str
    category: str = "general"
    shortcut: str | None = None


class AutoReplyCreate(BaseModel):
    account_id: int | None = None
    keywords: list[str]
    response: str
    match_type: str = "contains"
    priority: int = 0
    whatsapp_redirect: str | None = None


class TagRequest(BaseModel):
    tags: list[str]


# ─── Konuşmalar ───────────────────────────────────────
@router.get("/conversations/{account_id}")
async def get_conversations(
    account_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Bir hesabın DM konuşmalarını getirir."""
    conversations = await message_service.fetch_conversations(db, account_id)
    return {"conversations": conversations}


@router.get("/history/{account_id}")
async def get_message_history(
    account_id: int,
    conversation_id: str | None = None,
    limit: int = 50,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Mesaj geçmişi (konuşma bazlı veya tümü)."""
    query = db.query(Message).filter(Message.account_id == account_id)
    if conversation_id:
        query = query.filter(Message.conversation_id == conversation_id)

    messages = query.order_by(Message.timestamp.desc()).limit(limit).all()
    return {
        "messages": [
            {
                "id": m.id,
                "sender_username": m.sender_username,
                "content": m.content,
                "is_incoming": m.is_incoming,
                "is_read": m.is_read,
                "auto_replied": m.auto_replied,
                "tags": m.tags,
                "timestamp": m.timestamp.isoformat(),
            }
            for m in messages
        ]
    }


@router.post("/tag/{message_id}")
async def tag_message(
    message_id: int,
    data: TagRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Mesaja etiket ekler."""
    message_service.tag_message(db, message_id, data.tags)
    return {"message": "Etiketler eklendi"}


# ─── Şablonlar ────────────────────────────────────────
@router.get("/templates")
async def list_templates(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Hazır yanıt şablonlarını listeler."""
    templates = db.query(MessageTemplate).order_by(
        MessageTemplate.use_count.desc()
    ).all()
    return {
        "templates": [
            {
                "id": t.id,
                "name": t.name,
                "content": t.content,
                "category": t.category,
                "shortcut": t.shortcut,
                "use_count": t.use_count,
            }
            for t in templates
        ]
    }


@router.post("/templates")
async def create_template(
    data: TemplateCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Yeni yanıt şablonu oluşturur."""
    template = MessageTemplate(
        name=data.name,
        content=data.content,
        category=data.category,
        shortcut=data.shortcut,
    )
    db.add(template)
    db.commit()
    return {"message": "Şablon oluşturuldu", "template_id": template.id}


@router.delete("/templates/{template_id}")
async def delete_template(
    template_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Şablon siler."""
    template = db.query(MessageTemplate).filter(
        MessageTemplate.id == template_id
    ).first()
    if not template:
        raise HTTPException(status_code=404, detail="Şablon bulunamadı")
    db.delete(template)
    db.commit()
    return {"message": "Şablon silindi"}


# ─── Otomatik Yanıt Kuralları ─────────────────────────
@router.get("/auto-reply")
async def list_auto_reply_rules(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Otomatik yanıt kurallarını listeler."""
    rules = db.query(AutoReplyRule).order_by(AutoReplyRule.priority.desc()).all()
    return {
        "rules": [
            {
                "id": r.id,
                "account_id": r.account_id,
                "keywords": r.keywords,
                "response": r.response,
                "match_type": r.match_type,
                "is_active": r.is_active,
                "priority": r.priority,
                "whatsapp_redirect": r.whatsapp_redirect,
                "trigger_count": r.trigger_count,
            }
            for r in rules
        ]
    }


@router.post("/auto-reply")
async def create_auto_reply_rule(
    data: AutoReplyCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Yeni otomatik yanıt kuralı oluşturur."""
    rule = AutoReplyRule(
        account_id=data.account_id,
        keywords=data.keywords,
        response=data.response,
        match_type=data.match_type,
        priority=data.priority,
        whatsapp_redirect=data.whatsapp_redirect,
    )
    db.add(rule)
    db.commit()
    return {"message": "Kural oluşturuldu", "rule_id": rule.id}


@router.delete("/auto-reply/{rule_id}")
async def delete_auto_reply_rule(
    rule_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Otomatik yanıt kuralını siler."""
    rule = db.query(AutoReplyRule).filter(AutoReplyRule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Kural bulunamadı")
    db.delete(rule)
    db.commit()
    return {"message": "Kural silindi"}
