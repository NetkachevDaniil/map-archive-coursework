import re

UNKNOWN_PLACEHOLDER = "—"

COORDINATE_PATTERN = re.compile(
    r"^\s*-?\d{1,3}(?:\.\d+)?\s*,\s*-?\d{1,3}(?:\.\d+)?\s*$"
)
KNOWN_REGIONS = {
    "санкт-петербург",
    "москва",
    "ленинградская область",
    "московская область",
    "севастополь",
}


def normalize_coordinates(raw: str | None) -> str:
    return (raw or "").strip()


def normalize_region_name(raw: str | None) -> str:
    return (raw or "").strip()


def is_blank_or_unknown(value: str | None) -> bool:
    if value is None:
        return True
    stripped = value.strip()
    return not stripped or stripped == UNKNOWN_PLACEHOLDER


def store_optional_text(raw: str | None) -> str:
    value = (raw or "").strip()
    if not value or value == UNKNOWN_PLACEHOLDER:
        return UNKNOWN_PLACEHOLDER
    return value


def store_coordinates(raw: str | None) -> str:
    value = normalize_coordinates(raw)
    if not value or value == UNKNOWN_PLACEHOLDER:
        return UNKNOWN_PLACEHOLDER
    return value


def is_valid_coordinates(raw: str | None) -> bool:
    value = normalize_coordinates(raw)
    if not value or value == UNKNOWN_PLACEHOLDER:
        return True
    return bool(COORDINATE_PATTERN.match(value)) and len(value) <= 255


def is_valid_region_name(raw: str | None) -> bool:
    value = normalize_region_name(raw)
    return len(value) >= 2 and len(value) <= 120


def format_coordinates_from_bounds(bounds: list[tuple[float, float]]) -> str | None:
    if not bounds:
        return None
    lat = sum(point[0] for point in bounds) / len(bounds)
    lon = sum(point[1] for point in bounds) / len(bounds)
    return f"{lat:.5f}, {lon:.5f}"


def resolve_coordinates(
    *,
    bounds: list[tuple[float, float]] | None = None,
    raw: str | None = None,
) -> str | None:
    from_bounds = format_coordinates_from_bounds(bounds or [])
    if from_bounds:
        return from_bounds
    value = normalize_coordinates(raw)
    if value and is_valid_coordinates(value):
        return value
    return None
