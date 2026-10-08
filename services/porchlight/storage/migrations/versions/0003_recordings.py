"""Durable recording pagination, references and download jobs."""

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("events", sa.Column("camera_id", sa.String(), nullable=True))
    op.create_table(
        "recording_scans",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("since", sa.Float(), nullable=False),
        sa.Column("page", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.Float(), nullable=True),
        sa.Column("checked_at", sa.Float(), nullable=True),
    )
    op.create_table(
        "recording_references",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("source_key", sa.String(), unique=True, nullable=False),
        sa.Column("source_id", sa.String(), sa.ForeignKey("recording_scans.id"), nullable=False),
        sa.Column("source_type", sa.String(), nullable=False),
        sa.Column("camera_id", sa.String(), nullable=True),
        sa.Column("captured_at", sa.String(), nullable=True),
        sa.Column("raw_timestamp", sa.String(), nullable=False),
        sa.Column("discovered_at", sa.String(), nullable=False),
        sa.Column("media_path", sa.Text(), nullable=False),
        sa.Column("state", sa.String(), nullable=False),
        sa.Column("event_id", sa.String(), sa.ForeignKey("events.id"), nullable=True),
        sa.Column("safe_error", sa.String(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("recording_references")
    op.drop_table("recording_scans")
    op.drop_column("events", "camera_id")
