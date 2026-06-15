from io import BytesIO
from pathlib import Path

from PIL import Image

from app.core.config import get_settings

_ALLOWED_EXTENSIONS = frozenset({".jpg", ".jpeg", ".png", ".gif", ".tif", ".tiff", ".webp"})


def read_upload_limited(file_obj, max_bytes: int | None = None) -> bytes:
    limit = max_bytes or get_settings().max_upload_bytes
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = file_obj.read(1024 * 1024)
        if not chunk:
            break
        total += len(chunk)
        if total > limit:
            raise ValueError(f"Файл слишком большой (максимум {limit // (1024 * 1024)} МБ)")
        chunks.append(chunk)
    return b"".join(chunks)


def _is_webp_payload(content: bytes) -> bool:
    return len(content) >= 12 and content[:4] == b"RIFF" and content[8:12] == b"WEBP"


def prepare_map_image(content: bytes, source_name: str, max_bytes: int | None = None) -> tuple[bytes, str]:
    limit = max_bytes or get_settings().max_upload_bytes
    if len(content) > limit:
        raise ValueError(f"Файл слишком большой (максимум {limit // (1024 * 1024)} МБ)")

    ext = Path(source_name).suffix.lower()
    if ext not in _ALLOWED_EXTENSIONS:
        ext = ".jpg"

    if ext == ".webp" or _is_webp_payload(content):
        image = Image.open(BytesIO(content))
        if image.mode in ("RGBA", "LA", "P"):
            image = image.convert("RGB")
        buffer = BytesIO()
        image.save(buffer, format="JPEG", quality=95, subsampling=0)
        return buffer.getvalue(), ".jpg"

    return content, ext
