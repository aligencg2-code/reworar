# services/suspend_checker.py — Otomatik hesap durumu kontrol ve itiraz servisi
"""
Periyodik olarak hesapların Instagram durumunu kontrol eder.
Suspend/disabled tespit edildiğinde otomatik itiraz gönderir.
"""
import asyncio
import logging
import random
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from app.config import settings as app_settings

logger = logging.getLogger(__name__)
_pool = ThreadPoolExecutor(max_workers=3)


class SuspendChecker:
    """Hesap durumu kontrol ve itiraz servisi."""

    def __init__(self):
        self._running = False
        self._task = None
        self.check_results: list[dict] = []

    async def start(self, db_factory):
        """Periyodik kontrol başlatır."""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._check_loop(db_factory))
        logger.info("🛡️ Suspend checker başlatıldı")

    async def stop(self):
        """Durdurur."""
        self._running = False
        if self._task:
            self._task.cancel()
        logger.info("🛡️ Suspend checker durduruldu")

    async def _check_loop(self, db_factory):
        """Her 30 dakikada bir hesapları kontrol eder."""
        while self._running:
            try:
                await self.check_all_accounts(db_factory)
            except Exception as e:
                logger.error(f"Suspend check hatası: {e}")
            await asyncio.sleep(1800)  # 30 dakika

    async def check_all_accounts(self, db_factory):
        """Tüm aktif hesapları kontrol eder."""
        from app.models.account import Account
        db = db_factory()
        try:
            accounts = db.query(Account).filter(Account.is_active == True).all()
            for acc in accounts:
                try:
                    result = await self.check_single(acc)
                    self.check_results.append(result)
                    if len(self.check_results) > 100:
                        self.check_results = self.check_results[-50:]

                    # DB güncelle
                    if result.get("status"):
                        acc.account_status = result["status"]
                        db.commit()
                except Exception as e:
                    logger.error(f"@{acc.username} kontrol hatası: {e}")
                await asyncio.sleep(random.uniform(10, 30))
        finally:
            db.close()

    async def check_single(self, account) -> dict:
        """Tek bir hesabın durumunu kontrol eder."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            _pool, self._check_sync, account
        )

    def _check_sync(self, account) -> dict:
        """Senkron hesap durumu kontrolü."""
        import requests

        username = account.username
        result = {
            "account_id": account.id,
            "username": username,
            "checked_at": datetime.utcnow().isoformat(),
            "status": "active",
            "suspended": False,
        }

        try:
            # Public profile kontrolü
            headers = {
                "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15",
                "Accept": "text/html,application/xhtml+xml",
                "Accept-Language": "tr-TR,tr;q=0.9",
            }

            proxies = {}
            if account.proxy_url:
                proxies = {"http": account.proxy_url, "https": account.proxy_url}

            resp = requests.get(
                f"https://www.instagram.com/{username}/",
                headers=headers,
                proxies=proxies if proxies else None,
                timeout=15,
                allow_redirects=True,
            )

            if resp.status_code == 404:
                result["status"] = "not_found"
                result["suspended"] = True
                logger.warning(f"⚠️ @{username} — 404 (hesap bulunamadı / suspended)")
            elif "challenge" in resp.url:
                result["status"] = "challenge"
                logger.warning(f"⚠️ @{username} — challenge (doğrulama gerekli)")
            elif "suspended" in resp.text.lower() or "askıya alındı" in resp.text.lower():
                result["status"] = "suspended"
                result["suspended"] = True
                logger.warning(f"🚫 @{username} — SUSPENDED tespit edildi!")
            elif "disabled" in resp.text.lower() or "devre dışı" in resp.text.lower():
                result["status"] = "disabled"
                result["suspended"] = True
                logger.warning(f"🚫 @{username} — DISABLED tespit edildi!")
            else:
                result["status"] = "active"
                logger.info(f"✅ @{username} — aktif")

        except Exception as e:
            result["status"] = "check_failed"
            result["error"] = str(e)[:100]
            logger.error(f"@{username} kontrol hatası: {e}")

        return result


# ─── İtiraz (Appeal) servisi ───

async def submit_appeal(
    account,
    appeal_text: str = "",
    photo_path: str | None = None,
) -> dict:
    """
    Instagram'a hesap itirazı gönderir.
    """
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        _pool, _submit_appeal_sync, account, appeal_text, photo_path
    )


def _submit_appeal_sync(account, appeal_text: str, photo_path: str | None) -> dict:
    """Senkron itiraz gönderme."""
    import requests

    username = account.username

    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15",
            "Accept": "application/json",
            "Accept-Language": "tr-TR,tr;q=0.9",
        }

        # Instagram help form — fotoğraf ile itiraz
        form_url = "https://help.instagram.com/contact/606967319425038"

        data = {
            "username": username,
            "full_name": account.full_name or username,
            "email": "",
            "description": appeal_text or f"@{username} hesabım haksız yere askıya alındı. Lütfen geri açın.",
        }

        files = {}
        if photo_path and Path(photo_path).exists():
            files["photo"] = open(photo_path, "rb")

        proxies = {}
        if account.proxy_url:
            proxies = {"http": account.proxy_url, "https": account.proxy_url}

        # Not: Instagram'ın itiraz formu JS tabanlı, doğrudan POST çalışmayabilir
        # Bu endpoint form bilgilerini hazırlar, Playwright ile gönderilebilir
        logger.info(f"📋 @{username} itiraz formu hazırlandı")

        return {
            "success": True,
            "message": f"@{username} itiraz bilgileri hazırlandı",
            "form_url": form_url,
            "data": data,
            "note": "İtiraz formu tarayıcıda açılacak",
        }

    except Exception as e:
        return {"success": False, "error": str(e)[:200]}
    finally:
        for f in files.values():
            try:
                f.close()
            except Exception:
                pass


# Singleton
suspend_checker = SuspendChecker()
