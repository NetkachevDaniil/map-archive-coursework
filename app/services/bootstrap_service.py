from sqlalchemy import select

from app.core.config import get_settings
from app.core.security import get_password_hash
from app.db.session import SessionLocal
from app.models.models import User, UserRole


def ensure_default_admin() -> None:
    settings = get_settings()
    with SessionLocal() as db:
        existing = db.execute(select(User).where(User.role == UserRole.ADMIN)).scalar_one_or_none()
        if existing:
            if existing.full_name in {"Системный администратор", "", None}:
                existing.full_name = "Неткачев Даниил"
                db.commit()
        else:
            admin = User(
                login=settings.first_admin_login,
                email=str(settings.first_admin_email),
                full_name="Неткачев Даниил",
                password_hash=get_password_hash(settings.first_admin_password),
                role=UserRole.ADMIN,
                is_email_verified=True,
                is_active=True,
            )
            db.add(admin)
            db.commit()

        for login, password, full_name in [
            (settings.omaps_profile_login, settings.omaps_profile_password, "O-Maps Publisher"),
            (settings.omephi_profile_login, settings.omephi_profile_password, "o-mephi.net Publisher"),
        ]:
            user = db.execute(select(User).where(User.login == login)).scalar_one_or_none()
            if user:
                user.password_hash = get_password_hash(password)
                user.is_email_verified = True
                user.is_active = True
                if not user.full_name:
                    user.full_name = full_name
            else:
                user = User(
                    login=login,
                    email=f"{login.replace('.', '-')}-publisher@example.com",
                    full_name=full_name,
                    password_hash=get_password_hash(password),
                    role=UserRole.USER,
                    is_email_verified=True,
                    is_active=True,
                    bio="Системный профиль источника карт.",
                )
                db.add(user)
        db.commit()
