# routers/downloads.py — Gönderi indirme endpoint'leri (API + Web Scraping)
import uuid
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.database import get_db
from app.models.user import User
from app.routers.auth import get_current_user
from app.services.download_service import download_service

router = APIRouter(prefix="/api/downloads", tags=["Gönderi İndirme"])


class DownloadStart(BaseModel):
    target_username: str
    media_type_filter: str = "all"  # all, photo, video, carousel
    limit: int = 50
    mode: str = "scrape"  # scrape (takip gerektirmez) veya api (Graph API)
    account_id: int | None = None  # sadece api modu için


@router.post("/start")
async def start_download(
    data: DownloadStart,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Gönderi indirme işlemini başlatır."""
    job_id = uuid.uuid4().hex[:8]

    # Kullanıcı adını temizle
    target = data.target_username.strip().lstrip("@")
    if not target:
        raise HTTPException(status_code=400, detail="Kullanıcı adı gerekli")

    background_tasks.add_task(
        download_service.download_user_posts,
        db,
        target,
        data.media_type_filter,
        data.limit,
        job_id,
        data.mode,
        data.account_id,
    )

    return {
        "message": f"@{target} gönderileri indiriliyor...",
        "job_id": job_id,
        "mode": data.mode,
    }


@router.get("/status/{job_id}")
async def get_download_status(job_id: str):
    """İndirme durumunu sorgular."""
    job = download_service.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="İş bulunamadı")

    return {
        "job_id": job.job_id,
        "status": job.status,
        "total": job.total,
        "downloaded": job.downloaded,
        "failed": job.failed,
        "errors": job.errors[-5:],  # son 5 hata
    }


@router.post("/stop/{job_id}")
async def stop_download(job_id: str):
    """Aktif indirme işini durdurur."""
    success = download_service.stop_job(job_id)
    if not success:
        raise HTTPException(status_code=400, detail="İş durdurulamadı")
    return {"message": "İndirme durduruldu"}
