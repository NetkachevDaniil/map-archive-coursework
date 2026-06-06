"""rename territory to coordinates

Revision ID: 0003_coordinates
Revises: 0002_map_fields_upgrade
Create Date: 2026-06-06
"""

from alembic import op

revision = "0003_coordinates"
down_revision = "0002_map_fields_upgrade"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_index("ix_maps_territory", table_name="maps")
    op.alter_column("maps", "territory", new_column_name="coordinates")
    op.create_index("ix_maps_coordinates", "maps", ["coordinates"])


def downgrade() -> None:
    op.drop_index("ix_maps_coordinates", table_name="maps")
    op.alter_column("maps", "coordinates", new_column_name="territory")
    op.create_index("ix_maps_territory", "maps", ["territory"])
