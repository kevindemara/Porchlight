"""Explicit JPEG archive assets alongside existing MP4 recordings."""

import sqlalchemy as sa
from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "media_assets",
        sa.Column("media_type", sa.String(), nullable=False, server_default="video/mp4"),
    )


def downgrade() -> None:
    op.drop_column("media_assets", "media_type")
