#!/usr/bin/env python3
"""
Demet Backend Server Entry Point
Uvicorn sunucu başlatma — Electron tarafından çağrılır
Lisans kontrolü Electron tarafında yapılır.
"""
import os
import sys
from pathlib import Path

# PyInstaller uyumluluğu
if getattr(sys, 'frozen', False):
    BASE_DIR = Path(sys.executable).parent
    os.chdir(BASE_DIR)
    BUNDLE_DIR = Path(sys._MEIPASS) if hasattr(sys, '_MEIPASS') else BASE_DIR
else:
    BASE_DIR = Path(__file__).resolve().parent
    BUNDLE_DIR = BASE_DIR

sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(BUNDLE_DIR))


def main():
    # Sunucuyu doğrudan başlat (lisans kontrolü Electron tarafında)
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="127.0.0.1",
        port=8000,
        log_level="warning",
    )


if __name__ == "__main__":
    main()

