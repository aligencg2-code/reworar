# routers/bulk_import.py — Toplu hesap import ve session yönetimi
import uuid
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.database import get_db
from app.models.user import User
from app.routers.auth import get_current_user
from app.services.session_manager import session_manager

router = APIRouter(prefix="/api/accounts", tags=["Toplu Hesap Yönetimi"])


class BulkImportRequest(BaseModel):
    accounts_text: str  # satır başı: username:password veya username:password:proxy
    default_proxy: str | None = None


class SingleLoginRequest(BaseModel):
    account_id: int


class BulkLoginRequest(BaseModel):
    account_ids: list[int] | None = None  # None ise tümü


@router.post("/bulk-import")
async def bulk_import(
    data: BulkImportRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Toplu hesap import — username:password:proxy formatı."""
    result = await session_manager.import_accounts(
        db, data.accounts_text, data.default_proxy
    )
    return result


@router.post("/bulk-login")
async def bulk_login(
    data: BulkLoginRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Toplu giriş başlatır (arka planda)."""
    job_id = str(uuid.uuid4())[:8]
    # Background task'a DB session geçirme — kendi session'ını oluştursun
    background_tasks.add_task(
        session_manager.bulk_login_background, data.account_ids, job_id
    )
    return {"job_id": job_id, "message": "Toplu giriş başlatıldı"}


@router.get("/login-status/{job_id}")
async def login_status(
    job_id: str,
    user: User = Depends(get_current_user),
):
    """Toplu giriş ilerleme durumu."""
    return session_manager.get_progress(job_id)


@router.post("/login-single")
async def login_single(
    data: SingleLoginRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Tek hesaba giriş yapar."""
    import traceback
    try:
        result = await session_manager.login_single(db, data.account_id)
        if not result.get("success"):
            return result
        return result
    except Exception as e:
        tb = traceback.format_exc()
        print(f"[LOGIN ERROR] {e}\n{tb}")
        return {
            "success": False,
            "message": str(e) or "Beklenmeyen hata",
            "username": "",
            "error_detail": tb[-300:],
        }


class ChallengeCodeRequest(BaseModel):
    account_id: int
    code: str


@router.post("/submit-challenge-code")
async def submit_challenge_code(
    data: ChallengeCodeRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Challenge doğrulama kodu gönderir (email'den alınan 6 haneli kod)."""
    from app.services.instagram_web import InstagramWebClient

    result = await InstagramWebClient.submit_challenge_code_for_account(
        data.account_id, data.code
    )

    # Başarılıysa DB'yi güncelle
    if result.get("success"):
        from app.models.account import Account
        account = db.query(Account).filter(Account.id == data.account_id).first()
        if account:
            account.session_valid = True
            account.account_status = "active"
            account.last_login_at = __import__("datetime").datetime.utcnow()
            if result.get("user_id"):
                account.instagram_id = result["user_id"]
            # Session cookies kaydet
            if result.get("cookies"):
                from app.utils.encryption import encrypt_token
                account.session_cookies = encrypt_token(
                    __import__("json").dumps(result["cookies"])
                )
            if result.get("settings"):
                from app.utils.encryption import encrypt_token
                account.instagrapi_settings = encrypt_token(
                    __import__("json").dumps(result["settings"])
                )
            db.commit()

    return result


@router.post("/validate-sessions")
async def validate_sessions(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Tüm session'ları kontrol eder."""
    result = await session_manager.validate_all_sessions(db)
    return result


# ─── Proxy Havuzu Yönetimi ────────────────────────


class ProxyPoolRequest(BaseModel):
    proxies: list[str]


@router.get("/proxy-pool")
async def get_proxy_pool(user: User = Depends(get_current_user)):
    """Proxy havuzundaki tüm proxy'leri listeler."""
    from app.services.proxy_pool import proxy_pool
    return {
        "proxies": proxy_pool.get_all(),
        "count": proxy_pool.count,
    }


@router.post("/proxy-pool")
async def update_proxy_pool(
    data: ProxyPoolRequest,
    user: User = Depends(get_current_user),
):
    """Proxy havuzunu günceller."""
    from app.services.proxy_pool import proxy_pool
    proxy_pool.load_proxies(data.proxies)
    return {
        "message": f"{proxy_pool.count} proxy yüklendi",
        "count": proxy_pool.count,
    }


@router.post("/assign-proxies")
async def assign_proxies(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Proxy'si olmayan hesaplara havuzdan proxy atar."""
    from app.services.proxy_pool import proxy_pool
    from app.models.account import Account

    accounts = db.query(Account).filter(
        (Account.proxy_url.is_(None)) | (Account.proxy_url == "")
    ).all()

    assigned = 0
    for acc in accounts:
        proxy = proxy_pool.get_next()
        if proxy:
            acc.proxy_url = proxy
            assigned += 1

    db.commit()
    return {
        "message": f"{assigned} hesaba proxy atandı",
        "assigned": assigned,
        "total_without_proxy": len(accounts),
    }

