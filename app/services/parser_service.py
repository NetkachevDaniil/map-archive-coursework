from functools import lru_cache

import re
from dataclasses import dataclass
from datetime import datetime
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import get_password_hash
from app.models.models import MapPost, ParseStatus, Region, User, UserRole
from app.services.bootstrap_service import ensure_default_regions
from app.services.map_fields import normalize_coordinates, resolve_coordinates, store_coordinates, store_optional_text
from app.services.storage_service import storage_service

OMAPS_SOURCES = [
    ("https://o-maps.spb.ru/sheet-spb.html", "Санкт-Петербург"),
    ("https://o-maps.spb.ru/sheet-moscow.html", "Москва"),
]

OMAPS_SOURCE_BY_KEY = {
    "spb": OMAPS_SOURCES[0],
    "moscow": OMAPS_SOURCES[1],
}

OMAPS_JS_FEEDS = {
    "https://o-maps.spb.ru/sheet-spb.html": [
        "https://raw.githubusercontent.com/efradkin/o-maps/main/js/maps-city.js",
        "https://raw.githubusercontent.com/efradkin/o-maps/main/js/maps-parks.js",
        "https://raw.githubusercontent.com/efradkin/o-maps/main/js/maps-forest.js",
    ],
    "https://o-maps.spb.ru/sheet-moscow.html": [
        "https://raw.githubusercontent.com/efradkin/o-maps/main/js/maps-moscow.js",
    ],
}


OMAPS_PUBLIC_BASE = "https://o-maps.spb.ru/"
OMAPS_AUTHORS_JS = "https://raw.githubusercontent.com/efradkin/o-maps/main/js/authors.js"
OMAPS_OWNERS_JS = "https://raw.githubusercontent.com/efradkin/o-maps/main/js/owners.js"


def _is_pskov_item(*, region_name: str = "", image_url: str = "", title: str = "", source_url: str = "") -> bool:
    if (region_name or "").strip().casefold() == "псков":
        return True
    blob = " ".join(filter(None, [image_url, source_url, title])).casefold()
    return "/pskov/" in blob or "original_maps/pskov" in blob or "maps/pskov" in blob


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
    region_name: str = "Неизвестно"
    coordinates: str | None = None
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


def _strip_html(raw: str) -> str:
    return re.sub(r"<[^>]+>", "", raw or "").strip()


def _clean_owner_text(raw: str) -> str | None:
    text = _strip_html(raw)
    text = re.sub(r"^\s*©\s*", "", text).strip()
    text = text.split("//")[0].strip()
    if not text:
        return None
    person = re.search(
        r"[-–—]\s*([А-ЯЁA-Z][а-яёa-z]+(?:\s+[А-ЯЁA-Z][а-яёa-z]+){1,3})",
        text,
    )
    if person:
        return person.group(1).strip().rstrip(",")[:255]
    if text.lower().startswith("по вопросам"):
        return None
    club = re.search(r'клуб[ауе]?\s+[«"]?([^»".]+)[»"]?', text, flags=re.I)
    if club:
        return f'Клуб «{club.group(1).strip()}»'[:255]
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

    if prefer_owner and key in owners:
        cleaned = _clean_owner_text(owners[key])
        if cleaned:
            return cleaned

    if key in authors:
        name = _strip_html(authors[key]).split("//")[0].strip()
        if re.search(r"[А-ЯЁа-яё]", name):
            return name[:255]

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


def _image_download_headers(url: str) -> dict:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "image/jpeg,image/png,image/*,*/*;q=0.8",
        "Accept-Language": "ru-RU,ru;q=0.9",
    }
    if "o-maps.spb.ru" in url:
        headers["Referer"] = "https://o-maps.spb.ru/"
    elif "githubusercontent.com" in url:
        headers["Referer"] = "https://github.com/"
    return headers


def _fetch_html(url: str) -> str:
    headers = _build_headers()
    with httpx.Client(timeout=25, headers=headers, follow_redirects=True) as client:
        response = client.get(url)
        response.raise_for_status()
        return response.content.decode("utf-8")


