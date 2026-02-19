# services/instagram_web.py — Instagram Mobile API (instagrapi tabanlı)
import json
import time
import asyncio
import random
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from typing import Optional

from app.utils.logger import logger

# Login işlemleri için ayrı thread pool (ana server thread'lerini bloklamaz)
_login_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="ig-login")

# File-based logging (terminal logları scheduler sorguları ile dolup taşıyor)
import logging as _logging
from app.config import settings as _app_settings
_app_settings.LOG_DIR.mkdir(parents=True, exist_ok=True)
_fh = _logging.FileHandler(_app_settings.LOG_DIR / "login_debug.log", encoding="utf-8")
_fh.setFormatter(_logging.Formatter("%(asctime)s %(message)s"))
logger.addHandler(_fh)

# ─── Sabitler ────────────────────────────────────────────────

SESSIONS_DIR = _app_settings.SESSIONS_DIR
SESSIONS_DIR.mkdir(parents=True, exist_ok=True)

# In-memory challenge context store: {account_id: {client, challenge_context, username, ...}}
_challenge_store: dict[int, dict] = {}


class ChallengeCodeNeeded(Exception):
    """IMAP ile kod okunamadı — kullanıcıdan kod istenmeli."""
    pass


class InstagramWebError(Exception):
    """Instagram API hata sınıfı."""
    def __init__(self, message: str, status_code: int = 0):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class InstagramWebClient:
    """
    Instagram Mobile API istemcisi — instagrapi tabanlı.
    Session kalıcılığı, proxy, 2FA ve checkpoint desteği.
    """

    def __init__(self, proxy: str | None = None):
        self.proxy = proxy
        self.cookies: dict = {}
        self.csrf_token: str = ""
        self.user_id: str = ""
        self.username: str = ""
        self._cl = None  # instagrapi.Client

    def _get_instagrapi_client(self):
        """instagrapi Client oluşturur."""
        from instagrapi import Client

        cl = Client()

        # Proxy ayarla
        if self.proxy:
            cl.set_proxy(self.proxy)

        # Türkçe dil, gerçekçi ayarlar
        cl.set_locale("tr_TR")
        cl.set_timezone_offset(3 * 3600)  # UTC+3

        # Gerçekçi gecikme ayarları
        cl.delay_range = [1, 3]

        return cl

    def _session_path(self, username: str) -> Path:
        """Session dosya yolu."""
        return SESSIONS_DIR / f"{username}.json"

    # ──────────────────────────── LOGIN ────────────────────────────

    async def login(
        self, username: str, password: str,
        email_addr: str | None = None,
        email_password: str | None = None,
        two_factor_seed: str | None = None,
        account_id: int | None = None,
    ) -> dict:
        """
        Instagram'a giriş yapar (instagrapi Mobile API).
        Checkpoint ve 2FA otomatik çözülür.
        """
        self.username = username
        self._account_id = account_id
        loop = asyncio.get_event_loop()

        try:
            result = await loop.run_in_executor(
                _login_executor,
                self._login_sync,
                username, password, email_addr, email_password, two_factor_seed,
            )
            return result
        except Exception as e:
            logger.error(f"  ❌ @{username} login hatası: {e}")
            return {"success": False, "message": str(e)[:200]}

    def _retry_with_same_proxy(
        self, username, password, email_addr, email_password, two_factor_seed,
        challenge_code_handler, _apply_challenge_monkeypatch, _attempt_login,
    ) -> dict:
        """Aynı proxy ile tekrar dener — IP ASLA değişmez."""
        from instagrapi import Client
        from instagrapi.exceptions import BadPassword

        logger.info(f"  🔄 @{username} AYNI PROXY ile tekrar deneniyor... (proxy={self.proxy or 'YOK'})")

        cl_retry = Client()
        cl_retry.set_locale("tr_TR")
        cl_retry.set_timezone_offset(3 * 3600)
        cl_retry.delay_range = [1, 3]
        # AYNI PROXY'yi kullan — IP değişmemeli
        if self.proxy:
            cl_retry.set_proxy(self.proxy)

        cl_retry.challenge_code_handler = challenge_code_handler
        cl_retry.change_password_handler = lambda u: None
        _apply_challenge_monkeypatch(cl_retry)

        if two_factor_seed:
            cl_retry.totp_seed = two_factor_seed

        try:
            verification_code = ""
            if two_factor_seed:
                try:
                    verification_code = self._generate_totp(two_factor_seed)
                except Exception:
                    pass
            cl_retry.login(username, password, verification_code=verification_code)
            self._save_session(cl_retry, username)
            logger.info(f"  ✅ @{username} retry giriş başarılı!")
            return self._build_success(cl_retry, username)
        except ChallengeCodeNeeded:
            logger.info(f"  📧 @{username} retry challenge — kod bekleniyor")
            account_id = getattr(self, '_account_id', None)
            if account_id:
                api_path = getattr(cl_retry, '_saved_challenge_url', '') or ''
                _challenge_store[account_id] = {
                    "client": cl_retry, "username": username, "password": password,
                    "email_addr": email_addr, "timestamp": time.time(),
                    "type": "native", "api_path": api_path, "proxy": self.proxy,
                }
                logger.info(f"  💾 Retry challenge state kaydedildi (api_path={api_path})")
            masked_email = email_addr[:3] + "***" + email_addr[email_addr.index("@"):] if email_addr and "@" in email_addr else "kayıtlı email"
            return {
                "success": False, "checkpoint": True, "needs_code": True,
                "message": f"Instagram {masked_email} adresine doğrulama kodu gönderdi. Lütfen emailinizi kontrol edip kodu girin.",
            }
        except BadPassword:
            logger.error(f"  ❌ @{username} şifre kesinlikle hatalı")
            return {"success": False, "message": "Şifre hatalı — şifreyi kontrol edin"}
        except Exception as e2:
            logger.error(f"  ❌ @{username} retry hatası: {e2}")
            return {"success": False, "message": f"Giriş hatası: {str(e2)[:150]}"}

    def _login_sync(
        self, username: str, password: str,
        email_addr: str | None, email_password: str | None,
        two_factor_seed: str | None,
    ) -> dict:
        """Senkron login — thread pool'da çalışır."""
        from instagrapi import Client
        from instagrapi.exceptions import (
            LoginRequired,
            TwoFactorRequired,
            ChallengeRequired,
            ChallengeUnknownStep,
            BadPassword,
            RecaptchaChallengeForm,
            FeedbackRequired,
            PleaseWaitFewMinutes,
            ClientError,
            ProxyAddressIsBlocked,
            SentryBlock,
            BadCredentials,
        )

        cl = self._get_instagrapi_client()
        session_file = self._session_path(username)

        # 1) Challenge handler — her zaman set et (session login'de de gerekebilir)
        def challenge_code_handler(username_arg, choice):
            """Instagram checkpoint kodu handler.
            IMAP ile kod okumayı tek seferde dener, başarısızsa ChallengeCodeNeeded raise eder.
            """
            if email_addr and email_password:
                logger.info(f"  📧 @{username} checkpoint — email'den kod okunuyor...")
                try:
                    from app.services.email_service import EmailCodeReader
                    reader = EmailCodeReader(email_addr, email_password)
                    # Tek seferde dene (max_retries=1) — Gmail App Password yoksa zaten başarısız olacak
                    code = reader.fetch_instagram_code(
                        max_age_minutes=5,
                        max_retries=1,
                        retry_delay=5,
                    )
                    if code:
                        logger.info(f"  📧 Kod bulundu: {code}")
                        return code
                except Exception as imap_err:
                    logger.warning(f"  ⚠️ IMAP hatası: {imap_err}")

            # Otomatik okuma başarısız — kullanıcıdan kod iste
            logger.info(f"  📧 @{username} Otomatik kod okuma başarısız — kullanıcıdan kod bekleniyor")
            raise ChallengeCodeNeeded(f"Email'den kod okunamadı — manuel giriş gerekli ({email_addr})")

        cl.challenge_code_handler = challenge_code_handler
        cl.change_password_handler = lambda u: None  # Şifre değişikliği isterse engelle

        # 2) challenge_resolve'u monkeypatch et — challenge URL'yi yakala
        def _apply_challenge_monkeypatch(client):
            _orig = client.challenge_resolve
            def _patched(last_json):
                api_path = last_json.get("challenge", {}).get("api_path", "")
                client._saved_challenge_url = api_path
                logger.info(f"  🔗 Challenge URL yakalandı: {api_path}")
                return _orig(last_json)
            client.challenge_resolve = _patched

        _apply_challenge_monkeypatch(cl)

        # 3) Mevcut session varsa yükle — LOGIN ÇAĞIRMADAN session ile devam et
        if session_file.exists():
            try:
                logger.info(f"  📂 @{username} kayıtlı session yükleniyor...")
                cl.load_settings(session_file)
                
                # Session geçerli mi test et — login() çağırmadan direkt API isteği
                try:
                    cl.account_info()
                    self._save_session(cl, username)
                    logger.info(f"  ✅ @{username} session ile giriş başarılı (login bypass)")
                    return self._build_success(cl, username)
                except LoginRequired:
                    logger.info(f"  ⚠️ @{username} session expired, yeniden giriş gerekiyor...")
                except Exception as sess_err:
                    logger.info(f"  ⚠️ @{username} session test başarısız: {sess_err}")
                    
                # Session geçersiz — tamamen YENİ client oluştur (fresh login)
                cl = self._get_instagrapi_client()
                cl.challenge_code_handler = challenge_code_handler
                cl.change_password_handler = lambda u: None
                _apply_challenge_monkeypatch(cl)
                
            except ChallengeCodeNeeded:
                logger.info(f"  📧 @{username} session login challenge — kullanıcıdan kod bekleniyor")
                account_id = getattr(self, '_account_id', None)
                if account_id:
                    api_path = getattr(cl, '_saved_challenge_url', '') or ''
                    _challenge_store[account_id] = {
                        "client": cl, "username": username, "password": password,
                        "email_addr": email_addr, "timestamp": time.time(),
                        "type": "native", "api_path": api_path, "proxy": self.proxy,
                    }
                    logger.info(f"  💾 Session challenge state kaydedildi (api_path={api_path})")
                masked_email = email_addr[:3] + "***" + email_addr[email_addr.index("@"):] if email_addr and "@" in email_addr else "kayıtlı email"
                return {
                    "success": False, "checkpoint": True, "needs_code": True,
                    "message": f"Instagram {masked_email} adresine doğrulama kodu gönderdi. Lütfen emailinizi kontrol edip kodu girin.",
                }
            except Exception as e:
                logger.info(f"  ⚠️ @{username} session yüklenemedi: {e}")
                cl = self._get_instagrapi_client()
                cl.challenge_code_handler = challenge_code_handler
                cl.change_password_handler = lambda u: None
                _apply_challenge_monkeypatch(cl)

        # 4) TOTP 2FA seed varsa set et
        if two_factor_seed:
            cl.totp_seed = two_factor_seed

        # ────────── 5) RAW HTTP LOGIN (birincil yöntem) ──────────
        # instagrapi login BadPassword veriyor ama raw HTTP çalışıyor
        logger.info(f"🔑 @{username} RAW HTTP login deneniyor... (proxy={self.proxy or 'YOK'})")
        raw_result = self._raw_http_login(username, password, two_factor_seed)
        
        if raw_result and raw_result.get("success"):
            # Raw HTTP ile giriş başarılı
            user_id = raw_result.get("user_id", "")
            raw_cookies = raw_result.get("raw_session_cookies", {})
            logger.info(f"  ✅ @{username} RAW HTTP giriş başarılı! user_id={user_id}")
            
            # Session JSON dosyası oluştur (gelecekte session reuse için)
            try:
                import json as _json
                session_data = {
                    "user_id": user_id,
                    "username": username,
                    "authorization_data": {
                        "ds_user_id": str(user_id),
                        "sessionid": raw_cookies.get("sessionid", ""),
                        "csrftoken": raw_cookies.get("csrftoken", ""),
                        "mid": raw_cookies.get("mid", ""),
                    },
                    "cookies": {k: v for k, v in raw_cookies.items()},
                    "device_settings": cl.get_settings().get("device_settings", {}),
                    "user_agent": cl.get_settings().get("user_agent", ""),
                }
                session_file = self._session_path(username)
                session_file.write_text(_json.dumps(session_data, indent=2))
                logger.info(f"  💾 @{username} session dosyası kaydedildi ({session_file})")
            except Exception as se:
                logger.warning(f"  ⚠️ Session kaydetme hatası: {se}")
            
            # Cookie bilgilerini topla
            cookies = {k: v for k, v in raw_cookies.items()}
            
            return {
                "success": True,
                "user_id": str(user_id),
                "cookies": cookies,
                "message": "Giriş başarılı",
            }
        elif raw_result and raw_result.get("needs_code"):
            # Challenge/2FA gerekiyor
            return raw_result
        elif raw_result and raw_result.get("invalid_credentials"):
            # Şifre kesinlikle yanlış
            logger.error(f"  ❌ @{username} RAW HTTP: şifre kesinlikle yanlış")
            return {"success": False, "message": "Şifre hatalı — lütfen şifreyi kontrol edin"}

        # RAW HTTP başarısız veya belirsiz — instagrapi ile dene
        logger.info(f"  🔄 @{username} RAW HTTP belirsiz, instagrapi ile deneniyor...")

        # 6) Giriş dene — verification_code dış scope'da tanımla (BadPassword retry'de de lazım)
        verification_code = ""
        if two_factor_seed:
            try:
                verification_code = self._generate_totp(two_factor_seed)
                logger.info(f"  🔐 TOTP kodu üretildi: {verification_code}")
            except Exception as te:
                logger.warning(f"  ⚠️ TOTP üretim hatası: {te}")

        def _attempt_login(client):
            """Tek bir login denemesi yapar."""
            client.login(username, password, verification_code=verification_code)
            return client

        try:
            logger.info(f"🔑 @{username} instagrapi giriş deneniyor... (proxy={self.proxy or 'YOK'})")
            cl = _attempt_login(cl)

            self._save_session(cl, username)
            logger.info(f"  ✅ @{username} giriş başarılı!")
            return self._build_success(cl, username)

        except BadPassword as e:
            error_msg = str(e)
            logger.warning(f"  🔒 @{username} BadPassword: {error_msg[:200]}")
            
            # Instagram IP bloğunu BadPassword olarak döner
            # AYNI PROXY ile tekrar dene — IP ASLA değişmemeli
            logger.info(f"  🔄 @{username} AYNI PROXY ile tekrar deneniyor... ({self.proxy})")
            try:
                from instagrapi import Client as InstaClient
                cl2 = InstaClient()
                cl2.set_locale("tr_TR")
                cl2.set_timezone_offset(3 * 3600)
                cl2.delay_range = [1, 3]
                if self.proxy:
                    cl2.set_proxy(self.proxy)
                cl2.challenge_code_handler = challenge_code_handler
                cl2.change_password_handler = lambda u: None
                
                # Monkeypatch: challenge URL'yi yakala
                _orig2 = cl2.challenge_resolve
                def _patched2(last_json):
                    api_path = last_json.get("challenge", {}).get("api_path", "")
                    cl2._saved_challenge_url = api_path
                    logger.info(f"  🔗 Retry challenge URL: {api_path}")
                    return _orig2(last_json)
                cl2.challenge_resolve = _patched2
                
                cl2.login(username, password, verification_code=verification_code, relogin=True)
                self._save_session(cl2, username)
                logger.info(f"  ✅ @{username} aynı proxy ile giriş başarılı!")
                return self._build_success(cl2, username)
            except ChallengeCodeNeeded:
                logger.info(f"  📧 @{username} retry challenge — kullanıcıdan kod bekleniyor")
                account_id = getattr(self, '_account_id', None)
                if account_id:
                    api_path = getattr(cl2, '_saved_challenge_url', '') or ''
                    _challenge_store[account_id] = {
                        "client": cl2,
                        "username": username,
                        "password": password,
                        "email_addr": email_addr,
                        "timestamp": time.time(),
                        "type": "native",
                        "api_path": api_path,
                        "proxy": self.proxy,
                    }
                    logger.info(f"  💾 Retry challenge state kaydedildi (api_path={api_path})")
                masked_email = email_addr[:3] + "***" + email_addr[email_addr.index("@"):] if email_addr and "@" in email_addr else "kayıtlı email"
                return {
                    "success": False, "checkpoint": True, "needs_code": True,
                    "message": f"Instagram {masked_email} adresine doğrulama kodu gönderdi. Lütfen emailinizi kontrol edip kodu girin.",
                }
            except BadPassword:
                logger.error(f"  ❌ @{username} şifre kesinlikle hatalı")
                return {"success": False, "message": "Şifre hatalı — lütfen şifreyi kontrol edin"}
            except Exception as ce:
                logger.error(f"  ❌ Retry hatası: {ce}")
                return {"success": False, "checkpoint": True, "needs_code": True, "message": f"Doğrulama gerekiyor: {str(ce)[:120]}"}

        except TwoFactorRequired:
            logger.warning(f"  🔐 @{username} 2FA gerekli (login sırasında)")
            # TOTP seed ile tekrar dene
            if two_factor_seed:
                try:
                    code = self._generate_totp(two_factor_seed)
                    logger.info(f"  🔐 TOTP tekrar: {code}")
                    cl.login(username, password, verification_code=code)
                    self._save_session(cl, username)
                    return self._build_success(cl, username)
                except Exception as e2:
                    logger.error(f"  ❌ TOTP retry hatası: {e2}")
                    return {"success": False, "two_factor": True, "message": f"TOTP başarısız: {str(e2)[:100]}"}

            # Email ile dene
            if email_addr and email_password:
                try:
                    from app.services.email_service import EmailCodeReader
                    reader = EmailCodeReader(email_addr, email_password)
                    code = reader.fetch_instagram_code(max_retries=6, retry_delay=10)
                    if code:
                        cl.login(username, password, verification_code=code)
                        self._save_session(cl, username)
                        return self._build_success(cl, username)
                except Exception as e3:
                    logger.error(f"  ❌ Email 2FA hatası: {e3}")

            return {"success": False, "two_factor": True, "message": "2FA doğrulaması başarısız — kod alınamadı"}

        except ChallengeCodeNeeded as ccn:
            # IMAP ile kod okunamadı — kullanıcıdan manuel kod girişi iste
            logger.info(f"  📧 @{username} challenge — kullanıcıdan kod bekleniyor")
            account_id = getattr(self, '_account_id', None)
            if account_id:
                # Challenge URL'yi monkeypatch'ten al (last_json artık değişmiş durumda)
                api_path = getattr(cl, '_saved_challenge_url', '') or ''
                step_name = (getattr(cl, 'last_json', {}) or {}).get("step_name", "")
                
                _challenge_store[account_id] = {
                    "client": cl,
                    "username": username,
                    "password": password,
                    "email_addr": email_addr,
                    "timestamp": time.time(),
                    "type": "native",
                    "api_path": api_path,
                    "step_name": step_name,
                    "proxy": self.proxy,
                }
                logger.info(f"  💾 Challenge state kaydedildi (account_id={account_id}, api_path={api_path})")

            masked_email = email_addr[:3] + "***" + email_addr[email_addr.index("@"):] if email_addr else "kayıtlı email"
            return {
                "success": False,
                "checkpoint": True,
                "two_factor": False,
                "needs_code": True,
                "message": f"Instagram {masked_email} adresine doğrulama kodu gönderdi. Lütfen emailinizi kontrol edip kodu girin.",
            }

        except ChallengeRequired as e:
            logger.warning(f"  🔒 @{username} challenge gerekli — otomatik çözülüyor...")
            try:
                last = getattr(cl, 'last_json', {}) or {}
                challenge = last.get("challenge", {})
                api_path = challenge.get("api_path", "")

                if api_path:
                    try:
                        cl.challenge_resolve_simple(api_path)
                    except ChallengeCodeNeeded:
                        # IMAP başarısız — kullanıcıdan kod iste
                        account_id = getattr(self, '_account_id', None)
                        if account_id:
                            _challenge_store[account_id] = {
                                "client": cl,
                                "username": username,
                                "password": password,
                                "email_addr": email_addr,
                                "timestamp": time.time(),
                                "type": "native",
                                "api_path": api_path,
                                "proxy": self.proxy,
                            }
                        masked_email = email_addr[:3] + "***" + email_addr[email_addr.index("@"):] if email_addr else "kayıtlı email"
                        return {
                            "success": False,
                            "checkpoint": True,
                            "needs_code": True,
                            "message": f"Instagram {masked_email} adresine doğrulama kodu gönderdi. Lütfen emailinizi kontrol edip kodu girin.",
                        }
                else:
                    cl.challenge_resolve(last)

                self._save_session(cl, username)
                return self._build_success(cl, username)
            except ChallengeCodeNeeded:
                account_id = getattr(self, '_account_id', None)
                if account_id:
                    _challenge_store[account_id] = {
                        "client": cl,
                        "username": username,
                        "password": password,
                        "email_addr": email_addr,
                        "timestamp": time.time(),
                        "type": "native",
                        "proxy": self.proxy,
                    }
                masked_email = email_addr[:3] + "***" + email_addr[email_addr.index("@"):] if email_addr else "kayıtlı email"
                return {
                    "success": False,
                    "checkpoint": True,
                    "needs_code": True,
                    "message": f"Instagram {masked_email} adresine doğrulama kodu gönderdi. Lütfen emailinizi kontrol edip kodu girin.",
                }
            except Exception as ce:
                logger.error(f"  ❌ Challenge çözülemedi: {ce}")
                return {"success": False, "checkpoint": True, "message": f"Checkpoint çözülemedi: {str(ce)[:100]}"}

        except ChallengeUnknownStep as e:
            # Bloks-based challenge (Instagram yeni sistem)
            logger.warning(f"  🔒 @{username} Bloks challenge — otomatik çözülüyor...")
            try:
                result = self._resolve_bloks_challenge(
                    cl, username, email_addr, email_password,
                    account_id=getattr(self, '_account_id', None),
                )
                if result.get("success"):
                    self._save_session(cl, username)
                return result
            except Exception as be:
                logger.error(f"  ❌ Bloks challenge hatası: {be}")
                return {
                    "success": False,
                    "checkpoint": True,
                    "message": f"Doğrulama gerekli — email'e kod gönderildi.",
                }

        except RecaptchaChallengeForm:
            logger.warning(f"  ⚠️ @{username} reCAPTCHA — proxy sorunu")
            # IP değiştirmeden hata döndür
            return {"success": False, "message": "reCAPTCHA gerekli — proxy'yi kontrol edin veya değiştirin"}

        except ProxyAddressIsBlocked:
            logger.warning(f"  ⚠️ @{username} proxy engellenmiş")
            return {"success": False, "message": "Proxy IP adresi engellenmiş — farklı proxy gerekiyor"}

        except SentryBlock:
            logger.warning(f"  ⚠️ @{username} Sentry Block")
            return {"success": False, "message": "Instagram bu IP'yi engellemiş — proxy değiştirilmeli"}

        except BadCredentials:
            logger.error(f"  ❌ @{username} kimlik bilgileri hatalı")
            return {"success": False, "message": "Kullanıcı adı veya şifre hatalı"}

        except FeedbackRequired as e:
            msg = str(e)
            logger.error(f"  ❌ @{username} feedback: {msg}")
            if "login_required" in msg.lower():
                return {"success": False, "message": "Instagram hesabı kısıtlanmış"}
            return {"success": False, "message": f"Instagram uyarısı: {msg[:100]}"}

        except PleaseWaitFewMinutes:
            logger.error(f"  ⏳ @{username} rate limit — birkaç dakika bekleyin")
            return {"success": False, "message": "Rate limit — birkaç dakika bekleyin"}

        except Exception as e:
            error_msg = str(e)[:200]
            logger.error(f"  ❌ @{username} beklenmeyen hata: {error_msg}")

            # Proxy bağlantı hatası — IP değiştirmeden hata döndür
            is_connection_error = any(k in error_msg.lower() for k in [
                "connectionpool", "max retries", "connection refused",
                "timeout", "proxyerror", "502", "500 error", "503",
            ])
            if self.proxy and is_connection_error:
                logger.error(f"  ⚠️ @{username} proxy bağlantı hatası — IP koruması için proxy'siz denenmeyecek")
                return {"success": False, "message": f"Proxy bağlantı hatası — proxy'yi kontrol edin: {error_msg[:100]}"}

            # Yaygın hata mesajlarını Türkçe'ye çevir
            if "bad_password" in error_msg.lower():
                return {"success": False, "message": "Şifre hatalı"}
            elif "invalid_user" in error_msg.lower():
                return {"success": False, "message": "Kullanıcı bulunamadı"}
            elif "checkpoint" in error_msg.lower():
                return {"success": False, "checkpoint": True, "message": f"Checkpoint: {error_msg[:100]}"}
            elif "please wait" in error_msg.lower():
                return {"success": False, "message": "Rate limit — birkaç dakika bekleyin"}

            return {"success": False, "message": error_msg}

    # ─── Bloks Challenge Handler ───────────────────────────────

    def _resolve_bloks_challenge(
        self, cl, username: str,
        email_addr: str | None, email_password: str | None,
        account_id: int | None = None,
    ) -> dict:
        """
        Instagram Bloks challenge çözücü.
        Email doğrulama kodu ister → IMAP dener → başarısızsa kullanıcıdan ister.
        """
        import json as _json

        last = getattr(cl, "last_json", {}) or {}
        challenge_context = last.get("challenge_context", "")

        if not challenge_context:
            return {"success": False, "checkpoint": True, "message": "Challenge context bulunamadı"}

        # 1) Email ile doğrulama iste
        logger.info(f"  📧 @{username} Bloks challenge — email doğrulama isteniyor...")
        bloks_version = getattr(cl, "bloks_versioning_id", "") or ""
        try:
            data = {
                "bk_client_context": _json.dumps({
                    "bloks_version": bloks_version,
                    "styles_id": "instagram",
                }),
                "bloks_action": "com.bloks.www.ig.challenge.redirect.async",
                "challenge_context": challenge_context,
                "choice": "1",  # 1 = email
            }
            cl.private_request(
                "bloks/apps/com.bloks.www.ig.challenge.redirect.async/",
                data=data,
                with_signature=False,
            )
            logger.info(f"  ✅ Email doğrulama kodu istendi")
        except Exception as e:
            logger.warning(f"  ⚠️ Bloks email istek hatası: {e}")

        # 2) Email'den kodu oku
        email_code = None
        if email_addr and email_password:
            import time as _time
            is_aol = "@aol.com" in email_addr.lower() or "@aol.co" in email_addr.lower()

            if not is_aol:
                # Gmail / Hotmail / Outlook → IMAP ile otomatik oku
                try:
                    logger.info(f"  📧 IMAP ile kod okunuyor ({email_addr[:5]}***) — 15sn bekleniyor...")
                    _time.sleep(15)
                    from app.services.email_service import EmailCodeReader
                    reader = EmailCodeReader(email_addr, email_password)
                    email_code = reader.fetch_instagram_code(max_age_minutes=5, max_retries=4, retry_delay=10)
                    if email_code:
                        logger.info(f"  ✅ IMAP'dan kod alındı: {email_code}")
                except Exception as ie:
                    logger.warning(f"  ⚠️ IMAP okuma hatası: {ie}")
            else:
                # AOL → Playwright headless browser
                try:
                    logger.info(f"  📧 AOL webmail'den kod okunuyor (15sn bekleniyor)...")
                    _time.sleep(15)
                    from app.services.aol_reader import get_instagram_code_sync
                    email_code = get_instagram_code_sync(email_addr, email_password, max_wait=45)
                except Exception as ie:
                    logger.warning(f"  ⚠️ AOL okuma hatası: {ie}")

        # 3) Kod varsa gönder
        if email_code:
            return self._submit_bloks_code(cl, username, challenge_context, bloks_version, email_code)

        # 4) Otomatik okuma başarısız — challenge context'i sakla, kullanıcıdan kod iste
        if account_id:
            _challenge_store[account_id] = {
                "client": cl,
                "challenge_context": challenge_context,
                "bloks_version": bloks_version,
                "username": username,
                "timestamp": time.time(),
                "proxy": self.proxy,
            }
            logger.info(f"  💾 Challenge context saklandı (account_id={account_id})")

        masked_email = email_addr[:3] + "***" + email_addr[email_addr.index("@"):] if email_addr else "kayıtlı email"
        return {
            "success": False,
            "checkpoint": True,
            "needs_code": True,
            "message": f"Instagram {masked_email} adresine doğrulama kodu gönderdi. Lütfen emailinizi kontrol edip kodu girin.",
        }

    def _submit_bloks_code(self, cl, username: str, challenge_context: str, bloks_version: str, code: str) -> dict:
        """Bloks challenge kodunu gönderir."""
        import json as _json

        try:
            submit_data = {
                "bk_client_context": _json.dumps({
                    "bloks_version": bloks_version,
                    "styles_id": "instagram",
                }),
                "bloks_action": "com.bloks.www.ig.challenge.redirect.async",
                "challenge_context": challenge_context,
                "security_code": code,
            }
            cl.private_request(
                "bloks/apps/com.bloks.www.ig.challenge.redirect.async/",
                data=submit_data,
                with_signature=False,
            )
            logger.info(f"  ✅ Kod gönderildi — doğrulama kontrol ediliyor...")

            # Login başarılı mı?
            try:
                cl.get_timeline_feed()
                self._save_session(cl, username)
                return self._build_success(cl, username)
            except Exception:
                pass

            # Tekrar login dene
            try:
                password = getattr(cl, "password", None) or ""
                totp = getattr(cl, "totp_seed", None)
                vc = ""
                if totp:
                    vc = cl.totp_generate_code(totp)
                cl.login(username, password, verification_code=vc)
                self._save_session(cl, username)
                return self._build_success(cl, username)
            except Exception as e2:
                logger.warning(f"  ⚠️ Re-login başarısız: {e2}")

            return {"success": False, "checkpoint": True, "message": "Kod kabul edildi ama oturum tamamlanamadı. Tekrar deneyin."}

        except Exception as se:
            logger.error(f"  ❌ Kod gönderme hatası: {se}")
            return {"success": False, "checkpoint": True, "message": f"Kod hatası: {str(se)[:150]}"}

    @staticmethod
    async def submit_challenge_code_for_account(account_id: int, code: str) -> dict:
        """Kullanıcının girdiği challenge kodunu gönderir.
        İki tür challenge destekler:
        - native: instagrapi'nin kendi challenge çözümü (re-login ile)
        - bloks: Bloks API üzerinden kod gönderme
        """
        entry = _challenge_store.get(account_id)
        if not entry:
            return {"success": False, "message": "Challenge beklemiyor — önce giriş deneyin."}

        # Zaman aşımı (10 dk)
        if time.time() - entry["timestamp"] > 600:
            _challenge_store.pop(account_id, None)
            return {"success": False, "message": "Challenge süresi doldu — tekrar giriş deneyin."}

        cl = entry["client"]
        username = entry["username"]
        challenge_type = entry.get("type", "bloks")
        stored_proxy = entry.get("proxy")  # Login sırasında kullanılan proxy

        # Challenge'ı AYNI PROXY ile çöz — IP değişmemeli
        client = InstagramWebClient(proxy=stored_proxy)

        if challenge_type == "native":
            # instagrapi native challenge — doğrudan security_code gönder
            logger.info(f"  📧 @{username} challenge kodu gönderiliyor (native): {code}")
            api_path = entry.get("api_path", "")

            try:
                if api_path:
                    # Challenge URL'ye doğrudan kodu gönder (yeni login başlatmadan)
                    challenge_url = api_path[1:] if api_path.startswith("/") else api_path
                    cl._send_private_request(challenge_url, {"security_code": code})
                    
                    last_json = cl.last_json or {}
                    action = last_json.get("action", "")
                    status = last_json.get("status", "")
                    step_name = last_json.get("step_name", "")
                    
                    logger.info(f"  📧 Challenge response: action={action} status={status} step={step_name}")
                    
                    if action == "close" and status == "ok":
                        # Challenge başarılı — login_flow çalıştır
                        try:
                            cl.login_flow()
                        except Exception:
                            pass  # login_flow başarısız olsa bile session geçerli
                        client._save_session(cl, username)
                        _challenge_store.pop(account_id, None)
                        return client._build_success(cl, username)
                    elif step_name == "review_contact_point_change":
                        # Profil bilgilerini onayla
                        cl._send_private_request(challenge_url, {"choice": 0})
                        try:
                            cl.login_flow()
                        except Exception:
                            pass
                        client._save_session(cl, username)
                        _challenge_store.pop(account_id, None)
                        return client._build_success(cl, username)
                    else:
                        error_msg = str(last_json.get("errors", last_json.get("message", "Kod kabul edilmedi")))[:150]
                        return {"success": False, "checkpoint": True, "message": f"Doğrulama hatası: {error_msg}"}
                else:
                    # api_path yok — eski yöntem: re-login dene
                    cl.challenge_code_handler = lambda u, c: code
                    password = entry.get("password", getattr(cl, "password", ""))
                    cl.login(username, password)
                    client._save_session(cl, username)
                    _challenge_store.pop(account_id, None)
                    return client._build_success(cl, username)
                    
            except ChallengeCodeNeeded:
                return {"success": False, "checkpoint": True, "message": "Kod kabul edilmedi — yanlış veya süresi geçmiş olabilir."}
            except Exception as e:
                error_msg = str(e)[:150]
                logger.error(f"  ❌ Native challenge kodu hatası: {error_msg}")
                if "bad_password" in error_msg.lower():
                    return {"success": False, "message": "Şifre hatalı"}
                elif "invalid" in error_msg.lower() or "check the code" in error_msg.lower():
                    return {"success": False, "checkpoint": True, "message": "Doğrulama kodu geçersiz — doğru kodu girin"}
                return {"success": False, "checkpoint": True, "message": f"Giriş hatası: {error_msg}"}
        else:
            # Bloks challenge
            result = client._submit_bloks_code(
                cl, username,
                entry.get("challenge_context", ""),
                entry.get("bloks_version", ""),
                code,
            )

            if result.get("success"):
                _challenge_store.pop(account_id, None)

            return result

    # ─── Yardımcılar ───────────────────────────────────────────

    def _build_success(self, cl, username: str) -> dict:
        """Başarılı giriş sonrası bilgileri toplar."""
        settings = cl.get_settings()
        self.user_id = str(cl.user_id or "")
        self.username = username

        # Cookie'leri topla
        self.cookies = {}
        if hasattr(cl, 'private') and hasattr(cl.private, 'cookies'):
            for cookie in cl.private.cookies:
                self.cookies[cookie.name] = cookie.value

        # Settings'den cookie bilgilerini al
        if "cookies" in settings:
            self.cookies.update(settings.get("cookies", {}))

        # csrftoken ve sessionid ekle
        if not self.cookies.get("sessionid"):
            auth = settings.get("authorization_data", {})
            if auth.get("sessionid"):
                self.cookies["sessionid"] = auth["sessionid"]
            if auth.get("mid"):
                self.cookies["mid"] = auth["mid"]
            if auth.get("csrftoken"):
                self.cookies["csrftoken"] = auth["csrftoken"]

        self.csrf_token = self.cookies.get("csrftoken", "")
        self._cl = cl

        return {
            "success": True,
            "user_id": self.user_id,
            "cookies": self.cookies,
            "settings": settings,  # instagrapi session ayarları
        }

    def _save_session(self, cl, username: str):
        """Session'ı dosyaya kaydet."""
        try:
            session_file = self._session_path(username)
            cl.dump_settings(session_file)
            logger.info(f"  💾 @{username} session kaydedildi: {session_file}")
        except Exception as e:
            logger.warning(f"  ⚠️ Session kaydetme hatası: {e}")

    def _raw_http_login(self, username: str, password: str, two_factor_seed: str | None = None) -> dict | None:
        """Raw HTTP ile Instagram login — instagrapi'nin BadPassword sorununu bypass eder."""
        import requests as _req
        import hashlib
        import uuid

        proxy = self.proxy
        proxies = {"http": proxy, "https": proxy} if proxy else None

        device_id = "android-" + hashlib.md5(f"{username}_dev".encode()).hexdigest()[:16]
        phone_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{username}.ig"))

        UA = "Instagram 269.0.0.18.75 Android (30/11; 420dpi; 1080x2400; samsung; SM-G991B; o1s; exynos2100; tr_TR; 436384441)"

        session = _req.Session()
        if proxies:
            session.proxies = proxies
        session.headers.update({
            "User-Agent": UA,
            "X-IG-App-ID": "567067343352427",
            "X-IG-App-Locale": "tr_TR",
            "X-IG-Device-Locale": "tr_TR",
            "X-IG-Device-ID": device_id,
            "X-IG-Android-ID": device_id,
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        })

        # 1) CSRF token al
        try:
            session.get("https://i.instagram.com/api/v1/si/fetch_headers/",
                         params={"challenge_type": "signup", "guid": phone_id}, timeout=15)
        except Exception:
            pass
        csrf = session.cookies.get("csrftoken", "")

        # 2) Login isteği
        login_data = {
            "username": username,
            "enc_password": f"#PWD_INSTAGRAM:0:{int(time.time())}:{password}",
            "device_id": device_id,
            "phone_id": phone_id,
            "login_attempt_count": "0",
            "_csrftoken": csrf,
        }

        try:
            r = session.post("https://i.instagram.com/api/v1/accounts/login/",
                              data=login_data, timeout=30)
            resp = r.json()
        except Exception as e:
            logger.warning(f"  ⚠️ Raw HTTP login hatası: {e}")
            return None  # Belirsiz — fallback'e bırak

        # 3) Yanıtı işle
        if resp.get("logged_in_user"):
            user_id = str(resp["logged_in_user"]["pk"])
            logger.info(f"  ✅ @{username} RAW HTTP direkt giriş! user_id={user_id}")
            return {
                "success": True,
                "user_id": user_id,
                "message": "Giriş başarılı",
                "raw_session_cookies": dict(session.cookies),
            }

        if resp.get("two_factor_required"):
            logger.info(f"  🔐 @{username} RAW HTTP: 2FA gerekiyor")
            two_factor_info = resp.get("two_factor_info", {})
            identifier = two_factor_info.get("two_factor_identifier", "")

            # TOTP seed varsa otomatik 2FA çöz
            if two_factor_seed:
                totp_code = self._generate_totp(two_factor_seed)
                logger.info(f"  🔐 @{username} TOTP kodu üretildi: {totp_code}, 2FA çözülüyor...")
                try:
                    tfa_data = {
                        "username": username,
                        "verification_code": totp_code,
                        "two_factor_identifier": identifier,
                        "trust_this_device": "1",
                        "_csrftoken": csrf,
                        "device_id": device_id,
                    }
                    r2 = session.post("https://i.instagram.com/api/v1/accounts/two_factor_login/",
                                       data=tfa_data, timeout=30)
                    resp2 = r2.json()
                    if resp2.get("logged_in_user"):
                        user_id = str(resp2["logged_in_user"]["pk"])
                        logger.info(f"  ✅ @{username} RAW HTTP 2FA başarılı! user_id={user_id}")
                        return {
                            "success": True,
                            "user_id": user_id,
                            "message": "2FA ile giriş başarılı",
                            "raw_session_cookies": dict(session.cookies),
                        }
                    else:
                        logger.warning(f"  ⚠️ @{username} RAW HTTP 2FA yanıtı: {str(resp2)[:200]}")
                except Exception as tfa_e:
                    logger.warning(f"  ⚠️ @{username} RAW HTTP 2FA hatası: {tfa_e}")

            # 2FA çözülemedi — kullanıcıdan kod iste
            masked_email = ""
            obfuscated = two_factor_info.get("obfuscated_phone_number", "")
            if obfuscated:
                masked_email = f"telefon: ***{obfuscated}"
            return {
                "success": False, "checkpoint": True, "needs_code": True,
                "message": f"2FA doğrulama kodu gerekiyor. {masked_email}",
            }

        if resp.get("challenge") or resp.get("message") == "checkpoint_required":
            api_path = ""
            if resp.get("challenge"):
                api_path = resp["challenge"].get("api_path", "")
            logger.info(f"  📧 @{username} RAW HTTP: Challenge gerekiyor (api_path={api_path})")
            # Challenge'ı instagrapi ile çözmek için None dön — fallback'e geç
            return None

        if resp.get("invalid_credentials"):
            logger.error(f"  ❌ @{username} RAW HTTP: şifre kesinlikle yanlış (invalid_credentials)")
            return {"success": False, "invalid_credentials": True, "message": "Şifre hatalı — lütfen şifreyi kontrol edin"}

        # Bilinmeyen yanıt — logla ve None dön (fallback'e bırak)
        logger.warning(f"  ⚠️ @{username} RAW HTTP bilinmeyen yanıt: {str(resp)[:300]}")
        return None

    def _generate_totp(self, seed: str) -> str:
        """TOTP kodu üret."""
        import hmac
        import struct
        import base64

        seed_clean = seed.replace(" ", "").upper()
        # Padding ekle
        padding = 8 - len(seed_clean) % 8
        if padding != 8:
            seed_clean += "=" * padding

        try:
            key = base64.b32decode(seed_clean)
        except Exception:
            key = seed_clean.encode()

        counter = int(time.time()) // 30
        msg = struct.pack(">Q", counter)
        h = hmac.new(key, msg, "sha1").digest()
        offset = h[-1] & 0x0F
        code_int = (struct.unpack(">I", h[offset:offset + 4])[0] & 0x7FFFFFFF) % 1000000
        return str(code_int).zfill(6)

    # ──────────────────────────── SESSION YÜKLEME ────────────────────────────

    async def login_with_cookies(self, cookies: dict) -> bool:
        """Mevcut cookie'ler ile session'ı yükler."""
        self.cookies = cookies
        self.csrf_token = cookies.get("csrftoken", "")
        self.user_id = cookies.get("ds_user_id", "")
        return await self.check_session()

    async def login_with_settings(self, settings: dict, username: str, password: str) -> bool:
        """instagrapi settings ile session yükler."""
        loop = asyncio.get_event_loop()

        def _restore():
            from instagrapi import Client
            cl = self._get_instagrapi_client()
            cl.set_settings(settings)
            try:
                cl.login(username, password)
                cl.get_timeline_feed()
                self._cl = cl
                self.user_id = str(cl.user_id or "")
                return True
            except Exception:
                return False

        return await loop.run_in_executor(None, _restore)

    async def check_session(self) -> bool:
        """Session'ın geçerli olup olmadığını kontrol eder."""
        if self._cl:
            loop = asyncio.get_event_loop()
            try:
                await loop.run_in_executor(None, self._cl.get_timeline_feed)
                return True
            except Exception:
                return False

        # Cookie-based fallback
        if not self.cookies.get("sessionid"):
            return False

        import httpx
        try:
            async with httpx.AsyncClient(
                cookies=self.cookies,
                headers={
                    "User-Agent": "Instagram 275.0.0.27.98 Android",
                    "X-IG-App-ID": "936619743392459",
                },
                timeout=15.0,
                proxy=self.proxy,
                follow_redirects=True,
                verify=False,
            ) as client:
                resp = await client.get("https://i.instagram.com/api/v1/accounts/current_user/")
                return resp.status_code == 200 and resp.json().get("user") is not None
        except Exception:
            return False

    # ──────────────────────────── PROFİL İŞLEMLERİ ────────────────────────────

    async def get_user_info(self, user_id: str | None = None) -> dict:
        """Kullanıcı bilgilerini çeker."""
        if not self._cl:
            raise InstagramWebError("Giriş yapılmamış")

        loop = asyncio.get_event_loop()
        try:
            uid = int(user_id or self.user_id)
            info = await loop.run_in_executor(None, self._cl.user_info, uid)
            return {
                "pk": str(info.pk),
                "username": info.username,
                "full_name": info.full_name,
                "biography": info.biography,
                "follower_count": info.follower_count,
                "following_count": info.following_count,
                "media_count": info.media_count,
                "profile_pic_url": str(info.profile_pic_url) if info.profile_pic_url else None,
                "is_private": info.is_private,
                "is_verified": info.is_verified,
            }
        except Exception as e:
            raise InstagramWebError(f"Profil bilgisi alınamadı: {e}")

    async def load_session_from_file(self, username: str) -> bool:
        """Kaydedilmiş session dosyasından instagrapi client'ı yükler.
        Bu metot profil güncelleme gibi işlemler için gereklidir.
        """
        session_file = self._session_path(username)
        if not session_file.exists():
            raise InstagramWebError(f"@{username} session dosyası bulunamadı")

        loop = asyncio.get_event_loop()

        def _load():
            cl = self._get_instagrapi_client()
            try:
                cl.load_settings(session_file)
                # Session geçerli mi test et
                cl.account_info()
                self._cl = cl
                self.username = username
                self.user_id = str(cl.user_id or "")
                logger.info(f"  ✅ @{username} session dosyasından yüklendi")
                return True
            except Exception as e:
                logger.error(f"  ❌ @{username} session yüklenemedi: {e}")
                raise InstagramWebError(f"Session geçersiz, yeniden giriş gerekli: {e}")

        return await loop.run_in_executor(None, _load)

    async def update_profile(self, **kwargs) -> dict:
        """Profil bilgilerini günceller (bio, full_name, external_url, phone_number)."""
        if not self._cl:
            raise InstagramWebError("Giriş yapılmamış")
        loop = asyncio.get_event_loop()
        try:
            result = await loop.run_in_executor(None, lambda: self._cl.account_edit(**kwargs))
            return {"success": True, "user": str(result)}
        except Exception as e:
            raise InstagramWebError(f"Profil güncellenemedi: {e}")

    async def update_profile_picture(self, photo_path: str) -> dict:
        """Profil fotoğrafını değiştirir."""
        if not self._cl:
            raise InstagramWebError("Giriş yapılmamış")
        loop = asyncio.get_event_loop()
        try:
            result = await loop.run_in_executor(
                None, lambda: self._cl.account_change_picture(photo_path)
            )
            return {"success": True, "user": str(result)}
        except Exception as e:
            raise InstagramWebError(f"Profil fotoğrafı değiştirilemedi: {e}")

    # ──────────────────────────── MEDYA İŞLEMLERİ ────────────────────────────

    async def upload_photo(self, photo_path: str, caption: str = "") -> dict:
        """Fotoğraf paylaşır."""
        if not self._cl:
            raise InstagramWebError("Giriş yapılmamış")
        loop = asyncio.get_event_loop()
        try:
            media = await loop.run_in_executor(
                None, lambda: self._cl.photo_upload(photo_path, caption)
            )
            return {
                "success": True,
                "media_id": str(media.pk),
                "code": media.code,
            }
        except Exception as e:
            raise InstagramWebError(f"Fotoğraf yüklenemedi: {e}")

    async def upload_video(self, video_path: str, caption: str = "", thumbnail: str | None = None) -> dict:
        """Video paylaşır."""
        if not self._cl:
            raise InstagramWebError("Giriş yapılmamış")
        loop = asyncio.get_event_loop()
        try:
            media = await loop.run_in_executor(
                None, lambda: self._cl.video_upload(video_path, caption, thumbnail)
            )
            return {
                "success": True,
                "media_id": str(media.pk),
                "code": media.code,
            }
        except Exception as e:
            raise InstagramWebError(f"Video yüklenemedi: {e}")

    async def upload_reel(self, video_path: str, caption: str = "", thumbnail: str | None = None) -> dict:
        """Reels paylaşır."""
        if not self._cl:
            raise InstagramWebError("Giriş yapılmamış")
        loop = asyncio.get_event_loop()
        try:
            media = await loop.run_in_executor(
                None, lambda: self._cl.clip_upload(video_path, caption, thumbnail)
            )
            return {
                "success": True,
                "media_id": str(media.pk),
                "code": media.code,
            }
        except Exception as e:
            raise InstagramWebError(f"Reels yüklenemedi: {e}")

    async def upload_story(self, file_path: str) -> dict:
        """Story paylaşır."""
        if not self._cl:
            raise InstagramWebError("Giriş yapılmamış")
        loop = asyncio.get_event_loop()
        try:
            ext = Path(file_path).suffix.lower()
            if ext in (".mp4", ".mov"):
                media = await loop.run_in_executor(
                    None, lambda: self._cl.video_upload_to_story(file_path)
                )
            else:
                media = await loop.run_in_executor(
                    None, lambda: self._cl.photo_upload_to_story(file_path)
                )
            return {"success": True, "media_id": str(media.pk)}
        except Exception as e:
            raise InstagramWebError(f"Story yüklenemedi: {e}")

    # ──────────────────────────── DM İŞLEMLERİ ────────────────────────────

    async def send_dm(self, user_ids: list[str], message: str) -> dict:
        """Direkt mesaj gönderir."""
        if not self._cl:
            raise InstagramWebError("Giriş yapılmamış")
        loop = asyncio.get_event_loop()
        try:
            int_ids = [int(uid) for uid in user_ids]
            thread = await loop.run_in_executor(
                None, lambda: self._cl.direct_send(message, int_ids)
            )
            return {"success": True, "thread_id": str(thread.id) if thread else "sent"}
        except Exception as e:
            raise InstagramWebError(f"DM gönderilemedi: {e}")

    async def get_direct_threads(self, amount: int = 20) -> list:
        """DM thread'lerini listeler."""
        if not self._cl:
            raise InstagramWebError("Giriş yapılmamış")
        loop = asyncio.get_event_loop()
        try:
            threads = await loop.run_in_executor(
                None, lambda: self._cl.direct_threads(amount=amount)
            )
            return [
                {
                    "thread_id": str(t.id),
                    "thread_title": t.thread_title,
                    "last_activity_at": str(t.last_activity_at) if t.last_activity_at else None,
                    "is_group": t.is_group,
                }
                for t in threads
            ]
        except Exception as e:
            raise InstagramWebError(f"DM'ler alınamadı: {e}")
