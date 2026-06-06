from datetime import datetime

from fastapi.templating import Jinja2Templates

from app.core.config import get_settings

settings = get_settings()
templates = Jinja2Templates(directory="app/templates")
templates.env.globals["site_background_url"] = settings.site_background_url
templates.env.globals["default_avatar_url"] = settings.default_avatar_url
templates.env.globals["current_year"] = datetime.now().year


def resolve_avatar_url(user) -> str:
    if user and getattr(user, "avatar_url", None):
        return user.avatar_url
    return settings.default_avatar_url


templates.env.globals["resolve_avatar_url"] = resolve_avatar_url