def _download_bytes(url: str) -> bytes:
    headers = _image_download_headers(url)
    max_bytes = get_settings().max_upload_bytes
    with httpx.Client(timeout=40, headers=headers, follow_redirects=True) as client:
        response = client.get(url)
        response.raise_for_status()
        content_type = (response.headers.get("content-type") or "").lower()
        if "text/html" in content_type and len(response.content) < 50000:
            raise ValueError(f"По URL получена HTML-страница, а не изображение: {url}")
        if len(response.content) < 256:
            raise ValueError(f"Слишком маленький файл ({len(response.content)} байт): {url}")
        if len(response.content) > max_bytes:
            raise ValueError(f"Файл слишком большой ({len(response.content)} байт, максимум {max_bytes}): {url}")
        return response.content


def _expand_js_chunks(chunks: list[str]) -> list[str]:
    expanded: list[str] = []
    for chunk in chunks:
        if chunk.count("name:") <= 1:
            expanded.append(chunk)
            continue
        for part in re.split(r"\}\s*,\s*\{", chunk.strip().strip(",")):
            part = part.strip()
            if not part:
                continue
            if not part.startswith("{"):
                part = "{" + part
            if not part.endswith("}"):
                part = part + "}"
            if re.search(r"name\s*:\s*'", part):
                expanded.append(part)
    return expanded


def _map_metadata_text(chunk: str) -> str:
    parts: list[str] = []
    for field in ("name", "info", "url", "link"):
        single = re.search(rf"{field}\s*:\s*'((?:\\'|[^'])*)'", chunk)
        if single:
            parts.append(single.group(1))
        double = re.search(rf'{field}\s*:\s*"((?:\\"|[^"])*)"', chunk)
        if double:
            parts.append(double.group(1))
        array = re.search(rf"{field}\s*:\s*\[(.*?)\]", chunk, flags=re.DOTALL)
        if array:
            parts.extend(re.findall(r"'([^']+)'", array.group(1)))
    return " ".join(parts) if parts else chunk


_STANDARD_MAP_SCALES = frozenset({4000, 5000, 7500, 10000, 15000, 20000, 25000, 40000})


def _extract_scale(text: str) -> int | None:
    haystack = text or ""

    match = re.search(r"1\s*:\s*(\d{3,6})", haystack)
    if match:
        value = int(match.group(1))
        if value in _STANDARD_MAP_SCALES:
            return value

    for pattern in (
        r"(?:масштаб(?:е|а)?|генерализац(?:ией|ия)?\s+под|лонг\s+в)\s+(?:1\s*:?\s*)?(\d{4,5})\b",
        r"\bпод(?:\s+[\w-]+){0,4}\s+(\d{4,5})\b",
    ):
        match = re.search(pattern, haystack, flags=re.I)
        if match:
            value = int(match.group(1))
            if value in _STANDARD_MAP_SCALES:
                return value

    for match in re.finditer(
        r"(?:^|[_\s])(4000|5000|7500|10000|15000|20000|25000|40000)(?:[_\.\s,]|$)",
        haystack,
    ):
        return int(match.group(1))
    return None


_MIN_MAP_YEAR = 1955


def _passes_import_year(year: int | None) -> bool:
    if year is None:
        return False
    return year >= get_settings().parser_min_year


def _is_plausible_map_year(value: int) -> bool:
    return _MIN_MAP_YEAR <= value <= datetime.now().year + 1


def _extract_year_from_date_field(chunk: str) -> int | None:
    single = re.search(r"date\s*:\s*'(\d{4})-\d{2}-\d{2}'", chunk)
    if single:
        year = int(single.group(1))
        if _is_plausible_map_year(year):
            return year

    array = re.search(r"date\s*:\s*\[(.*?)\]", chunk, flags=re.DOTALL)
    if array:
        years = [
            int(match)
            for match in re.findall(r"'(\d{4})-\d{2}-\d{2}'", array.group(1))
            if _is_plausible_map_year(int(match))
        ]
        if years:
            return max(years)
    return None


def _extract_years_from_paths(*paths: str) -> list[int]:
    years: list[int] = []
    for path in paths:
        if not path:
            continue
        basename = path.rsplit("/", 1)[-1].split("?", 1)[0]
        dated_prefix = re.match(r"^((?:19|20)\d{2})\d{4}[_\-.]", basename)
        if dated_prefix:
            year = int(dated_prefix.group(1))
            if _is_plausible_map_year(year):
                years.append(year)
        for match in re.finditer(r"(?<![\d])((?:19|20)\d{2})(?![\d])", basename):
            year = int(match.group(1))
            if _is_plausible_map_year(year):
                years.append(year)
    return years


