import mimetypes
import uuid
from pathlib import Path

import boto3
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
            self.s3_client.put_object(
                Bucket=self.settings.s3_bucket_name,
                Key=key,
                Body=data,
                ContentType=content_type,
            )
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
            self.s3_client.put_object(
                Bucket=self.settings.s3_bucket_name,
                Key=key,
                Body=content,
                ContentType=content_type,
            )
            return key

        local_path = Path(self.settings.local_upload_dir) / key
        local_path.parent.mkdir(parents=True, exist_ok=True)
        local_path.write_bytes(content)
        return key

    def get_public_url(self, key: str) -> str:
        if key.startswith("http://") or key.startswith("https://"):
            return key
        if self.settings.use_s3:
            if self.settings.s3_public_base_url:
                return f"{self.settings.s3_public_base_url.rstrip('/')}/{key}"
            bucket = self.settings.s3_bucket_name
            endpoint = (self.settings.s3_endpoint_url or "").rstrip("/")
            return f"{endpoint}/{bucket}/{key}"
        return f"/media/{key}"


storage_service = StorageService()
