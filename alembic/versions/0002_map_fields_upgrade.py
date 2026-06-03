"""add territory and ownership fields

Revision ID: 0002_map_fields_upgrade
Revises: 0001_initial
Create Date: 2026-05-25
"""

from alembic import op
import sqlalchemy as sa


revision = "0002_map_fields_upgrade"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "maps",
        sa.Column("territory", sa.String(length=255), nullable=False, server_default="Неизвестно-Неизвестно-Неизвестно"),
    )
    op.add_column("maps", sa.Column("cartographer", sa.String(length=255), nullable=True))
    op.add_column("maps", sa.Column("rights_holder", sa.String(length=255), nullable=True))
    op.create_index("ix_maps_territory", "maps", ["territory"])
    op.alter_column("maps", "territory", server_default=None)


def downgrade() -> None:
    op.drop_index("ix_maps_territory", table_name="maps")
    op.drop_column("maps", "rights_holder")
    op.drop_column("maps", "cartographer")
    op.drop_column("maps", "territory")
