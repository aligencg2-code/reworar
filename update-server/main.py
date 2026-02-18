"""
Demet Update Server — Railway'de çalışan güncelleme API'si.
Electron uygulaması bu sunucuyu kontrol ederek yeni sürüm olup olmadığını öğrenir.

Deploy: Railway'e bu klasörü deploy edin.
Güncelleme yayınlamak için:
  1. update_config.json dosyasını düzenleyin
  2. ZIP'i updates/ klasörüne koyun
  3. railway up ile deploy edin
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse, FileResponse
from pathlib import Path
import json
import os

app = FastAPI(title="Demet Update Server", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

SERVER_DIR = Path(__file__).parent
CONFIG_FILE = SERVER_DIR / "update_config.json"
UPDATES_DIR = SERVER_DIR / "updates"


def load_config() -> dict:
    """Güncelleme yapılandırmasını yükler."""
    if CONFIG_FILE.exists():
        return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    return {
        "latest_version": "1.0.0",
        "changelog": "",
        "download_url": "",
        "force_update": False,
        "min_version": "1.0.0",
    }


def version_tuple(v: str):
    """Sürüm string'ini karşılaştırma için tuple'a çevirir."""
    return tuple(int(x) for x in v.replace("v", "").split("."))


@app.get("/")
async def root():
    config = load_config()
    return {
        "service": "Demet Update Server",
        "status": "online",
        "latest_version": config.get("latest_version", "1.0.0"),
    }


@app.get("/api/update/check")
async def check_update(current_version: str = "1.0.0"):
    """
    Güncelleme kontrolü.
    Electron uygulaması bu endpoint'i çağırır.
    """
    config = load_config()
    latest = config.get("latest_version", "1.0.0")

    try:
        needs_update = version_tuple(current_version) < version_tuple(latest)
    except (ValueError, TypeError):
        needs_update = False

    return {
        "update_available": needs_update,
        "current_version": current_version,
        "latest_version": latest,
        "changelog": config.get("changelog", ""),
        "download_url": f"/api/update/download",
        "force_update": config.get("force_update", False),
        "file_size": config.get("file_size", 0),
        "release_date": config.get("release_date", ""),
    }


@app.get("/api/update/download")
async def download_update():
    """
    Güncelleme ZIP dosyasını indirir.
    updates/ klasöründeki en güncel ZIP'i serve eder.
    Eğer download_url harici bir link ise redirect yapar.
    """
    config = load_config()
    download_url = config.get("download_url", "")

    # Harici URL ise redirect
    if download_url.startswith("http"):
        return RedirectResponse(url=download_url)

    # updates/ klasöründe sürüme göre ZIP ara
    version = config.get("latest_version", "")
    if version and UPDATES_DIR.exists():
        zip_file = UPDATES_DIR / f"update-{version}.zip"
        if zip_file.exists():
            return FileResponse(
                path=str(zip_file),
                media_type="application/zip",
                filename=f"demet-update-{version}.zip",
            )

        # Fallback: herhangi bir zip dosyası var mı?
        zips = sorted(UPDATES_DIR.glob("update-*.zip"))
        if zips:
            latest_zip = zips[-1]
            return FileResponse(
                path=str(latest_zip),
                media_type="application/zip",
                filename=latest_zip.name,
            )

    return JSONResponse(
        status_code=404,
        content={"error": "Güncelleme dosyası bulunamadı"},
    )


@app.get("/api/update/info")
async def update_info():
    """Mevcut güncelleme bilgisi."""
    config = load_config()
    has_zip = False
    if UPDATES_DIR.exists():
        has_zip = len(list(UPDATES_DIR.glob("update-*.zip"))) > 0
    return {
        "config": config,
        "zip_available": has_zip,
    }


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
