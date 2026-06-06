import re

TERRITORY_PATTERN = re.compile(r"^\s*[^-]+-[^-]+-[^-]+\s*$")
FEDERAL_CITIES = {"Москва", "Санкт-Петербург", "Севастополь"}


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


def _extract_district_from_title(title: str) -> str | None:
    cleaned = re.sub(r"\(\d{4}\)", "", title or "")
    cleaned = re.sub(r"1\s*:\s*\d+", "", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" .,-—–")
    if not cleaned:
        return None
    for sep in [",", "—", "–", "|"]:
        if sep in cleaned:
            part = cleaned.split(sep)[0].strip()
            if 3 <= len(part) <= 80:
                return part
    if 3 <= len(cleaned) <= 80:
        return cleaned
    return None


def build_territory(region_name: str, title: str = "") -> str:
    region = (region_name or "Неизвестно").strip() or "Неизвестно"
    city = region if region in FEDERAL_CITIES else "Неизвестно"
    district = _extract_district_from_title(title) or "Неизвестно"
    value = normalize_territory(f"{region}-{city}-{district}")
    return value or f"{region}-{city}-{district}"
