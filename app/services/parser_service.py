from functools import lru_cache

import re
from dataclasses import dataclass
from datetime import datetime
from uuid import uuid4
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import get_password_hash
from app.models.models import MapPost, ParseStatus, User, UserRole
from app.services.map_fields import build_territory, normalize_territory
from app.services.storage_service import storage_service

OMAPS_SOURCES = [
    ("https://o-maps.spb.ru/sheet-spb.html", "Санкт-Петербург"),
    ("https://o-maps.spb.ru/sheet-moscow.html", "Москва"),
    ("https://o-maps.spb.ru/sheet-pskov.html", "Псков"),
]

OMAPS_JS_FEEDS = {
    "https://o-maps.spb.ru/sheet-spb.html": [
        "https://raw.githubusercontent.com/efradkin/o-maps/main/js/maps-city.js",
        "https://raw.githubusercontent.com/efradkin/o-maps/main/js/maps-parks.js",
        "https://raw.githubusercontent.com/efradkin/o-maps/main/js/maps-forest.js",
    ],
    "https://o-maps.spb.ru/sheet-moscow.html": [
        "https://raw.githubusercontent.com/efradkin/o-maps/main/js/maps-moscow.js",
    ],
    "https://o-maps.spb.ru/sheet-pskov.html": [
        "https://raw.githubusercontent.com/efradkin/o-maps/main/js/maps-pskov.js",
    ],
}


OMAPS_AUTHORS_JS = "https://raw.githubusercontent.com/efradkin/o-maps/main/js/authors.js"
OMAPS_OWNERS_JS = "https://raw.githubusercontent.com/efradkin/o-maps/main/js/owners.js"


@dataclass
class ParsedItem:
    source_name: str
    page_url: str
    image_url: str
    title: str
    year: int | None = None
    scale_denominator: int | None = None
    cartographer: str | None = None
    rights_holder: str | None = None
    territory: str = "Неизвестно-Неизвестно-Неизвестно"
    description: str = ""
    published_at: datetime | None = None


def _parse_js_name_lookup(js_text: str) -> dict[str, str]:
    lookup: dict[str, str] = {}
    for match in re.finditer(r"(\w+)\s*:\s*\{[^}]*?name\s*:\s*'([^']*)'", js_text, flags=re.DOTALL):
        code, name = match.group(1), match.group(2).strip()
        if code and name:
            lookup[code] = name
    return lookup


@lru_cache(maxsize=2)
def _authors_lookup() -> dict[str, str]:
    try:
        return _parse_js_name_lookup(_fetch_html(OMAPS_AUTHORS_JS))
    except Exception:
        return {}


@lru_cache(maxsize=2)
def _owners_lookup() -> dict[str, str]:
    try:
        return _parse_js_name_lookup(_fetch_html(OMAPS_OWNERS_JS))
    except Exception:
        return {}


def _clean_owner_text(raw: str) -> str | None:
    text = re.sub(r"^\s*©\s*", "", raw).strip()
    text = text.split("//")[0].strip()
    if not text or text.lower().startswith("по вопросам"):
        return None
    text = re.split(r"\s[-–—|]\s|\[", text)[0].strip()
    if re.search(r"[А-ЯЁа-яё]", text) and len(text) >= 4:
        return text[:255]
    return None


def _resolve_person_name(code: str | None, *, prefer_owner: bool = False) -> str | None:
    if not code or not code.strip():
        return None
    key = code.strip()
    authors = _authors_lookup()
    owners = _owners_lookup()

    if key in authors:
        name = authors[key].split("//")[0].strip()
        if re.search(r"[А-ЯЁа-яё]", name):
            return name[:255]

    if prefer_owner and key in owners:
        cleaned = _clean_owner_text(owners[key])
        if cleaned:
            return cleaned

    if not prefer_owner and key in owners:
        cleaned = _clean_owner_text(owners[key])
        if cleaned:
            return cleaned

    if re.fullmatch(r"[A-Z0-9_]{2,20}", key):
        return None
    if re.search(r"[А-ЯЁа-яё]", key):
        return key[:255]
    return None


