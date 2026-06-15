from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.security import read_user_id_from_access_token
from app.db.session import get_db
from app.models.models import User, UserRole


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User | None:
    token = request.cookies.get("access_token")
    if not token:
        return None
    user_id = read_user_id_from_access_token(token)
    if not user_id:
        return None
    return db.get(User, user_id)


def require_user(user: User | None = Depends(get_current_user)) -> User:
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Требуется авторизация")
    if not user.is_email_verified:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Подтвердите email")
    return user


def require_admin(user: User = Depends(require_user)) -> User:
    if user.role != UserRole.ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Требуются права администратора")
    return user
