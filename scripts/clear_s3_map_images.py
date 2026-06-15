"""Удалить из S3 каталоги parsed/, maps/, avatars/ (не трогает ui/). Запуск на сервере:
docker compose exec web python scripts/clear_s3_map_images.py
"""
from app.core.config import get_settings

PREFIXES = ("parsed/", "maps/", "avatars/")


def main() -> None:
    settings = get_settings()
    if not settings.use_s3 or not settings.s3_bucket_name:
        print("USE_S3=false — нечего чистить в облаке.")
        return

    import boto3
    from botocore.client import Config

    client = boto3.client(
        "s3",
        endpoint_url=settings.s3_endpoint_url,
        aws_access_key_id=settings.s3_access_key_id,
        aws_secret_access_key=settings.s3_secret_access_key,
        region_name=settings.s3_region,
        config=Config(signature_version="s3v4"),
    )
    bucket = settings.s3_bucket_name
    deleted = 0

    for prefix in PREFIXES:
        token = None
        while True:
            kwargs = {"Bucket": bucket, "Prefix": prefix, "MaxKeys": 1000}
            if token:
                kwargs["ContinuationToken"] = token
            response = client.list_objects_v2(**kwargs)
            contents = response.get("Contents") or []
            if not contents:
                break
            keys = [{"Key": item["Key"]} for item in contents]
            client.delete_objects(Bucket=bucket, Delete={"Objects": keys})
            deleted += len(keys)
            print(f"Удалено {len(keys)} объектов из {prefix}")
            if not response.get("IsTruncated"):
                break
            token = response.get("NextContinuationToken")

    print(f"Готово. Всего удалено объектов: {deleted}")


if __name__ == "__main__":
    main()
