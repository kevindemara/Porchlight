"""Local review, metadata and restart-safe deletion journal."""

import sqlalchemy as sa
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("events", sa.Column("corrected_summary", sa.Text(), nullable=True))
    op.create_table(
        "source_tombstones",
        sa.Column("source_key", sa.String(), primary_key=True),
        sa.Column("deleted_at", sa.String(), nullable=False),
    )
    op.create_table("file_deletions", sa.Column("relative_path", sa.String(), primary_key=True))
    op.create_table(
        "camera_metadata",
        sa.Column("camera_id", sa.String(), primary_key=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("group", sa.String(), nullable=False),
    )
    op.create_index("ix_events_camera_time", "events", ["camera_id", "captured_at"])


def downgrade() -> None:
    op.drop_index("ix_events_camera_time", "events")
    for table in ("camera_metadata", "file_deletions", "source_tombstones"):
        op.drop_table(table)
    op.drop_column("events", "corrected_summary")
