from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.core.config import get_settings
from app.db.base import Base
from app.db.session import engine
from app.routers import admin, auth, files, pages, posts
from app.services.bootstrap_service import ensure_default_admin

settings = get_settings()
Path(settings.local_upload_dir).mkdir(parents=True, exist_ok=True)

app = FastAPI(title=settings.app_name)

app.include_router(auth.router)
app.include_router(files.router)
app.include_router(posts.router)
app.include_router(admin.router)
app.include_router(pages.router)


@app.on_event("startup")
def on_startup() -> None:
    # Для простого локального старта создаём таблицы автоматически.
    Base.metadata.create_all(bind=engine)
    ensure_default_admin()


app.mount("/static", StaticFiles(directory="app/static"), name="static")
app.mount("/media", StaticFiles(directory=settings.local_upload_dir), name="media")
