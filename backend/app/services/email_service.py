# services/email_service.py — IMAP ile email'den otomatik 2FA/checkpoint kodu okuma
import imaplib
import email
import re
import time
import asyncio
from email.header import decode_header
from datetime import datetime, timedelta
from typing import Optional

from app.utils.logger import logger


# Popüler email sağlayıcıların IMAP sunucuları
IMAP_SERVERS = {
    "gmail.com": "imap.gmail.com",
    "googlemail.com": "imap.gmail.com",
    "outlook.com": "imap-mail.outlook.com",
    "hotmail.com": "imap-mail.outlook.com",
    "live.com": "imap-mail.outlook.com",
    "yahoo.com": "imap.mail.yahoo.com",
    "yahoo.co.uk": "imap.mail.yahoo.com",
    "yandex.com": "imap.yandex.com",
    "yandex.ru": "imap.yandex.com",
    "mail.ru": "imap.mail.ru",
    "aol.com": "imap.aol.com",
    "icloud.com": "imap.mail.me.com",
    "me.com": "imap.mail.me.com",
    "zoho.com": "imap.zoho.com",
    "protonmail.com": "127.0.0.1",  # Bridge gerekli
    "gmx.com": "imap.gmx.com",
    "gmx.net": "imap.gmx.net",
}


def _get_imap_server(email_addr: str) -> str:
    """Email adresinden IMAP sunucusunu belirler."""
    domain = email_addr.split("@")[-1].lower()
    return IMAP_SERVERS.get(domain, f"imap.{domain}")


def _decode_subject(subject_raw) -> str:
    """Email konusunu decode eder."""
    if not subject_raw:
        return ""
    decoded_parts = decode_header(subject_raw)
    result = []
    for part, charset in decoded_parts:
        if isinstance(part, bytes):
            result.append(part.decode(charset or "utf-8", errors="replace"))
        else:
            result.append(part)
    return " ".join(result)


