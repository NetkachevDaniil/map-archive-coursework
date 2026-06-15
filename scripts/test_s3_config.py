from app.core.config import get_settings
import boto3
from botocore.client import Config

s = get_settings()
print("use_s3", s.use_s3)
print("bucket", s.s3_bucket_name)
print("endpoint", s.s3_endpoint_url)
print("region", s.s3_region)
print("key_id set", bool(s.s3_access_key_id))
print("secret set", bool(s.s3_secret_access_key))

client = boto3.client(
    "s3",
    endpoint_url=s.s3_endpoint_url,
    aws_access_key_id=s.s3_access_key_id,
    aws_secret_access_key=s.s3_secret_access_key,
    region_name=s.s3_region,
    config=Config(signature_version="s3v4"),
)
try:
    client.head_bucket(Bucket=s.s3_bucket_name)
    print("head_bucket OK")
except Exception as exc:
    print("head_bucket FAIL", exc)

try:
    client.put_object(Bucket=s.s3_bucket_name, Key="healthcheck/test.txt", Body=b"ok", ContentType="text/plain")
    print("put_object plain OK")
except Exception as exc:
    print("put_object plain FAIL", exc)
