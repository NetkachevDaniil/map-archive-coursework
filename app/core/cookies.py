from app.core.config import get_settings


def set_auth_cookie(response, token: str) -> None:
    settings = get_settings()
    response.set_cookie(
        "access_token",
        token,
        httponly=True,
        samesite="lax",
        secure=settings.cookie_secure,
        path="/",
    )
