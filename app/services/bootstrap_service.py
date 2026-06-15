from sqlalchemy import select

from app.core.config import get_settings
from app.core.security import get_password_hash
from app.db.session import SessionLocal
from app.data.russian_regions import RUSSIAN_REGIONS
from app.models.models import Region, User, UserRole


def ensure_default_regions() -> None:
    with SessionLocal() as db:
        for name in RUSSIAN_REGIONS:
            exists = db.execute(select(Region.id).where(Region.name == name).limit(1)).scalar_one_or_none()
            if not exists:
                db.add(Region(name=name))
        db.commit()


def _upsert_service_user(db, login: str, password: str, full_name: str, bio: str) -> None:
    user = db.execute(select(User).where(User.login == login)).scalar_one_or_none()
    if user:
        user.password_hash = get_password_hash(password)
        user.is_email_verified = True
        user.is_active = True
        user.full_name = full_name
        if bio:
            user.bio = bio
    else:
        db.add(
            User(
                login=login,
                email=f"{login.replace('.', '-')}@mapsnet.ru",
                full_name=full_name,
                password_hash=get_password_hash(password),
                role=UserRole.USER,
                is_email_verified=True,
                is_active=True,
                bio=bio,
            )
        )


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

        _upsert_service_user(
            db,
            settings.omaps_spb_login,
            settings.omaps_spb_password,
            "Карты O-Maps — Санкт-Петербург",
            "Импортированные карты Санкт-Петербурга из o-maps.spb.ru.",
        )
        _upsert_service_user(
            db,
            settings.omaps_moscow_login,
            settings.omaps_moscow_password,
            "Карты O-Maps — Москва",
            "Импортированные карты Москвы из o-maps.spb.ru.",
        )
        db.commit()

    ensure_default_regions()
