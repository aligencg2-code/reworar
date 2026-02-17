# services/public_scraper.py — Takip gerektirmeden public profil indirme
# Instagram web sayfasından scraping — token gerektirmez
import re
import json
import httpx
import asyncio
from pathlib import Path
from datetime import datetime
from app.config import settings
from app.utils.logger import logger

# User-Agent rotasyonu
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) Gecko/20100101 Firefox/133.0",
]


class PublicScraper:
    """Instagram public sayfalarından içerik çekerek indiren servis."""

    def __init__(self):
        self._ua_index = 0

    def _get_ua(self) -> str:
        ua = USER_AGENTS[self._ua_index % len(USER_AGENTS)]
        self._ua_index += 1
        return ua

    def _get_headers(self) -> dict:
        return {
            "User-Agent": self._get_ua(),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Cache-Control": "max-age=0",
        }

    async def get_profile_media(
        self,
        username: str,
        limit: int = 50,
        proxy: str | None = None,
    ) -> list[dict]:
        """Public profilin medya listesini çeker — takip veya token gerektirmez."""
        media_items = []

        transport = None
        if proxy:
            transport = httpx.AsyncHTTPTransport(proxy=proxy)

        async with httpx.AsyncClient(
            timeout=30.0,
            follow_redirects=True,
            transport=transport,
        ) as client:
            # Yol 1: Instagram GraphQL Web API
            try:
                media_items = await self._fetch_via_web_api(client, username, limit)
            except Exception as e1:
                logger.warning(f"Web API yöntemi başarısız: {e1}")

                # Yol 2: HTML embed sayfası
                try:
                    media_items = await self._fetch_via_embed(client, username, limit)
                except Exception as e2:
                    logger.warning(f"Embed yöntemi başarısız: {e2}")

                    # Yol 3: Doğrudan sayfa HTML parse
                    try:
                        media_items = await self._fetch_via_html(client, username, limit)
                    except Exception as e3:
                        logger.error(f"Tüm yöntemler başarısız: {e3}")
                        raise Exception(
                            f"@{username} gönderleri çekilemedi. "
                            f"Profil gizli olabilir veya Instagram erişimi engelliyor."
                        )

        return media_items[:limit] if limit > 0 else media_items

    async def _fetch_via_web_api(
        self, client: httpx.AsyncClient, username: str, limit: int
    ) -> list[dict]:
        """Instagram'ın dahili GraphQL web API'si üzerinden."""
        # İlk sayfa: profil sayfasını yükle ve app_id yakala
        headers = self._get_headers()
        profile_url = f"https://www.instagram.com/{username}/"
        resp = await client.get(profile_url, headers=headers)

        if resp.status_code == 404:
            raise Exception(f"@{username} bulunamadı")
        if resp.status_code != 200:
            raise Exception(f"HTTP {resp.status_code}")

        html = resp.text

        # Sayfadaki JSON verisini çıkar
        media_items = []

        # __additionalData veya window._sharedData pattern
        patterns = [
            r'"edge_owner_to_timeline_media":\s*(\{.*?\})\s*,\s*"edge_saved_media"',
            r'"edge_owner_to_timeline_media":\s*(\{.*?\})\s*\}',
            r'"user":\s*(\{[^}]*"edge_owner_to_timeline_media"[^}]*\})',
        ]

        for pat in patterns:
            match = re.search(pat, html, re.DOTALL)
            if match:
                try:
                    data = json.loads(match.group(1))
                    edges = data.get("edges", [])
                    for edge in edges:
                        node = edge.get("node", {})
                        item = self._parse_node(node, username)
                        if item:
                            media_items.append(item)
                    if media_items:
                        return media_items
                except (json.JSONDecodeError, KeyError):
                    continue

        # Alternatif: script tag'dan tüm JSON'u çıkar
        script_match = re.search(
            r'<script type="application/ld\+json">(.*?)</script>',
            html, re.DOTALL
        )
        if script_match:
            try:
                ld_data = json.loads(script_match.group(1))
                # LD+JSON'dan image URL'leri çıkar
                if isinstance(ld_data, dict):
                    images = ld_data.get("image", [])
                    if isinstance(images, list):
                        for i, img_url in enumerate(images[:limit]):
                            media_items.append({
                                "id": f"{username}_{i}",
                                "media_url": img_url,
                                "media_type": "IMAGE",
                                "caption": "",
                                "timestamp": datetime.utcnow().isoformat(),
                            })
            except json.JSONDecodeError:
                pass

        if media_items:
            return media_items

        raise Exception("Web API: Veri çıkarılamadı")

    async def _fetch_via_embed(
        self, client: httpx.AsyncClient, username: str, limit: int
    ) -> list[dict]:
        """Instagram embed/oembed API üzerinden."""
        # oembed API — tek bir gönderi URL'si gerektirir, profil değil
        # Bu yöntem daha sınırlı ama daha güvenilir
        headers = self._get_headers()

        # Önce profil sayfasından permalink'leri çıkar
        profile_url = f"https://www.instagram.com/{username}/"
        resp = await client.get(profile_url, headers=headers)

        if resp.status_code != 200:
            raise Exception(f"HTTP {resp.status_code}")

        # Direkt link pattern'leri bul
        permalink_pattern = r'"/p/([A-Za-z0-9_-]+)/"'
        matches = re.findall(permalink_pattern, resp.text)
        unique_codes = list(dict.fromkeys(matches))[:limit]

        media_items = []
        for code in unique_codes:
            permalink = f"https://www.instagram.com/p/{code}/"
            try:
                # oembed API'yi dene
                oembed_url = f"https://api.instagram.com/oembed/?url={permalink}"
                oembed_resp = await client.get(oembed_url, headers=headers)
                if oembed_resp.status_code == 200:
                    oembed_data = oembed_resp.json()
                    media_items.append({
                        "id": code,
                        "media_url": oembed_data.get("thumbnail_url", ""),
                        "media_type": "IMAGE",
                        "caption": oembed_data.get("title", ""),
                        "timestamp": datetime.utcnow().isoformat(),
                        "permalink": permalink,
                    })
                await asyncio.sleep(0.3)
            except Exception:
                continue

        if not media_items:
            raise Exception("Embed: Gönderi bulunamadı")

        return media_items

    async def _fetch_via_html(
        self, client: httpx.AsyncClient, username: str, limit: int
    ) -> list[dict]:
        """Direkt sayfa HTML'inden URL'leri çıkar."""
        headers = self._get_headers()
        resp = await client.get(
            f"https://www.instagram.com/{username}/",
            headers=headers,
        )

        if resp.status_code != 200:
            raise Exception(f"HTTP {resp.status_code}")

        html = resp.text

        # Content URL'lerini bul
        media_items = []

        # Instagram CDN URL pattern
        cdn_pattern = r'"(https://(?:scontent|instagram)[^"]*?\.(?:jpg|mp4)[^"]*)"'
        urls = re.findall(cdn_pattern, html)

        # Tekrarları kaldır, profil fotoğraflarını atla
        seen = set()
        for url in urls:
            clean = url.split("?")[0]  # query params kaldır
            if clean in seen:
                continue
            if "profile" in url.lower() or "150x150" in url:
                continue
            seen.add(clean)

            is_video = url.endswith(".mp4") or "video" in url.lower()
            media_items.append({
                "id": f"{username}_{len(media_items)}",
                "media_url": url.replace("\\u0026", "&"),
                "media_type": "VIDEO" if is_video else "IMAGE",
                "caption": "",
                "timestamp": datetime.utcnow().isoformat(),
            })

            if limit > 0 and len(media_items) >= limit:
                break

        if not media_items:
            raise Exception("HTML parse: Medya bulunamadı")

        return media_items

    def _parse_node(self, node: dict, username: str) -> dict | None:
        """GraphQL node'unu standart formata dönüştürür."""
        if not node:
            return None

        media_type = "IMAGE"
        if node.get("is_video"):
            media_type = "VIDEO"
        elif node.get("__typename") == "GraphSidecar":
            media_type = "CAROUSEL_ALBUM"

        media_url = (
            node.get("video_url")
            or node.get("display_url")
            or node.get("thumbnail_src")
        )
        if not media_url:
            return None

        return {
            "id": node.get("shortcode", node.get("id", "")),
            "media_url": media_url,
            "media_type": media_type,
            "caption": (
                node.get("edge_media_to_caption", {})
                .get("edges", [{}])[0]
                .get("node", {})
                .get("text", "")
                if node.get("edge_media_to_caption")
                else ""
            ),
            "timestamp": datetime.fromtimestamp(
                node.get("taken_at_timestamp", 0)
            ).isoformat() if node.get("taken_at_timestamp") else datetime.utcnow().isoformat(),
            "like_count": node.get("edge_liked_by", {}).get("count", 0),
            "comment_count": node.get("edge_media_to_comment", {}).get("count", 0),
            "permalink": f"https://www.instagram.com/p/{node.get('shortcode', '')}/",
        }

    async def download_media_file(
        self,
        url: str,
        save_dir: Path,
        filename: str,
        proxy: str | None = None,
    ) -> Path | None:
        """Tek bir medya dosyasını indirir."""
        filepath = save_dir / filename
        if filepath.exists():
            return filepath

        transport = None
        if proxy:
            transport = httpx.AsyncHTTPTransport(proxy=proxy)

        try:
            async with httpx.AsyncClient(
                timeout=120.0,
                follow_redirects=True,
                transport=transport,
            ) as client:
                resp = await client.get(url, headers={"User-Agent": self._get_ua()})
                if resp.status_code == 200:
                    filepath.write_bytes(resp.content)
                    return filepath
        except Exception as e:
            logger.error(f"İndirme hatası: {filename} — {e}")

        return None


public_scraper = PublicScraper()
