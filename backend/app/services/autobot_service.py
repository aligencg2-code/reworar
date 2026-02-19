# services/autobot_service.py — Otomatik paylaşım bot motoru
"""
Müşteri "Botu Başlat" butonuna bastığında:
1. Tüm aktif hesapları sırayla dolaşır
2. Medya havuzundan sıradaki medyayı seçer
3. Caption + hashtag + konum ekler
4. instagrapi ile Instagram'a paylaşır
5. Güvenli aralıklarla bir sonraki hesaba geçer
6. "Botu Durdur" butonuna basılana kadar döngüde kalır
"""

import asyncio
import random
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models.account import Account
from app.models.media import Media, MediaFileType
from app.models.post import Post, PostStatus, MediaType
from app.models.hashtag import HashtagGroup
from app.utils.logger import logger
from app.config import settings as _app_settings

SESSIONS_DIR = _app_settings.SESSIONS_DIR

# Bot yayınlama thread pool
_bot_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="autobot")

# ─── Güvenli Aralık Sabitleri ──────────────────────────
MIN_DELAY_BETWEEN_ACCOUNTS = 25 * 60   # 25 dakika (saniye)
MAX_DELAY_BETWEEN_ACCOUNTS = 45 * 60   # 45 dakika
MIN_SAME_ACCOUNT_COOLDOWN = 3 * 3600   # 3 saat
NIGHT_START_HOUR = 1    # Gece 01:00
NIGHT_END_HOUR = 6      # Sabah 06:00


