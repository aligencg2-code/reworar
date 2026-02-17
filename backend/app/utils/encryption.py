# utils/encryption.py — Token şifreleme/çözme (Fernet)
import os
from pathlib import Path
from cryptography.fernet import Fernet
from app.config import settings


def _get_fernet() -> Fernet:
    """Fernet şifreleme nesnesi döndürür. Anahtar yoksa üretir ve .env'ye kaydeder."""
    key = settings.ENCRYPTION_KEY
    if not key:
        # Yeni key üret
        key = Fernet.generate_key().decode()
        settings.ENCRYPTION_KEY = key

        # .env dosyasına kalıcı olarak yaz
        env_path = Path(__file__).resolve().parent.parent.parent / ".env"
        try:
            if env_path.exists():
                content = env_path.read_text(encoding="utf-8")
                if "ENCRYPTION_KEY=" in content:
                    # Mevcut satırı güncelle
                    import re
                    content = re.sub(
                        r"ENCRYPTION_KEY=.*",
                        f"ENCRYPTION_KEY={key}",
                        content,
                    )
                else:
                    content += f"\nENCRYPTION_KEY={key}\n"
                env_path.write_text(content, encoding="utf-8")
            else:
                env_path.write_text(f"ENCRYPTION_KEY={key}\n", encoding="utf-8")
            print(f"[Encryption] ✅ Yeni şifreleme anahtarı oluşturuldu ve .env'ye kaydedildi")
        except Exception as e:
            print(f"[Encryption] ⚠️ Anahtar .env'ye yazılamadı: {e}")

    return Fernet(key.encode() if isinstance(key, str) else key)


_fernet = None


def get_fernet() -> Fernet:
    global _fernet
    if _fernet is None:
        _fernet = _get_fernet()
    return _fernet


def encrypt_token(token: str) -> str:
    """Token'ı şifreler."""
    return get_fernet().encrypt(token.encode()).decode()


def decrypt_token(encrypted_token: str) -> str:
    """Şifreli token'ı çözer."""
    return get_fernet().decrypt(encrypted_token.encode()).decode()

