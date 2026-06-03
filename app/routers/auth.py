from fastapi import APIRouter, Depends, Form, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy import or_, select
from sqlalchemy.orm import Session
from uuid import UUID

from app.core.security import create_access_token, create_verify_token, decode_token, get_password_hash, verify_password
from app.db.session import get_db
from app.models.models import User
from app.services.email_service import send_verification_email
from app.web import templates

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/login")
def login_page(request: Request):
    return templates.TemplateResponse(request=request, name="auth_login.html", context={"request": request, "error": None})


@router.post("/login")
def login(
    request: Request,
    login_or_email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    stmt = select(User).where(or_(User.login == login_or_email, User.email == login_or_email))
    user = db.execute(stmt).scalar_one_or_none()
    if not user or not verify_password(password, user.password_hash):
        return templates.TemplateResponse(
            request=request,
            name="auth_login.html",
            context={"request": request, "error": "Неверный логин/email или пароль"},
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    response = RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
    response.set_cookie("access_token", create_access_token(user.id), httponly=True, samesite="lax")
    return response


@router.get("/register")
def register_page(request: Request):
    return templates.TemplateResponse(request=request, name="auth_register.html", context={"request": request, "error": None})


@router.post("/register")
def register(
    request: Request,
    login: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    existing = db.execute(select(User).where(or_(User.login == login, User.email == email))).scalar_one_or_none()
    if existing:
        return templates.TemplateResponse(
            request=request,
            name="auth_register.html",
            context={"request": request, "error": "Пользователь с таким логином или email уже существует"},
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    user = User(
        login=login.strip(),
        email=email.strip().lower(),
        full_name=login.strip(),
        password_hash=get_password_hash(password),
        is_email_verified=False,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    verify_token = create_verify_token(user.id, user.email)
    verify_link = str(request.url_for("verify_email")) + f"?token={verify_token}"
    sent, send_error = send_verification_email(user.email, verify_link)

    return templates.TemplateResponse(
        request=request,
        name="auth_register_success.html",
        context={
            "request": request,
            "email": user.email,
            "email_sent": sent,
            "email_error": send_error,
        },
    )


@router.get("/verify", name="verify_email")
def verify_email(token: str, db: Session = Depends(get_db)):
    try:
        payload = decode_token(token)
    except Exception:
        return RedirectResponse(url="/auth/login?error=invalid_token", status_code=status.HTTP_302_FOUND)

    if payload.get("type") != "verify":
        return RedirectResponse(url="/auth/login?error=invalid_token", status_code=status.HTTP_302_FOUND)

    try:
        user_id = UUID(payload.get("sub", ""))
    except ValueError:
        return RedirectResponse(url="/auth/login?error=invalid_token", status_code=status.HTTP_302_FOUND)

    user = db.get(User, user_id)
    if not user:
        return RedirectResponse(url="/auth/login?error=user_not_found", status_code=status.HTTP_302_FOUND)

    user.is_email_verified = True
    db.commit()

    response = RedirectResponse(url="/profile/me", status_code=status.HTTP_302_FOUND)
    response.set_cookie("access_token", create_access_token(user.id), httponly=True, samesite="lax")
    return response


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
