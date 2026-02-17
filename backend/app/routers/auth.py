# routers/auth.py — Kimlik doğrulama ve OAuth endpoint'leri
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Request, Query
from fastapi.responses import RedirectResponse, HTMLResponse
from sqlalchemy.orm import Session
from jose import jwt
import bcrypt
from pydantic import BaseModel, EmailStr

from app.database import get_db
from app.config import settings
from app.models.user import User, UserRole
from app.models.account import Account
from app.services.oauth_service import oauth_service
from app.utils.encryption import encrypt_token
from app.utils.logger import logger

router = APIRouter(prefix="/api/auth", tags=["Kimlik Doğrulama"])


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))


# ─── Şemalar ───────────────────────────────────────────
class RegisterRequest(BaseModel):
    username: str
    email: EmailStr
    password: str
    role: str = "editor"


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict


# ─── Yardımcılar ──────────────────────────────────────
def create_jwt(user_id: int, username: str, role: str) -> str:
    payload = {
        "sub": str(user_id),
        "username": username,
        "role": role,
        "exp": datetime.utcnow() + timedelta(minutes=settings.JWT_EXPIRE_MINUTES),
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    """JWT'den aktif kullanıcıyı çözer."""
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Token gerekli")

    token = auth.split(" ", 1)[1]
    try:
        payload = jwt.decode(
            token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM]
        )
        user = db.query(User).filter(User.id == int(payload["sub"])).first()
        if not user or not user.is_active:
            raise HTTPException(status_code=401, detail="Geçersiz kullanıcı")
        return user
    except jwt.JWTError:
        raise HTTPException(status_code=401, detail="Geçersiz token")


def require_admin(user: User = Depends(get_current_user)) -> User:
    """Sadece admin erişimi."""
    if user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Yetki yetersiz")
    return user


