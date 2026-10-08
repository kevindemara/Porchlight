"""Transactional rule intents and local inbox."""

import sqlalchemy as sa
from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "notification_rules",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("values", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.String(), nullable=False),
    )
    op.create_table(
        "notification_outbox",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column(
            "event_id", sa.String(), sa.ForeignKey("events.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "rule_id",
            sa.String(),
            sa.ForeignKey("notification_rules.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("channel", sa.String(), nullable=False),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("dedup_key", sa.String(), nullable=False, unique=True),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("available_at", sa.Float(), nullable=False),
        sa.Column("expires_at", sa.Float(), nullable=False),
        sa.Column("attempt", sa.Integer(), nullable=False),
        sa.Column("safe_error", sa.String(), nullable=True),
    )
    op.create_table(
        "notifications",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column(
            "event_id", sa.String(), sa.ForeignKey("events.id", ondelete="CASCADE"), nullable=True
        ),
        sa.Column(
            "rule_id",
            sa.String(),
            sa.ForeignKey("notification_rules.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("tag", sa.String(), nullable=False, unique=True),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("body", sa.String(), nullable=False),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.Column("read", sa.Boolean(), nullable=False),
    )


def downgrade() -> None:
    for table in ("notifications", "notification_outbox", "notification_rules"):
        op.drop_table(table)