class AutoBotService:
    """Otomatik paylaşım bot motoru."""

    def __init__(self):
        self._running = False
        self._task: asyncio.Task | None = None
        self._logs: list[dict] = []          # Son 50 log
        self._current_account: str = ""      # Şu an hangi hesap
        self._posts_made: int = 0            # Toplam paylaşım
        self._last_publish: dict[int, datetime] = {}  # account_id → son paylaşım zamanı
        self._started_at: datetime | None = None
        self._media_index: dict[int, int] = {}  # account_id → medya index (sıralı)

    # ─── Public API ────────────────────────────────────────

    def start(self):
        """Botu başlatır."""
        if self._running:
            return {"success": False, "message": "Bot zaten çalışıyor"}

        self._running = True
        self._started_at = datetime.utcnow()
        self._posts_made = 0
        self._add_log("info", "🤖 Bot başlatıldı!")

        loop = asyncio.get_event_loop()
        self._task = loop.create_task(self._bot_loop())
        return {"success": True, "message": "Bot başlatıldı"}

    def stop(self):
        """Botu durdurur."""
        if not self._running:
            return {"success": False, "message": "Bot zaten durmuş"}

        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
        self._add_log("info", "⏹ Bot durduruldu.")
        return {"success": True, "message": "Bot durduruldu"}

    def status(self):
        """Bot durumunu döner."""
        return {
            "running": self._running,
            "current_account": self._current_account,
            "posts_made": self._posts_made,
            "started_at": self._started_at.isoformat() if self._started_at else None,
            "logs": self._logs[-30:],  # Son 30 log
        }

    # ─── Ana Bot Döngüsü ──────────────────────────────────

    async def _bot_loop(self):
        """Ana bot döngüsü — tüm hesapları sırayla dolaşır."""
        try:
            while self._running:
                # Gece saati kontrolü
                now = datetime.utcnow()
                local_hour = (now.hour + 3) % 24  # UTC → TR saat
                if NIGHT_START_HOUR <= local_hour < NIGHT_END_HOUR:
                    self._add_log("info", f"🌙 Gece modu — {NIGHT_END_HOUR}:00'e kadar bekleniyor...")
                    await self._safe_sleep(3600)  # 1 saat bekle, tekrar kontrol et
                    continue

                db = SessionLocal()
                try:
                    # Aktif hesapları al
                    accounts = (
                        db.query(Account)
                        .filter(Account.is_active == True, Account.session_valid == True)
                        .all()
                    )

                    if not accounts:
                        self._add_log("warning", "⚠️ Aktif ve oturumu geçerli hesap bulunamadı")
                        await self._safe_sleep(60)
                        continue

                    self._add_log("info", f"📋 {len(accounts)} aktif hesap bulundu, sırayla paylaşım başlıyor...")

                    for account in accounts:
                        if not self._running:
                            break

                        # Günlük limit kontrolü
                        if not self._check_daily_limit(db, account):
                            self._add_log("info", f"⏸ @{account.username} günlük limit doldu, atlanıyor")
                            continue

                        # Aynı hesap cooldown kontrolü
                        if not self._check_cooldown(account.id):
                            remaining = self._get_cooldown_remaining(account.id)
                            self._add_log("info", f"⏳ @{account.username} cooldown — {remaining} dk kaldı")
                            continue

                        # Paylaşım yap
                        self._current_account = account.username
                        success = await self._publish_for_account(db, account)

                        if success:
                            self._posts_made += 1
                            self._last_publish[account.id] = datetime.utcnow()

                        # Bir sonraki hesaba geçmeden önce bekle
                        if self._running:
                            delay = random.randint(MIN_DELAY_BETWEEN_ACCOUNTS, MAX_DELAY_BETWEEN_ACCOUNTS)
                            delay_min = delay // 60
                            self._add_log("info", f"⏰ Sonraki hesap için {delay_min} dk bekleniyor...")
                            await self._safe_sleep(delay)

                finally:
                    db.close()

                # Tüm hesaplar dolaşıldı, döngüye devam
                if self._running:
                    self._add_log("info", "🔄 Tüm hesaplar kontrol edildi, yeni döngü başlıyor...")

        except asyncio.CancelledError:
            self._add_log("info", "🛑 Bot görevi iptal edildi")
        except Exception as e:
            self._add_log("error", f"❌ Bot hatası: {str(e)[:200]}")
            logger.error(f"AutoBot hatası: {e}")
        finally:
            self._running = False
            self._current_account = ""

    # ─── Hesap İçin Paylaşım ──────────────────────────────

    async def _publish_for_account(self, db: Session, account: Account) -> bool:
        """Bir hesap için medya havuzundan seçip paylaşım yapar."""
        try:
            self._add_log("info", f"📸 @{account.username} için paylaşım hazırlanıyor...")

            # Session dosyası kontrol
            session_file = SESSIONS_DIR / f"{account.username}.json"
            if not session_file.exists():
                self._add_log("warning", f"⚠️ @{account.username} session dosyası yok, atlanıyor")
                return False

            # Medya havuzundan sıradaki medyayı seç
            media = self._pick_next_media(db, account)
            if not media:
                self._add_log("warning", f"⚠️ @{account.username} için uygun medya bulunamadı")
                return False

            # Caption oluştur
            caption = self._build_caption(db, account)

            # Konum bilgisi
            location_name = self._get_location(db, account)

            # instagrapi ile yayınla (senkron, thread pool'da)
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                _bot_executor,
                self._publish_sync,
                account, session_file, media, caption, location_name,
            )

            if result.get("success"):
                self._add_log("info", f"✅ @{account.username} paylaşım başarılı! ({media.filename})")

                # Medyayı kullanıldı olarak işaretle
                media.is_used = True if hasattr(media, 'is_used') else None
                db.commit()
                return True
            else:
                self._add_log("error", f"❌ @{account.username} paylaşım başarısız: {result.get('error', 'bilinmiyor')}")
                return False

        except Exception as e:
            self._add_log("error", f"❌ @{account.username} hata: {str(e)[:150]}")
            logger.error(f"AutoBot publish hatası @{account.username}: {e}")
            return False

    def _publish_sync(self, account, session_file, media, caption, location_name):
        """Senkron instagrapi yayınlama (thread pool'da çalışır)."""
        try:
            import instagrapi
            from app.utils.encryption import decrypt_token

            cl = instagrapi.Client()
            cl.delay_range = [1, 3]

            # Proxy
            if account.proxy_url:
                try:
                    cl.set_proxy(account.proxy_url)
                except Exception:
                    pass

            # Session yükle
            password = ""
            if account.password_encrypted:
                try:
                    password = decrypt_token(account.password_encrypted)
                except Exception:
                    pass

            logged_in = False
            if session_file.exists():
                try:
                    cl.load_settings(session_file)
                    if password:
                        cl.login(account.username, password)
                    else:
                        cl.get_timeline_feed()
                    logged_in = True
                except Exception as e:
                    logger.warning(f"AutoBot session login hatası @{account.username}: {e}")

            if not logged_in and password:
                try:
                    cl = instagrapi.Client()
                    if account.proxy_url:
                        try:
                            cl.set_proxy(account.proxy_url)
                        except Exception:
                            pass
                    cl.login(account.username, password)
                    logged_in = True
                    try:
                        cl.dump_settings(session_file)
                    except Exception:
                        pass
                except Exception as e:
                    return {"success": False, "error": f"Giriş yapılamadı: {str(e)[:100]}"}

            if not logged_in:
                return {"success": False, "error": "Hesaba giriş yapılamadı"}

            # Konum varsa ara
            location = None
            if location_name:
                try:
                    locations = cl.location_search(location_name)
                    if locations:
                        location = locations[0]
                except Exception:
                    pass  # Konum bulunamazsa devam et

            # Dosya yolunu al
            file_path = Path(media.file_path)
            if not file_path.exists():
                return {"success": False, "error": f"Dosya bulunamadı: {media.filename}"}

            # Medya türüne göre yayınla
            if media.media_type == MediaFileType.VIDEO:
                result = cl.video_upload(file_path, caption=caption, location=location)
            else:
                result = cl.photo_upload(file_path, caption=caption, location=location)

            return {"success": True, "media_id": str(getattr(result, 'id', ''))}

        except Exception as e:
            return {"success": False, "error": str(e)[:200]}

    # ─── Yardımcı Fonksiyonlar ─────────────────────────────

    def _pick_next_media(self, db: Session, account: Account) -> Media | None:
        """Medya havuzundan sıradaki medyayı seçer."""
        # Hesaba bağlı veya genel medyaları al
        query = db.query(Media).filter(
            Media.media_type.in_([MediaFileType.PHOTO, MediaFileType.VIDEO]),
        )

        # Hesaba özel medyalar varsa onları öncelikle al
        account_media = query.filter(Media.account_id == account.id).all()
        if not account_media:
            # Genel medya havuzu (hesaba bağlı olmayan)
            account_media = query.filter(Media.account_id == None).all()

        if not account_media:
            return None

        # Sıralı mod
        idx = self._media_index.get(account.id, 0)
        if idx >= len(account_media):
            idx = 0  # Başa dön
        self._media_index[account.id] = idx + 1

        return account_media[idx]

    def _build_caption(self, db: Session, account: Account) -> str:
        """Caption + hashtag oluşturur."""
        from app.models.caption import Caption
        from app.models.settings import SystemSettings

        parts = []

        # Sistem ayarlarını oku
        caption_mode = "random"
        selected_hash_id = None
        try:
            mode_setting = db.query(SystemSettings).filter(SystemSettings.key == "caption_mode").first()
            if mode_setting:
                caption_mode = mode_setting.value
            hash_setting = db.query(SystemSettings).filter(SystemSettings.key == "selected_hashtag_group_id").first()
            if hash_setting and hash_setting.value:
                selected_hash_id = int(hash_setting.value)
        except Exception:
            pass

        # 1) Caption seçimi
        captions = db.query(Caption).filter(Caption.is_active == True).all()
        if captions:
            if caption_mode == "sequential":
                captions.sort(key=lambda c: c.use_count)
                caption = captions[0]
            else:
                caption = random.choice(captions)
            parts.append(caption.text)
            caption.use_count += 1

        # 2) Hashtag grubu seçimi
        if selected_hash_id:
            group = db.query(HashtagGroup).filter(HashtagGroup.id == selected_hash_id).first()
            if group:
                parts.append(group.get_hashtag_string())
        else:
            groups = db.query(HashtagGroup).all()
            if groups:
                group = random.choice(groups)
                parts.append(group.get_hashtag_string())

        return "\n\n".join(parts)

    def _get_location(self, db: Session, account: Account) -> str | None:
        """Hesap veya genel konum bilgisini döner."""
        from app.models.location import Location
        from app.models.settings import SystemSettings
        try:
            # Seçili liste filtresi
            selected_list = None
            list_setting = db.query(SystemSettings).filter(SystemSettings.key == "selected_location_list").first()
            if list_setting and list_setting.value:
                selected_list = list_setting.value

            query = db.query(Location).filter(Location.is_active == True)
            if selected_list:
                query = query.filter(Location.list_name == selected_list)
            locations = query.all()
            if locations:
                loc = random.choice(locations)
                return loc.name
        except Exception:
            pass
        return None

    def _check_daily_limit(self, db: Session, account: Account) -> bool:
        """Günlük limit kontrolü."""
        today = datetime.utcnow().replace(hour=0, minute=0, second=0)
        published_today = (
            db.query(Post)
            .filter(
                Post.account_id == account.id,
                Post.status == PostStatus.PUBLISHED,
                Post.published_at >= today,
            )
            .count()
        )
        return published_today < account.daily_post_limit

    def _check_cooldown(self, account_id: int) -> bool:
        """Aynı hesap cooldown kontrolü."""
        last = self._last_publish.get(account_id)
        if not last:
            return True
        elapsed = (datetime.utcnow() - last).total_seconds()
        return elapsed >= MIN_SAME_ACCOUNT_COOLDOWN

    def _get_cooldown_remaining(self, account_id: int) -> int:
        """Kalan cooldown süresi (dakika)."""
        last = self._last_publish.get(account_id)
        if not last:
            return 0
        elapsed = (datetime.utcnow() - last).total_seconds()
        remaining = max(0, MIN_SAME_ACCOUNT_COOLDOWN - elapsed)
        return int(remaining / 60)

    def _add_log(self, level: str, message: str):
        """Log ekler."""
        entry = {
            "time": datetime.utcnow().isoformat(),
            "level": level,
            "message": message,
        }
        self._logs.append(entry)
        if len(self._logs) > 50:
            self._logs = self._logs[-50:]

        # Logger'a da yaz
        if level == "error":
            logger.error(f"[AutoBot] {message}")
        elif level == "warning":
            logger.warning(f"[AutoBot] {message}")
        else:
            logger.info(f"[AutoBot] {message}")

    async def _safe_sleep(self, seconds: int):
        """Güvenli uyku — bot durdurulursa erken çıkar."""
        step = 5  # 5 saniyede bir kontrol
        elapsed = 0
        while elapsed < seconds and self._running:
            await asyncio.sleep(min(step, seconds - elapsed))
            elapsed += step


# Singleton
autobot_service = AutoBotService()