def _build_headers() -> dict:
    settings = get_settings()
    return {
        "User-Agent": settings.parser_user_agent,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
        "Referer": "https://o-maps.spb.ru/",
    }


def _fetch_html(url: str) -> str:
    headers = _build_headers()
    with httpx.Client(timeout=25, headers=headers, follow_redirects=True) as client:
        response = client.get(url)
        response.raise_for_status()
        return response.text


def _download_bytes(url: str) -> bytes:
    with httpx.Client(timeout=40, headers=_build_headers(), follow_redirects=True) as client:
        response = client.get(url)
        response.raise_for_status()
        return response.content


def _extract_scale(text: str) -> int | None:
    m = re.search(r"1\s*:\s*(\d{3,6})", text)
    if not m:
        return None
    return int(m.group(1))


def _extract_year(text: str) -> int | None:
    m = re.search(r"(19|20)\d{2}", text)
    if not m:
        return None
    return int(m.group(0))


def _extract_image_link_from_row(row) -> str | None:
    for link in row.select("a[href]"):
        href = link.get("href") or ""
        lower = href.lower()
        if any(lower.endswith(ext) for ext in [".jpg", ".jpeg", ".png", ".webp", ".gif", ".tif", ".tiff"]):
            return href
    return None


def _extract_link_from_js_chunk(chunk: str) -> str | None:
    # link: '...'
    m = re.search(r"link\s*:\s*'([^']+)'", chunk)
    if m:
        return m.group(1)
    # link: ["...", ...]
    m = re.search(r"link\s*:\s*\[\s*'([^']+)'", chunk)
    if m:
        return m.group(1)
    # link: {name: '...'}
    m = re.search(r"link\s*:\s*\{[^{}]*'([^']+\.(?:jpg|jpeg|png|webp|gif|tif|tiff)[^']*)'", chunk, flags=re.I)
    if m:
        return m.group(1)
    return None


def _extract_url_from_js_chunk(chunk: str) -> str | None:
    m = re.search(r"url\s*:\s*'([^']+)'", chunk)
    if m:
        return m.group(1)
    return None


def _split_js_objects(js_text: str) -> list[str]:
    objects: list[str] = []
    start = js_text.find("[")
    if start == -1:
        return objects
    depth = 0
    obj_start = -1
    in_string = False
    prev = ""
    for i, ch in enumerate(js_text[start:], start=start):
        if ch == "'" and prev != "\\":
            in_string = not in_string
        if in_string:
            prev = ch
            continue
        if ch == "{":
            if depth == 0:
                obj_start = i
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0 and obj_start != -1:
                objects.append(js_text[obj_start : i + 1])
                obj_start = -1
        prev = ch
    return objects


def _to_absolute_link(raw_link: str, page_url: str) -> str:
    value = raw_link.strip()
    if value.startswith("http://") or value.startswith("https://"):
        return value
    cleaned = value.lstrip("./")
    return f"https://raw.githubusercontent.com/efradkin/o-maps/main/{cleaned}"


