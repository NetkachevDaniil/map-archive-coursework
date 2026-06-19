from datetime import datetime
from typing import Any

from fastapi import Request
from fastapi.templating import Jinja2Templates

from app.core.config import get_settings
from app.services.map_fields import is_blank_or_unknown

settings = get_settings()

UNKNOWN_VALUE = "—"


def resolve_avatar_url(user) -> str:
    if user and getattr(user, "avatar_url", None):
        return user.avatar_url
    return settings.default_avatar_url


def unknown(value) -> str:
    if value is None:
        return UNKNOWN_VALUE
    if isinstance(value, str) and is_blank_or_unknown(value):
        return UNKNOWN_VALUE
    return value


def unknown_scale(denominator) -> str:
    if denominator:
        return f"1:{denominator}"
    return UNKNOWN_VALUE


def display_description(value: str | None) -> str | None:
    if not value or not value.strip():
        return None
    text = value.strip()
    if text.startswith("Импорт из таблицы O-Maps:"):
        return None
    if text == "Требуется модерация администратором.":
        return None
    return text


def known_tag(value) -> str | None:
    if is_blank_or_unknown(value):
        return None
    return value


def _template_context(_request: Request) -> dict[str, Any]:
    return {
        "site_background_url": settings.site_background_url,
        "default_avatar_url": settings.default_avatar_url,
        "current_year": datetime.now().year,
        "resolve_avatar_url": resolve_avatar_url,
        "unknown": unknown,
        "unknown_scale": unknown_scale,
        "display_description": display_description,
        "known_tag": known_tag,
        "static_asset_version": "3",
    }


templates = Jinja2Templates(
    directory="app/templates",
    context_processors=[_template_context],
)
