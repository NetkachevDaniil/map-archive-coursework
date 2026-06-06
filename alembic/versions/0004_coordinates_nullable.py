"""make coordinates nullable

Revision ID: 0004_coordinates_nullable
Revises: 0003_coordinates
Create Date: 2026-06-06
"""

from alembic import op
import sqlalchemy as sa

revision = "0004_coordinates_nullable"
down_revision = "0003_coordinates"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("maps", "coordinates", existing_type=sa.String(length=255), nullable=True)


def downgrade() -> None:
    op.alter_column("maps", "coordinates", existing_type=sa.String(length=255), nullable=False)
