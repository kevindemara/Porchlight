"""Private device metadata and durable per-device delivery; secrets stay in DPAPI."""

import sqlalchemy as sa
from alembic import op

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "push_devices",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("endpoint_hash", sa.String(), nullable=False, unique=True),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.String(), nullable=False),
    )
    op.create_table(
        "push_deliveries",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column(
            "device_id",
            sa.String(),
            sa.ForeignKey("push_devices.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "outbox_id",
            sa.String(),
            sa.ForeignKey("notification_outbox.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("dedup_key", sa.String(), nullable=False, unique=True),
        sa.Column(
            "event_id", sa.String(), sa.ForeignKey("events.id", ondelete="CASCADE"), nullable=True
        ),
        sa.Column("tag", sa.String(), nullable=False),
        sa.Column("body", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.Column("available_at", sa.Float(), nullable=False),
        sa.Column("expires_at", sa.Float(), nullable=False),
        sa.Column("attempt", sa.Integer(), nullable=False),
        sa.Column("safe_error", sa.String(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("push_deliveries")
    op.drop_table("push_devices")
