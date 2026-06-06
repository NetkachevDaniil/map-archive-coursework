"""Upload site background image to S3 or local storage."""
from pathlib import Path

import boto3
from botocore.client import Config


BACKGROUND_KEY = "ui/site-background.jpg"
SOURCE = Path(r"D:\Downloads\Рисунок1.jpg")
ENV_PATH = Path(__file__).resolve().parents[1] / ".env"


def _read_env() -> dict[str, str]:
    values: dict[str, str] = {}
    if not ENV_PATH.exists():
        return values
    for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def main() -> None:
    if not SOURCE.exists():
        raise SystemExit(f"Source image not found: {SOURCE}")

    env = _read_env()
    use_s3 = env.get("USE_S3", "false").lower() == "true"
    data = SOURCE.read_bytes()

    if use_s3:
        client = boto3.client(
            "s3",
            endpoint_url=env.get("S3_ENDPOINT_URL"),
            aws_access_key_id=env.get("S3_ACCESS_KEY_ID"),
            aws_secret_access_key=env.get("S3_SECRET_ACCESS_KEY"),
            region_name=env.get("S3_REGION", "ru-central1"),
            config=Config(signature_version="s3v4"),
        )
        bucket = env["S3_BUCKET_NAME"]
        client.put_object(
            Bucket=bucket,
            Key=BACKGROUND_KEY,
            Body=data,
            ContentType="image/jpeg",
        )
        base = (env.get("S3_PUBLIC_BASE_URL") or f"{env['S3_ENDPOINT_URL'].rstrip('/')}/{bucket}").rstrip("/")
        url = f"{base}/{BACKGROUND_KEY}"
    else:
        upload_dir = Path(env.get("LOCAL_UPLOAD_DIR", "uploads"))
        dest = upload_dir / BACKGROUND_KEY
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        url = f"/media/{BACKGROUND_KEY}"

    print(f"Uploaded: {BACKGROUND_KEY}")
    print(f"Public URL: {url}")
    print(f"Add to .env: SITE_BACKGROUND_URL={url}")


if __name__ == "__main__":
    main()
