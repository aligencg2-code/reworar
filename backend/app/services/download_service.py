# services/download_service.py — Gönderi indirme servisi (API + Web Scraping)
import os
import httpx
import asyncio
from pathlib import Path
from datetime import datetime
from sqlalchemy.orm import Session
from app.models.media import Media, MediaFileType
from app.models.account import Account
from app.services.instagram_api import InstagramAPIClient
from app.services.public_scraper import public_scraper
from app.services.media_service import media_service
from app.utils.encryption import decrypt_token
from app.utils.logger import logger
from app.config import settings


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
    """Instagram gönderi indirme servisi — API ve Web Scraping destekli."""

    def __init__(self):
        self._active_jobs: dict[str, DownloadJob] = {}

    def get_job(self, job_id: str) -> DownloadJob | None:
        return self._active_jobs.get(job_id)

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
            if mode == "scrape":
                await self._download_via_scrape(db, target_username, media_type_filter, limit, job)
            elif mode == "api" and account_id:
                await self._download_via_api(db, account_id, target_username, media_type_filter, limit, job)
            else:
                # Varsayılan: scrape
                await self._download_via_scrape(db, target_username, media_type_filter, limit, job)

        except Exception as e:
            job.status = "error"
            job.errors.append(str(e))
            logger.error(f"İndirme hatası: {e}")

        return job

    async def _download_via_scrape(
        self, db: Session, username: str, media_type_filter: str,
        limit: int, job: DownloadJob
    ):
        """Web scraping ile indirme — takip veya token gerektirmez."""
        logger.info(f"[Scrape] @{username} gönderileri çekiliyor...")

        try:
            media_items = await public_scraper.get_profile_media(username, limit)
        except Exception as e:
            job.status = "error"
            job.errors.append(str(e))
            return

        # Filtre uygula
        if media_type_filter != "all":
            type_map = {
                "photo": ["IMAGE"],
                "video": ["VIDEO"],
                "carousel": ["CAROUSEL_ALBUM"],
            }
            allowed = type_map.get(media_type_filter, [])
            media_items = [m for m in media_items if m.get("media_type") in allowed]

        job.total = len(media_items)
        logger.info(f"[Scrape] @{username} — {job.total} medya bulundu")

        # İndirme dizini
        download_dir = settings.UPLOAD_DIR / "downloads" / username
        download_dir.mkdir(parents=True, exist_ok=True)

        async with httpx.AsyncClient(timeout=120.0, follow_redirects=True) as http:
            for item in media_items:
                if job.status == "stopped":
                    break

                try:
                    media_url = item.get("media_url")
                    if not media_url:
                        continue

                    item_type = item.get("media_type", "IMAGE")
                    ext = ".mp4" if item_type == "VIDEO" else ".jpg"
                    item_id = item.get("id", f"unknown_{job.downloaded}")
                    filename = f"{item_id}{ext}"
                    filepath = download_dir / filename

                    if filepath.exists():
                        job.downloaded += 1
                        continue

                    resp = await http.get(
                        media_url,
                        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/131.0.0.0"}
                    )
                    if resp.status_code == 200 and len(resp.content) > 1000:
                        filepath.write_bytes(resp.content)

                        # Veritabanına kaydet
                        file_type_map = {
                            "IMAGE": MediaFileType.PHOTO,
                            "VIDEO": MediaFileType.VIDEO,
                            "CAROUSEL_ALBUM": MediaFileType.PHOTO,
                        }
                        new_media = Media(
                            filename=filename,
                            original_filename=filename,
                            file_path=str(filepath),
                            media_type=file_type_map.get(item_type, MediaFileType.PHOTO),
                            folder=username,
                            mime_type="video/mp4" if item_type == "VIDEO" else "image/jpeg",
                            file_size=len(resp.content),
                            source_url=media_url,
                            source_username=username,
                        )

                        # Fotoğraf boyutları
                        if item_type != "VIDEO":
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

                    # Rate limiting
                    await asyncio.sleep(0.2)

                except Exception as e:
                    job.failed += 1
                    job.errors.append(str(e))

        job.status = "completed" if job.status != "stopped" else "stopped"
        logger.info(
            f"[Scrape] @{username} — {job.downloaded}/{job.total} başarılı, {job.failed} hata"
        )

    async def _download_via_api(
        self, db: Session, account_id: int, target_username: str,
        media_type_filter: str, limit: int, job: DownloadJob
    ):
        """Instagram Graph API ile indirme (eski yöntem — business discovery)."""
        account = db.query(Account).filter(Account.id == account_id).first()
        if not account or not account.access_token_encrypted:
            job.status = "error"
            job.errors.append("Hesap bulunamadı veya token eksik")
            return

        token = decrypt_token(account.access_token_encrypted)
        client = InstagramAPIClient(token, account.instagram_id)

        try:
            all_media = []
            after = None

            while True:
                if job.status == "stopped":
                    break

                data = await client.get_user_media_by_username(
                    target_username, limit=25, after=after
                )
                bd = data.get("business_discovery", {})
                media_data = bd.get("media", {})
                items = media_data.get("data", [])

                if not items:
                    break

                for item in items:
                    item_type = item.get("media_type", "IMAGE").lower()
                    if media_type_filter != "all":
                        type_map = {
                            "photo": ["image"],
                            "video": ["video"],
                            "carousel": ["carousel_album"],
                        }
                        allowed = type_map.get(media_type_filter, [])
                        if item_type not in allowed:
                            continue
                    all_media.append(item)
                    if limit > 0 and len(all_media) >= limit:
                        break

                if limit > 0 and len(all_media) >= limit:
                    break

                paging = media_data.get("paging", {})
                cursors = paging.get("cursors", {})
                after = cursors.get("after")
                if not after or not paging.get("next"):
                    break

            job.total = len(all_media)
            download_dir = settings.UPLOAD_DIR / "downloads" / target_username
            download_dir.mkdir(parents=True, exist_ok=True)

            async with httpx.AsyncClient(timeout=120.0) as http:
                for item in all_media:
                    if job.status == "stopped":
                        break
                    try:
                        media_url = item.get("media_url") or item.get("thumbnail_url")
                        if not media_url:
                            continue

                        item_type = item.get("media_type", "IMAGE")
                        ext = ".mp4" if item_type == "VIDEO" else ".jpg"
                        filename = f"{item['id']}{ext}"
                        filepath = download_dir / filename

                        if filepath.exists():
                            job.downloaded += 1
                            continue

                        response = await http.get(media_url)
                        if response.status_code == 200:
                            filepath.write_bytes(response.content)

                            file_type_map = {
                                "IMAGE": MediaFileType.PHOTO,
                                "VIDEO": MediaFileType.VIDEO,
                                "CAROUSEL_ALBUM": MediaFileType.PHOTO,
                            }
                            new_media = Media(
                                account_id=account_id,
                                filename=filename,
                                original_filename=filename,
                                file_path=str(filepath),
                                media_type=file_type_map.get(item_type, MediaFileType.PHOTO),
                                folder=target_username,
                                mime_type="video/mp4" if item_type == "VIDEO" else "image/jpeg",
                                file_size=len(response.content),
                                source_url=media_url,
                                source_username=target_username,
                            )

                            if item_type != "VIDEO":
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
                            job.errors.append(f"HTTP {response.status_code}: {item['id']}")

                    except Exception as e:
                        job.failed += 1
                        job.errors.append(str(e))

            job.status = "completed" if job.status != "stopped" else "stopped"

        except Exception as e:
            job.status = "error"
            job.errors.append(str(e))
        finally:
            await client.close()

    def stop_job(self, job_id: str) -> bool:
        """Aktif indirme işini durdurur."""
        job = self._active_jobs.get(job_id)
        if job and job.status == "running":
            job.status = "stopped"
            return True
        return False


download_service = DownloadService()
