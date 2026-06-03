import re


TERRITORY_PATTERN = re.compile(r"^\s*[^-]+-[^-]+-[^-]+\s*$")


def normalize_territory(raw: str | None) -> str:
    value = (raw or "").strip()
    if not value:
        return ""
    parts = [p.strip() for p in value.split("-")]
    if len(parts) != 3 or any(not p for p in parts):
        return value
    return "-".join(parts)


def is_valid_territory(raw: str | None) -> bool:
    return bool(TERRITORY_PATTERN.match((raw or "").strip()))
