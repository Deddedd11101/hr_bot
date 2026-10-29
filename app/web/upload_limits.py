from fastapi import HTTPException, UploadFile

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
    return content
