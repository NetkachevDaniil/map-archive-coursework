import enum
import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Enum, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class UserRole(str, enum.Enum):
    USER = "user"
    ADMIN = "admin"


class ParseStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    login: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    full_name: Mapped[str] = mapped_column(String(128), default="")
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole, name="user_role"), default=UserRole.USER, nullable=False)
    bio: Mapped[str] = mapped_column(Text, default="")
    avatar_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_email_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    maps: Mapped[list["MapPost"]] = relationship(back_populates="author")
    comments: Mapped[list["Comment"]] = relationship(back_populates="author")
    likes: Mapped[list["Like"]] = relationship(back_populates="user")


class Region(Base):
    __tablename__ = "regions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False, index=True)

    maps: Mapped[list["MapPost"]] = relationship(back_populates="region")
    events: Mapped[list["Event"]] = relationship(back_populates="region")


class Event(Base):
    __tablename__ = "events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    region_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("regions.id"), nullable=True)
    event_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    description: Mapped[str] = mapped_column(Text, default="")

    region: Mapped[Region | None] = relationship(back_populates="events")
    maps: Mapped[list["MapPost"]] = relationship(back_populates="event")


class MapPost(Base):
    __tablename__ = "maps"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    region_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("regions.id"), nullable=True, index=True)
    event_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("events.id"), nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    territory: Mapped[str] = mapped_column(String(255), default="Неизвестно-Неизвестно-Неизвестно", nullable=False, index=True)
    year_of_event: Mapped[int | None] = mapped_column(Integer, nullable=True)
    scale_denominator: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cartographer: Mapped[str | None] = mapped_column(String(255), nullable=True)
    rights_holder: Mapped[str | None] = mapped_column(String(255), nullable=True)
    image_key: Mapped[str] = mapped_column(Text, nullable=False)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    description: Mapped[str] = mapped_column(Text, default="")
    parsed_source: Mapped[str | None] = mapped_column(String(120), nullable=True)
    is_parsed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    parse_status: Mapped[ParseStatus] = mapped_column(
        Enum(ParseStatus, name="parse_status"),
        default=ParseStatus.APPROVED,
        nullable=False,
    )
    is_public: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    author: Mapped[User | None] = relationship(back_populates="maps")
    region: Mapped[Region | None] = relationship(back_populates="maps")
    event: Mapped[Event | None] = relationship(back_populates="maps")
    comments: Mapped[list["Comment"]] = relationship(back_populates="map_post", cascade="all, delete-orphan")
    likes: Mapped[list["Like"]] = relationship(back_populates="map_post", cascade="all, delete-orphan")


class Comment(Base):
    __tablename__ = "comments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    map_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("maps.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    map_post: Mapped[MapPost] = relationship(back_populates="comments")
    author: Mapped[User] = relationship(back_populates="comments")


class Like(Base):
    __tablename__ = "likes"
    __table_args__ = (UniqueConstraint("map_id", "user_id", name="uq_like_map_user"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    map_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("maps.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    map_post: Mapped[MapPost] = relationship(back_populates="likes")
    user: Mapped[User] = relationship(back_populates="likes")
