# services/session_manager.py — Toplu session yönetimi
import asyncio
import json
from datetime import datetime
from sqlalchemy.orm import Session as DBSession

from app.models.account import Account
from app.services.instagram_web import InstagramWebClient, InstagramWebError
from app.services.proxy_pool import proxy_pool
from app.utils.encryption import encrypt_token, decrypt_token
from app.utils.logger import logger


class SessionManager:
    """400-500 hesabın session/cookie yönetimi."""

    def __init__(self):
        self._active_tasks: dict[int, str] = {}  # account_id → durum
        self._progress: dict[str, dict] = {}  # job_id → ilerleme

    async def login_single(self, db: DBSession, account_id: int) -> dict:
        """Tek bir hesaba giriş yapar ve session'ı kaydeder."""
        account = db.query(Account).filter(Account.id == account_id).first()
        if not account:
            raise Exception("Hesap bulunamadı")

        if not account.password_encrypted:
            raise Exception("Şifre tanımlı değil")

        password = decrypt_token(account.password_encrypted)

        # Email bilgileri — checkpoint/2FA otomatik çözme için
        email_addr = None
        email_password = None
        two_factor_seed = account.two_factor_seed

        if account.email_encrypted:
            try:
                email_addr = decrypt_token(account.email_encrypted)
            except Exception:
                pass

        if account.email_password_encrypted:
            try:
                email_password = decrypt_token(account.email_password_encrypted)
            except Exception:
                pass

        # Proxy: hesapta yoksa havuzdan ata
        from app.services.proxy_pool import normalize_proxy
        proxy = normalize_proxy(account.proxy_url)

        if not proxy:
            proxy = proxy_pool.get_next()
            if proxy:
                account.proxy_url = proxy
                logger.info(f"  🌐 @{account.username} → proxy atandı: {proxy}")

        # Login proxy ile yapılır (kullanıcının IP'si karalistede)
        client = InstagramWebClient(proxy=proxy)

        try:
            result = await client.login(
                account.username, password,
                email_addr=email_addr,
                email_password=email_password,
                two_factor_seed=two_factor_seed,
                account_id=account_id,
            )

            if result.get("success"):
                # Cookie'leri ve instagrapi settings'i şifreli kaydet
                session_data = {
                    "cookies": result.get("cookies", {}),
                    "settings": result.get("settings", {}),
                }
                account.session_cookies = encrypt_token(json.dumps(session_data))
                account.session_valid = True
                account.last_login_at = datetime.utcnow()
                account.instagram_id = result.get("user_id", account.instagram_id or "")

                # User-Agent kalıcılığı — ilk login'de UA kaydet, sonra hep aynı kalacak
                if not account.user_agent:
                    ua = result.get("settings", {}).get("user_agent", "")
                    if ua:
                        account.user_agent = ua
                        logger.info(f"  📱 @{account.username} UA kaydedildi")

                db.commit()

                return {
                    "success": True,
                    "username": account.username,
                    "message": "Giriş başarılı",
                }
            else:
                account.session_valid = False
                account.status_message = result.get("message", "Giriş başarısız")
                db.commit()

                return {
                    "success": False,
                    "username": account.username,
                    "message": result.get("message"),
                    "checkpoint": result.get("checkpoint", False),
                    "two_factor": result.get("two_factor", False),
                    "needs_code": result.get("needs_code", False),
                }

        except Exception as e:
            account.session_valid = False
            account.status_message = str(e)
            db.commit()
            return {
                "success": False,
                "username": account.username,
                "message": str(e),
            }

    async def bulk_login(self, db: DBSession, account_ids: list[int] | None = None, job_id: str = "") -> dict:
        """Toplu giriş — sıralı, her hesap arasında bekleme ile."""
        if account_ids:
            accounts = db.query(Account).filter(Account.id.in_(account_ids)).all()
        else:
            accounts = db.query(Account).filter(
                Account.password_encrypted.isnot(None)
            ).all()

        total = len(accounts)
        success = 0
        errors = 0
        results = []

        self._progress[job_id] = {
            "total": total, "done": 0,
            "success": 0, "errors": 0,
            "current": "", "status": "running",
        }

        for i, account in enumerate(accounts):
            self._progress[job_id]["current"] = f"@{account.username}"
            self._progress[job_id]["done"] = i

            try:
                result = await self.login_single(db, account.id)
                if result["success"]:
                    success += 1
                else:
                    errors += 1
                results.append(result)
            except Exception as e:
                errors += 1
                results.append({
                    "success": False,
                    "username": account.username,
                    "message": str(e),
                })

            # Hesaplar arası bekleme (3-8 sn)
            if i < total - 1:
                import random
                await asyncio.sleep(random.uniform(3.0, 8.0))

            self._progress[job_id]["success"] = success
            self._progress[job_id]["errors"] = errors

        self._progress[job_id]["done"] = total
        self._progress[job_id]["status"] = "completed"

        return {
            "total": total,
            "success": success,
            "errors": errors,
            "results": results,
        }

    async def bulk_login_background(self, account_ids: list[int] | None = None, job_id: str = "") -> dict:
        """Toplu giriş — BackgroundTask için kendi DB session'ını oluşturur."""
        from app.database import SessionLocal

        db = SessionLocal()
        try:
            if account_ids:
                accounts = db.query(Account).filter(Account.id.in_(account_ids)).all()
            else:
                accounts = db.query(Account).filter(
                    Account.password_encrypted.isnot(None)
                ).all()

            # Hesap ID'lerini al (session bağımsız)
            account_id_list = [(a.id, a.username) for a in accounts]
        finally:
            db.close()

        total = len(account_id_list)
        success = 0
        errors = 0
        challenges = 0
        results = []
        challenge_accounts = []  # [{id, username, message}]

        self._progress[job_id] = {
            "total": total, "done": 0,
            "success": 0, "errors": 0, "challenges": 0,
            "challenge_accounts": [],
            "current": "", "status": "running",
        }

        for i, (acc_id, acc_username) in enumerate(account_id_list):
            self._progress[job_id]["current"] = f"@{acc_username}"
            self._progress[job_id]["done"] = i

            # Her login için yeni DB session
            db = SessionLocal()
            try:
                result = await self.login_single(db, acc_id)
                if result.get("success"):
                    success += 1
                elif result.get("needs_code"):
                    # Challenge — ayrı say, hata değil
                    challenges += 1
                    challenge_accounts.append({
                        "id": acc_id,
                        "username": acc_username,
                        "message": result.get("message", "Doğrulama kodu gerekiyor"),
                    })
                else:
                    errors += 1
                results.append(result)
            except Exception as e:
                errors += 1
                results.append({
                    "success": False,
                    "username": acc_username,
                    "message": str(e),
                })
            finally:
                db.close()

            # Hesaplar arası bekleme (2-5 sn)
            if i < total - 1:
                import random
                await asyncio.sleep(random.uniform(2.0, 5.0))

            self._progress[job_id]["success"] = success
            self._progress[job_id]["errors"] = errors
            self._progress[job_id]["challenges"] = challenges
            self._progress[job_id]["challenge_accounts"] = challenge_accounts

        self._progress[job_id]["done"] = total
        self._progress[job_id]["status"] = "completed"

        return {
            "total": total,
            "success": success,
            "errors": errors,
            "challenges": challenges,
            "challenge_accounts": challenge_accounts,
            "results": results,
        }

    async def validate_all_sessions(self, db: DBSession) -> dict:
        """Tüm session'ları kontrol eder."""
        accounts = db.query(Account).filter(
            Account.session_cookies.isnot(None)
        ).all()

        valid = 0
        invalid = 0
        results = []

        for account in accounts:
            try:
                cookies = json.loads(decrypt_token(account.session_cookies))
                from app.services.proxy_pool import normalize_proxy
                client = InstagramWebClient(proxy=normalize_proxy(account.proxy_url))
                is_valid = await client.login_with_cookies(cookies)

                account.session_valid = is_valid
                if is_valid:
                    valid += 1
                else:
                    invalid += 1

                results.append({
                    "username": account.username,
                    "valid": is_valid,
                })

                await asyncio.sleep(1.0)

            except Exception as e:
                invalid += 1
                account.session_valid = False
                results.append({
                    "username": account.username,
                    "valid": False,
                    "error": str(e),
                })

        db.commit()
        return {"valid": valid, "invalid": invalid, "results": results}

    def get_client_for_account(self, db: DBSession, account_id: int) -> InstagramWebClient:
        """Hesap için hazır bir web client döndürür."""
        account = db.query(Account).filter(Account.id == account_id).first()
        if not account:
            raise Exception("Hesap bulunamadı")

        client = InstagramWebClient(proxy=account.proxy_url)

        if account.session_cookies:
            try:
                cookies = json.loads(decrypt_token(account.session_cookies))
                client.cookies = cookies
                client.csrf_token = cookies.get("csrftoken", "")
                client.user_id = cookies.get("ds_user_id", "")
                client.username = account.username
            except Exception:
                raise Exception("Session çözümlenemedi, yeniden giriş gerekli")
        else:
            raise Exception("Session yok, önce giriş yapılmalı")

        return client

    def get_progress(self, job_id: str) -> dict:
        """Toplu giriş ilerleme durumunu döndürür."""
        return self._progress.get(job_id, {"status": "not_found"})

    def _is_valid_proxy(self, value: str) -> bool:
        """Proxy URL'si geçerli mi kontrol eder."""
        if not value:
            return False
        valid_schemes = ("http://", "https://", "socks4://", "socks5://")
        return value.lower().startswith(valid_schemes)

    async def import_accounts(
        self, db: DBSession, accounts_text: str, default_proxy: str | None = None
    ) -> dict:
        """
        Toplu hesap import.
        Desteklenen formatlar:
          username:password
          username:password:email
          username:password:email:email_password
          username:password:email:email_password:2fa_seed
        """
        from app.utils.encryption import encrypt_token

        lines = [l.strip() for l in accounts_text.strip().split("\n") if l.strip()]
        added = 0
        updated = 0
        errors = []

        for line in lines:
            parts = line.split(":")
            if len(parts) < 2:
                errors.append(f"Geçersiz format: {line}")
                continue

            username = parts[0].strip().lstrip("@")
            password = parts[1].strip()

            # 5 alanlı format: username:password:email:email_password:2fa_seed
            email_addr = parts[2].strip() if len(parts) >= 3 else None
            email_pass = parts[3].strip() if len(parts) >= 4 else None
            tfa_seed = parts[4].strip() if len(parts) >= 5 else None

            # Email valid mi kontrol
            if email_addr and "@" not in email_addr:
                # 3. alan email değilse proxy olabilir (eski format uyumu)
                if self._is_valid_proxy(email_addr):
                    # Eski format: username:password:proxy
                    proxy = email_addr
                    email_addr = None
                    email_pass = None
                    tfa_seed = None
                else:
                    # email olarak değerlendir
                    pass

            # Proxy havuzundan veya default'dan al
            proxy = default_proxy
            if not proxy:
                proxy = proxy_pool.get_next()

            # Mevcut hesap kontrolü
            existing = db.query(Account).filter(Account.username == username).first()
            if existing:
                # Şifre ve bilgileri güncelle
                existing.password_encrypted = encrypt_token(password)
                if email_addr:
                    existing.email_encrypted = encrypt_token(email_addr)
                if email_pass:
                    existing.email_password_encrypted = encrypt_token(email_pass)
                if tfa_seed:
                    existing.two_factor_seed = tfa_seed
                if proxy and not existing.proxy_url:
                    existing.proxy_url = proxy
                updated += 1
                continue

            account = Account(
                username=username,
                instagram_id=f"pending_{username}",
                password_encrypted=encrypt_token(password),
                email_encrypted=encrypt_token(email_addr) if email_addr else None,
                email_password_encrypted=encrypt_token(email_pass) if email_pass else None,
                two_factor_seed=tfa_seed,
                proxy_url=proxy,
                login_method="password",
                session_valid=False,
                is_active=True,
            )
            db.add(account)
            added += 1

        db.commit()
        return {
            "added": added,
            "updated": updated,
            "errors": errors,
            "total_lines": len(lines),
        }


session_manager = SessionManager()