def _parse_js_feed(js_url: str, page_url: str, region_name: str, limit: int = 50) -> list[ParsedItem]:
    js_text = _fetch_html(js_url)
    items: list[ParsedItem] = []
    for chunk in _split_js_objects(js_text):
        name_m = re.search(r"name\s*:\s*'([^']+)'", chunk)
        if not name_m:
            continue
        raw_link = _extract_link_from_js_chunk(chunk) or _extract_url_from_js_chunk(chunk)
        if not raw_link:
            continue
        image_url = _to_absolute_link(raw_link, page_url=page_url)
        if not re.search(r"\.(jpg|jpeg|png|webp|gif|tif|tiff)(\?|$)", image_url, flags=re.I):
            continue
        year_m = re.search(r"year\s*:\s*(\d{4})", chunk)
        author_m = re.search(r"author\s*:\s*'([^']+)'", chunk)
        owner_m = re.search(r"owner\s*:\s*'([^']+)'", chunk)
        scale = _extract_scale(chunk)
        cartographer = _resolve_person_name(author_m.group(1) if author_m else None)
        rights_holder = _resolve_person_name(owner_m.group(1) if owner_m else None, prefer_owner=True)
        items.append(
            ParsedItem(
                source_name="o-maps.spb.ru",
                page_url=page_url,
                image_url=image_url,
                title=name_m.group(1)[:200],
                year=int(year_m.group(1)) if year_m else None,
                scale_denominator=scale,
                cartographer=cartographer,
                rights_holder=rights_holder,
                territory=build_territory(region_name, name_m.group(1)),
                description=f"Импорт из таблицы O-Maps: {page_url}",
            )
        )
        if len(items) >= limit:
            break
    return items


def _parse_table_like_page(url: str, region_name: str, limit: int = 50) -> list[ParsedItem]:
    html = _fetch_html(url)
    soup = BeautifulSoup(html, "html.parser")
    items: list[ParsedItem] = []
    rows = soup.select("table tr")
    for row in rows:
        img_href = _extract_image_link_from_row(row)
        if not img_href:
            continue
        cols = [c.get_text(" ", strip=True) for c in row.select("td")]
        row_text = " ".join(cols)
        title = cols[1] if len(cols) > 1 else row_text[:180] or "Карта"
        year = _extract_year(row_text)
        scale = _extract_scale(row_text)
        cartographer = _resolve_person_name(cols[8] if len(cols) >= 9 else None)
        rights_holder = _resolve_person_name(cols[10] if len(cols) >= 11 else None, prefer_owner=True)
        territory = build_territory(region_name, title)
        items.append(
            ParsedItem(
                source_name="o-maps.spb.ru",
                page_url=url,
                image_url=urljoin(url, img_href),
                title=title[:200],
                year=year,
                scale_denominator=scale,
                cartographer=cartographer,
                rights_holder=rights_holder,
                territory=territory,
                description=f"Импорт из таблицы O-Maps: {url}",
                published_at=None,
            )
        )
        if len(items) >= limit:
            break

    # Резервный парсер: ищем объекты с полями name/year/link/author/owner в JS.
    if not items:
        scripts = [s.get_text(" ", strip=False) for s in soup.select("script") if s.get_text(strip=True)]
        blob = "\n".join(scripts)
        for chunk in re.findall(r"\{[^{}]{10,1000}\}", blob):
            name_m = re.search(r"name\s*:\s*'([^']+)'", chunk)
            link_m = re.search(r"link\s*:\s*'([^']+)'", chunk)
            if not name_m or not link_m:
                continue
            image_url = urljoin(url, link_m.group(1))
            if not re.search(r"\.(jpg|jpeg|png|webp|gif|tif|tiff)$", image_url, flags=re.I):
                continue
            year_m = re.search(r"year\s*:\s*(\d{4})", chunk)
            scale = _extract_scale(chunk)
            author_m = re.search(r"author\s*:\s*'([^']+)'", chunk)
            owner_m = re.search(r"owner\s*:\s*'([^']+)'", chunk)
            cartographer = _resolve_person_name(author_m.group(1) if author_m else None)
            rights_holder = _resolve_person_name(owner_m.group(1) if owner_m else None, prefer_owner=True)
            items.append(
                ParsedItem(
                    source_name="o-maps.spb.ru",
                    page_url=url,
                    image_url=image_url,
                    title=name_m.group(1)[:200],
                    year=int(year_m.group(1)) if year_m else None,
                    scale_denominator=scale,
                    cartographer=cartographer,
                    rights_holder=rights_holder,
                    territory=build_territory(region_name, name_m.group(1)),
                    description=f"Импорт из таблицы O-Maps: {url}",
                )
            )
            if len(items) >= limit:
                break

    return items


