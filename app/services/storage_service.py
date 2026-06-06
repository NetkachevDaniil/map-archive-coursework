import mimetypes
import uuid
from pathlib import Path
from urllib.parse import quote

import boto3
import httpx
from botocore.client import Config
from fastapi import UploadFile

from app.core.config import get_settings


class StorageService:
    def __init__(self) -> None:
        self.settings = get_settings()
        if self.settings.use_s3:
            self.s3_client = boto3.client(
                "s3",
                endpoint_url=self.settings.s3_endpoint_url,
                aws_access_key_id=self.settings.s3_access_key_id,
                aws_secret_access_key=self.settings.s3_secret_access_key,
                region_name=self.settings.s3_region,
                config=Config(signature_version="s3v4"),
            )
        else:
            self.s3_client = None
            Path(self.settings.local_upload_dir).mkdir(parents=True, exist_ok=True)

    def save_upload(self, upload: UploadFile, folder: str = "maps") -> str:
        ext = Path(upload.filename or "").suffix or ".jpg"
        key = f"{folder}/{uuid.uuid4()}{ext}"
        data = upload.file.read()
        content_type = upload.content_type or mimetypes.guess_type(upload.filename or "")[0] or "application/octet-stream"

        if self.settings.use_s3 and self.s3_client:
            put_args = {
                "Bucket": self.settings.s3_bucket_name,
                "Key": key,
                "Body": data,
                "ContentType": content_type,
            }
            try:
                put_args["ACL"] = "public-read"
                self.s3_client.put_object(**put_args)
            except Exception:
                put_args.pop("ACL", None)
                self.s3_client.put_object(**put_args)
            return key

        local_path = Path(self.settings.local_upload_dir) / key
        local_path.parent.mkdir(parents=True, exist_ok=True)
        local_path.write_bytes(data)
        return key

    def upload_bytes(self, content: bytes, filename: str, folder: str = "parsed") -> str:
        ext = Path(filename).suffix or ".jpg"
        key = f"{folder}/{uuid.uuid4()}{ext}"
        content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"

        if self.settings.use_s3 and self.s3_client:
            put_args = {
                "Bucket": self.settings.s3_bucket_name,
                "Key": key,
                "Body": content,
                "ContentType": content_type,
            }
            try:
                put_args["ACL"] = "public-read"
                self.s3_client.put_object(**put_args)
            except Exception:
                put_args.pop("ACL", None)
                self.s3_client.put_object(**put_args)
            return key

        local_path = Path(self.settings.local_upload_dir) / key
        local_path.parent.mkdir(parents=True, exist_ok=True)
        local_path.write_bytes(content)
        return key

    def read_bytes(self, key: str) -> tuple[bytes, str]:
        if key.startswith("http://") or key.startswith("https://"):
            headers = {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                ),
                "Accept": "image/avif,image/webp,image/apng,image/jpeg,image/*,*/*;q=0.8",
                "Accept-Language": "ru-RU,ru;q=0.9",
            }
            if "o-maps.spb.ru" in key:
                headers["Referer"] = "https://o-maps.spb.ru/"
            elif "githubusercontent.com" in key:
                headers["Referer"] = "https://github.com/"
            with httpx.Client(timeout=40, follow_redirects=True, headers=headers) as client:
                response = client.get(key)
                response.raise_for_status()
                content_type = response.headers.get("content-type") or mimetypes.guess_type(key)[0] or "application/octet-stream"
                return response.content, content_type

        if self.settings.use_s3 and self.s3_client:
            response = self.s3_client.get_object(Bucket=self.settings.s3_bucket_name, Key=key)
            body = response["Body"].read()
            content_type = response.get("ContentType") or mimetypes.guess_type(key)[0] or "application/octet-stream"
            return body, content_type

        local_path = Path(self.settings.local_upload_dir) / key
        if not local_path.is_file():
            raise FileNotFoundError(key)
        content_type = mimetypes.guess_type(str(local_path))[0] or "application/octet-stream"
        return local_path.read_bytes(), content_type

    def get_public_url(self, key: str) -> str:
        if key.startswith("http://") or key.startswith("https://"):
            return f"/files/remote?url={quote(key, safe='')}"
        return f"/files/{key.lstrip('/')}"


storage_service = StorageService()
