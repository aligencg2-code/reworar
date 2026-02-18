# routers/update_server.py — Uzaktan güncelleme endpoint'leri
import json
from pathlib import Path
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from app.config import settings

router = APIRouter(prefix="/api/update", tags=["Güncelleme"])

MANIFEST_PATH = Path(__file__).resolve().parent.parent.parent / "update_manifest.json"
UPDATES_DIR = Path(__file__).resolve().parent.parent.parent / "updates"


def _load_manifest() -> dict:
    """Güncelleme manifest dosyasını yükler."""
    if not MANIFEST_PATH.exists():
        return {"latest_version": settings.APP_VERSION, "changelog": "", "force_update": False}
    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def _compare_versions(current: str, latest: str) -> bool:
    """Yeni sürüm varsa True döner."""
    try:
        current_parts = [int(x) for x in current.split(".")]
        latest_parts = [int(x) for x in latest.split(".")]
        return latest_parts > current_parts
    except (ValueError, AttributeError):
        return False


@router.get("/check")
async def check_for_update(current_version: str = "1.0.0"):
    """
    Güncel sürüm kontrolü yapar.
    Müşteri uygulaması her açılışta bu endpoint'i çağırır.
    """
    manifest = _load_manifest()
    latest = manifest.get("latest_version", settings.APP_VERSION)
    has_update = _compare_versions(current_version, latest)

    return {
        "update_available": has_update,
        "current_version": current_version,
        "latest_version": latest,
        "changelog": manifest.get("changelog", ""),
        "force_update": manifest.get("force_update", False),
        "download_url": manifest.get("download_url", ""),
        "file_size": manifest.get("file_size", 0),
        "release_date": manifest.get("release_date", ""),
    }


@router.get("/download")
async def download_update():
    """
    En son güncelleme ZIP dosyasını indirir.
    ZIP, değişen backend + frontend dosyalarını içerir.
    """
    manifest = _load_manifest()
    version = manifest.get("latest_version", "")

    # updates/ klasöründe ZIP ara
    zip_file = UPDATES_DIR / f"update-{version}.zip"
    if not zip_file.exists():
        # Fallback: herhangi bir zip dosyası var mı?
        zips = list(UPDATES_DIR.glob("update-*.zip")) if UPDATES_DIR.exists() else []
        if zips:
            zip_file = sorted(zips)[-1]  # En son
        else:
            raise HTTPException(status_code=404, detail="Güncelleme dosyası bulunamadı")

    return FileResponse(
        path=str(zip_file),
        filename=zip_file.name,
        media_type="application/zip",
    )


@router.get("/changelog")
async def get_changelog():
    """Değişiklik notlarını döner."""
    manifest = _load_manifest()
    return {
        "version": manifest.get("latest_version", settings.APP_VERSION),
        "changelog": manifest.get("changelog", ""),
        "release_date": manifest.get("release_date", ""),
    }
