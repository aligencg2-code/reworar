# routers/appeals.py — Sorunlu hesap yönetimi endpoint'leri
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.database import get_db
from app.models.user import User
from app.models.account import Account, AccountStatus, AppealStatus
from app.routers.auth import get_current_user
from app.services.appeal_service import appeal_service

router = APIRouter(prefix="/api/appeals", tags=["Sorunlu Hesaplar"])


class BulkAppealRequest(BaseModel):
    account_ids: list[int] | None = None  # None = tüm sorunlu hesaplar


class UpdateStatusRequest(BaseModel):
    account_status: str | None = None
    appeal_status: str | None = None


@router.get("/summary")
async def get_summary(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Tüm hesapların durum özetini getirir."""
    return appeal_service.get_account_summary(db)


@router.post("/check-all")
async def check_all_accounts(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Tüm hesapları kontrol eder (arka planda)."""
    # Zaten devam eden iş var mı?
    current = appeal_service.get_current_job()
    if current and current.status == "running":
        return {
            "message": "Kontrol zaten devam ediyor",
            "checked": current.checked,
            "total": current.total,
        }

    background_tasks.add_task(appeal_service.check_all_accounts, db)
    return {"message": "Hesap kontrolü başlatıldı"}


@router.get("/check-status")
async def get_check_status(
    user: User = Depends(get_current_user),
):
    """Devam eden kontrol işinin durumunu getirir."""
    job = appeal_service.get_current_job()
    if not job:
        return {"status": "idle", "message": "Aktif kontrol yok"}

    return {
        "status": job.status,
        "total": job.total,
        "checked": job.checked,
        "problematic": job.problematic,
        "appeals_sent": job.appeals_sent,
        "errors": job.errors[-5:],
        "results": job.results,
    }


@router.post("/submit-bulk")
async def submit_bulk_appeal(
    data: BulkAppealRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Toplu appeal gönderir."""
    result = await appeal_service.submit_bulk_appeal(db, data.account_ids)
    return result


@router.post("/check-single/{account_id}")
async def check_single_account(
    account_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Tek bir hesabı kontrol eder."""
    account = db.query(Account).filter(Account.id == account_id).first()
    if not account:
        raise HTTPException(status_code=404, detail="Hesap bulunamadı")

    result = await appeal_service.check_single_account(db, account)
    return result


@router.put("/{account_id}/status")
async def update_account_status(
    account_id: int,
    data: UpdateStatusRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Hesap durumunu manuel günceller."""
    account = db.query(Account).filter(Account.id == account_id).first()
    if not account:
        raise HTTPException(status_code=404, detail="Hesap bulunamadı")

    if data.account_status:
        account.account_status = data.account_status
    if data.appeal_status:
        account.appeal_status = data.appeal_status

    db.commit()
    return {"message": f"@{account.username} durumu güncellendi"}
