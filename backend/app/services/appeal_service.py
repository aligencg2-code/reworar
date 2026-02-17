# services/appeal_service.py — Sorunlu hesap yönetimi ve toplu appeal servisi
import asyncio
from datetime import datetime
from sqlalchemy.orm import Session
from app.models.account import Account, AccountStatus, AppealStatus
from app.services.instagram_api import InstagramAPIClient, InstagramAPIError
from app.utils.encryption import decrypt_token
from app.utils.logger import logger


class AppealJob:
    """Toplu appeal işi durumu."""
    def __init__(self):
        self.total = 0
        self.checked = 0
        self.problematic = 0
        self.appeals_sent = 0
        self.errors: list[str] = []
        self.results: list[dict] = []
        self.status = "running"  # running, completed, error


class AppealService:
    """Sorunlu hesap tespit ve toplu appeal yönetimi."""

    def __init__(self):
        self._current_job: AppealJob | None = None

    def get_current_job(self) -> AppealJob | None:
        return self._current_job

    async def check_single_account(self, db: Session, account: Account) -> dict:
        """Tek bir hesabın durumunu kontrol eder."""
        result = {
            "id": account.id,
            "username": account.username,
            "previous_status": account.account_status,
            "new_status": account.account_status,
            "message": "",
            "healthy": True,
        }

        if not account.access_token_encrypted:
            result["new_status"] = AccountStatus.UNKNOWN.value
            result["message"] = "Token eksik — hesap bağlanmamış"
            result["healthy"] = False
            account.account_status = AccountStatus.UNKNOWN.value
            account.status_message = result["message"]
            account.last_checked_at = datetime.utcnow()
            db.commit()
            return result

        token = decrypt_token(account.access_token_encrypted)
        client = InstagramAPIClient(token, account.instagram_id)

        try:
            # Profil bilgisi çekmeyi dene — başarısız olursa sorun var
            profile = await client.get_profile()

            # Token çalışıyor demek ki hesap aktif
            account.account_status = AccountStatus.ACTIVE.value
            account.status_message = None
            account.last_checked_at = datetime.utcnow()

            # Profil bilgilerini güncelle
            account.username = profile.get("username", account.username)
            account.full_name = profile.get("name", account.full_name)
            account.followers_count = profile.get("followers_count", account.followers_count)
            account.following_count = profile.get("follows_count", account.following_count)
            account.media_count = profile.get("media_count", account.media_count)
            if profile.get("profile_picture_url"):
                account.profile_picture_url = profile["profile_picture_url"]

            result["new_status"] = AccountStatus.ACTIVE.value
            result["message"] = "Hesap sağlıklı ✓"
            result["healthy"] = True

            db.commit()

        except InstagramAPIError as e:
            result["healthy"] = False
            error_code = e.code
            error_subcode = e.subcode

            # Instagram hata kodlarına göre durum belirle
            if error_code == 190:
                # Token geçersiz
                account.account_status = AccountStatus.DISABLED.value
                result["new_status"] = AccountStatus.DISABLED.value
                result["message"] = f"Token geçersiz: {e.message}"
            elif error_code == 10 or error_code == 100:
                # Yetki hatası veya parametre hatası
                account.account_status = AccountStatus.RESTRICTED.value
                result["new_status"] = AccountStatus.RESTRICTED.value
                result["message"] = f"API erişimi kısıtlandı: {e.message}"
            elif error_code == 4 or error_code == 17:
                # Rate limit
                account.account_status = AccountStatus.ACTION_BLOCKED.value
                result["new_status"] = AccountStatus.ACTION_BLOCKED.value
                result["message"] = f"İşlem engeli: {e.message}"
            elif error_code == 368:
                # Checkpoint gerekli
                account.account_status = AccountStatus.CHECKPOINT.value
                result["new_status"] = AccountStatus.CHECKPOINT.value
                result["message"] = f"Doğrulama gerekli: {e.message}"
            else:
                account.account_status = AccountStatus.RESTRICTED.value
                result["new_status"] = AccountStatus.RESTRICTED.value
                result["message"] = f"Hata ({error_code}): {e.message}"

            account.status_message = result["message"]
            account.last_checked_at = datetime.utcnow()
            db.commit()

        except Exception as e:
            result["healthy"] = False
            account.account_status = AccountStatus.UNKNOWN.value
            result["new_status"] = AccountStatus.UNKNOWN.value
            result["message"] = f"Bağlantı hatası: {str(e)}"
            account.status_message = result["message"]
            account.last_checked_at = datetime.utcnow()
            db.commit()

        finally:
            await client.close()

        return result

    async def check_all_accounts(self, db: Session) -> AppealJob:
        """Tüm hesapları kontrol eder."""
        job = AppealJob()
        self._current_job = job

        accounts = db.query(Account).all()
        job.total = len(accounts)

        for account in accounts:
            try:
                result = await self.check_single_account(db, account)
                job.results.append(result)
                job.checked += 1
                if not result["healthy"]:
                    job.problematic += 1

                # Her hesap arası kısa bekleme (rate limit koruması)
                await asyncio.sleep(0.5)

            except Exception as e:
                job.errors.append(f"@{account.username}: {str(e)}")
                job.checked += 1

        job.status = "completed"
        logger.info(
            f"Hesap kontrolü tamamlandı: {job.checked}/{job.total} kontrol, "
            f"{job.problematic} sorunlu"
        )
        return job

    async def submit_bulk_appeal(
        self, db: Session, account_ids: list[int] | None = None
    ) -> dict:
        """Toplu appeal gönderir — sorunlu hesaplar için itiraz bildirimi."""
        if account_ids:
            accounts = db.query(Account).filter(
                Account.id.in_(account_ids)
            ).all()
        else:
            # Tüm sorunlu hesaplar
            accounts = db.query(Account).filter(
                Account.account_status.in_([
                    AccountStatus.RESTRICTED.value,
                    AccountStatus.ACTION_BLOCKED.value,
                    AccountStatus.DISABLED.value,
                    AccountStatus.CHECKPOINT.value,
                ])
            ).all()

        results = []
        for account in accounts:
            # Appeal durumunu güncelle
            account.appeal_status = AppealStatus.SUBMITTED.value
            account.last_appeal_at = datetime.utcnow()
            results.append({
                "id": account.id,
                "username": account.username,
                "status": account.account_status,
                "appeal": "submitted",
                "message": f"@{account.username} için itiraz kaydedildi",
            })

        db.commit()

        logger.info(f"Toplu appeal: {len(results)} hesap için itiraz kaydedildi")

        return {
            "total": len(results),
            "results": results,
        }

    def get_account_summary(self, db: Session) -> dict:
        """Tüm hesapların durum özetini getirir."""
        accounts = db.query(Account).all()

        summary = {
            "total": len(accounts),
            "active": 0,
            "restricted": 0,
            "action_blocked": 0,
            "disabled": 0,
            "checkpoint": 0,
            "unknown": 0,
            "never_checked": 0,
            "accounts": [],
        }

        for acc in accounts:
            status = acc.account_status or AccountStatus.UNKNOWN.value
            if status == AccountStatus.ACTIVE.value:
                summary["active"] += 1
            elif status == AccountStatus.RESTRICTED.value:
                summary["restricted"] += 1
            elif status == AccountStatus.ACTION_BLOCKED.value:
                summary["action_blocked"] += 1
            elif status == AccountStatus.DISABLED.value:
                summary["disabled"] += 1
            elif status == AccountStatus.CHECKPOINT.value:
                summary["checkpoint"] += 1
            else:
                summary["unknown"] += 1

            if not acc.last_checked_at:
                summary["never_checked"] += 1

            summary["accounts"].append({
                "id": acc.id,
                "username": acc.username,
                "full_name": acc.full_name,
                "profile_picture_url": acc.profile_picture_url,
                "followers_count": acc.followers_count,
                "account_status": status,
                "appeal_status": acc.appeal_status or AppealStatus.NONE.value,
                "status_message": acc.status_message,
                "last_checked_at": acc.last_checked_at.isoformat() if acc.last_checked_at else None,
                "last_appeal_at": acc.last_appeal_at.isoformat() if acc.last_appeal_at else None,
                "is_active": acc.is_active,
            })

        return summary


appeal_service = AppealService()
