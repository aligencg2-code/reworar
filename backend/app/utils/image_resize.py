# utils/image_resize.py — Instagram boyutuna göre fotoğraf ayarlama
"""
Instagram desteklenen en-boy oranları:
  - 1:1  (kare)     → 1080x1080
  - 4:5  (portre)   → 1080x1350
  - 1.91:1 (yatay)  → 1080x566
Varsayılan: 4:5 (portre) — en çok etkileşim alan format.
"""
import os
import shutil
from pathlib import Path

try:
    from PIL import Image, ImageFilter
except ImportError:
    Image = None  # type: ignore


IG_MAX_WIDTH = 1080
IG_RATIOS = {
    "square":    (1080, 1080),   # 1:1
    "portrait":  (1080, 1350),   # 4:5
    "landscape": (1080, 566),    # 1.91:1
}


def resize_for_instagram(
    file_path: str | Path,
    mode: str = "portrait",
    quality: int = 95,
    output_path: str | Path | None = None,
) -> str:
    """
    Fotoğrafı Instagram boyutuna resize eder.

    Args:
        file_path: Kaynak dosya yolu
        mode: "square" | "portrait" | "landscape"
        quality: JPEG kalitesi (1-100)
        output_path: Çıktı yolu (None ise üzerine yazar)

    Returns:
        Çıktı dosya yolu
    """
    file_path = Path(file_path)

    if Image is None:
        # Pillow yüklü değilse dosyayı olduğu gibi döndür
        return str(file_path)

    # Video dosyalarını atla
    video_exts = {'.mp4', '.mov', '.avi', '.mkv', '.webm'}
    if file_path.suffix.lower() in video_exts:
        return str(file_path)

    target_w, target_h = IG_RATIOS.get(mode, IG_RATIOS["portrait"])

    try:
        img = Image.open(file_path)

        # EXIF rotation düzeltmesi
        try:
            from PIL import ImageOps
            img = ImageOps.exif_transpose(img)
        except Exception:
            pass

        # RGB'ye çevir (RGBA veya P mod desteği)
        if img.mode in ('RGBA', 'P', 'LA'):
            background = Image.new('RGB', img.size, (255, 255, 255))
            if img.mode == 'P':
                img = img.convert('RGBA')
            background.paste(img, mask=img.split()[-1] if 'A' in img.mode else None)
            img = background
        elif img.mode != 'RGB':
            img = img.convert('RGB')

        orig_w, orig_h = img.size
        target_ratio = target_w / target_h
        orig_ratio = orig_w / orig_h

        if abs(orig_ratio - target_ratio) < 0.05:
            # Oran zaten uygun — sadece resize
            img = img.resize((target_w, target_h), Image.LANCZOS)
        elif orig_ratio > target_ratio:
            # Daha geniş — yüksekliğe göre ölçekle, genişlikten kırp
            new_h = target_h
            new_w = int(orig_w * (target_h / orig_h))
            img = img.resize((new_w, new_h), Image.LANCZOS)
            left = (new_w - target_w) // 2
            img = img.crop((left, 0, left + target_w, target_h))
        else:
            # Daha uzun — genişliğe göre ölçekle, yükseklikten kırp
            new_w = target_w
            new_h = int(orig_h * (target_w / orig_w))
            img = img.resize((new_w, new_h), Image.LANCZOS)
            top = (new_h - target_h) // 2
            img = img.crop((0, top, target_w, top + target_h))

        # Kaydet
        out = Path(output_path) if output_path else file_path
        img.save(str(out), 'JPEG', quality=quality, optimize=True)
        return str(out)

    except Exception as e:
        # Hata durumunda orijinal dosyayı döndür
        return str(file_path)
