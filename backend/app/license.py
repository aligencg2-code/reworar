# app/license.py — HWID tabanlı offline lisans sistemi
import json
import hashlib
import platform
import subprocess
import time
from pathlib import Path
from typing import Optional
from cryptography.fernet import Fernet

# Sabit master anahtar (admin_keygen ile paylaşılır)
_MASTER_KEY = b"dEm3t-L1c3nS3-K3y-2024-AES256-OK"  # 32 byte
_FERNET_KEY = hashlib.sha256(_MASTER_KEY).digest()
_FERNET = Fernet(
    __import__("base64").urlsafe_b64encode(_FERNET_KEY)
)

LICENSE_FILE = Path(__file__).resolve().parent.parent / "license.key"


def get_hwid() -> str:
    """Makine benzersiz donanım kimliği (HWID)."""
    try:
        if platform.system() == "Windows":
            result = subprocess.run(
                ["wmic", "csproduct", "get", "UUID"],
                capture_output=True, text=True, timeout=5,
                creationflags=0x08000000,  # CREATE_NO_WINDOW
            )
            lines = [l.strip() for l in result.stdout.strip().split("\n") if l.strip()]
            if len(lines) >= 2:
                return lines[-1].upper()
    except Exception:
        pass
    # Fallback
    raw = f"{platform.node()}-{platform.machine()}-{platform.processor()}"
    return hashlib.sha256(raw.encode()).hexdigest()[:32].upper()


def generate_license_key(hwid: str, days: int = 30, owner: str = "Müşteri") -> str:
    """Lisans anahtarı üret (admin tarafı)."""
    import time
    payload = json.dumps({
        "hwid": hwid.upper(),
        "owner": owner,
        "days": days,
        "created": int(time.time()),
        "expires": int(time.time()) + (days * 86400),
    })
    encrypted = _FERNET.encrypt(payload.encode())
    return encrypted.decode()


def verify_license(key_text: Optional[str] = None) -> dict:
    """
    Lisans doğrula.
    Returns: {"valid": bool, "owner": str, "expires": int, "remaining_days": int, "error": str}
    """
    if key_text is None:
        if not LICENSE_FILE.exists():
            return {"valid": False, "error": "Lisans dosyası bulunamadı"}
        key_text = LICENSE_FILE.read_text(encoding="utf-8").strip()

    if not key_text:
        return {"valid": False, "error": "Lisans anahtarı boş"}

    try:
        decrypted = _FERNET.decrypt(key_text.encode())
        data = json.loads(decrypted.decode())
    except Exception:
        return {"valid": False, "error": "Geçersiz lisans anahtarı"}

    # HWID kontrolü
    current_hwid = get_hwid()
    if data.get("hwid", "").upper() != current_hwid:
        return {
            "valid": False,
            "error": f"Bu lisans bu makineye ait değil\nLisans HWID: {data.get('hwid')}\nBu makine: {current_hwid}",
        }

    # Süre kontrolü
    now = int(time.time())
    expires = data.get("expires", 0)
    if now > expires:
        return {"valid": False, "error": "Lisans süresi dolmuş"}

    remaining = max(0, (expires - now) // 86400)
    return {
        "valid": True,
        "owner": data.get("owner", ""),
        "expires": expires,
        "remaining_days": remaining,
    }


def activate_license(key_text: str) -> dict:
    """Lisans anahtarını doğrula ve kaydet."""
    result = verify_license(key_text)
    if result["valid"]:
        LICENSE_FILE.write_text(key_text.strip(), encoding="utf-8")
    return result
