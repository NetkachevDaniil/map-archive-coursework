#!/bin/bash
# Применяет S3-ключи из файла s3_keys.env к /opt/orientmaps/.env
set -euo pipefail
cd /opt/orientmaps
python3 <<'PY'
from pathlib import Path

patch = {}
for line in Path("s3_keys.env").read_text(encoding="utf-8").splitlines():
    line = line.strip()
    if not line or line.startswith("#") or "=" not in line:
        continue
    k, v = line.split("=", 1)
    patch[k.strip()] = v.strip()

env_path = Path(".env")
lines = env_path.read_text(encoding="utf-8").splitlines()
out = []
seen = set()
for line in lines:
    if "=" in line and not line.strip().startswith("#"):
        key = line.split("=", 1)[0].strip()
        if key in patch:
            out.append(f"{key}={patch[key]}")
            seen.add(key)
            continue
    out.append(line)
for key, value in patch.items():
    if key not in seen:
        out.append(f"{key}={value}")
env_path.write_text("\n".join(out) + "\n", encoding="utf-8")
print("Updated keys:", ", ".join(sorted(patch)))
PY
docker compose restart web
