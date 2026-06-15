"""Диагностика парсера. Запуск: docker compose exec web python scripts/diagnose_parser.py [spb|moscow]"""
import sys

from sqlalchemy import func, select

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models.models import MapPost
from app.services.parser_service import (
    OMAPS_JS_FEEDS,
    OMAPS_SOURCE_BY_KEY,
    _download_bytes,
    _parse_js_feed,
    _passes_import_year,
    import_parsed_items_to_queue,
    parse_recent_items,
)


def main() -> None:
    source_key = (sys.argv[1] if len(sys.argv) > 1 else "moscow").lower()
    page_url, region = OMAPS_SOURCE_BY_KEY[source_key]
    settings = get_settings()

    print(f"=== {source_key} / {region} / min_year={settings.parser_min_year} ===")

    raw_js: list = []
    for js_url in OMAPS_JS_FEEDS.get(page_url, []):
        try:
            chunk_items = _parse_js_feed(js_url, page_url=page_url, region_name=region, limit=500)
            raw_js.extend(chunk_items)
            print(f"JS {js_url}: {len(chunk_items)} items")
        except Exception as exc:
            print(f"JS FAIL {js_url}: {exc}")

    with_year = [i for i in raw_js if _passes_import_year(i.year)]
    no_year = [i for i in raw_js if i.year is None]
    old_year = [i for i in raw_js if i.year is not None and not _passes_import_year(i.year)]
    print(f"JS total={len(raw_js)} year_ok={len(with_year)} no_year={len(no_year)} old_year={len(old_year)}")

    filtered = parse_recent_items(source_key=source_key, per_source_limit=200)
    print(f"parse_recent_items returned: {len(filtered)}")

    db = SessionLocal()
    in_db = db.scalar(select(func.count()).select_from(MapPost).where(MapPost.parsed_source == "o-maps.spb.ru")) or 0
    pending = db.scalar(
        select(func.count()).select_from(MapPost).where(
            MapPost.is_parsed.is_(True), MapPost.parse_status == "pending"
        )
    ) or 0
    print(f"DB maps total={in_db} pending_moderation={pending}")

    for item in with_year[:8]:
        exists = db.execute(select(MapPost.id).where(MapPost.source_url == item.image_url).limit(1)).scalar_one_or_none()
        mark = "IN_DB" if exists else "new"
        print(f"  [{mark}] year={item.year} {item.title[:45]}")
        print(f"         {item.image_url[:100]}")
        if not exists:
            try:
                data = _download_bytes(item.image_url)
                print(f"         download OK: {len(data)} bytes")
            except Exception as exc:
                print(f"         download FAIL: {exc}")

    result = import_parsed_items_to_queue(db, source_key=source_key, per_source_batch=5)
    print("import:", result)
    db.close()


if __name__ == "__main__":
    main()
