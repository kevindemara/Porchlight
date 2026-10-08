"""Owner-requested local live recordings and snapshots."""

import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "live_captures",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("camera_id", sa.String(), nullable=False),
        sa.Column("camera_name", sa.String(), nullable=False),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("state", sa.String(), nullable=False),
        sa.Column("saved_at", sa.String(), nullable=False),
        sa.Column("bytes", sa.Integer(), nullable=False),
        sa.Column("duration_seconds", sa.Float(), nullable=True),
        sa.Column("width", sa.Integer(), nullable=False),
        sa.Column("height", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(), nullable=True),
        sa.Column("safe_error", sa.String(), nullable=True),
    )
    op.create_index("ix_live_captures_saved_at", "live_captures", ["saved_at"])


def downgrade() -> None:
    op.drop_table("live_captures")
