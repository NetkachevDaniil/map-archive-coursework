from uuid import UUID

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import case, select
from sqlalchemy.orm import Session, joinedload

from app.deps import require_admin
from app.db.session import get_db
from app.models.models import MapPost, ParseStatus, User
from app.services.map_fields import is_valid_territory, normalize_territory
from app.services.parser_service import import_parsed_items_to_queue
from app.services.storage_service import storage_service
from app.web import templates

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/parsing")
def parsing_queue(request: Request, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    all_posts = (
        db.execute(
            select(MapPost)
            .where(MapPost.is_parsed.is_(True), MapPost.parsed_source == "o-maps.spb.ru")
            .options(joinedload(MapPost.region), joinedload(MapPost.event), joinedload(MapPost.author))
            .order_by(
                case((MapPost.parse_status == ParseStatus.PENDING, 0), else_=1),
                MapPost.updated_at.desc(),
            )
        )
        .scalars()
        .all()
    )
    pending_posts = [p for p in all_posts if p.parse_status == ParseStatus.PENDING]
    processed_posts = [p for p in all_posts if p.parse_status != ParseStatus.PENDING]
    return templates.TemplateResponse(
        request=request,
        name="admin_parsing.html",
        context={
            "request": request,
            "current_user": admin,
            "pending_posts": pending_posts,
            "processed_posts": processed_posts,
            "storage_service": storage_service,
        },
    )


@router.post("/parsing/import")
def run_import(db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    _ = admin
    result = import_parsed_items_to_queue(db, per_source_batch=5)
    return RedirectResponse(
        f"/admin/parsing?imported={result['imported']}"
        f"&external={result['imported_with_external_url']}"
        f"&skipped={result['skipped']}"
        f"&errors={result['errors']}",
        status_code=302,
    )


@router.post("/parsing/{post_id}/approve")
def approve_parsed_post(
    post_id: UUID,
    title: str = Form(...),
    territory: str = Form(...),
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
    post.title = title.strip()
    if not is_valid_territory(territory):
        return RedirectResponse("/admin/parsing?errors=invalid_territory", status_code=302)
    post.territory = normalize_territory(territory) or "Неизвестно-Неизвестно-Неизвестно"
    post.description = description.strip()
    post.year_of_event = year_of_event
    post.scale_denominator = scale_denominator
    post.cartographer = cartographer.strip() or None
    post.rights_holder = rights_holder.strip() or None

    if event_name.strip():
        from app.routers.posts import _get_or_create_event

        event = _get_or_create_event(db, event_name, post.region_id, year_of_event, None)
        post.event_id = event.id if event else None

    post.parse_status = ParseStatus.APPROVED
    post.is_public = True
    db.commit()
    return RedirectResponse("/admin/parsing", status_code=302)


@router.post("/parsing/{post_id}/reject")
def reject_parsed_post(post_id: UUID, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    _ = admin
    post = db.get(MapPost, post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Пост не найден")
    post.parse_status = ParseStatus.REJECTED
    post.is_public = False
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
