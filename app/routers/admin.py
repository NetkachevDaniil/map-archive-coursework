from uuid import UUID

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.deps import require_admin
from app.db.session import get_db
from app.models.models import MapPost, ParseStatus, Region, User
from app.routers.posts import _get_or_create_region
from app.services.map_fields import is_valid_coordinates, is_valid_region_name, store_coordinates, store_optional_text
from app.services.parser_service import import_parsed_items_to_queue
from app.services.storage_service import storage_service
from app.web import templates

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/parsing")
def parsing_queue(request: Request, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    pending_posts = (
        db.execute(
            select(MapPost)
            .where(
                MapPost.is_parsed.is_(True),
                MapPost.parsed_source == "o-maps.spb.ru",
                MapPost.parse_status == ParseStatus.PENDING,
            )
            .options(joinedload(MapPost.region), joinedload(MapPost.event), joinedload(MapPost.author))
            .order_by(MapPost.updated_at.desc())
        )
        .scalars()
        .all()
    )
    regions = db.execute(select(Region).order_by(Region.name.asc())).scalars().all()
    return templates.TemplateResponse(
        request=request,
        name="admin_parsing.html",
        context={
            "request": request,
            "current_user": admin,
            "pending_posts": pending_posts,
            "regions": regions,
            "storage_service": storage_service,
        },
    )


def _redirect_after_import(result: dict) -> RedirectResponse:
    source = result["source_key"]
    return RedirectResponse(
        f"/admin/parsing?imported={result['imported']}&errors={result['errors']}&source={source}",
        status_code=302,
    )


@router.post("/parsing/import/spb")
def run_import_spb(db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    _ = admin
    return _redirect_after_import(import_parsed_items_to_queue(db, source_key="spb", per_source_batch=5))


@router.post("/parsing/import/moscow")
def run_import_moscow(db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    _ = admin
    return _redirect_after_import(import_parsed_items_to_queue(db, source_key="moscow", per_source_batch=5))


@router.post("/parsing/{post_id}/approve")
def approve_parsed_post(
    post_id: UUID,
    title: str = Form(...),
    region_name: str = Form(...),
    coordinates: str = Form(""),
    event_name: str = Form(""),
    year_of_event: int | None = Form(default=None),
    scale_denominator: int | None = Form(default=None),
    cartographer: str = Form(""),
    rights_holder: str = Form(""),
    description: str = Form(""),
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    _ = admin
    post = db.get(MapPost, post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Пост не найден")
    if not is_valid_region_name(region_name):
        return RedirectResponse("/admin/parsing?errors=invalid_region", status_code=302)
    if not is_valid_coordinates(coordinates):
        return RedirectResponse("/admin/parsing?errors=invalid_coordinates", status_code=302)

    region = _get_or_create_region(db, region_name)
    post.title = title.strip()
    post.region_id = region.id if region else None
    post.coordinates = store_coordinates(coordinates)
    post.description = description.strip()
    post.year_of_event = year_of_event
    post.scale_denominator = scale_denominator
    post.cartographer = store_optional_text(cartographer)
    post.rights_holder = store_optional_text(rights_holder)

    if event_name.strip():
        from app.routers.posts import _get_or_create_event

        event = _get_or_create_event(db, event_name, post.region_id, year_of_event, None)
        post.event_id = event.id if event else None

    post.parse_status = ParseStatus.APPROVED
    post.is_public = True
    db.commit()
    return RedirectResponse("/admin/parsing", status_code=302)


@router.post("/parsing/{post_id}/delete")
def delete_parsed_post(post_id: UUID, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    _ = admin
    post = db.get(MapPost, post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Пост не найден")
    db.delete(post)
    db.commit()
    return RedirectResponse("/admin/parsing", status_code=302)
