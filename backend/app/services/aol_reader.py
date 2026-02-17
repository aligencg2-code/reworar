"""
AOL Webmail Email Reader — Playwright headless browser.
AOL login + inbox okuma + Instagram doğrulama kodu çıkarma.
"""
import re
import time
import asyncio
from playwright.async_api import async_playwright
from app.utils.logger import logger


class AOLEmailReader:
    """Playwright ile AOL webmail'e giriş yapıp Instagram doğrulama kodunu okur."""

    async def get_instagram_code(
        self, email: str, password: str, max_wait: int = 60
    ) -> str | None:
        """AOL'a giriş yap ve Instagram doğrulama kodunu döndür."""
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                context = await browser.new_context(
                    user_agent=(
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/120.0.0.0 Safari/537.36"
                    ),
                    viewport={"width": 1280, "height": 800},
                )
                page = await context.new_page()

                logged_in = await self._login(page, email, password)
                if not logged_in:
                    await browser.close()
                    return None

                code = await self._wait_for_code(page, max_wait)
                await browser.close()
                return code

        except Exception as e:
            logger.error(f"  ❌ AOL Playwright hatası: {e}")
            return None

    async def _login(self, page, email: str, password: str) -> bool:
        """AOL'a Playwright ile giriş yapar."""
        try:
            logger.info(f"  📧 AOL Playwright login: {email[:3]}***@aol.com")

            # 1) Login sayfası
            await page.goto(
                "https://login.aol.com/?src=mail&done=https://mail.aol.com/d/folders/1",
                wait_until="load",
                timeout=30000,
            )

            # 2) Username
            await page.wait_for_selector('input[name="username"]', state="visible", timeout=10000)
            await page.fill('input[name="username"]', email)
            await page.click('#login-signin')

            # 3) Password sayfasını bekle
            await asyncio.sleep(3)

            # Error kontrolü
            error_text = await page.evaluate("""() => {
                const err = document.querySelector('.error-msg, .error, [role="alert"]');
                return err ? err.innerText.trim() : null;
            }""")
            if error_text and ("recognize" in error_text.lower() or "tanı" in error_text.lower()):
                logger.warning(f"  ❌ AOL email tanınmıyor: {email}")
                return False

            # 4) Password — AOL id="login-passwd" kullanıyor
            pw_input = page.locator('#login-passwd')
            try:
                await pw_input.wait_for(state="visible", timeout=8000)
            except:
                # Alternatif selector dene
                pw_input = page.locator('input[type="password"]')
                try:
                    await pw_input.wait_for(state="visible", timeout=5000)
                except:
                    logger.warning(f"  ❌ AOL password alanı bulunamadı")
                    return False

            await pw_input.fill(password)

            # 5) Submit
            submit_btn = page.locator('#login-signin')
            await submit_btn.click()

            # 6) Sonucu bekle
            for _ in range(10):
                await asyncio.sleep(2)
                current_url = page.url
                if "mail.aol.com" in current_url and "login" not in current_url:
                    logger.info(f"  ✅ AOL giriş başarılı: {email}")
                    return True

            # Consent sayfası?
            if "consent" in page.url.lower():
                try:
                    agree_btn = page.locator('button:has-text("Agree"), button:has-text("Kabul"), input[name="agree"]')
                    await agree_btn.click(timeout=5000)
                    await asyncio.sleep(3)
                    if "mail.aol.com" in page.url:
                        logger.info(f"  ✅ AOL giriş başarılı (consent sonrası): {email}")
                        return True
                except:
                    pass

            # Hata kontrolü
            error_text2 = await page.evaluate("""() => {
                const err = document.querySelector('.error-msg, .error, [role="alert"]');
                return err ? err.innerText.trim() : null;
            }""")
            if error_text2:
                logger.warning(f"  ❌ AOL giriş hatası: {error_text2[:100]}")
            else:
                logger.warning(f"  ❌ AOL giriş belirsiz: {page.url[:80]}")
            return False

        except Exception as e:
            logger.error(f"  ❌ AOL login hatası: {e}")
            return False

    async def _wait_for_code(self, page, max_wait: int) -> str | None:
        """Inbox'ta Instagram doğrulama kodunu bekler."""
        start = time.time()
        attempt = 0

        while time.time() - start < max_wait:
            attempt += 1
            code = await self._find_code(page)
            if code:
                logger.info(f"  ✅ Instagram kodu bulundu: {code}")
                return code

            logger.info(f"  ⏳ Kod bekleniyor... (deneme {attempt}, {int(time.time() - start)}s)")
            await asyncio.sleep(5)

            # Yenile
            try:
                await page.reload(wait_until="load", timeout=10000)
                await asyncio.sleep(2)
            except:
                pass

        logger.warning(f"  ⚠️ Instagram kodu {max_wait}s içinde gelmedi")
        return None

    async def _find_code(self, page) -> str | None:
        """Sayfadaki Instagram emailinden kodu çıkarır."""
        try:
            body_text = await page.inner_text("body")

            if "instagram" not in body_text.lower():
                return None

            # Subject'ten veya inbox preview'dan kodu bul
            patterns = [
                r'(\d{6})\s+is your Instagram',
                r'(\d{6})\s+Instagram',
                r'(?:code|kod|Code)\s*[:：]?\s*(\d{6})',
                r'(\d{6})\s*(?:is your|verification)',
            ]

            for pattern in patterns:
                match = re.search(pattern, body_text)
                if match:
                    return match.group(match.lastindex)

            # Instagram emailine tıkla
            ig_link = page.locator('[data-test-id*="message"]:has-text("Instagram"), a:has-text("Instagram"), span:has-text("Instagram")')
            count = await ig_link.count()
            if count > 0:
                try:
                    await ig_link.first.click()
                    await asyncio.sleep(2)
                    msg_text = await page.inner_text("body")

                    for pattern in patterns:
                        match = re.search(pattern, msg_text)
                        if match:
                            return match.group(match.lastindex)

                    # Herhangi bir 6 haneli sayı
                    all_codes = re.findall(r'\b(\d{6})\b', msg_text)
                    if all_codes:
                        return all_codes[0]
                except:
                    pass

            return None

        except Exception as e:
            logger.warning(f"  ⚠️ Kod arama hatası: {e}")
            return None


def get_instagram_code_sync(email: str, password: str, max_wait: int = 60) -> str | None:
    """Senkron wrapper — thread pool'dan çağrılabilir."""
    reader = AOLEmailReader()
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(reader.get_instagram_code(email, password, max_wait))
    finally:
        loop.close()
