from fastapi import APIRouter, Depends, Form, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import create_access_token, get_password_hash, verify_password
from app.db.session import get_db
from app.models.models import User
from app.web import templates

router = APIRouter(prefix="/auth", tags=["auth"])


def _login_response(user: User) -> RedirectResponse:
    response = RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
    response.set_cookie("access_token", create_access_token(user.id), httponly=True, samesite="lax")
    return response


@router.get("/login")
def login_page(request: Request):
    return templates.TemplateResponse(request=request, name="auth_login.html", context={"request": request, "error": None})


@router.post("/login")
def login(
    request: Request,
    login: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    user = db.execute(select(User).where(User.login == login.strip())).scalar_one_or_none()
    if not user or not verify_password(password, user.password_hash):
        return templates.TemplateResponse(
            request=request,
            name="auth_login.html",
            context={"request": request, "error": "Неверный логин или пароль"},
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    return _login_response(user)


@router.get("/register")
def register_page(request: Request):
    return templates.TemplateResponse(request=request, name="auth_register.html", context={"request": request, "error": None})


@router.post("/register")
def register(
    request: Request,
    login: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    login = login.strip()
    if not login:
        return templates.TemplateResponse(
            request=request,
            name="auth_register.html",
            context={"request": request, "error": "Укажите логин"},
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    existing = db.execute(select(User).where(User.login == login)).scalar_one_or_none()
    if existing:
        return templates.TemplateResponse(
            request=request,
            name="auth_register.html",
            context={"request": request, "error": "Пользователь с таким логином уже существует"},
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    user = User(
        login=login,
        email=f"{login.lower()}@users.orientmaps",
        full_name=login,
        password_hash=get_password_hash(password),
        is_email_verified=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    return _login_response(user)


@router.get("/logout")
def logout_get():
    response = RedirectResponse(url="/auth/login", status_code=status.HTTP_303_SEE_OTHER)
    response.delete_cookie("access_token", path="/")
    response.set_cookie("access_token", "", max_age=0, expires=0, path="/")
    return response


@router.post("/logout")
def logout():
    response = RedirectResponse(url="/auth/login", status_code=status.HTTP_303_SEE_OTHER)
    response.delete_cookie("access_token", path="/")
    response.set_cookie("access_token", "", max_age=0, expires=0, path="/")
    return response
