# services/proxy_pool.py — Proxy havuzu yönetimi
import random
from typing import Optional

from app.utils.logger import logger


def normalize_proxy(raw: str | None) -> str | None:
    """
    Proxy formatını standartlaştırır.
    Desteklenen formatlar:
      host:port:user:pass → http://user:pass@host:port
      host:port           → http://host:port
      http://...          → olduğu gibi
    """
    if not raw or not raw.strip():
        return None
    raw = raw.strip()
    # Zaten URL formatındaysa dokunma
    if raw.lower().startswith(("http://", "https://", "socks4://", "socks5://")):
        return raw
    parts = raw.split(":")
    if len(parts) == 4:
        return f"http://{parts[2]}:{parts[3]}@{parts[0]}:{parts[1]}"
    elif len(parts) == 2:
        return f"http://{parts[0]}:{parts[1]}"
    return None  # Geçersiz format


class ProxyPool:
    """Round-robin proxy havuzu."""

    def __init__(self):
        self._proxies: list[str] = []
        self._index: int = 0

    @property
    def count(self) -> int:
        return len(self._proxies)

    def load_proxies(self, proxy_list: list[str]):
        """Proxy listesini yükler. ip:port → http://ip:port formatına çevirir."""
        self._proxies = []
        for p in proxy_list:
            p = p.strip()
            if not p:
                continue
            if not p.startswith(("http://", "https://", "socks4://", "socks5://")):
                p = f"http://{p}"
            self._proxies.append(p)
        self._index = 0
        logger.info(f"🌐 Proxy havuzu güncellendi: {len(self._proxies)} proxy")

    def get_next(self) -> Optional[str]:
        """Sıradaki proxy'yi döndürür (round-robin)."""
        if not self._proxies:
            return None
        proxy = self._proxies[self._index % len(self._proxies)]
        self._index += 1
        return proxy

    def get_random(self) -> Optional[str]:
        """Rastgele proxy döndürür."""
        if not self._proxies:
            return None
        return random.choice(self._proxies)

    def get_all(self) -> list[str]:
        """Tüm proxy'leri listeler."""
        return self._proxies.copy()

    def add_proxy(self, proxy: str):
        """Tek proxy ekler."""
        if not proxy.startswith(("http://", "https://", "socks4://", "socks5://")):
            proxy = f"http://{proxy}"
        if proxy not in self._proxies:
            self._proxies.append(proxy)

    def remove_proxy(self, proxy: str):
        """Proxy kaldırır."""
        self._proxies = [p for p in self._proxies if p != proxy]


# Global singleton
proxy_pool = ProxyPool()

# Varsayılan proxy listesi — Residential proxy (Geonode TR)
DEFAULT_PROXIES = [
    "http://geonode_GP3GdOd85m-type-residential-country-tr:64ca689c-ab33-4a69-a0c8-642fe411ac8d@proxy.geonode.io:9000",
]

# Başlangıçta yükle
proxy_pool.load_proxies(DEFAULT_PROXIES)
