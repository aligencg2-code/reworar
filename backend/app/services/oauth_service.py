# services/oauth_service.py — OAuth 2.0 token yönetimi
import httpx
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from app.config import settings
from app.models.account import Account
from app.utils.encryption import encrypt_token, decrypt_token
from app.utils.logger import logger


class OAuthService:
    """Facebook/Instagram OAuth 2.0 akış yönetimi."""

    SCOPES = [
        "instagram_basic",
        "instagram_content_publish",
        "instagram_manage_comments",
        "instagram_manage_messages",
        "pages_show_list",
        "pages_read_engagement",
        "pages_manage_metadata",
    ]

    def get_authorization_url(self) -> str:
        """Facebook OAuth yetkilendirme URL'si oluşturur."""
        scope = ",".join(self.SCOPES)
        return (
            f"https://www.facebook.com/v21.0/dialog/oauth?"
            f"client_id={settings.FACEBOOK_APP_ID}"
            f"&redirect_uri={settings.FACEBOOK_REDIRECT_URI}"
            f"&scope={scope}"
            f"&response_type=code"
        )

    async def exchange_code_for_token(self, code: str) -> dict:
        """Auth code'u short-lived access token ile değiştirir."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{settings.FACEBOOK_GRAPH_API_BASE}/oauth/access_token",
                params={
                    "client_id": settings.FACEBOOK_APP_ID,
                    "client_secret": settings.FACEBOOK_APP_SECRET,
                    "redirect_uri": settings.FACEBOOK_REDIRECT_URI,
                    "code": code,
                },
            )
            data = response.json()
            if "error" in data:
                raise Exception(f"Token alma hatası: {data['error']['message']}")

            # Long-lived token'a çevir
            long_lived = await self._get_long_lived_token(data["access_token"])
            return long_lived

    async def _get_long_lived_token(self, short_lived_token: str) -> dict:
        """Short-lived token'ı long-lived (60 gün) token'a çevirir."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{settings.FACEBOOK_GRAPH_API_BASE}/oauth/access_token",
                params={
                    "grant_type": "fb_exchange_token",
                    "client_id": settings.FACEBOOK_APP_ID,
                    "client_secret": settings.FACEBOOK_APP_SECRET,
                    "fb_exchange_token": short_lived_token,
                },
            )
            data = response.json()
            if "error" in data:
                raise Exception(f"Long-lived token hatası: {data['error']['message']}")
            return {
                "access_token": data["access_token"],
                "expires_in": data.get("expires_in", 5184000),  # 60 gün
            }

    async def get_instagram_accounts(self, user_token: str) -> list[dict]:
        """Kullanıcının bağlı Instagram Business hesaplarını listeler."""
        async with httpx.AsyncClient() as client:
            # Önce Facebook sayfalarını al
            response = await client.get(
                f"{settings.FACEBOOK_GRAPH_API_BASE}/me/accounts",
                params={
                    "fields": "id,name,access_token,instagram_business_account"
                              "{id,username,name,profile_picture_url,"
                              "followers_count,follows_count,media_count,biography}",
                    "access_token": user_token,
                },
            )
            data = response.json()
            accounts = []
            for page in data.get("data", []):
                ig = page.get("instagram_business_account")
                if ig:
                    accounts.append({
                        "instagram_id": ig["id"],
                        "username": ig.get("username", ""),
                        "full_name": ig.get("name", ""),
                        "profile_picture_url": ig.get("profile_picture_url", ""),
                        "followers_count": ig.get("followers_count", 0),
                        "following_count": ig.get("follows_count", 0),
                        "media_count": ig.get("media_count", 0),
                        "biography": ig.get("biography", ""),
                        "facebook_page_id": page["id"],
                        "facebook_page_token": page["access_token"],
                    })
            return accounts

    async def refresh_token(self, db: Session, account_id: int) -> bool:
        """Bir hesabın token'ını yeniler (60 günlük token ise)."""
        account = db.query(Account).filter(Account.id == account_id).first()
        if not account or not account.access_token_encrypted:
            return False

        try:
            current_token = decrypt_token(account.access_token_encrypted)
            long_lived = await self._get_long_lived_token(current_token)

            account.access_token_encrypted = encrypt_token(long_lived["access_token"])
            account.token_expires_at = datetime.utcnow() + timedelta(
                seconds=long_lived["expires_in"]
            )
            db.commit()
            logger.info(f"Token yenilendi: @{account.username}")
            return True
        except Exception as e:
            logger.error(f"Token yenileme hatası @{account.username}: {e}")
            return False

    async def validate_token(self, token: str) -> dict:
        """Token geçerliliğini kontrol eder."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{settings.FACEBOOK_GRAPH_API_BASE}/debug_token",
                params={
                    "input_token": token,
                    "access_token": f"{settings.FACEBOOK_APP_ID}|{settings.FACEBOOK_APP_SECRET}",
                },
            )
            return response.json()


oauth_service = OAuthService()
