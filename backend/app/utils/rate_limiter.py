# utils/rate_limiter.py — API rate limit takibi
import time
from collections import defaultdict
from threading import Lock
from app.config import settings


class RateLimiter:
    """Hesap bazlı sliding-window rate limiter."""

    def __init__(self):
        self._calls: dict[str, list[float]] = defaultdict(list)
        self._lock = Lock()

    def can_call(self, account_id: str, window_seconds: int = 3600) -> bool:
        """Verilen hesap için API çağrısı yapılabilir mi kontrol eder."""
        with self._lock:
            now = time.time()
            key = f"account:{account_id}"
            # Pencere dışı kayıtları temizle
            self._calls[key] = [
                t for t in self._calls[key] if now - t < window_seconds
            ]
            max_calls = settings.API_CALLS_PER_HOUR
            return len(self._calls[key]) < max_calls

    def record_call(self, account_id: str):
        """Bir API çağrısı kaydeder."""
        with self._lock:
            self._calls[f"account:{account_id}"].append(time.time())

    def get_remaining(self, account_id: str, window_seconds: int = 3600) -> int:
        """Kalan çağrı hakkını döndürür."""
        with self._lock:
            now = time.time()
            key = f"account:{account_id}"
            self._calls[key] = [
                t for t in self._calls[key] if now - t < window_seconds
            ]
            return max(0, settings.API_CALLS_PER_HOUR - len(self._calls[key]))

    def get_wait_time(self, account_id: str, window_seconds: int = 3600) -> float:
        """Rate limit aşıldıysa bekleme süresini döndürür (saniye)."""
        with self._lock:
            now = time.time()
            key = f"account:{account_id}"
            self._calls[key] = [
                t for t in self._calls[key] if now - t < window_seconds
            ]
            if len(self._calls[key]) < settings.API_CALLS_PER_HOUR:
                return 0.0
            oldest = min(self._calls[key])
            return max(0.0, window_seconds - (now - oldest))


# Global instance
rate_limiter = RateLimiter()
