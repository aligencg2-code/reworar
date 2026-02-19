# services/browser_login_service.py — Tarayıcı ile Instagram girişi
"""
Playwright ile tarayıcı penceresi açar, kullanıcı giriş yapar,
cookie'ler ve session bilgisi kaydedilir.
"""
import asyncio
import json
import logging
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

from app.config import settings as app_settings

logger = logging.getLogger(__name__)
_pool = ThreadPoolExecutor(max_workers=2)

SESSIONS_DIR = app_settings.SESSIONS_DIR
SESSIONS_DIR.mkdir(parents=True, exist_ok=True)


async def browser_login(account_id: int, username: str, proxy_url: str | None = None) -> dict:
    """
    Playwright ile Instagram tarayıcı girişi.
    Tarayıcı penceresi açar, kullanıcı giriş yapar,
    Instagram cookie'leri kaydedilir.
    """
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        _pool, _browser_login_sync, account_id, username, proxy_url
    )


def _ensure_chromium():
    """Playwright Chromium yoksa otomatik indirir."""
    import subprocess, sys
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return False, "Playwright yüklü değil."

    # Chromium'un yüklü olup olmadığını kontrol et
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            browser.close()
        return True, None
    except Exception as e:
        err = str(e)
        if "Executable doesn't exist" not in err and "browserType.launch" not in err:
            return False, f"Tarayıcı hatası: {err[:200]}"

    # Chromium yüklü değil — otomatik indir
    logger.info("🔄 Chromium indiriliyor (ilk kullanım — bu birkaç dakika sürebilir)...")
    try:
        # playwright'in kendi install komutunu kullan
        from playwright._impl._driver import compute_driver_executable
        driver_exec = compute_driver_executable()
        if isinstance(driver_exec, tuple):
            # Bazı versiyonlarda (node_exe, cli_js) tuple döner
            node_exe, cli_js = driver_exec
            subprocess.run(
                [str(node_exe), str(cli_js), "install", "chromium"],
                check=True, timeout=300
            )
        else:
            subprocess.run(
                [str(driver_exec), "install", "chromium"],
                check=True, timeout=300
            )
        logger.info("✅ Chromium başarıyla indirildi!")
        return True, None
    except Exception:
        # Fallback — doğrudan subprocess ile çalıştır
        try:
            subprocess.run(
                [sys.executable, "-m", "playwright", "install", "chromium"],
                check=True, timeout=300
            )
            logger.info("✅ Chromium başarıyla indirildi! (fallback)")
            return True, None
        except Exception as e2:
            return False, f"Chromium indirilemedi: {e2}"


def _browser_login_sync(account_id: int, username: str, proxy_url: str | None = None) -> dict:
    """Senkron tarayıcı giriş işlemi."""
    # Chromium kontrolü — yoksa otomatik indir
    ok, err = _ensure_chromium()
    if not ok:
        return {"success": False, "error": err}

    from playwright.sync_api import sync_playwright

    try:
        with sync_playwright() as p:
            # Proxy ayarı
            browser_args = {}
            if proxy_url:
                try:
                    parts = proxy_url.replace("http://", "").replace("https://", "")
                    if "@" in parts:
                        auth, server = parts.rsplit("@", 1)
                        user, pwd = auth.split(":", 1)
                        browser_args["proxy"] = {
                            "server": f"http://{server}",
                            "username": user,
                            "password": pwd,
                        }
                    else:
                        browser_args["proxy"] = {"server": f"http://{parts}"}
                except Exception:
                    pass

            # Tarayıcı başlat (headful — kullanıcı görecek)
            browser = p.chromium.launch(
                headless=False,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                ],
                **browser_args,
            )

            context = browser.new_context(
                viewport={"width": 430, "height": 932},
                user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1",
                locale="tr-TR",
            )

            page = context.new_page()
            page.goto("https://www.instagram.com/accounts/login/", wait_until="networkidle", timeout=30000)

            # Eğer username biliyorsak doldur
            try:
                page.fill('input[name="username"]', username, timeout=5000)
            except Exception:
                pass

            logger.info(f"🌐 @{username} için tarayıcı penceresi açıldı — giriş bekleniyor...")

            # Kullanıcı giriş yapana kadar bekle (max 5 dk)
            # Giriş başarılı olduğunda URL değişir veya ana sayfaya yönlenir
            try:
                page.wait_for_url(
                    lambda url: "instagram.com" in url and "/accounts/login" not in url,
                    timeout=300000,  # 5 dakika
                )
            except Exception:
                browser.close()
                return {"success": False, "error": "Giriş zaman aşımına uğradı (5 dk)"}

            # Kısa bekleme — sayfanın tam yüklenmesi için
            page.wait_for_timeout(3000)

            # Cookie'leri al
            cookies = context.cookies()
            ig_cookies = [c for c in cookies if "instagram.com" in c.get("domain", "")]

            if not ig_cookies:
                browser.close()
                return {"success": False, "error": "Instagram cookie'leri alınamadı"}

            # session_id ve csrftoken kontrol
            cookie_dict = {c["name"]: c["value"] for c in ig_cookies}
            session_id = cookie_dict.get("sessionid", "")

            if not session_id:
                browser.close()
                return {"success": False, "error": "sessionid cookie'si bulunamadı — giriş başarısız"}

            # Cookie'leri dosyaya kaydet
            session_file = SESSIONS_DIR / f"{username}_browser.json"
            with open(session_file, "w") as f:
                json.dump({
                    "cookies": ig_cookies,
                    "cookie_dict": cookie_dict,
                    "session_id": session_id,
                    "username": username,
                    "account_id": account_id,
                }, f, indent=2)

            # instagrapi session oluştur (cookie'den)
            try:
                _create_instagrapi_session(username, cookie_dict)
            except Exception as e:
                logger.warning(f"instagrapi session oluşturulamadı: {e}")

            browser.close()

            logger.info(f"✅ @{username} tarayıcı ile giriş başarılı!")
            return {
                "success": True,
                "username": username,
                "session_id": session_id,
                "message": f"@{username} tarayıcı ile giriş başarılı",
            }

    except Exception as e:
        logger.error(f"Tarayıcı giriş hatası @{username}: {e}")
        return {"success": False, "error": str(e)[:200]}


def _create_instagrapi_session(username: str, cookie_dict: dict):
    """Cookie'lerden instagrapi session dosyası oluşturur."""
    from instagrapi import Client

    cl = Client()
    cl.delay_range = [1, 3]

    # Cookie'leri set et
    session_data = {
        "uuids": {
            "phone_id": cl.phone_id,
            "uuid": cl.uuid,
            "client_session_id": cl.client_session_id,
            "advertising_id": cl.advertising_id,
            "android_device_id": cl.android_device_id,
            "request_id": cl.request_id,
            "tray_session_id": cl.tray_session_id,
        },
        "cookies": cookie_dict,
        "authorization_data": {
            "ds_user_id": cookie_dict.get("ds_user_id", ""),
            "sessionid": cookie_dict.get("sessionid", ""),
            "mid": cookie_dict.get("mid", ""),
        },
    }

    session_file = SESSIONS_DIR / f"{username}.json"
    with open(session_file, "w") as f:
        json.dump(session_data, f, indent=2)
