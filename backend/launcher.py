#!/usr/bin/env python3
"""
Demet Desktop Launcher
EXE giriş noktası — Lisans kontrolü + Server başlatma + Tarayıcı açma
"""
import os
import sys
import time
import webbrowser
import threading
import tkinter as tk
from tkinter import ttk, messagebox
from pathlib import Path

# PyInstaller uyumluluğu — çalışma dizini
if getattr(sys, 'frozen', False):
    BASE_DIR = Path(sys.executable).parent
    os.chdir(BASE_DIR)
    # PyInstaller bundle'dan _MEIPASS
    BUNDLE_DIR = Path(sys._MEIPASS) if hasattr(sys, '_MEIPASS') else BASE_DIR
else:
    BASE_DIR = Path(__file__).resolve().parent
    BUNDLE_DIR = BASE_DIR

# Python path ayarla
sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(BUNDLE_DIR))

PORT = 8000
URL = f"http://localhost:{PORT}"


class LicenseWindow:
    """Lisans aktivasyon penceresi."""

    def __init__(self):
        self.result = None
        self.root = tk.Tk()
        self.root.title("Demet — Lisans Aktivasyonu")
        self.root.geometry("600x400")
        self.root.resizable(False, False)
        self.root.configure(bg="#1a1a2e")

        # Center window
        self.root.update_idletasks()
        x = (self.root.winfo_screenwidth() // 2) - 300
        y = (self.root.winfo_screenheight() // 2) - 200
        self.root.geometry(f"+{x}+{y}")

        self._build_ui()

    def _build_ui(self):
        from app.license import get_hwid

        # Title
        tk.Label(
            self.root, text="🔐 Demet Lisans Aktivasyonu",
            font=("Segoe UI", 16, "bold"), fg="#e94560", bg="#1a1a2e",
        ).pack(pady=(25, 10))

        # HWID Frame
        hwid_frame = tk.Frame(self.root, bg="#16213e", padx=15, pady=10)
        hwid_frame.pack(fill="x", padx=30, pady=(5, 15))

        tk.Label(
            hwid_frame, text="Bu Makinenin HWID'si:",
            font=("Segoe UI", 9), fg="#a0a0a0", bg="#16213e",
        ).pack(anchor="w")

        hwid = get_hwid()
        hwid_entry = tk.Entry(
            hwid_frame, font=("Consolas", 11), fg="#00d2ff", bg="#0f3460",
            relief="flat", readonlybackground="#0f3460",
        )
        hwid_entry.insert(0, hwid)
        hwid_entry.config(state="readonly")
        hwid_entry.pack(fill="x", pady=(3, 0))

        # Info label
        tk.Label(
            self.root,
            text="Bu HWID'yi yöneticinize gönderin, size lisans anahtarı verilecektir.",
            font=("Segoe UI", 9), fg="#a0a0a0", bg="#1a1a2e", wraplength=500,
        ).pack(pady=(0, 10))

        # Key Input
        tk.Label(
            self.root, text="Lisans Anahtarı:",
            font=("Segoe UI", 10, "bold"), fg="#ffffff", bg="#1a1a2e",
        ).pack(anchor="w", padx=30)

        self.key_text = tk.Text(
            self.root, height=4, font=("Consolas", 10),
            fg="#ffffff", bg="#0f3460", relief="flat",
            insertbackground="#ffffff",
        )
        self.key_text.pack(fill="x", padx=30, pady=(3, 15))

        # Buttons
        btn_frame = tk.Frame(self.root, bg="#1a1a2e")
        btn_frame.pack(fill="x", padx=30)

        activate_btn = tk.Button(
            btn_frame, text="✅ Aktive Et", font=("Segoe UI", 11, "bold"),
            fg="#ffffff", bg="#e94560", relief="flat", padx=20, pady=8,
            cursor="hand2", command=self._activate,
        )
        activate_btn.pack(side="left")

        exit_btn = tk.Button(
            btn_frame, text="Çıkış", font=("Segoe UI", 10),
            fg="#a0a0a0", bg="#16213e", relief="flat", padx=15, pady=8,
            cursor="hand2", command=self._exit,
        )
        exit_btn.pack(side="right")

        # Status
        self.status_label = tk.Label(
            self.root, text="", font=("Segoe UI", 9),
            fg="#a0a0a0", bg="#1a1a2e",
        )
        self.status_label.pack(pady=(10, 0))

    def _activate(self):
        from app.license import activate_license

        key = self.key_text.get("1.0", "end").strip()
        if not key:
            self.status_label.config(text="⚠️ Lisans anahtarı giriniz", fg="#ffcc00")
            return

        result = activate_license(key)
        if result["valid"]:
            self.result = result
            messagebox.showinfo(
                "Başarılı",
                f"✅ Lisans aktive edildi!\n\nSahip: {result['owner']}\nKalan: {result['remaining_days']} gün",
            )
            self.root.destroy()
        else:
            self.status_label.config(text=f"❌ {result['error']}", fg="#ff4444")

    def _exit(self):
        self.root.destroy()
        sys.exit(0)

    def run(self):
        self.root.mainloop()
        return self.result


class SplashWindow:
    """Başlangıç splash ekranı."""

    def __init__(self, license_info):
        self.root = tk.Tk()
        self.root.title("Demet")
        self.root.geometry("400x250")
        self.root.resizable(False, False)
        self.root.overrideredirect(True)  # frameless
        self.root.configure(bg="#1a1a2e")

        # Center
        self.root.update_idletasks()
        x = (self.root.winfo_screenwidth() // 2) - 200
        y = (self.root.winfo_screenheight() // 2) - 125
        self.root.geometry(f"+{x}+{y}")

        # Content
        tk.Label(
            self.root, text="Demet", font=("Segoe UI", 28, "bold"),
            fg="#e94560", bg="#1a1a2e",
        ).pack(pady=(35, 5))

        tk.Label(
            self.root, text="Instagram İçerik Yönetim Sistemi",
            font=("Segoe UI", 10), fg="#a0a0a0", bg="#1a1a2e",
        ).pack()

        remaining = license_info.get("remaining_days", 0)
        tk.Label(
            self.root,
            text=f"👤 {license_info.get('owner', '')}  •  📅 {remaining} gün kaldı",
            font=("Segoe UI", 9), fg="#00d2ff", bg="#1a1a2e",
        ).pack(pady=(15, 20))

        self.status = tk.Label(
            self.root, text="⏳ Sunucu başlatılıyor...",
            font=("Segoe UI", 10), fg="#ffffff", bg="#1a1a2e",
        )
        self.status.pack()

        # Progress bar
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("red.Horizontal.TProgressbar", background="#e94560", troughcolor="#16213e")
        self.progress = ttk.Progressbar(
            self.root, length=300, mode="indeterminate",
            style="red.Horizontal.TProgressbar",
        )
        self.progress.pack(pady=(15, 0))
        self.progress.start(15)

    def update_status(self, text):
        self.status.config(text=text)
        self.root.update()

    def close(self):
        self.progress.stop()
        self.root.destroy()


def start_server():
    """Uvicorn sunucuyu başlat."""
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="127.0.0.1",
        port=PORT,
        log_level="warning",
    )


def wait_for_server(timeout=30):
    """Sunucunun hazır olmasını bekle."""
    import urllib.request
    start = time.time()
    while time.time() - start < timeout:
        try:
            urllib.request.urlopen(f"{URL}/health", timeout=2)
            return True
        except Exception:
            time.sleep(0.5)
    return False


def main():
    from app.license import verify_license

    # 1. Lisans kontrolü
    license_info = verify_license()

    if not license_info["valid"]:
        # Lisans penceresi göster
        win = LicenseWindow()
        license_info = win.run()
        if not license_info or not license_info.get("valid"):
            sys.exit(0)

    # 2. Splash göster + sunucu başlat
    splash = SplashWindow(license_info)

    # Server thread
    server_thread = threading.Thread(target=start_server, daemon=True)
    server_thread.start()

    splash.update_status("⏳ Sunucu başlatılıyor...")
    splash.root.update()

    # Server hazır olana kadar bekle
    ready = False
    for i in range(60):
        splash.root.update()
        time.sleep(0.5)
        try:
            import urllib.request
            urllib.request.urlopen(f"{URL}/health", timeout=1)
            ready = True
            break
        except Exception:
            pass

    if not ready:
        messagebox.showerror("Hata", "Sunucu başlatılamadı!")
        sys.exit(1)

    splash.update_status("✅ Hazır! Tarayıcı açılıyor...")
    splash.root.update()
    time.sleep(1)
    splash.close()

    # 3. Tarayıcıda aç
    webbrowser.open(URL)

    # 4. Konsol bekle (sunucu arka planda çalışır)
    print(f"\n{'='*50}")
    print(f"  🚀 Demet çalışıyor: {URL}")
    print(f"  👤 Lisans: {license_info.get('owner')} ({license_info.get('remaining_days')} gün)")
    print(f"  Kapatmak için bu pencereyi kapatın veya Ctrl+C")
    print(f"{'='*50}\n")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nKapatılıyor...")


if __name__ == "__main__":
    main()