def _extract_code_from_text(text: str) -> Optional[str]:
    """Email metninden doğrulama kodunu çıkarır."""
    # 6 haneli sayısal kodları ara (en yaygın format)
    patterns = [
        r'(?:code|kod|doğrulama|verification|güvenlik|security)\s*(?:is|:)?\s*(\d{6})',
        r'(\d{6})\s*(?:is your|kodunuz|doğrulama)',
        r'>\s*(\d{6})\s*<',  # HTML içinde
        r'(?:^|\s)(\d{6})(?:\s|$)',  # Tek başına 6 haneli
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
        if match:
            return match.group(1)

    # 8 haneli kodları da dene (bazı sağlayıcılar)
    match = re.search(r'(?:code|kod)\s*(?:is|:)?\s*(\d{8})', text, re.IGNORECASE)
    if match:
        return match.group(1)

    return None


def _get_email_body(msg) -> str:
    """Email mesajının gövdesini çıkarır."""
    body = ""

    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            if content_type in ("text/plain", "text/html"):
                try:
                    payload = part.get_payload(decode=True)
                    charset = part.get_content_charset() or "utf-8"
                    body += payload.decode(charset, errors="replace")
                except Exception:
                    continue
    else:
        try:
            payload = msg.get_payload(decode=True)
            charset = msg.get_content_charset() or "utf-8"
            body = payload.decode(charset, errors="replace")
        except Exception:
            pass

    return body


class EmailCodeReader:
    """IMAP ile email'den doğrulama kodu okuyucu."""

    def __init__(self, email_addr: str, email_password: str):
        self.email_addr = email_addr
        self.email_password = email_password
        self.imap_server = _get_imap_server(email_addr)

    def fetch_instagram_code(self, max_age_minutes: int = 10, max_retries: int = 6, retry_delay: int = 10) -> Optional[str]:
        """
        Instagram'dan gelen en son doğrulama kodunu email'den okur.

        Args:
            max_age_minutes: En fazla kaç dakika önceki emaili kabul et
            max_retries: Kaç kez deneyecek
            retry_delay: Denemeler arası bekleme (saniye)

        Returns:
            Doğrulama kodu veya None
        """
        for attempt in range(max_retries):
            try:
                code = self._try_fetch_code(max_age_minutes)
                if code:
                    logger.info(f"  📧 Email'den kod bulundu: {code} (deneme {attempt + 1})")
                    return code

                if attempt < max_retries - 1:
                    logger.info(f"  📧 Kod henüz gelmedi, {retry_delay}sn bekleniyor... (deneme {attempt + 1}/{max_retries})")
                    time.sleep(retry_delay)

            except imaplib.IMAP4.error as e:
                logger.error(f"  ❌ IMAP hatası: {e}")
                return None
            except Exception as e:
                logger.error(f"  ❌ Email okuma hatası: {e}")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)

        logger.warning(f"  ⚠️ {max_retries} denemede kod bulunamadı")
        return None

    def _try_fetch_code(self, max_age_minutes: int) -> Optional[str]:
        """Tek seferde kod çekmeyi dener."""
        mail = imaplib.IMAP4_SSL(self.imap_server, 993, timeout=30)

        try:
            mail.login(self.email_addr, self.email_password)
            mail.select("INBOX")

            # Instagram'dan gelen son emailleri ara
            since_date = (datetime.utcnow() - timedelta(minutes=max_age_minutes)).strftime("%d-%b-%Y")

            # Farklı filtreler dene
            search_queries = [
                f'(FROM "security@mail.instagram.com" SINCE {since_date})',
                f'(FROM "no-reply@mail.instagram.com" SINCE {since_date})',
                f'(FROM "instagram" SINCE {since_date})',
            ]

            all_ids = []
            for query in search_queries:
                try:
                    status, data = mail.search(None, query)
                    if status == "OK" and data[0]:
                        ids = data[0].split()
                        all_ids.extend(ids)
                except Exception:
                    continue

            if not all_ids:
                return None

            # En son email'i kontrol et (son gelen önce)
            # Tekrarları kaldır ve sırala
            unique_ids = list(dict.fromkeys(all_ids))
            unique_ids.reverse()  # En yeniden en eskiye

            for msg_id in unique_ids[:5]:  # Son 5 email'i kontrol et
                try:
                    status, data = mail.fetch(msg_id, "(RFC822)")
                    if status != "OK":
                        continue

                    raw_email = data[0][1]
                    msg = email.message_from_bytes(raw_email)

                    # Email tarihi kontrolü
                    date_str = msg.get("Date", "")
                    subject = _decode_subject(msg.get("Subject", ""))

                    # Konu Instagram ile ilgili mi?
                    ig_keywords = ["instagram", "verification", "doğrulama", "security", "güvenlik", "code", "kod", "confirm"]
                    if not any(kw in subject.lower() for kw in ig_keywords):
                        # Gövdeyi de kontrol et
                        body = _get_email_body(msg)
                        if "instagram" not in body.lower():
                            continue
                    else:
                        body = _get_email_body(msg)

                    # Kodu çıkar
                    code = _extract_code_from_text(body)
                    if not code:
                        code = _extract_code_from_text(subject)

                    if code:
                        return code

                except Exception:
                    continue

            return None

        finally:
            try:
                mail.logout()
            except Exception:
                pass


async def fetch_instagram_code_async(
    email_addr: str, email_password: str,
    max_age_minutes: int = 10, max_retries: int = 6, retry_delay: int = 10
) -> Optional[str]:
    """Async wrapper — email kodu okumayı ayrı thread'de çalıştırır."""
    reader = EmailCodeReader(email_addr, email_password)

    # IMAP blocking olduğu için thread pool'da çalıştır
    loop = asyncio.get_event_loop()
    code = await loop.run_in_executor(
        None,
        reader.fetch_instagram_code,
        max_age_minutes,
        max_retries,
        retry_delay,
    )
    return code
