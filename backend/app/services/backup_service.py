# services/backup_service.py — Günlük veritabanı yedekleme
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from app.config import settings
from app.utils.logger import logger


class BackupService:
    """Otomatik veritabanı yedekleme ve rotasyon servisi."""

    def create_backup(self) -> str | None:
        """Veritabanı yedeği oluşturur."""
        if "sqlite" not in settings.DATABASE_URL:
            logger.warning("Yedekleme yalnızca SQLite için destekleniyor")
            return None

        db_path = settings.DATABASE_URL.replace("sqlite:///", "")
        if not Path(db_path).exists():
            logger.error(f"Veritabanı bulunamadı: {db_path}")
            return None

        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        backup_name = f"demet_backup_{timestamp}.db"
        backup_path = settings.BACKUP_DIR / backup_name

        try:
            shutil.copy2(db_path, backup_path)
            logger.info(f"Yedek oluşturuldu: {backup_name}")
            self.cleanup_old_backups()
            return str(backup_path)
        except Exception as e:
            logger.error(f"Yedekleme hatası: {e}")
            return None

    def cleanup_old_backups(self):
        """Eski yedekleri temizler (retention_days'den eski)."""
        cutoff = datetime.utcnow() - timedelta(days=settings.BACKUP_RETENTION_DAYS)
        removed = 0
        for backup_file in settings.BACKUP_DIR.glob("demet_backup_*.db"):
            if datetime.fromtimestamp(backup_file.stat().st_mtime) < cutoff:
                backup_file.unlink()
                removed += 1

        if removed:
            logger.info(f"{removed} eski yedek temizlendi")

    def list_backups(self) -> list[dict]:
        """Mevcut yedekleri listeler."""
        backups = []
        for f in sorted(settings.BACKUP_DIR.glob("demet_backup_*.db"), reverse=True):
            backups.append({
                "filename": f.name,
                "size": f.stat().st_size,
                "created_at": datetime.fromtimestamp(f.stat().st_mtime).isoformat(),
            })
        return backups

    def restore_backup(self, backup_filename: str) -> bool:
        """Yedekten geri yükleme yapar."""
        backup_path = settings.BACKUP_DIR / backup_filename
        if not backup_path.exists():
            return False

        db_path = settings.DATABASE_URL.replace("sqlite:///", "")
        try:
            shutil.copy2(backup_path, db_path)
            logger.info(f"Yedek geri yüklendi: {backup_filename}")
            return True
        except Exception as e:
            logger.error(f"Geri yükleme hatası: {e}")
            return False


backup_service = BackupService()
