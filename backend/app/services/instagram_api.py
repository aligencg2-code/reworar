# services/instagram_api.py — Instagram Graph API istemcisi
import httpx
from datetime import datetime
from app.config import settings
from app.utils.rate_limiter import rate_limiter
from app.utils.logger import logger


class InstagramAPIError(Exception):
    """Instagram API hata sınıfı."""
    def __init__(self, message: str, code: int = 0, subcode: int = 0):
        self.message = message
        self.code = code
        self.subcode = subcode
        super().__init__(message)


class InstagramAPIClient:
    """Instagram Graph API istemcisi — tüm API çağrılarını yönetir."""

    def __init__(self, access_token: str, account_ig_id: str):
        self.access_token = access_token
        self.account_ig_id = account_ig_id
        self.base_url = settings.INSTAGRAM_API_BASE
        self.fb_base_url = settings.FACEBOOK_GRAPH_API_BASE
        self._client = httpx.AsyncClient(timeout=60.0)

    async def close(self):
        await self._client.aclose()

    async def _request(self, method: str, url: str, **kwargs) -> dict:
        """Rate limit kontrollü API çağrısı."""
        if not rate_limiter.can_call(self.account_ig_id):
            wait = rate_limiter.get_wait_time(self.account_ig_id)
            raise InstagramAPIError(
                f"Rate limit aşıldı. {wait:.0f} saniye bekleyin.", code=429
            )

        rate_limiter.record_call(self.account_ig_id)

        try:
            response = await self._client.request(method, url, **kwargs)
            data = response.json()

            if "error" in data:
                err = data["error"]
                raise InstagramAPIError(
                    message=err.get("message", "Bilinmeyen hata"),
                    code=err.get("code", 0),
                    subcode=err.get("error_subcode", 0),
                )

            return data
        except httpx.HTTPError as e:
            logger.error(f"HTTP hatası: {e}")
            raise InstagramAPIError(f"Bağlantı hatası: {str(e)}")

    # ─── Profil ────────────────────────────────────────
    async def get_profile(self) -> dict:
        """Hesap profil bilgilerini getirir."""
        url = f"{self.base_url}/{self.account_ig_id}"
        params = {
            "fields": "id,username,name,biography,profile_picture_url,"
                      "followers_count,follows_count,media_count",
            "access_token": self.access_token,
        }
        return await self._request("GET", url, params=params)

    # ─── İçerik Yayınlama ──────────────────────────────
    async def create_media_container(
        self,
        image_url: str = None,
        video_url: str = None,
        caption: str = "",
        media_type: str = "IMAGE",
        is_carousel_item: bool = False,
        location_id: str = None,
    ) -> str:
        """Medya container oluşturur (yayınlama 1. adım)."""
        url = f"{self.base_url}/{self.account_ig_id}/media"
        data = {
            "caption": caption,
            "access_token": self.access_token,
        }

        if media_type == "IMAGE" or media_type == "CAROUSEL":
            data["image_url"] = image_url
        elif media_type == "VIDEO":
            data["video_url"] = video_url
            data["media_type"] = "VIDEO"
        elif media_type == "REELS":
            data["video_url"] = video_url
            data["media_type"] = "REELS"
        elif media_type == "STORIES":
            if image_url:
                data["image_url"] = image_url
            elif video_url:
                data["video_url"] = video_url
                data["media_type"] = "VIDEO"

        if is_carousel_item:
            data["is_carousel_item"] = True
            data.pop("caption", None)

        if location_id:
            data["location_id"] = location_id

        result = await self._request("POST", url, data=data)
        return result["id"]

    async def create_carousel_container(
        self, children_ids: list[str], caption: str = ""
    ) -> str:
        """Carousel container oluşturur."""
        url = f"{self.base_url}/{self.account_ig_id}/media"
        data = {
            "media_type": "CAROUSEL",
            "children": ",".join(children_ids),
            "caption": caption,
            "access_token": self.access_token,
        }
        result = await self._request("POST", url, data=data)
        return result["id"]

    async def publish_media(self, creation_id: str) -> dict:
        """Container'ı yayınlar (yayınlama 2. adım)."""
        url = f"{self.base_url}/{self.account_ig_id}/media_publish"
        data = {
            "creation_id": creation_id,
            "access_token": self.access_token,
        }
        return await self._request("POST", url, data=data)

    async def check_media_status(self, container_id: str) -> dict:
        """Medya container durumunu kontrol eder (video işleme)."""
        url = f"{self.base_url}/{container_id}"
        params = {
            "fields": "status_code,status",
            "access_token": self.access_token,
        }
        return await self._request("GET", url, params=params)

    # ─── Kullanıcı Medyası ─────────────────────────────
    async def get_user_media(self, user_id: str = None, limit: int = 25) -> dict:
        """Kullanıcının medya listesini getirir."""
        uid = user_id or self.account_ig_id
        url = f"{self.base_url}/{uid}/media"
        params = {
            "fields": "id,caption,media_type,media_url,thumbnail_url,"
                      "permalink,timestamp,like_count,comments_count",
            "limit": limit,
            "access_token": self.access_token,
        }
        return await self._request("GET", url, params=params)

    # ─── Mesajlaşma (Conversations API) ────────────────
    async def get_conversations(self, limit: int = 20) -> dict:
        """DM konuşmalarını getirir."""
        # Instagram Messaging API — Facebook Page üzerinden
        url = f"{self.fb_base_url}/{self.account_ig_id}/conversations"
        params = {
            "platform": "instagram",
            "fields": "participants,messages{message,from,created_time}",
            "limit": limit,
            "access_token": self.access_token,
        }
        return await self._request("GET", url, params=params)

    async def get_messages(self, conversation_id: str, limit: int = 50) -> dict:
        """Bir konuşmanın mesajlarını getirir."""
        url = f"{self.fb_base_url}/{conversation_id}/messages"
        params = {
            "fields": "message,from,created_time,attachments",
            "limit": limit,
            "access_token": self.access_token,
        }
        return await self._request("GET", url, params=params)

    async def send_message(self, recipient_id: str, message: str) -> dict:
        """DM mesajı gönderir."""
        url = f"{self.fb_base_url}/{self.account_ig_id}/messages"
        data = {
            "recipient": {"id": recipient_id},
            "message": {"text": message},
            "access_token": self.access_token,
        }
        return await self._request("POST", url, json=data)

    # ─── Kullanıcı Arama ──────────────────────────────
    async def search_user(self, username: str) -> dict:
        """Kullanıcı adına göre ID arar."""
        url = f"{self.base_url}/{self.account_ig_id}"
        params = {
            "fields": f"business_discovery.fields(id,username,name,"
                      f"profile_picture_url,media_count,followers_count)"
                      f"{{username={username}}}",
            "access_token": self.access_token,
        }
        return await self._request("GET", url, params=params)

    async def get_user_media_by_username(
        self, username: str, limit: int = 25, after: str = None
    ) -> dict:
        """Kullanıcı adı ile medya listesi çeker (business discovery)."""
        fields = (
            f"business_discovery.fields("
            f"media.limit({limit})"
            f"{'after(' + after + ')' if after else ''}"
            f"{{id,caption,media_type,media_url,thumbnail_url,"
            f"timestamp,like_count,comments_count,permalink}}"
            f"){{username={username}}}"
        )
        url = f"{self.base_url}/{self.account_ig_id}"
        params = {
            "fields": fields,
            "access_token": self.access_token,
        }
        return await self._request("GET", url, params=params)
