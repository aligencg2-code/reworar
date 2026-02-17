# services/scheduler_service.py — İçerik planlama ve yayınlama motoru (instagrapi)
import asyncio
import random
import os
from pathlib import Path
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor
from sqlalchemy.orm import Session
from app.models.account import Account
from app.models.post import Post, PostStatus, MediaType
from app.models.hashtag import HashtagGroup
from app.utils.logger import logger

# Session dosyaları instagrapi tarafından kaydediliyor
SESSIONS_DIR = Path(__file__).resolve().parent.parent.parent / "sessions"
SESSIONS_DIR.mkdir(exist_ok=True)

# Yayınlama işlemleri için thread pool (instagrapi senkron)
_publish_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="publisher")


class SchedulerService:
    """Zamanlanmış gönderi yayınlama ve kuyruğa alma servisi (instagrapi tabanlı)."""

    async def execute_scheduled_posts(self, db: Session):
        """Zamanı gelen tüm gönderileri yayınlar."""
        now = datetime.utcnow()
        pending = (
            db.query(Post)
            .filter(
                Post.status == PostStatus.SCHEDULED,
                Post.scheduled_at <= now,
            )
            .order_by(Post.scheduled_at)
            .all()
        )

        if not pending:
            return

        logger.info(f"Yayınlanacak {len(pending)} gönderi bulundu")

        for post in pending:
            try:
                # Günlük limit kontrolü
                if not self.check_daily_limit(db, post.account_id):
                    logger.warning(
                        f"Günlük limit aşıldı: Hesap #{post.account_id}, "
                        f"gönderi #{post.id} ertelendi"
                    )
                    continue

                await self.publish_post(db, post)
            except Exception as e:
                post.status = PostStatus.FAILED
                post.error_message = str(e)
                post.retry_count += 1
                db.commit()
                logger.error(f"Gönderi #{post.id} yayınlanamadı: {e}")

    async def publish_post(self, db: Session, post: Post):
        """Tek bir gönderiyi Instagram'da yayınlar (instagrapi kullanarak)."""
        account = db.query(Account).filter(Account.id == post.account_id).first()
        if not account:
            raise Exception("Hesap bulunamadı")

        # Session dosyasını kontrol et
        session_file = SESSIONS_DIR / f"{account.username}.json"
        if not session_file.exists():
            raise Exception(
                f"@{account.username} için session dosyası bulunamadı. "
                f"Önce hesabı giriş yaparak aktif edin."
            )

        try:
            post.status = PostStatus.PUBLISHING
            db.commit()

            # Hashtag ekle
            caption = post.caption or ""
            if post.hashtag_group_id:
                group = db.query(HashtagGroup).filter(
                    HashtagGroup.id == post.hashtag_group_id
                ).first()
                if group:
                    caption = f"{caption}\n\n{group.get_hashtag_string()}"
                    group.usage_count += 1

            # Medya türüne göre yayınla
            media_items = post.media_items
            if not media_items:
                raise Exception("Gönderiye bağlı medya bulunamadı")

            # instagrapi senkron — thread pool'da çalıştır
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                _publish_executor,
                self._publish_sync,
                account, session_file, post, media_items, caption,
            )

            post.status = PostStatus.PUBLISHED
            post.published_at = datetime.utcnow()
            post.instagram_media_id = str(result.get("id", "")) if isinstance(result, dict) else str(result)
            db.commit()

            logger.info(
                f"✅ Gönderi #{post.id} yayınlandı: @{account.username}"
            )
        except Exception as e:
            post.status = PostStatus.FAILED
            post.error_message = str(e)[:500]
            db.commit()
            logger.error(f"❌ Gönderi #{post.id} yayınlanamadı: {e}")
            raise

    def _publish_sync(self, account, session_file, post, media_items, caption):
        """Senkron instagrapi yayınlama (thread pool'da çalışır)."""
        import instagrapi
        from app.utils.encryption import decrypt_token

        # Şifreyi çöz
        password = ""
        if account.password_encrypted:
            try:
                password = decrypt_token(account.password_encrypted)
            except Exception as e:
                logger.warning(f"  ⚠️ Şifre çözme hatası: {e}")

        cl = instagrapi.Client()

        # Proxy varsa ayarla
        if account.proxy_url:
            try:
                cl.set_proxy(account.proxy_url)
            except Exception:
                pass  # Proxy hatası olursa devam et

        # Session yükle ve giriş yap
        logged_in = False

        # Yöntem 1: Session + şifre ile login
        if session_file.exists():
            try:
                cl.load_settings(session_file)
                if password:
                    cl.login(account.username, password)
                else:
                    # Şifre yoksa session ile timeline erişimi dene
                    cl.get_timeline_feed()
                logged_in = True
                logger.info(f"  📱 @{account.username} session ile giriş başarılı")
            except Exception as e:
                logger.warning(f"  ⚠️ Session login başarısız: {e}")

        # Yöntem 2: Temiz client ile login
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
                # Session'ı kaydet
                try:
                    cl.dump_settings(session_file)
                    logger.info(f"  💾 @{account.username} yeni session kaydedildi")
                except Exception:
                    pass
                logger.info(f"  ✅ @{account.username} şifre ile giriş başarılı")
            except Exception as e:
                logger.error(f"  ❌ @{account.username} şifre ile giriş de başarısız: {e}")

        if not logged_in:
            raise Exception(
                f"@{account.username} giriş yapılamadı. "
                f"Hesab panelden tekrar giriş yapın."
            )

        # Medya dosya yollarını hazırla
        file_paths = []
        for item in media_items:
            media = item.media
            path = media.file_path
            if not os.path.exists(path):
                raise Exception(f"Medya dosyası bulunamadı: {path}")
            file_paths.append(path)

        # Medya türüne göre yayınla
        if post.media_type == MediaType.CAROUSEL and len(file_paths) > 1:
            return self._upload_carousel(cl, file_paths, caption)
        elif post.media_type in (MediaType.VIDEO,):
            return self._upload_video(cl, file_paths[0], caption)
        elif post.media_type == MediaType.REELS:
            return self._upload_reels(cl, file_paths[0], caption)
        elif post.media_type == MediaType.STORY:
            return self._upload_story(cl, file_paths[0])
        else:
            return self._upload_photo(cl, file_paths[0], caption)

    def _upload_photo(self, cl, file_path: str, caption: str) -> dict:
        """Fotoğraf yükler."""
        logger.info(f"  📷 Fotoğraf yükleniyor: {file_path}")
        result = cl.photo_upload(Path(file_path), caption=caption)
        media_id = result.id if hasattr(result, 'id') else str(result)
        logger.info(f"  ✅ Fotoğraf yüklendi: {media_id}")
        return {"id": media_id}

    def _upload_video(self, cl, file_path: str, caption: str) -> dict:
        """Video yükler."""
        logger.info(f"  🎬 Video yükleniyor: {file_path}")
        result = cl.video_upload(Path(file_path), caption=caption)
        media_id = result.id if hasattr(result, 'id') else str(result)
        logger.info(f"  ✅ Video yüklendi: {media_id}")
        return {"id": media_id}

    def _upload_reels(self, cl, file_path: str, caption: str) -> dict:
        """Reels yükler."""
        logger.info(f"  🎭 Reels yükleniyor: {file_path}")
        result = cl.clip_upload(Path(file_path), caption=caption)
        media_id = result.id if hasattr(result, 'id') else str(result)
        logger.info(f"  ✅ Reels yüklendi: {media_id}")
        return {"id": media_id}

    def _upload_story(self, cl, file_path: str) -> dict:
        """Story yükler."""
        logger.info(f"  📱 Story yükleniyor: {file_path}")
        path = Path(file_path)
        # Dosya uzantısına göre fotoğraf/video story
        if path.suffix.lower() in ('.mp4', '.mov', '.avi', '.mkv'):
            result = cl.video_upload_to_story(path)
        else:
            result = cl.photo_upload_to_story(path)
        media_id = result.id if hasattr(result, 'id') else str(result)
        logger.info(f"  ✅ Story yüklendi: {media_id}")
        return {"id": media_id}

    def _upload_carousel(self, cl, file_paths: list, caption: str) -> dict:
        """Carousel (kaydırmalı) gönderi yükler."""
        logger.info(f"  🎠 Carousel yükleniyor: {len(file_paths)} medya")
        paths = [Path(p) for p in file_paths]
        result = cl.album_upload(paths, caption=caption)
        media_id = result.id if hasattr(result, 'id') else str(result)
        logger.info(f"  ✅ Carousel yüklendi: {media_id}")
        return {"id": media_id}

    def check_daily_limit(self, db: Session, account_id: int) -> bool:
        """Hesabın günlük paylaşım limitini kontrol eder."""
        account = db.query(Account).filter(Account.id == account_id).first()
        if not account:
            return False

        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0)
        published_today = (
            db.query(Post)
            .filter(
                Post.account_id == account_id,
                Post.status == PostStatus.PUBLISHED,
                Post.published_at >= today_start,
            )
            .count()
        )
        return published_today < account.daily_post_limit

    def select_media_type_by_percentage(self, account: Account) -> str:
        """Hesabın yüzde ayarlarına göre medya tipi seçer."""
        choices = []
        if account.photo_percentage > 0:
            choices.extend(["photo"] * account.photo_percentage)
        if account.video_percentage > 0:
            choices.extend(["video"] * account.video_percentage)
        if account.story_percentage > 0:
            choices.extend(["story"] * account.story_percentage)
        if account.reels_percentage > 0:
            choices.extend(["reels"] * account.reels_percentage)

        if not choices:
            return "photo"
        return random.choice(choices)


scheduler_service = SchedulerService()
