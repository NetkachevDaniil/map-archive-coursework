"""initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-05-25
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    user_role = postgresql.ENUM("USER", "ADMIN", name="user_role")
    parse_status = postgresql.ENUM("PENDING", "APPROVED", "REJECTED", name="parse_status")

    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("login", sa.String(length=64), nullable=False),
        sa.Column("full_name", sa.String(length=128), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("role", user_role, nullable=False),
        sa.Column("bio", sa.Text(), nullable=False),
        sa.Column("avatar_url", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("is_email_verified", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("login"),
        sa.UniqueConstraint("email"),
    )
    op.create_index("ix_users_login", "users", ["login"])
    op.create_index("ix_users_email", "users", ["email"])

    op.create_table(
        "regions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.UniqueConstraint("name"),
    )
    op.create_index("ix_regions_name", "regions", ["name"])

    op.create_table(
        "events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("region_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("regions.id"), nullable=True),
        sa.Column("event_date", sa.Date(), nullable=True),
        sa.Column("year", sa.Integer(), nullable=True),
        sa.Column("description", sa.Text(), nullable=False),
    )
    op.create_index("ix_events_name", "events", ["name"])

    op.create_table(
        "maps",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("region_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("regions.id"), nullable=True),
        sa.Column("event_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("events.id"), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("year_of_event", sa.Integer(), nullable=True),
        sa.Column("scale_denominator", sa.Integer(), nullable=True),
        sa.Column("image_key", sa.Text(), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("parsed_source", sa.String(length=120), nullable=True),
        sa.Column("is_parsed", sa.Boolean(), nullable=False),
        sa.Column("parse_status", parse_status, nullable=False),
        sa.Column("is_public", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_maps_title", "maps", ["title"])
    op.create_index("ix_maps_user_id", "maps", ["user_id"])
    op.create_index("ix_maps_region_id", "maps", ["region_id"])
    op.create_index("ix_maps_event_id", "maps", ["event_id"])

    op.create_table(
        "comments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("map_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("maps.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_comments_map_id", "comments", ["map_id"])
    op.create_index("ix_comments_user_id", "comments", ["user_id"])

    op.create_table(
        "likes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("map_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("maps.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("map_id", "user_id", name="uq_like_map_user"),
    )
    op.create_index("ix_likes_map_id", "likes", ["map_id"])
    op.create_index("ix_likes_user_id", "likes", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_likes_user_id", table_name="likes")
    op.drop_index("ix_likes_map_id", table_name="likes")
    op.drop_table("likes")
    op.drop_index("ix_comments_user_id", table_name="comments")
    op.drop_index("ix_comments_map_id", table_name="comments")
    op.drop_table("comments")
    op.drop_index("ix_maps_event_id", table_name="maps")
    op.drop_index("ix_maps_region_id", table_name="maps")
    op.drop_index("ix_maps_user_id", table_name="maps")
    op.drop_index("ix_maps_title", table_name="maps")
    op.drop_table("maps")
    op.drop_index("ix_events_name", table_name="events")
    op.drop_table("events")
    op.drop_index("ix_regions_name", table_name="regions")
    op.drop_table("regions")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_index("ix_users_login", table_name="users")
    op.drop_table("users")

    sa.Enum(name="parse_status").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="user_role").drop(op.get_bind(), checkfirst=True)
