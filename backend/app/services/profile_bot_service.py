# services/profile_bot_service.py — Profil düzenleme ve yönetim servisi
import asyncio
from datetime import datetime
from sqlalchemy.orm import Session
from app.models.account import Account
from app.services.instagram_api import InstagramAPIClient, InstagramAPIError
from app.utils.encryption import decrypt_token
from app.utils.logger import logger


class ProfileTemplate:
    """Profil düzenleme şablonu."""
    def __init__(
        self,
        bio: str | None = None,
        website: str | None = None,
        full_name: str | None = None,
        phone: str | None = None,
        email: str | None = None,
    ):
        self.bio = bio
        self.website = website
        self.full_name = full_name
        self.phone = phone
        self.email = email


class ProfileBotService:
    """Profil bilgilerini yönetme ve gözetleme servisi."""

    async def get_profile_info(self, db: Session, account_id: int) -> dict:
        """Tek bir hesabın güncel profil bilgilerini Instagram'dan çeker."""
        account = db.query(Account).filter(Account.id == account_id).first()
        if not account or not account.access_token_encrypted:
            raise Exception("Hesap bulunamadı veya token eksik")

        token = decrypt_token(account.access_token_encrypted)
        client = InstagramAPIClient(token, account.instagram_id)

        try:
            profile = await client.get_profile()

            # Veritabanını güncelle
            account.username = profile.get("username", account.username)
            account.full_name = profile.get("name", account.full_name)
            account.biography = profile.get("biography", account.biography)
            account.profile_picture_url = profile.get("profile_picture_url", account.profile_picture_url)
            account.followers_count = profile.get("followers_count", account.followers_count)
            account.following_count = profile.get("follows_count", account.following_count)
            account.media_count = profile.get("media_count", account.media_count)
            db.commit()

            return {
                "id": account.id,
                "instagram_id": account.instagram_id,
                "username": profile.get("username"),
                "full_name": profile.get("name"),
                "biography": profile.get("biography"),
                "profile_picture_url": profile.get("profile_picture_url"),
                "followers_count": profile.get("followers_count", 0),
                "following_count": profile.get("follows_count", 0),
                "media_count": profile.get("media_count", 0),
                "website": profile.get("website", ""),
            }

        finally:
            await client.close()

    async def refresh_all_profiles(self, db: Session) -> dict:
        """Tüm hesapların profil bilgilerini yeniler."""
        accounts = db.query(Account).filter(
            Account.access_token_encrypted.isnot(None)
        ).all()

        results = []
        success = 0
        errors = 0

        for account in accounts:
            try:
                profile = await self.get_profile_info(db, account.id)
                results.append({
                    "id": account.id,
                    "username": profile["username"],
                    "status": "success",
                    "followers": profile["followers_count"],
                })
                success += 1
                await asyncio.sleep(0.5)
            except Exception as e:
                results.append({
                    "id": account.id,
                    "username": account.username,
                    "status": "error",
                    "error": str(e),
                })
                errors += 1

        return {
            "total": len(accounts),
            "success": success,
            "errors": errors,
            "results": results,
        }

    async def update_profile_notes(
        self, db: Session, account_id: int,
        bio_note: str | None = None,
        name_note: str | None = None,
        website_note: str | None = None,
    ) -> dict:
        """Profil düzenleme notlarını veritabanında saklar.

        NOT: Instagram Graph API profil düzenlemeyi (bio, isim, fotoğraf)
        DESTEKLEMİYOR. Bu endpointler sadece profil notlarını saklar
        ve kullanıcıya ne değiştirilmesi gerektiğini gösterir.
        """
        account = db.query(Account).filter(Account.id == account_id).first()
        if not account:
            raise Exception("Hesap bulunamadı")

        # Notları biography alanında sakla (meta veri olarak)
        if bio_note is not None:
            account.biography = bio_note
        if name_note is not None:
            account.full_name = name_note

        db.commit()

        return {
            "id": account.id,
            "username": account.username,
            "message": "Profil bilgileri güncellendi",
        }

    async def get_all_profiles_summary(self, db: Session) -> list[dict]:
        """Tüm hesapların profil özetini getirir."""
        accounts = db.query(Account).all()

        return [
            {
                "id": a.id,
                "username": a.username,
                "full_name": a.full_name,
                "biography": a.biography,
                "profile_picture_url": a.profile_picture_url,
                "followers_count": a.followers_count,
                "following_count": a.following_count,
                "media_count": a.media_count,
                "is_active": a.is_active,
                "proxy_url": a.proxy_url,
                "daily_post_limit": a.daily_post_limit,
                "photo_percentage": a.photo_percentage,
                "video_percentage": a.video_percentage,
                "posting_mode": a.posting_mode,
                "auto_publish": a.auto_publish,
                "created_at": a.created_at.isoformat() if a.created_at else None,
            }
            for a in accounts
        ]


profile_bot_service = ProfileBotService()