# ─── Endpoint'ler ─────────────────────────────────────
@router.post("/register", response_model=TokenResponse)
async def register(data: RegisterRequest, db: Session = Depends(get_db)):
    """Yeni kullanıcı kaydı."""
    existing = db.query(User).filter(
        (User.username == data.username) | (User.email == data.email)
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Kullanıcı adı veya email zaten kullanımda")

    user = User(
        username=data.username,
        email=data.email,
        password_hash=hash_password(data.password),
        role=UserRole(data.role.upper()) if data.role and data.role.upper() in ("ADMIN", "EDITOR") else UserRole.EDITOR,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_jwt(user.id, user.username, user.role.value.lower())
    logger.info(f"Yeni kullanıcı kaydı: {user.username}")
    return TokenResponse(
        access_token=token,
        user={"id": user.id, "username": user.username, "role": user.role.value.lower()},
    )


@router.post("/login", response_model=TokenResponse)
async def login(data: LoginRequest, db: Session = Depends(get_db)):
    """Kullanıcı girişi."""
    user = db.query(User).filter(User.username == data.username).first()
    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Geçersiz kullanıcı adı veya şifre")

    if not user.is_active:
        raise HTTPException(status_code=403, detail="Hesap devre dışı")

    user.last_login = datetime.utcnow()
    db.commit()

    token = create_jwt(user.id, user.username, user.role.value.lower())
    return TokenResponse(
        access_token=token,
        user={"id": user.id, "username": user.username, "role": user.role.value.lower()},
    )


@router.get("/instagram/connect")
async def instagram_connect():
    """Instagram OAuth akışını başlatır — doğrudan Facebook'a yönlendirir."""
    # Önce API ayarlarının yapılıp yapılmadığını kontrol et
    if not settings.FACEBOOK_APP_ID or settings.FACEBOOK_APP_ID == "your_facebook_app_id":
        raise HTTPException(
            status_code=400,
            detail="Facebook App ID henüz ayarlanmamış. Ayarlar sayfasından API bilgilerini girin."
        )
    url = oauth_service.get_authorization_url()
    return RedirectResponse(url=url)


@router.get("/instagram/status")
async def instagram_api_status():
    """Facebook/Instagram API yapılandırma durumunu döndürür."""
    app_id = settings.FACEBOOK_APP_ID
    app_secret = settings.FACEBOOK_APP_SECRET
    
    configured = bool(
        app_id and app_id != "your_facebook_app_id" and
        app_secret and app_secret != "your_facebook_app_secret"
    )
    
    return {
        "configured": configured,
        "app_id_set": bool(app_id and app_id != "your_facebook_app_id"),
        "app_secret_set": bool(app_secret and app_secret != "your_facebook_app_secret"),
        "redirect_uri": settings.FACEBOOK_REDIRECT_URI,
    }


@router.get("/callback")
async def oauth_callback(
    code: str = Query(None),
    error: str = Query(None),
    error_reason: str = Query(None),
    error_description: str = Query(None),
    db: Session = Depends(get_db),
):
    """Facebook OAuth callback — hesabı sisteme ekler."""
    # Kullanıcı izin vermediyse
    if error:
        logger.warning(f"OAuth reddedildi: {error} — {error_description}")
        return RedirectResponse(
            url=f"http://localhost:3000/accounts?error={error_description or error_reason or 'İzin verilmedi'}"
        )
    
    if not code:
        return RedirectResponse(
            url="http://localhost:3000/accounts?error=Yetkilendirme kodu alınamadı"
        )
    
    try:
        token_data = await oauth_service.exchange_code_for_token(code)
        access_token = token_data["access_token"]
        expires_in = token_data["expires_in"]

        # Instagram hesaplarını bul
        ig_accounts = await oauth_service.get_instagram_accounts(access_token)
        if not ig_accounts:
            return RedirectResponse(
                url="http://localhost:3000/accounts?error=Bağlı Instagram Business hesabı bulunamadı. Hesabınızın Business veya Creator türünde olduğundan emin olun."
            )

        added = []
        for ig in ig_accounts:
            existing = db.query(Account).filter(
                Account.instagram_id == ig["instagram_id"]
            ).first()

            if existing:
                existing.access_token_encrypted = encrypt_token(access_token)
                existing.token_expires_at = datetime.utcnow() + timedelta(seconds=expires_in)
                existing.facebook_page_id = ig["facebook_page_id"]
                existing.facebook_page_token_encrypted = encrypt_token(
                    ig["facebook_page_token"]
                )
                existing.profile_picture_url = ig["profile_picture_url"]
                existing.followers_count = ig["followers_count"]
                existing.following_count = ig["following_count"]
                existing.media_count = ig["media_count"]
                existing.is_active = True
                added.append(existing.username)
            else:
                account = Account(
                    instagram_id=ig["instagram_id"],
                    username=ig["username"],
                    full_name=ig["full_name"],
                    profile_picture_url=ig["profile_picture_url"],
                    biography=ig.get("biography", ""),
                    followers_count=ig["followers_count"],
                    following_count=ig["following_count"],
                    media_count=ig["media_count"],
                    access_token_encrypted=encrypt_token(access_token),
                    token_expires_at=datetime.utcnow() + timedelta(seconds=expires_in),
                    facebook_page_id=ig["facebook_page_id"],
                    facebook_page_token_encrypted=encrypt_token(ig["facebook_page_token"]),
                    is_active=True,
                )
                db.add(account)
                added.append(ig["username"])

        db.commit()
        logger.info(f"Instagram hesapları bağlandı: {', '.join(added)}")

        # Frontend'e yönlendir
        connected_names = ",".join(added)
        return RedirectResponse(
            url=f"http://localhost:3000/accounts?connected={connected_names}"
        )

    except Exception as e:
        logger.error(f"OAuth callback hatası: {e}")
        return RedirectResponse(
            url=f"http://localhost:3000/accounts?error=Bağlantı hatası: {str(e)}"
        )


@router.post("/token/refresh/{account_id}")
async def refresh_account_token(
    account_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Hesap token'ını yeniler."""
    success = await oauth_service.refresh_token(db, account_id)
    if not success:
        raise HTTPException(status_code=400, detail="Token yenilenemedi")
    return {"message": "Token başarıyla yenilendi"}


@router.post("/api-config")
async def update_api_config(
    data: dict,
    user: User = Depends(require_admin),
):
    """Facebook API yapılandırmasını günceller (.env dosyasına yazar)."""
    import os
    from pathlib import Path
    
    env_path = Path(__file__).resolve().parent.parent.parent / ".env"
    
    # Mevcut .env'yi oku
    env_lines = []
    if env_path.exists():
        env_lines = env_path.read_text(encoding="utf-8").splitlines()
    
    updates = {}
    if "facebook_app_id" in data and data["facebook_app_id"]:
        updates["FACEBOOK_APP_ID"] = data["facebook_app_id"]
    if "facebook_app_secret" in data and data["facebook_app_secret"]:
        updates["FACEBOOK_APP_SECRET"] = data["facebook_app_secret"]
    if "redirect_uri" in data and data["redirect_uri"]:
        updates["FACEBOOK_REDIRECT_URI"] = data["redirect_uri"]
    
    if not updates:
        raise HTTPException(status_code=400, detail="Güncellenecek alan bulunamadı")
    
    # .env dosyasını güncelle
    for key, value in updates.items():
        found = False
        for i, line in enumerate(env_lines):
            if line.strip().startswith(f"{key}="):
                env_lines[i] = f"{key}={value}"
                found = True
                break
        if not found:
            env_lines.append(f"{key}={value}")
        
        # Runtime ayarını da güncelle
        os.environ[key] = value
        setattr(settings, key, value)
    
    env_path.write_text("\n".join(env_lines) + "\n", encoding="utf-8")
    
    logger.info("Facebook API yapılandırması güncellendi")
    return {"message": "API ayarları başarıyla kaydedildi", "configured": True}
