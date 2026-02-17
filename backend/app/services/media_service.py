# services/media_service.py — Medya işleme servisi (boyutlandırma, optimizasyon)
import uuid
import shutil
from pathlib import Path
from PIL import Image
from app.config import settings
from app.utils.logger import logger

# Instagram aspect ratio boyutları
ASPECT_RATIOS = {
    "1:1": (1080, 1080),
    "4:5": (1080, 1350),
    "9:16": (1080, 1920),
    "16:9": (1080, 608),
}

MAX_FILE_SIZE_BYTES = 8 * 1024 * 1024  # 8MB Instagram limiti


class MediaService:
    """Görsel boyutlandırma, optimizasyon ve organizasyon servisi."""

    def generate_filename(self, original: str, prefix: str = "") -> str:
        """Benzersiz dosya adı üretir."""
        ext = Path(original).suffix.lower()
        uid = uuid.uuid4().hex[:12]
        return f"{prefix}{uid}{ext}" if prefix else f"{uid}{ext}"

    def get_upload_path(self, media_type: str, filename: str) -> Path:
        """Medya türüne göre yükleme yolunu döndürür."""
        type_dirs = {
            "photo": "photos",
            "video": "videos",
            "story": "stories",
            "reels": "reels",
            "profile": "photos",
        }
        sub_dir = type_dirs.get(media_type, "photos")
        return settings.UPLOAD_DIR / sub_dir / filename

    def resize_image(
        self, image_path: str, aspect_ratio: str = "1:1", quality: int = 90
    ) -> str:
        """Görseli belirtilen aspect ratio'ya göre boyutlandırır."""
        target_size = ASPECT_RATIOS.get(aspect_ratio)
        if not target_size:
            raise ValueError(f"Geçersiz aspect ratio: {aspect_ratio}")

        with Image.open(image_path) as img:
            # EXIF rotasyonunu düzelt
            img = self._fix_orientation(img)

            target_w, target_h = target_size
            img_w, img_h = img.size

            # Crop + resize stratejisi (center crop)
            img_ratio = img_w / img_h
            target_ratio = target_w / target_h

            if img_ratio > target_ratio:
                # Görsel daha geniş — yanlardan kırp
                new_w = int(img_h * target_ratio)
                offset = (img_w - new_w) // 2
                img = img.crop((offset, 0, offset + new_w, img_h))
            else:
                # Görsel daha uzun — üst-alttan kırp
                new_h = int(img_w / target_ratio)
                offset = (img_h - new_h) // 2
                img = img.crop((0, offset, img_w, offset + new_h))

            img = img.resize(target_size, Image.Resampling.LANCZOS)

            # Kaydet
            output_path = str(Path(image_path).with_suffix(".jpg"))
            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")
            img.save(output_path, "JPEG", quality=quality, optimize=True)
            logger.info(f"Görsel boyutlandırıldı: {aspect_ratio} → {output_path}")
            return output_path

    def optimize_image(self, image_path: str, max_quality: int = 85) -> str:
        """Görseli Instagram limitlerine uygun boyuta optimize eder."""
        with Image.open(image_path) as img:
            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")

            output_path = str(Path(image_path).with_suffix(".jpg"))
            quality = max_quality

            # Dosya boyutu limiti altına inene kadar kaliteyi azalt
            while quality > 30:
                img.save(output_path, "JPEG", quality=quality, optimize=True)
                size = Path(output_path).stat().st_size
                if size <= MAX_FILE_SIZE_BYTES:
                    break
                quality -= 5

            logger.info(
                f"Görsel optimize edildi: {Path(output_path).stat().st_size / 1024:.0f}KB"
            )
            return output_path

    def create_thumbnail(self, image_path: str) -> str:
        """Önizleme görseli oluşturur."""
        thumb_size = settings.THUMBNAIL_SIZE
        filename = f"thumb_{Path(image_path).stem}.jpg"
        thumb_path = settings.UPLOAD_DIR / "thumbnails" / filename

        with Image.open(image_path) as img:
            img.thumbnail(thumb_size, Image.Resampling.LANCZOS)
            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")
            img.save(str(thumb_path), "JPEG", quality=80)

        return str(thumb_path)

    def get_image_dimensions(self, image_path: str) -> tuple[int, int]:
        """Görsel boyutlarını döndürür."""
        with Image.open(image_path) as img:
            return img.size

    def _fix_orientation(self, img: Image.Image) -> Image.Image:
        """EXIF rotasyon bilgisine göre görseli düzeltir."""
        try:
            from PIL import ExifTags
            exif = img._getexif()
            if exif:
                orientation_key = None
                for key, val in ExifTags.TAGS.items():
                    if val == "Orientation":
                        orientation_key = key
                        break
                if orientation_key and orientation_key in exif:
                    orientation = exif[orientation_key]
                    rotations = {3: 180, 6: 270, 8: 90}
                    if orientation in rotations:
                        img = img.rotate(rotations[orientation], expand=True)
        except (AttributeError, TypeError):
            pass
        return img


media_service = MediaService()
