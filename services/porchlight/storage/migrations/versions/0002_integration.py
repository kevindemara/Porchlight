"""Persist cached inventory separately from DPAPI-protected auth material."""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "integration_state",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("values", sa.JSON(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("integration_state")
