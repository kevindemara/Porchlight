"""Optional non-identifying face observations, independent of Qwen analysis."""

import sqlalchemy as sa
from alembic import op

revision = "0018"
down_revision = "0017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "face_detections",
        sa.Column(
            "event_id",
            sa.String(),
            sa.ForeignKey("events.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("job_id", sa.String(), nullable=False),
        sa.Column("report", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.Column("elapsed_seconds", sa.Float(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("face_detections")
