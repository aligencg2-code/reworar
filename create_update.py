"""
create_update.py — Demet Güncelleme Paketi Oluşturucu

Kullanım:
    python create_update.py 1.1.0 "Medya lightbox, caption yönetimi eklendi"

Bu script:
1. Backend .py dosyalarını ve frontend dist dosyalarını ZIP'ler
2. update_manifest.json dosyasını günceller
3. ZIP dosyasını updates/ klasörüne koyar
4. Railway'e deploy ettiğinizde müşteriler otomatik güncellenir
"""
import sys
import os
import json
import zipfile
from datetime import date
from pathlib import Path

# Proje kök dizini
PROJECT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = PROJECT_DIR / "backend"
FRONTEND_OUT_DIR = PROJECT_DIR / "frontend" / "out"
MANIFEST_PATH = BACKEND_DIR / "update_manifest.json"
UPDATES_DIR = BACKEND_DIR / "updates"
UPDATE_SERVER_DIR = PROJECT_DIR / "update-server"
UPDATE_SERVER_UPDATES = UPDATE_SERVER_DIR / "updates"
UPDATE_SERVER_CONFIG = UPDATE_SERVER_DIR / "update_config.json"


def create_update_package(version: str, changelog: str = ""):
    """Güncelleme ZIP paketi oluşturur."""

    # updates/ klasörünü oluştur
    UPDATES_DIR.mkdir(parents=True, exist_ok=True)

    zip_path = UPDATES_DIR / f"update-{version}.zip"
    print(f"📦 Güncelleme paketi oluşturuluyor: {zip_path}")

    file_count = 0

    # PyInstaller dist kontrolü
    PYINSTALLER_DIST = BACKEND_DIR / "dist" / "Demet"
    if not PYINSTALLER_DIST.exists():
        print("❌ Backend PyInstaller build bulunamadı!")
        print(f"   Beklenen: {PYINSTALLER_DIST}")
        print("   Önce çalıştırın: python -m PyInstaller Demet.spec --noconfirm")
        sys.exit(1)

    pyinstaller_exe = PYINSTALLER_DIST / "Demet.exe"
    if not pyinstaller_exe.exists():
        print("❌ Demet.exe bulunamadı! PyInstaller build bozuk.")
        sys.exit(1)

    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        # Backend — PyInstaller build çıktısını ekle (Demet.exe + _internal/)
        # Electron'da backend resources/backend/ olarak çalışır
        print("📂 Backend (PyInstaller build) ekleniyor...")
        for root, dirs, files in os.walk(PYINSTALLER_DIST):
            for f in files:
                full_path = Path(root) / f
                arcname = "backend" / full_path.relative_to(PYINSTALLER_DIST)
                zf.write(full_path, str(arcname))
                file_count += 1

        # Frontend dist dosyalarını ekle
        if FRONTEND_OUT_DIR.exists():
            print("📂 Frontend dosyaları ekleniyor...")
            for root, dirs, files in os.walk(FRONTEND_OUT_DIR):
                for f in files:
                    full_path = Path(root) / f
                    arcname = "frontend-out" / full_path.relative_to(FRONTEND_OUT_DIR)
                    zf.write(full_path, str(arcname))
                    file_count += 1
        else:
            print("⚠️ Frontend out/ dizini bulunamadı. Önce 'npm run build' çalıştırın.")

    # ZIP boyutunu hesapla
    zip_size = zip_path.stat().st_size
    zip_size_mb = zip_size / (1024 * 1024)

    print(f"✅ {file_count} dosya eklendi ({zip_size_mb:.1f} MB)")

    # Manifest güncelle
    manifest = {
        "latest_version": version,
        "min_version": "1.0.0",
        "changelog": changelog,
        "download_url": "/api/update/download",
        "file_size": zip_size,
        "release_date": date.today().isoformat(),
        "force_update": False,
    }

    with open(MANIFEST_PATH, 'w', encoding='utf-8') as f:
        json.dump(manifest, f, indent=4, ensure_ascii=False)

    print(f"📋 Manifest güncellendi: v{version}")

    # Frontend package.json'daki versiyonu da güncelle
    pkg_json = PROJECT_DIR / "frontend" / "package.json"
    if pkg_json.exists():
        with open(pkg_json, 'r', encoding='utf-8') as f:
            pkg = json.load(f)
        pkg['version'] = version
        with open(pkg_json, 'w', encoding='utf-8') as f:
            json.dump(pkg, f, indent=2, ensure_ascii=False)
        print(f"📦 package.json versiyonu güncellendi: {version}")

    # Backend config'deki versiyonu güncelle
    config_path = BACKEND_DIR / "app" / "config.py"
    if config_path.exists():
        content = config_path.read_text(encoding='utf-8')
        import re
        new_content = re.sub(
            r'APP_VERSION:\s*str\s*=\s*"[^"]*"',
            f'APP_VERSION: str = "{version}"',
            content
        )
        config_path.write_text(new_content, encoding='utf-8')
        print(f"⚙️ config.py versiyonu güncellendi: {version}")

    # Update-server'a ZIP ve config kopyala (Railway deploy için)
    UPDATE_SERVER_UPDATES.mkdir(parents=True, exist_ok=True)

    import shutil
    server_zip = UPDATE_SERVER_UPDATES / f"update-{version}.zip"
    shutil.copy2(zip_path, server_zip)
    print(f"📦 ZIP update-server'a kopyalandı: {server_zip}")

    # update-server config güncelle
    server_config = {
        "latest_version": version,
        "min_version": "1.0.0",
        "changelog": changelog,
        "download_url": f"updates/update-{version}.zip",
        "file_size": zip_size,
        "release_date": date.today().isoformat(),
        "force_update": False,
    }
    with open(UPDATE_SERVER_CONFIG, 'w', encoding='utf-8') as f:
        json.dump(server_config, f, indent=2, ensure_ascii=False)
    print(f"⚙️ update-server/update_config.json güncellendi")

    print()
    print("=" * 50)
    print(f"🎉 Güncelleme paketi hazır!")
    print(f"   ZIP: {zip_path}")
    print(f"   Boyut: {zip_size_mb:.1f} MB")
    print(f"   Dosya: {file_count} adet")
    print()
    print("📤 Sonraki adım:")
    print(f"   cd update-server && railway up")
    print(f"   Müşteriler uygulamayı açtığında v{version} güncellemesini alacak!")
    print("=" * 50)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Kullanım: python create_update.py <sürüm> [değişiklik notu]")
        print("Örnek:    python create_update.py 1.1.0 'Medya lightbox, caption yönetimi eklendi'")
        sys.exit(1)

    version = sys.argv[1]
    changelog = sys.argv[2] if len(sys.argv) > 2 else ""

    create_update_package(version, changelog)
