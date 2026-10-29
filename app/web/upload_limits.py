from fastapi import HTTPException, UploadFile
from io import BytesIO
from pathlib import Path
import warnings

from PIL import Image, UnidentifiedImageError

from ..config import settings


async def read_web_upload(upload: UploadFile) -> bytes:
    limit = settings.WEB_UPLOAD_MAX_BYTES
    if limit <= 0:
        raise HTTPException(status_code=503, detail="Загрузка файлов временно недоступна: неверный лимит.")
    detail = f"Максимальный размер файла: {limit / (1024 * 1024):g} МиБ."
    size = getattr(upload, "size", None)
    if isinstance(size, int) and size > limit:
        raise HTTPException(status_code=413, detail=detail)
    content = await upload.read(limit + 1)
    if len(content) > limit:
        raise HTTPException(status_code=413, detail=detail)
    filename = upload.filename or ""
    if filename in {".", ".."} or len(filename.encode("utf-8")) > 255 or any(ord(char) < 32 or ord(char) == 127 for char in filename) or any(char in filename for char in "/\\"):
        raise HTTPException(status_code=400, detail="Недопустимое имя файла: используйте имя без пути и управляющих символов.")
    return content


def validate_profile_photo(content: bytes, filename: str) -> None:
    formats = {".jpg": "JPEG", ".jpeg": "JPEG", ".png": "PNG", ".webp": "WEBP", ".gif": "GIF", ".bmp": "BMP", ".tif": "TIFF", ".tiff": "TIFF"}
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(content)) as image:
                if formats.get(Path(filename).suffix.lower()) != image.format:
                    raise ValueError("Image format mismatch")
                if image.width * image.height > 25_000_000:
                    raise ValueError("Image pixel limit")
                image.verify()
            with Image.open(BytesIO(content)) as image:
                image.load()
    except (UnidentifiedImageError, OSError, ValueError, SyntaxError, EOFError, Image.DecompressionBombError, Image.DecompressionBombWarning) as error:
        raise HTTPException(status_code=400, detail="Выберите корректную фотографию JPEG, PNG, WebP, GIF, BMP или TIFF до 25 мегапикселей.") from error