def _collect_chunk_paths(chunk: str, *, image_url: str, raw_link: str | None, preview_url: str | None) -> list[str]:
    paths = [image_url, raw_link or "", preview_url or ""]
    for field in ("url", "link"):
        single = re.search(rf"{field}\s*:\s*'([^']+)'", chunk)
        if single:
            paths.append(single.group(1))
        array = re.search(rf"{field}\s*:\s*\[(.*?)\]", chunk, flags=re.DOTALL)
        if array:
            paths.extend(re.findall(r"'([^']+)'", array.group(1)))
    return paths


def _resolve_map_year(*, chunk: str, title: str, image_url: str, raw_link: str | None = None, preview_url: str | None = None) -> int | None:
    year_match = re.search(r"year\s*:\s*(\d{4})", chunk)
    if year_match:
        year = int(year_match.group(1))
        if _is_plausible_map_year(year):
            return year

    from_date = _extract_year_from_date_field(chunk)
    if from_date is not None:
        return from_date

    paths = _collect_chunk_paths(chunk, image_url=image_url, raw_link=raw_link, preview_url=preview_url)
    path_years = _extract_years_from_paths(*paths)
    if path_years:
        return max(path_years)

    title_years = _extract_years_from_paths(title)
    if title_years:
        return max(title_years)

    return None


def _extract_year(text: str) -> int | None:
    path_years = _extract_years_from_paths(text)
    if path_years:
        return max(path_years)
    match = re.search(r"(?<![\d])((?:19|20)\d{2})(?![\d])", text or "")
    if match:
        year = int(match.group(1))
        if _is_plausible_map_year(year):
            return year
    return None


def _extract_image_link_from_row(row) -> str | None:
    for link in row.select("a[href]"):
        href = link.get("href") or ""
        lower = href.lower()
        if any(lower.endswith(ext) for ext in [".jpg", ".jpeg", ".png", ".webp", ".gif", ".tif", ".tiff"]):
            return href
    return None


def _extract_link_from_js_chunk(chunk: str) -> str | None:
    links: list[str] = []
    single = re.search(r"link\s*:\s*'([^']+)'", chunk)
    if single:
        links.append(single.group(1))
    array_match = re.search(r"link\s*:\s*\[(.*?)\]", chunk, flags=re.DOTALL)
    if array_match:
        links.extend(re.findall(r"'([^']+)'", array_match.group(1)))
    object_match = re.search(r"link\s*:\s*\{[^{}]*'([^']+\.(?:jpg|jpeg|png|webp|gif|tif|tiff)[^']*)'", chunk, flags=re.I)
    if object_match:
        links.append(object_match.group(1))
    url_match = re.search(r"url\s*:\s*'([^']+)'", chunk)
    if url_match:
        links.append(url_match.group(1))
    return _pick_best_map_link(links)


def _pick_best_map_link(links: list[str]) -> str | None:
    if not links:
        return None

    def priority(link: str) -> tuple[int, int]:
        lower = link.lower()
        if lower.endswith((".jpg", ".jpeg")):
            return (0, len(link))
        if lower.endswith(".png"):
            return (1, len(link))
        if lower.endswith(".gif"):
            return (2, len(link))
        if lower.endswith((".tif", ".tiff")):
            return (3, len(link))
        if lower.endswith(".webp"):
            return (9, len(link))
        if lower.endswith(".pdf"):
            return (9, len(link))
        return (5, len(link))

    return sorted(links, key=priority)[0]


def _extract_bounds_from_js_chunk(chunk: str) -> list[tuple[float, float]] | None:
    match = re.search(r"bounds\s*:\s*\[(.*?)\]", chunk, flags=re.DOTALL)
    if not match:
        return None
    pairs = re.findall(r"([\d.]+)\s*,\s*([\d.]+)", match.group(1))
    if not pairs:
        return None
    return [(float(lat), float(lon)) for lat, lon in pairs]


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
    if cleaned.startswith("original_maps/"):
        return urljoin(OMAPS_PUBLIC_BASE, cleaned)
    if cleaned.startswith("maps/"):
        return f"https://raw.githubusercontent.com/efradkin/o-maps/main/{cleaned}"
    return urljoin(page_url or OMAPS_PUBLIC_BASE, cleaned)


