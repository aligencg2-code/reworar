# services/message_service.py — Mesaj yönetim servisi
from datetime import datetime
from sqlalchemy.orm import Session
from app.models.message import Message, MessageTemplate, AutoReplyRule
from app.models.account import Account
from app.services.instagram_api import InstagramAPIClient
from app.utils.encryption import decrypt_token
from app.utils.logger import logger


class MessageService:
    """DM mesaj yönetimi, otomatik yanıt ve şablon servisi."""

    async def fetch_conversations(self, db: Session, account_id: int) -> list[dict]:
        """Bir hesabın DM konuşmalarını çeker ve kaydeder."""
        account = db.query(Account).filter(Account.id == account_id).first()
        if not account or not account.access_token_encrypted:
            return []

        token = decrypt_token(account.access_token_encrypted)
        client = InstagramAPIClient(token, account.instagram_id)

        try:
            data = await client.get_conversations()
            conversations = []
            for conv in data.get("data", []):
                conv_id = conv["id"]
                participants = conv.get("participants", {}).get("data", [])
                messages = conv.get("messages", {}).get("data", [])

                for msg in messages:
                    existing = (
                        db.query(Message)
                        .filter(
                            Message.conversation_id == conv_id,
                            Message.content == msg.get("message", ""),
                            Message.sender_id == msg.get("from", {}).get("id", ""),
                        )
                        .first()
                    )
                    if not existing:
                        new_msg = Message(
                            account_id=account_id,
                            conversation_id=conv_id,
                            sender_id=msg.get("from", {}).get("id", ""),
                            sender_username=msg.get("from", {}).get("name", ""),
                            content=msg.get("message", ""),
                            is_incoming=msg.get("from", {}).get("id") != account.instagram_id,
                            timestamp=datetime.fromisoformat(
                                msg.get("created_time", datetime.utcnow().isoformat())
                            ),
                        )
                        db.add(new_msg)

                conversations.append({
                    "id": conv_id,
                    "participants": participants,
                    "last_message": messages[0] if messages else None,
                    "message_count": len(messages),
                })

            db.commit()
            return conversations
        finally:
            await client.close()

    async def check_auto_reply(self, db: Session, message: Message):
        """Gelen mesajı otomatik yanıt kurallarıyla eşleştirir."""
        rules = (
            db.query(AutoReplyRule)
            .filter(
                AutoReplyRule.is_active == True,
                (AutoReplyRule.account_id == message.account_id)
                | (AutoReplyRule.account_id == None),
            )
            .order_by(AutoReplyRule.priority.desc())
            .all()
        )

        for rule in rules:
            if self._matches_rule(message.content, rule):
                # Otomatik yanıt gönder
                account = db.query(Account).filter(
                    Account.id == message.account_id
                ).first()
                if not account:
                    continue

                response_text = rule.response
                # WhatsApp yönlendirmesi varsa ekle
                if rule.whatsapp_redirect:
                    response_text += f"\n\nWhatsApp: {rule.whatsapp_redirect}"

                token = decrypt_token(account.access_token_encrypted)
                client = InstagramAPIClient(token, account.instagram_id)
                try:
                    await client.send_message(message.sender_id, response_text)
                    message.auto_replied = True
                    rule.trigger_count += 1

                    # Yanıtı da kaydet
                    reply = Message(
                        account_id=message.account_id,
                        conversation_id=message.conversation_id,
                        sender_id=account.instagram_id,
                        sender_username=account.username,
                        content=response_text,
                        is_incoming=False,
                        auto_replied=True,
                    )
                    db.add(reply)
                    db.commit()

                    logger.info(
                        f"Otomatik yanıt gönderildi: {message.sender_username} "
                        f"→ Kural: {rule.keywords}"
                    )
                finally:
                    await client.close()
                return True
        return False

    def _matches_rule(self, content: str, rule: AutoReplyRule) -> bool:
        """Mesaj içeriğini kuralla eşleştirir."""
        content_lower = content.lower()
        keywords = [kw.lower() for kw in rule.keywords]

        if rule.match_type == "exact":
            return content_lower in keywords
        elif rule.match_type == "starts_with":
            return any(content_lower.startswith(kw) for kw in keywords)
        else:  # contains
            return any(kw in content_lower for kw in keywords)

    def tag_message(self, db: Session, message_id: int, tags: list[str]):
        """Mesaja etiket ekler."""
        message = db.query(Message).filter(Message.id == message_id).first()
        if message:
            existing_tags = message.tags or []
            message.tags = list(set(existing_tags + tags))
            db.commit()

    @staticmethod
    def generate_whatsapp_link(phone: str, text: str = "") -> str:
        """WhatsApp yönlendirme bağlantısı oluşturur."""
        clean_phone = phone.replace("+", "").replace(" ", "").replace("-", "")
        link = f"https://wa.me/{clean_phone}"
        if text:
            from urllib.parse import quote
            link += f"?text={quote(text)}"
        return link


message_service = MessageService()