def parse_recent_items(per_source_limit: int = 5) -> list[ParsedItem]:
    items: list[ParsedItem] = []
    for url, region_name in OMAPS_SOURCES:
        try:
            page_items = _parse_table_like_page(url, region_name=region_name, limit=200)
        except Exception:
            page_items = []
        if not page_items:
            for js_url in OMAPS_JS_FEEDS.get(url, []):
                try:
                    page_items.extend(_parse_js_feed(js_url, page_url=url, region_name=region_name, limit=200))
                except Exception:
                    continue
        items.extend(page_items)
    return items


def _ensure_omaps_publisher_user(db: Session) -> User:
    settings = get_settings()
    user = db.execute(select(User).where(User.login == settings.omaps_profile_login)).scalar_one_or_none()
    if user:
        user.password_hash = get_password_hash(settings.omaps_profile_password)
        user.is_email_verified = True
        user.is_active = True
        db.flush()
        return user
    user = User(
        login=settings.omaps_profile_login,
        email=f"o-maps-{uuid4().hex[:8]}@example.com",
        full_name="O-Maps Publisher",
        password_hash=get_password_hash(settings.omaps_profile_password),
        role=UserRole.USER,
        is_active=True,
        is_email_verified=True,
        bio="Профиль публикаций импортированных из таблиц O-Maps.",
    )
    db.add(user)
    db.flush()
    return user


def import_parsed_items_to_queue(db: Session, per_source_batch: int = 5) -> dict:
    imported = 0
    imported_with_external_url = 0
    skipped = 0
    errors = 0
    total_candidates = 0
    last_error = None
    publisher_user = _ensure_omaps_publisher_user(db)
    all_items = parse_recent_items(per_source_limit=200)
    by_source: dict[str, list[ParsedItem]] = {}
    for item in all_items:
        by_source.setdefault(item.page_url, []).append(item)

    for source_url, items in by_source.items():
        loaded_from_source = 0
        seen_in_batch: set[str] = set()
        for item in items:
            if loaded_from_source >= per_source_batch:
                break
            if item.image_url in seen_in_batch:
                continue
            seen_in_batch.add(item.image_url)
            total_candidates += 1
            exists_stmt = select(MapPost.id).where(MapPost.source_url == item.image_url).limit(1)
            if db.execute(exists_stmt).scalar_one_or_none():
                skipped += 1
                continue
            try:
                image_bytes = _download_bytes(item.image_url)
                key = storage_service.upload_bytes(image_bytes, filename=item.image_url.rsplit("/", 1)[-1] or "parsed.jpg")
            except Exception as exc:
                # Если загрузка/запись в хранилище не удалась (например, проблемы S3),
                # оставляем внешний URL картинки, чтобы карточка всё равно появилась в модерации.
                key = item.image_url
                imported_with_external_url += 1
                errors += 1
                last_error = str(exc)

            post = MapPost(
                user_id=publisher_user.id,
                title=item.title or "Карта из парсинга",
                territory=item.territory or "Неизвестно-Неизвестно-Неизвестно",
                year_of_event=item.year,
                scale_denominator=item.scale_denominator,
                cartographer=item.cartographer,
                rights_holder=item.rights_holder,
                image_key=key,
                source_url=item.image_url,
                description=item.description or "Требуется модерация администратором.",
                parsed_source=item.source_name,
                is_parsed=True,
                parse_status=ParseStatus.PENDING,
                is_public=False,
            )
            db.add(post)
            imported += 1
            loaded_from_source += 1
    db.commit()
    return {
        "imported": imported,
        "imported_with_external_url": imported_with_external_url,
        "skipped": skipped,
        "errors": errors,
        "total_candidates": total_candidates,
        "last_error": last_error,
    }
