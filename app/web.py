from fastapi.templating import Jinja2Templates

from app.core.config import get_settings

templates = Jinja2Templates(directory="app/templates")
templates.env.globals["site_background_url"] = get_settings().site_background_url
