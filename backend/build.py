#!/usr/bin/env python3
"""
Demet — Build Script
Frontend build + PyInstaller ile tek EXE oluşturma.

Kullanım:
    python build.py          # Full build (frontend + EXE)
    python build.py --exe    # Sadece EXE build (frontend zaten build edilmişse)
"""
import subprocess
import shutil
import sys
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent
FRONTEND_DIR = ROOT.parent / "frontend"
BACKEND_DIR = ROOT
DIST_DIR = BACKEND_DIR / "dist"
FRONTEND_DIST = BACKEND_DIR / "frontend_dist"


def build_frontend():
    """Next.js static export build."""
    print("\n📦 Frontend build başlıyor...")

    if not FRONTEND_DIR.exists():
        print("⚠️  Frontend dizini bulunamadı, atlanıyor.")
        return False

    # npm run build
    result = subprocess.run(
        ["npx", "next", "build"],
        cwd=str(FRONTEND_DIR),
        shell=True,
    )
    if result.returncode != 0:
        print("❌ Frontend build başarısız!")
        return False

    # out/ -> backend/frontend_dist/
    out_dir = FRONTEND_DIR / "out"
    if not out_dir.exists():
        print("❌ Frontend out/ dizini bulunamadı!")
        return False

    if FRONTEND_DIST.exists():
        shutil.rmtree(FRONTEND_DIST)
    shutil.copytree(out_dir, FRONTEND_DIST)

    file_count = sum(1 for _ in FRONTEND_DIST.rglob("*") if _.is_file())
    print(f"✅ Frontend build tamamlandı ({file_count} dosya)")
    return True


def build_exe():
    """PyInstaller ile EXE oluştur."""
    print("\n🔨 PyInstaller build başlıyor...")

    if not FRONTEND_DIST.exists():
        print("⚠️  frontend_dist/ bulunamadı! Önce frontend build edin.")
        return False

    # PyInstaller komutu
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm",
        "--onedir",
        "--name", "Demet",
        "--add-data", f"{FRONTEND_DIST};frontend_dist",
        "--add-data", f"{BACKEND_DIR / 'app'};app",
        "--hidden-import", "uvicorn",
        "--hidden-import", "uvicorn.logging",
        "--hidden-import", "uvicorn.loops",
        "--hidden-import", "uvicorn.loops.auto",
        "--hidden-import", "uvicorn.protocols",
        "--hidden-import", "uvicorn.protocols.http",
        "--hidden-import", "uvicorn.protocols.http.auto",
        "--hidden-import", "uvicorn.protocols.websockets",
        "--hidden-import", "uvicorn.protocols.websockets.auto",
        "--hidden-import", "uvicorn.lifespan",
        "--hidden-import", "uvicorn.lifespan.on",
        "--hidden-import", "uvicorn.lifespan.off",
        "--hidden-import", "fastapi",
        "--hidden-import", "pydantic",
        "--hidden-import", "pydantic_settings",
        "--hidden-import", "sqlalchemy",
        "--hidden-import", "sqlalchemy.dialects.sqlite",
        "--hidden-import", "apscheduler",
        "--hidden-import", "apscheduler.schedulers.asyncio",
        "--hidden-import", "apscheduler.triggers.interval",
        "--hidden-import", "passlib.handlers.bcrypt",
        "--hidden-import", "jose",
        "--hidden-import", "cryptography",
        "--hidden-import", "email_validator",
        "--hidden-import", "httpx",
        "--hidden-import", "aiofiles",
        "--hidden-import", "PIL",
        "--hidden-import", "multipart",
        "--hidden-import", "dotenv",
        "--collect-all", "uvicorn",
        "--collect-all", "fastapi",
        "--collect-all", "starlette",
        "--collect-submodules", "app",
        "launcher.py",
    ]

    result = subprocess.run(cmd, cwd=str(BACKEND_DIR))
    if result.returncode != 0:
        print("❌ PyInstaller build başarısız!")
        return False

    print(f"\n✅ EXE build tamamlandı!")
    print(f"   📁 {DIST_DIR / 'Demet'}")
    print(f"   🚀 Demet.exe çalıştırın")
    return True


def main():
    args = sys.argv[1:]

    if "--exe" in args:
        build_exe()
    else:
        if build_frontend():
            build_exe()
        else:
            print("\n⚠️  Frontend build atlandı, sadece EXE build yapılıyor...")
            build_exe()


if __name__ == "__main__":
    main()
