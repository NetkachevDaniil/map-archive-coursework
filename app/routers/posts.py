from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, RedirectResponse
from sqlalchemy import and_, select
from sqlalchemy.orm import Session, joinedload

from app.deps import get_current_user, require_user
from app.db.session import get_db
from app.models.models import Comment, Event, Like, MapPost, ParseStatus, Region, User, UserRole
from app.services.map_fields import is_valid_territory, normalize_territory
from app.services.storage_service import storage_service
from app.web import templates

router = APIRouter(prefix="/maps", tags=["maps"])


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


def _get_or_create_event(db: Session, event_name: str | None, region_id: UUID | None, year: int | None, event_date: str | None) -> Event | None:
    if not event_name or not event_name.strip():
        return None
    normalized = event_name.strip()
    event = db.execute(select(Event).where(Event.name == normalized, Event.year == year)).scalar_one_or_none()
    if event:
        return event
    event = Event(name=normalized, region_id=region_id, year=year, event_date=event_date or None)
    db.add(event)
    db.flush()
    return event


@router.get("/create")
def create_map_page(request: Request, current_user: User = Depends(require_user)):
    return templates.TemplateResponse(
        request=request,
        name="map_create.html",
        context={"request": request, "current_user": current_user, "error": None, "similar_posts": [], "form_data": {}},
    )


@router.post("/create")
def create_map_post(
    request: Request,
    title: str = Form(...),
    territory: str = Form(""),
    event_name: str = Form(""),
    year_of_event: int | None = Form(default=None),
    scale_denominator: int | None = Form(default=None),
    cartographer: str = Form(""),
    rights_holder: str = Form(""),
    description: str = Form(""),
    image: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user),
):
    if not image.filename:
        return templates.TemplateResponse(
            request=request,
            name="map_create.html",
            context={"request": request, "current_user": current_user, "error": "Выберите изображение карты", "similar_posts": [], "form_data": {}},
            status_code=400,
        )

    if not is_valid_territory(territory):
        return templates.TemplateResponse(
            request=request,
            name="map_create.html",
            context={
                "request": request,
                "current_user": current_user,
                "error": "Поле 'Территория' должно быть в формате: Регион-Город-Район",
                "similar_posts": [],
                "form_data": {
                    "title": title,
                    "territory": territory,
                    "event_name": event_name,
                    "year_of_event": year_of_event,
                    "scale_denominator": scale_denominator,
                    "cartographer": cartographer,
                    "rights_holder": rights_holder,
                    "description": description,
                },
            },
            status_code=400,
        )

    normalized_territory = normalize_territory(territory)
    similar_posts = (
        db.execute(
            select(MapPost)
            .where(
                MapPost.is_public.is_(True),
                MapPost.territory == normalized_territory,
                MapPost.year_of_event == year_of_event,
            )
            .order_by(MapPost.created_at.desc())
            .limit(20)
        )
        .scalars()
        .all()
    )

    event = _get_or_create_event(db, event_name, None, year_of_event, None)
    image_key = storage_service.save_upload(image, folder="maps")

    post = MapPost(
        user_id=current_user.id,
        region_id=None,
        event_id=event.id if event else None,
        title=title.strip(),
        territory=normalized_territory,
        year_of_event=year_of_event,
        scale_denominator=scale_denominator,
        cartographer=cartographer.strip() or None,
        rights_holder=rights_holder.strip() or None,
        image_key=image_key,
        source_url=None,
        description=description.strip(),
        is_parsed=False,
        parse_status=ParseStatus.APPROVED,
        is_public=True,
    )
    db.add(post)
    db.commit()
    if similar_posts:
        return RedirectResponse(f"/maps/{post.id}?similar_notice=1", status_code=302)
    return RedirectResponse(f"/maps/{post.id}", status_code=302)


