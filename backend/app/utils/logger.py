# utils/logger.py — Yapılandırılmış log sistemi
import logging
import logging.handlers
import json
from datetime import datetime
from pathlib import Path
from app.config import settings


class JSONFormatter(logging.Formatter):
    """JSON formatında log çıktısı."""

    def format(self, record):
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
            "message": record.getMessage(),
        }
        if hasattr(record, "account_id"):
            log_entry["account_id"] = record.account_id
        if hasattr(record, "category"):
            log_entry["category"] = record.category
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_entry, ensure_ascii=False)


def setup_logger(name: str = "demet") -> logging.Logger:
    """Ana uygulama logger'ını yapılandırır."""
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO))

    # Konsol handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(
        logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(module)s:%(funcName)s:%(lineno)d | %(message)s"
        )
    )
    logger.addHandler(console_handler)

    # Dosya handler (günlük rotasyon)
    log_file = settings.LOG_DIR / "demet.log"
    file_handler = logging.handlers.TimedRotatingFileHandler(
        log_file, when="midnight", interval=1, backupCount=30, encoding="utf-8"
    )
    file_handler.setFormatter(JSONFormatter())
    logger.addHandler(file_handler)

    return logger


# Global logger
logger = setup_logger()
