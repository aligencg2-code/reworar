#!/usr/bin/env python3
"""
Demet - Lisans Anahtarı Üretici (Admin Aracı)

Kullanım:
    python admin_keygen.py --hwid ABC123 --days 30 --owner "Müşteri Adı"
    python admin_keygen.py --show-hwid          # Bu makinenin HWID'sini göster
    python admin_keygen.py --verify KEY_TEXT     # Bir anahtarı doğrula
"""
import argparse
import sys
import os

# Modül yolunu ayarla
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.license import generate_license_key, verify_license, get_hwid


def main():
    parser = argparse.ArgumentParser(
        description="Demet Lisans Anahtarı Üretici",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Örnekler:
  python admin_keygen.py --show-hwid
  python admin_keygen.py --hwid ABC123DEF456 --days 30 --owner "Ali Veli"
  python admin_keygen.py --hwid ABC123DEF456 --days 365 --owner "Premium Müşteri"
  python admin_keygen.py --verify "gAAAAABn..."
        """,
    )

    parser.add_argument("--show-hwid", action="store_true", help="Bu makinenin HWID'sini göster")
    parser.add_argument("--hwid", type=str, help="Hedef makinenin HWID'si")
    parser.add_argument("--days", type=int, default=30, help="Lisans süresi (gün) [varsayılan: 30]")
    parser.add_argument("--owner", type=str, default="Müşteri", help="Lisans sahibi adı")
    parser.add_argument("--verify", type=str, help="Bir lisans anahtarını doğrula")

    args = parser.parse_args()

    if args.show_hwid:
        hwid = get_hwid()
        print(f"\n{'='*50}")
        print(f"  Bu Makinenin HWID'si:")
        print(f"  {hwid}")
        print(f"{'='*50}\n")
        return

    if args.verify:
        result = verify_license(args.verify)
        print(f"\n{'='*50}")
        if result["valid"]:
            print(f"  ✅ Lisans GEÇERLİ")
            print(f"  Sahip: {result['owner']}")
            print(f"  Kalan gün: {result['remaining_days']}")
        else:
            print(f"  ❌ Lisans GEÇERSİZ")
            print(f"  Hata: {result['error']}")
        print(f"{'='*50}\n")
        return

    if not args.hwid:
        parser.print_help()
        print("\n⚠️  --hwid parametresi gerekli!")
        print("    Müşterinin HWID'sini öğrenmek için:")
        print("    Müşteriye programı çalıştırmasını söyleyin, HWID ekranda gösterilir.")
        return

    # Key üret
    key = generate_license_key(
        hwid=args.hwid,
        days=args.days,
        owner=args.owner,
    )

    print(f"\n{'='*60}")
    print(f"  🔑 Demet Lisans Anahtarı Üretildi")
    print(f"{'='*60}")
    print(f"  Sahip  : {args.owner}")
    print(f"  HWID   : {args.hwid}")
    print(f"  Süre   : {args.days} gün")
    print(f"{'='*60}")
    print(f"\n  ANAHTAR:")
    print(f"  {key}")
    print(f"\n{'='*60}")
    print(f"  Bu anahtarı müşteriye gönderin.")
    print(f"  Müşteri programı açtığında bu anahtarı girecek.")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
