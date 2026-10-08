"""Manual camera command audit and read-back; interrupted commands are never replayed."""

import sqlalchemy as sa
from alembic import op

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "camera_commands",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("camera_id", sa.String(), nullable=False),
        sa.Column("actor", sa.String(), nullable=False),
        sa.Column("operation", sa.String(), nullable=False),
        sa.Column("desired", sa.Boolean(), nullable=False),
        sa.Column("state", sa.String(), nullable=False),
        sa.Column("observed", sa.Boolean(), nullable=True),
        sa.Column("safe_error", sa.String(), nullable=True),
        sa.Column("created_at", sa.String(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("camera_commands")
