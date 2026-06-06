from fastapi import APIRouter, Depends, File, Form, Query, Request, UploadFile
from fastapi.responses import RedirectResponse
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session, joinedload

from app.deps import get_current_user, require_user
from app.db.session import get_db
from app.models.models import Comment, Event, Like, MapPost, ParseStatus, Region, User
from app.services.storage_service import storage_service
from app.web import templates

router = APIRouter(tags=["pages"])


def _posts_for_feed(db: Session):
    posts_stmt = (
        select(MapPost)
        .where(
            and_(
                MapPost.is_public.is_(True),
                or_(MapPost.is_parsed.is_(False), MapPost.parse_status == ParseStatus.APPROVED),
            )
        )
        .options(joinedload(MapPost.author), joinedload(MapPost.region), joinedload(MapPost.event))
        .order_by(MapPost.created_at.desc())
        .limit(50)
    )
    posts = db.execute(posts_stmt).scalars().all()
    if not posts:
        return []

    ids = [p.id for p in posts]
    likes_counts = {
        row[0]: row[1]
        for row in db.execute(select(Like.map_id, func.count(Like.id)).where(Like.map_id.in_(ids)).group_by(Like.map_id)).all()
    }
    comments_counts = {
        row[0]: row[1]
        for row in db.execute(
            select(Comment.map_id, func.count(Comment.id)).where(Comment.map_id.in_(ids)).group_by(Comment.map_id)
        ).all()
    }
    return [(p, likes_counts.get(p.id, 0), comments_counts.get(p.id, 0)) for p in posts]


@router.get("/")
def home(request: Request, db: Session = Depends(get_db), current_user: User | None = Depends(get_current_user)):
    rows = _posts_for_feed(db)
    post_ids = [post.id for post, _, _ in rows]
    liked_ids: set = set()
    if current_user and post_ids:
        liked_ids = {
            row[0]
            for row in db.execute(
                select(Like.map_id).where(Like.user_id == current_user.id, Like.map_id.in_(post_ids))
            ).all()
        }
    posts = []
    for post, likes_count, comments_count in rows:
        posts.append(
            {
                "post": post,
                "likes_count": likes_count,
                "comments_count": comments_count,
                "liked": post.id in liked_ids,
                "image_url": storage_service.get_public_url(post.image_key),
            }
        )
    return templates.TemplateResponse(request=request, name="home.html", context={"request": request, "current_user": current_user, "posts": posts})


@router.get("/catalog")
def catalog(
    request: Request,
    q: str | None = Query(default=None),
    tab: str = Query(default="maps"),
    region: str | None = Query(default=None),
    sort: str = Query(default="published_desc"),
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_current_user),
):
    search = (q or "").strip()
    region_filter = (region or "").strip()

    maps_stmt = (
        select(MapPost)
        .options(joinedload(MapPost.region), joinedload(MapPost.event), joinedload(MapPost.author))
        .where(MapPost.is_public.is_(True))
    )
    if search:
        maps_stmt = maps_stmt.where(
            or_(
                MapPost.title.ilike(f"%{search}%"),
                MapPost.description.ilike(f"%{search}%"),
            )
        )
    if region_filter:
        maps_stmt = maps_stmt.where(MapPost.region.has(Region.name.ilike(f"%{region_filter}%")))

    if sort == "year_asc":
        maps_stmt = maps_stmt.order_by(MapPost.year_of_event.asc().nullslast())
    elif sort == "year_desc":
        maps_stmt = maps_stmt.order_by(MapPost.year_of_event.desc().nullslast())
    elif sort == "coordinates_asc":
        maps_stmt = maps_stmt.order_by(MapPost.coordinates.asc().nullslast())
    elif sort == "coordinates_desc":
        maps_stmt = maps_stmt.order_by(MapPost.coordinates.desc().nullslast())
    elif sort == "region_asc":
        maps_stmt = maps_stmt.outerjoin(Region, MapPost.region_id == Region.id).order_by(Region.name.asc().nullslast())
    elif sort == "region_desc":
        maps_stmt = maps_stmt.outerjoin(Region, MapPost.region_id == Region.id).order_by(Region.name.desc().nullslast())
    elif sort == "published_asc":
        maps_stmt = maps_stmt.order_by(MapPost.created_at.asc())
    else:
        maps_stmt = maps_stmt.order_by(MapPost.created_at.desc())
    maps = db.execute(maps_stmt.limit(200)).unique().scalars().all()

    regions = db.execute(select(Region).order_by(Region.name.asc())).scalars().all()

    users_stmt = select(User).where(User.is_active.is_(True))
    if search:
        users_stmt = users_stmt.where(or_(User.login.ilike(f"%{search}%"), User.full_name.ilike(f"%{search}%")))
    users = db.execute(users_stmt.order_by(User.created_at.desc()).limit(200)).scalars().all()

    return templates.TemplateResponse(
        request=request,
        name="catalog.html",
        context={
            "request": request,
            "current_user": current_user,
            "tab": tab,
            "q": search,
            "region": region_filter,
            "sort": sort,
            "maps": maps,
            "users": users,
            "regions": regions,
        },
    )


@router.get("/profile/me")
def my_profile(request: Request, db: Session = Depends(get_db), current_user: User = Depends(require_user)):
    posts = (
        db.execute(
            select(MapPost)
            .where(MapPost.user_id == current_user.id)
            .order_by(MapPost.created_at.desc())
            .options(joinedload(MapPost.region), joinedload(MapPost.event))
        )
        .scalars()
        .all()
    )
    return templates.TemplateResponse(
        request=request,
        name="profile.html",
        context={
            "request": request,
            "current_user": current_user,
            "profile_user": current_user,
            "posts": posts,
            "is_self": True,
            "storage_service": storage_service,
        },
    )


@router.get("/profile/me/edit")
def profile_edit_page(request: Request, current_user: User = Depends(require_user)):
    return templates.TemplateResponse(
        request=request,
        name="profile_edit.html",
        context={
            "request": request,
            "current_user": current_user,
            "profile_user": current_user,
            "error": None,
        },
    )


@router.post("/profile/me/edit")
def profile_edit_submit(
    request: Request,
    full_name: str = Form(""),
    bio: str = Form(""),
    avatar: UploadFile | None = File(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user),
):
    current_user.full_name = full_name.strip() or current_user.login
    current_user.bio = bio.strip()

    if avatar and avatar.filename:
        key = storage_service.save_upload(avatar, folder="avatars")
        current_user.avatar_url = storage_service.get_public_url(key)

    db.commit()
    return RedirectResponse(url="/profile/me", status_code=303)


@router.get("/profile/{login}")
def profile_page(request: Request, login: str, db: Session = Depends(get_db), current_user: User | None = Depends(get_current_user)):
    user = db.execute(select(User).where(User.login == login)).scalar_one_or_none()
    if not user:
        return templates.TemplateResponse(
            request=request,
            name="not_found.html",
            context={"request": request, "current_user": current_user},
            status_code=404,
        )

    posts = (
        db.execute(
            select(MapPost)
            .where(MapPost.user_id == user.id, MapPost.is_public.is_(True))
            .order_by(MapPost.created_at.desc())
            .options(joinedload(MapPost.region), joinedload(MapPost.event))
        )
        .scalars()
        .all()
    )
    return templates.TemplateResponse(
        request=request,
        name="profile.html",
        context={
            "request": request,
            "current_user": current_user,
            "profile_user": user,
            "posts": posts,
            "is_self": bool(current_user and current_user.id == user.id),
            "storage_service": storage_service,
        },
    )