def _parse_js_feed(js_url: str, page_url: str, region_name: str, limit: int = 50) -> list[ParsedItem]:
    js_text = _fetch_html(js_url)
    items: list[ParsedItem] = []
    for chunk in _expand_js_chunks(_split_js_objects(js_text)):
        name_m = re.search(r"name\s*:\s*'([^']+)'", chunk)
        if not name_m:
            continue
        raw_link = _extract_link_from_js_chunk(chunk) or _extract_url_from_js_chunk(chunk)
        if not raw_link:
            continue
        preview_url = _extract_url_from_js_chunk(chunk)
        image_url = _to_absolute_link(raw_link, page_url=page_url)
        if not re.search(r"\.(jpg|jpeg|png|webp|gif|tif|tiff)(\?|$)", image_url, flags=re.I):
            continue
        title = name_m.group(1)[:200]
        author_m = re.search(r"author\s*:\s*'([^']+)'", chunk)
        owner_m = re.search(r"owner\s*:\s*'([^']+)'", chunk)
        scale = _extract_scale(_map_metadata_text(chunk))
        cartographer = _resolve_person_name(author_m.group(1) if author_m else None)
        rights_holder = _resolve_person_name(owner_m.group(1) if owner_m else None, prefer_owner=True)
        bounds = _extract_bounds_from_js_chunk(chunk)
        preview_abs = _to_absolute_link(preview_url, page_url=page_url) if preview_url else None
        items.append(
            ParsedItem(
                source_name="o-maps.spb.ru",
                page_url=page_url,
                image_url=image_url,
                title=title,
                year=_resolve_map_year(
                    chunk=chunk,
                    title=title,
                    image_url=image_url,
                    raw_link=raw_link,
                    preview_url=preview_abs,
                ),
                scale_denominator=scale,
                cartographer=cartographer,
                rights_holder=rights_holder,
                region_name=region_name,
                coordinates=resolve_coordinates(bounds=bounds),
                description="",
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
        img_abs = urljoin(url, img_href)
        year = _extract_year(" ".join([row_text, title, img_href]))
        scale = _extract_scale(row_text)
        cartographer = _resolve_person_name(cols[8] if len(cols) >= 9 else None)
        rights_holder = _resolve_person_name(cols[10] if len(cols) >= 11 else None, prefer_owner=True)
        coordinates = resolve_coordinates(bounds=None)
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
                region_name=region_name,
                coordinates=coordinates,
                description="",
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
            title = name_m.group(1)[:200]
            scale = _extract_scale(_map_metadata_text(chunk))
            author_m = re.search(r"author\s*:\s*'([^']+)'", chunk)
            owner_m = re.search(r"owner\s*:\s*'([^']+)'", chunk)
            cartographer = _resolve_person_name(author_m.group(1) if author_m else None)
            rights_holder = _resolve_person_name(owner_m.group(1) if owner_m else None, prefer_owner=True)
            items.append(
                ParsedItem(
                    source_name="o-maps.spb.ru",
                    page_url=url,
                    image_url=image_url,
                    title=title,
                    year=_resolve_map_year(chunk=chunk, title=title, image_url=image_url, raw_link=link_m.group(1)),
                    scale_denominator=scale,
                    cartographer=cartographer,
                    rights_holder=rights_holder,
                    region_name=region_name,
                    coordinates=resolve_coordinates(bounds=None),
                    description="",
                )
            )
            if len(items) >= limit:
                break

    return items


def build_source_coordinates_lookup() -> dict[str, tuple[str, str | None]]:
    lookup: dict[str, tuple[str, str | None]] = {}
    for page_url, region_name in OMAPS_SOURCES:
        for js_url in OMAPS_JS_FEEDS.get(page_url, []):
            try:
                js_text = _fetch_html(js_url)
            except Exception:
                continue
            for chunk in _split_js_objects(js_text):
                raw_link = _extract_link_from_js_chunk(chunk) or _extract_url_from_js_chunk(chunk)
                if not raw_link:
                    continue
                image_url = _to_absolute_link(raw_link, page_url=page_url)
                bounds = _extract_bounds_from_js_chunk(chunk)
                lookup[image_url] = (region_name, resolve_coordinates(bounds=bounds))
    return lookup


def parse_recent_items(*, source_key: str | None = None, per_source_limit: int = 200) -> list[ParsedItem]:
    items: list[ParsedItem] = []
    sources = [OMAPS_SOURCE_BY_KEY[source_key]] if source_key else OMAPS_SOURCES
    for url, region_name in sources:
        try:
            page_items = _parse_table_like_page(url, region_name=region_name, limit=per_source_limit)
        except Exception:
            page_items = []
        if not page_items:
            for js_url in OMAPS_JS_FEEDS.get(url, []):
                try:
                    page_items.extend(_parse_js_feed(js_url, page_url=url, region_name=region_name, limit=per_source_limit))
                except Exception:
                    continue
        for item in page_items:
            if _is_pskov_item(region_name=item.region_name, image_url=item.image_url, title=item.title):
                continue
            if not _passes_import_year(item.year):
                continue
            items.append(item)
    return items


def _ensure_publisher_user(db: Session, source_key: str) -> User:
    settings = get_settings()
    if source_key == "moscow":
        login, password, full_name = (
            settings.omaps_moscow_login,
            settings.omaps_moscow_password,
            "Карты O-Maps — Москва",
        )
    else:
        login, password, full_name = (
            settings.omaps_spb_login,
            settings.omaps_spb_password,
            "Карты O-Maps — Санкт-Петербург",
        )

    user = db.execute(select(User).where(User.login == login)).scalar_one_or_none()
    if user:
        user.password_hash = get_password_hash(password)
        user.is_email_verified = True
        user.is_active = True
        user.full_name = full_name
        db.flush()
        return user

    user = User(
        login=login,
        email=f"{login.replace('.', '-')}@mapsnet.ru",
        full_name=full_name,
        password_hash=get_password_hash(password),
        role=UserRole.USER,
        is_active=True,
        is_email_verified=True,
        bio=f"Импортированные карты из o-maps.spb.ru ({source_key}).",
    )
    db.add(user)
    db.flush()
    return user


def _get_or_create_region(db: Session, region_name: str | None) -> Region | None:
    if not region_name or not region_name.strip():
        return None
    normalized = region_name.strip()
    region = db.execute(select(Region).where(Region.name == normalized)).scalar_one_or_none()
    if region:
        return region
    region = Region(name=normalized)
    db.add(region)
    db.flush()
    return region


def import_parsed_items_to_queue(db: Session, *, source_key: str, per_source_batch: int = 5) -> dict:
    imported = 0
    skipped = 0
    errors = 0
    total_candidates = 0
    last_error = None
    publisher_user = _ensure_publisher_user(db, source_key)
    page_url, _region_name = OMAPS_SOURCE_BY_KEY[source_key]
    all_items = parse_recent_items(source_key=source_key)
    loaded_from_source = 0
    seen_in_batch: set[str] = set()

    for item in all_items:
        if loaded_from_source >= per_source_batch:
            break
        if _is_pskov_item(region_name=item.region_name, image_url=item.image_url, title=item.title):
            skipped += 1
            continue
        if not _passes_import_year(item.year):
            skipped += 1
            continue
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
            key = storage_service.upload_bytes(
                image_bytes,
                filename=item.image_url.rsplit("/", 1)[-1] or "parsed.jpg",
            )
        except Exception as exc:
            errors += 1
            skipped += 1
            last_error = f"{item.image_url} -> {exc}"
            continue

        region = _get_or_create_region(db, item.region_name)
        post = MapPost(
            user_id=publisher_user.id,
            region_id=region.id if region else None,
            title=item.title or "Карта из парсинга",
            coordinates=store_coordinates(item.coordinates),
            year_of_event=item.year,
            scale_denominator=item.scale_denominator,
            cartographer=store_optional_text(item.cartographer),
            rights_holder=store_optional_text(item.rights_holder),
            image_key=key,
            source_url=item.image_url,
            description=item.description.strip() if item.description else "",
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
        "skipped": skipped,
        "errors": errors,
        "total_candidates": total_candidates,
        "last_error": last_error,
        "source_key": source_key,
        "page_url": page_url,
    }
