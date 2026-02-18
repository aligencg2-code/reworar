# services/download_service.py — Gönderi indirme servisi (instagrapi tabanlı)
import os
import json
import httpx
import asyncio
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from sqlalchemy.orm import Session
from app.models.media import Media, MediaFileType
from app.models.account import Account
from app.services.media_service import media_service
from app.utils.encryption import decrypt_token
from app.utils.logger import logger
from app.config import settings

_executor = ThreadPoolExecutor(max_workers=2)


class DownloadJob:
    """Aktif indirme işi durumu."""
    def __init__(self, job_id: str):
        self.job_id = job_id
        self.status = "running"  # running, completed, stopped, error
        self.total = 0
        self.downloaded = 0
        self.failed = 0
        self.errors: list[str] = []


class DownloadService:
    """Instagram gönderi indirme servisi — instagrapi tabanlı."""

    def __init__(self):
        self._active_jobs: dict[str, DownloadJob] = {}

    def get_job(self, job_id: str) -> DownloadJob | None:
        return self._active_jobs.get(job_id)

    def _get_instagrapi_client(self, db: Session, account_id: int | None = None):
        """Kayıtlı hesabın instagrapi session'ını yükler."""
        from instagrapi import Client

        # Belirli hesap veya ilk aktif hesabı al
        if account_id:
            account = db.query(Account).filter(Account.id == account_id).first()
        else:
            account = (
                db.query(Account)
                .filter(Account.is_active == True, Account.session_valid == True)
                .first()
            )

        if not account:
            # Session'ı geçerli olmasa bile herhangi bir aktif hesap dene
            account = (
                db.query(Account)
                .filter(Account.is_active == True)
                .first()
            )

        if not account:
            raise Exception("Aktif hesap bulunamadı. Lütfen en az bir Instagram hesabı ekleyin.")

        cl = Client()
        cl.delay_range = [1, 3]

        # Session cookies varsa yükle
        if account.session_cookies:
            try:
                cookies_data = decrypt_token(account.session_cookies)
                settings_dict = json.loads(cookies_data)
                cl.set_settings(settings_dict)
                cl.login_by_sessionid(cl.sessionid)
                logger.info(f"[Download] @{account.username} session ile giriş yapıldı")
                return cl, account
            except Exception as e:
                logger.warning(f"[Download] Session yükleme başarısız: {e}")

        # Session yoksa username/password ile giriş
        if account.password_encrypted:
            try:
                password = decrypt_token(account.password_encrypted)
                cl.login(account.username, password)
                logger.info(f"[Download] @{account.username} şifre ile giriş yapıldı")
                return cl, account
            except Exception as e:
                logger.error(f"[Download] Giriş başarısız: {e}")
                raise Exception(f"@{account.username} ile giriş yapılamadı: {e}")

        raise Exception(f"@{account.username} için session veya şifre bulunamadı")

    async def download_user_posts(
        self,
        db: Session,
        target_username: str,
        media_type_filter: str = "all",
        limit: int = 50,
        job_id: str = None,
        mode: str = "scrape",
        account_id: int | None = None,
    ) -> DownloadJob:
        """Hedef kullanıcının gönderilerini indirir."""
        import uuid
        job_id = job_id or uuid.uuid4().hex[:8]
        job = DownloadJob(job_id)
        self._active_jobs[job_id] = job

        try:
            await self._download_via_instagrapi(
                db, target_username, media_type_filter, limit, job, account_id
            )
        except Exception as e:
            job.status = "error"
            job.errors.append(str(e))
            logger.error(f"İndirme hatası: {e}")

        return job

    def _fetch_medias_sync(self, cl, target_username: str, limit: int):
        """Senkron instagrapi çağrısı (thread pool'da çalışır)."""
        # Kullanıcı ID'sini bul
        user_id = cl.user_id_from_username(target_username)
        # Medyaları çek
        medias = cl.user_medias(user_id, amount=limit)
        return medias

    async def _download_via_instagrapi(
        self, db: Session, username: str, media_type_filter: str,
        limit: int, job: DownloadJob, account_id: int | None = None
    ):
        """instagrapi ile indirme — kayıtlı hesap session'ı kullanır."""
        logger.info(f"[Download] @{username} gönderileri instagrapi ile çekiliyor...")

        # instagrapi client'ı al
        loop = asyncio.get_event_loop()
        cl, account = await loop.run_in_executor(
            _executor, lambda: self._get_instagrapi_client(db, account_id)
        )

        try:
            # Medyaları çek (senkron, thread pool'da)
            medias = await loop.run_in_executor(
                _executor, lambda: self._fetch_medias_sync(cl, username, limit)
            )
        except Exception as e:
            job.status = "error"
            err_msg = str(e)
            if "not found" in err_msg.lower() or "user" in err_msg.lower():
                job.errors.append(f"@{username} bulunamadı veya profil gizli")
            else:
                job.errors.append(f"Medya çekme hatası: {err_msg}")
            return

        # Filtre uygula
        if media_type_filter != "all":
            type_map = {
                "photo": [1],  # instagrapi: 1=Photo
                "video": [2],  # 2=Video
                "carousel": [8],  # 8=Album
            }
            allowed = type_map.get(media_type_filter, [])
            medias = [m for m in medias if m.media_type in allowed]

        job.total = len(medias)
        logger.info(f"[Download] @{username} — {job.total} medya bulundu")

        if job.total == 0:
            job.status = "completed"
            return

        # İndirme dizini
        download_dir = settings.UPLOAD_DIR / "downloads" / username
        download_dir.mkdir(parents=True, exist_ok=True)

        async with httpx.AsyncClient(timeout=120.0, follow_redirects=True) as http:
            for media in medias:
                if job.status == "stopped":
                    break

                try:
                    # Medya URL'sini belirle
                    if media.media_type == 2:  # Video
                        media_url = str(media.video_url) if media.video_url else None
                        ext = ".mp4"
                        file_type = MediaFileType.VIDEO
                        mime = "video/mp4"
                    elif media.media_type == 8:  # Carousel/Album
                        # İlk fotoğrafı indir
                        if media.resources:
                            res = media.resources[0]
                            media_url = str(res.video_url or res.thumbnail_url)
                            ext = ".mp4" if res.video_url else ".jpg"
                        else:
                            media_url = str(media.thumbnail_url) if media.thumbnail_url else None
                            ext = ".jpg"
                        file_type = MediaFileType.PHOTO
                        mime = "image/jpeg"
                    else:  # Photo
                        media_url = str(media.thumbnail_url) if media.thumbnail_url else None
                        ext = ".jpg"
                        file_type = MediaFileType.PHOTO
                        mime = "image/jpeg"

                    if not media_url:
                        job.failed += 1
                        continue

                    item_id = media.code or str(media.pk)
                    filename = f"{item_id}{ext}"
                    filepath = download_dir / filename

                    if filepath.exists():
                        job.downloaded += 1
                        continue

                    # İndir
                    resp = await http.get(
                        media_url,
                        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/131.0.0.0"}
                    )
                    if resp.status_code == 200 and len(resp.content) > 1000:
                        filepath.write_bytes(resp.content)

                        # Veritabanına kaydet
                        new_media = Media(
                            filename=filename,
                            original_filename=filename,
                            file_path=str(filepath),
                            media_type=file_type,
                            folder=username,
                            mime_type=mime,
                            file_size=len(resp.content),
                            source_url=media_url,
                            source_username=username,
                        )

                        # Fotoğraf boyutları
                        if ext == ".jpg":
                            try:
                                w, h = media_service.get_image_dimensions(str(filepath))
                                new_media.width = w
                                new_media.height = h
                                thumb = media_service.create_thumbnail(str(filepath))
                                new_media.thumbnail_path = thumb
                            except Exception:
                                pass

                        db.add(new_media)
                        db.commit()
                        job.downloaded += 1
                    else:
                        job.failed += 1
                        job.errors.append(f"HTTP {resp.status_code}: {item_id}")

                    # Rate limit
                    await asyncio.sleep(0.3)

                except Exception as e:
                    job.failed += 1
                    job.errors.append(str(e))

        job.status = "completed" if job.status != "stopped" else "stopped"
        logger.info(
            f"[Download] @{username} — {job.downloaded}/{job.total} başarılı, {job.failed} hata"
        )

    def stop_job(self, job_id: str) -> bool:
        """Aktif indirme işini durdurur."""
        job = self._active_jobs.get(job_id)
        if job and job.status == "running":
            job.status = "stopped"
            return True
        return False


download_service = DownloadService()
