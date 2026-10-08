"""Independent resumable history cursors and durable silent-import provenance."""

import sqlalchemy as sa
from alembic import op

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "events", sa.Column("historical", sa.Boolean(), nullable=False, server_default="0")
    )
    op.add_column(
        "recording_references",
        sa.Column("historical", sa.Boolean(), nullable=False, server_default="0"),
    )
    op.add_column(
        "recording_scans", sa.Column("generation", sa.Integer(), nullable=False, server_default="0")
    )
    op.add_column("recording_scans", sa.Column("history_days", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("recording_scans", "history_days")
    op.drop_column("recording_scans", "generation")
    op.drop_column("recording_references", "historical")
    op.drop_column("events", "historical")
