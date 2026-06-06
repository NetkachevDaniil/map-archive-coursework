from urllib.parse import quote, unquote

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response

from app.services.storage_service import storage_service

router = APIRouter(tags=["files"])


@router.get("/files/remote")
def serve_remote_file(url: str = Query(..., min_length=8)):
    target = unquote(url)
    if not target.startswith(("http://", "https://")):
        raise HTTPException(status_code=400, detail="Некорректный URL")
    try:
        data, content_type = storage_service.read_bytes(target)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Не удалось загрузить изображение: {exc}") from exc

    return Response(
        content=data,
        media_type=content_type,
        headers={"Cache-Control": "public, max-age=3600"},
    )


@router.get("/files/{file_path:path}")
def serve_stored_file(file_path: str):
    try:
        data, content_type = storage_service.read_bytes(file_path)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Файл не найден") from None
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Не удалось загрузить файл: {exc}") from exc

    return Response(
        content=data,
        media_type=content_type,
        headers={"Cache-Control": "public, max-age=86400"},
    )