@router.get("/{post_id}")
def map_detail(post_id: UUID, request: Request, db: Session = Depends(get_db), current_user: User | None = Depends(get_current_user)):
    result = db.execute(
        select(MapPost)
        .where(MapPost.id == post_id)
        .options(joinedload(MapPost.author), joinedload(MapPost.region), joinedload(MapPost.event), joinedload(MapPost.comments).joinedload(Comment.author), joinedload(MapPost.likes))
    ).unique()
    post = result.scalar_one_or_none()
    if not post:
        return templates.TemplateResponse(
            request=request,
            name="not_found.html",
            context={"request": request, "current_user": current_user},
            status_code=404,
        )
    if not post.is_public and (not current_user or current_user.role != UserRole.ADMIN):
        raise HTTPException(status_code=403, detail="Пост недоступен")

    liked = False
    if current_user:
        liked = any(l.user_id == current_user.id for l in post.likes)
    can_manage = bool(current_user and (current_user.role == UserRole.ADMIN or current_user.id == post.user_id))

    return templates.TemplateResponse(
        request=request,
        name="map_detail.html",
        context={
            "request": request,
            "current_user": current_user,
            "post": post,
            "image_url": storage_service.get_public_url(post.image_key),
            "liked": liked,
            "likes_count": len(post.likes),
            "can_manage": can_manage,
            "similar_notice": request.query_params.get("similar_notice"),
        },
    )


@router.get("/{post_id}/edit")
def edit_map_page(post_id: UUID, request: Request, db: Session = Depends(get_db), current_user: User = Depends(require_user)):
    post = db.get(MapPost, post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Пост не найден")
    if current_user.role != UserRole.ADMIN and current_user.id != post.user_id:
        raise HTTPException(status_code=403, detail="Недостаточно прав")
    return templates.TemplateResponse(
        request=request,
        name="map_edit.html",
        context={"request": request, "current_user": current_user, "post": post, "error": None},
    )


@router.post("/{post_id}/edit")
def edit_map_submit(
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
    current_user: User = Depends(require_user),
):
    post = db.get(MapPost, post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Пост не найден")
    if current_user.role != UserRole.ADMIN and current_user.id != post.user_id:
        raise HTTPException(status_code=403, detail="Недостаточно прав")
    if not is_valid_territory(territory):
        return RedirectResponse(url=f"/maps/{post_id}/edit?error=territory", status_code=302)

    post.title = title.strip()
    post.territory = normalize_territory(territory)
    post.year_of_event = year_of_event
    post.scale_denominator = scale_denominator
    post.cartographer = cartographer.strip() or None
    post.rights_holder = rights_holder.strip() or None
    post.description = description.strip()
    if event_name.strip():
        event = _get_or_create_event(db, event_name, post.region_id, year_of_event, None)
        post.event_id = event.id if event else None
    db.commit()
    return RedirectResponse(url=f"/maps/{post_id}", status_code=302)


@router.post("/{post_id}/delete")
def delete_map(post_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(require_user)):
    post = db.get(MapPost, post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Пост не найден")
    if current_user.role != UserRole.ADMIN and current_user.id != post.user_id:
        raise HTTPException(status_code=403, detail="Недостаточно прав")
    db.delete(post)
    db.commit()
    return RedirectResponse(url="/profile/me", status_code=302)


@router.post("/{post_id}/comment")
def add_comment(
    post_id: UUID,
    text: str = Form(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user),
):
    post = db.get(MapPost, post_id)
    if not post or not post.is_public:
        raise HTTPException(status_code=404, detail="Пост не найден")

    comment = Comment(map_id=post.id, user_id=current_user.id, text=text.strip())
    db.add(comment)
    db.commit()
    return RedirectResponse(url=f"/maps/{post_id}", status_code=302)


@router.post("/{post_id}/like")
def toggle_like(post_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(require_user)):
    post = db.get(MapPost, post_id)
    if not post or not post.is_public:
        raise HTTPException(status_code=404, detail="Пост не найден")

    existing = db.execute(select(Like).where(and_(Like.map_id == post_id, Like.user_id == current_user.id))).scalar_one_or_none()
    if existing:
        db.delete(existing)
    else:
        db.add(Like(map_id=post_id, user_id=current_user.id))
    db.commit()
    return RedirectResponse(url=f"/maps/{post_id}", status_code=302)


@router.get("/{post_id}/download")
def download_map(post_id: UUID, db: Session = Depends(get_db)):
    post = db.get(MapPost, post_id)
    if not post or not post.is_public:
        raise HTTPException(status_code=404, detail="Пост не найден")

    if not post.image_key:
        raise HTTPException(status_code=404, detail="Файл не найден")

    if storage_service.settings.use_s3:
        return RedirectResponse(url=storage_service.get_public_url(post.image_key), status_code=302)

    settings_path = storage_service.settings.local_upload_dir
    file_path = f"{settings_path}/{post.image_key}"
    return FileResponse(file_path, filename=f"map-{post.id}.jpg")
