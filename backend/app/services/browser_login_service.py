# services/browser_login_service.py — Selenium Edge ile Instagram girişi
"""
Selenium + Microsoft Edge ile tarayıcı penceresi açar,
kullanıcı giriş yapar, cookie'ler ve session bilgisi kaydedilir.

Edge her Windows 10/11'de varsayılan olarak yüklü.
EdgeDriver otomatik olarak Selenium Manager tarafından indirilir.
"""
import asyncio
import json
import logging
import time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

from app.config import settings as app_settings

logger = logging.getLogger(__name__)
_pool = ThreadPoolExecutor(max_workers=2)

SESSIONS_DIR = app_settings.SESSIONS_DIR
SESSIONS_DIR.mkdir(parents=True, exist_ok=True)


async def browser_login(account_id: int, username: str, proxy_url: str | None = None) -> dict:
    """
    Selenium Edge ile Instagram tarayıcı girişi.
    Tarayıcı penceresi açar, kullanıcı giriş yapar,
    Instagram cookie'leri kaydedilir.
    """
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        _pool, _browser_login_sync, account_id, username, proxy_url
    )


def _browser_login_sync(account_id: int, username: str, proxy_url: str | None = None) -> dict:
    """Senkron tarayıcı giriş işlemi — Selenium Edge."""
    try:
        from selenium import webdriver
        from selenium.webdriver.edge.options import Options
        from selenium.webdriver.edge.service import Service
        from selenium.webdriver.common.by import By
    except ImportError:
        return {"success": False, "error": "Selenium yüklü değil."}

    driver = None
    try:
        # Edge seçenekleri
        options = Options()
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--window-size=430,932")
        options.add_argument("--lang=tr-TR")

        # Bot tespitini engelle
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)

        # Mobil User-Agent
        options.add_argument(
            "--user-agent=Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) "
            "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 "
            "Mobile/15E148 Safari/604.1"
        )

        # Proxy ayarı
        if proxy_url:
            try:
                clean = proxy_url.replace("http://", "").replace("https://", "")
                if "@" in clean:
                    # user:pass@host:port formatı — Edge proxy auth desteklemez
                    # doğrudan host:port kullan
                    _, server = clean.rsplit("@", 1)
                    options.add_argument(f"--proxy-server=http://{server}")
                else:
                    options.add_argument(f"--proxy-server=http://{clean}")
            except Exception:
                pass

        # Selenium Manager otomatik olarak EdgeDriver indirir
        logger.info(f"🌐 @{username} için Edge tarayıcı başlatılıyor...")
        driver = webdriver.Edge(options=options)

        # Bot tespitinden kaçınmak için navigator.webdriver'ı gizle
        driver.execute_cdp_cmd(
            "Page.addScriptToEvaluateOnNewDocument",
            {"source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"},
        )

        # Instagram login sayfasına git
        driver.get("https://www.instagram.com/accounts/login/")

        # Sayfanın yüklenmesini bekle
        time.sleep(3)

        # Username doldur
        try:
            username_input = driver.find_element(By.CSS_SELECTOR, 'input[name="username"]')
            username_input.clear()
            username_input.send_keys(username)
        except Exception:
            pass

        logger.info(f"🌐 @{username} için tarayıcı penceresi açıldı — giriş bekleniyor...")

        # Kullanıcının giriş yapmasını bekle (max 5 dk)
        timeout = 300  # 5 dakika
        start = time.time()
        logged_in = False

        while time.time() - start < timeout:
            current_url = driver.current_url
            if "instagram.com" in current_url and "/accounts/login" not in current_url:
                logged_in = True
                break
            time.sleep(2)

        if not logged_in:
            driver.quit()
            return {"success": False, "error": "Giriş zaman aşımına uğradı (5 dk)"}

        # Sayfanın tam yüklenmesi için bekle
        time.sleep(3)

        # Cookie'leri al
        cookies = driver.get_cookies()
        ig_cookies = [c for c in cookies if "instagram.com" in c.get("domain", "")]

        if not ig_cookies:
            driver.quit()
            return {"success": False, "error": "Instagram cookie'leri alınamadı"}

        # Cookie dict oluştur
        cookie_dict = {c["name"]: c["value"] for c in ig_cookies}
        session_id = cookie_dict.get("sessionid", "")

        if not session_id:
            driver.quit()
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

        # instagrapi session oluştur
        try:
            _create_instagrapi_session(username, cookie_dict)
        except Exception as e:
            logger.warning(f"instagrapi session oluşturulamadı: {e}")

        driver.quit()

        logger.info(f"✅ @{username} tarayıcı ile giriş başarılı!")
        return {
            "success": True,
            "username": username,
            "session_id": session_id,
            "message": f"@{username} tarayıcı ile giriş başarılı",
        }

    except Exception as e:
        logger.error(f"Tarayıcı giriş hatası @{username}: {e}")
        if driver:
            try:
                driver.quit()
            except Exception:
                pass
        return {"success": False, "error": str(e)[:200]}


def _create_instagrapi_session(username: str, cookie_dict: dict):
    """Cookie'lerden instagrapi session dosyası oluşturur."""
    from instagrapi import Client

    cl = Client()
    cl.delay_range = [1, 3]

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
