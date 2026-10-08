"""Initial local owner, settings, archive and job contracts."""

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("login_name", sa.String(), nullable=False, unique=True),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("created_at", sa.Float(), nullable=False),
    )
    op.create_table(
        "sessions",
        sa.Column("id_hash", sa.String(), primary_key=True),
        sa.Column("user_id", sa.String(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("csrf_hash", sa.String(), nullable=False),
        sa.Column("expires_at", sa.Float(), nullable=False),
    )
    op.create_table(
        "settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("values", sa.JSON(), nullable=False),
    )
    op.create_table(
        "login_attempts",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("attempted_at", sa.Float(), nullable=False),
    )
    op.create_index("ix_login_attempts_attempted_at", "login_attempts", ["attempted_at"])
    op.create_table(
        "media_assets",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("sha256", sa.String(), nullable=False, unique=True),
        sa.Column("relative_path", sa.String(), nullable=False),
        sa.Column("bytes", sa.Integer(), nullable=False),
        sa.Column("duration_seconds", sa.Float(), nullable=False),
        sa.Column("width", sa.Integer(), nullable=False),
        sa.Column("height", sa.Integer(), nullable=False),
    )
    op.create_table(
        "events",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("source_type", sa.String(), nullable=False),
        sa.Column("source_key", sa.String(), nullable=False, unique=True),
        sa.Column("captured_at", sa.String(), nullable=True),
        sa.Column("discovered_at", sa.String(), nullable=False),
        sa.Column("timestamp_quality", sa.String(), nullable=False),
        sa.Column("media_id", sa.String(), sa.ForeignKey("media_assets.id"), nullable=False),
        sa.Column("analysis_status", sa.String(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("favourite", sa.Boolean(), nullable=False),
        sa.Column("note", sa.Text(), nullable=False),
    )
    op.create_table(
        "jobs",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("type", sa.String(), nullable=False),
        sa.Column("dedup_key", sa.String(), nullable=False, unique=True),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("attempt", sa.Integer(), nullable=False),
        sa.Column("available_at", sa.Float(), nullable=False),
        sa.Column("lease_until", sa.Float(), nullable=True),
        sa.Column("safe_error", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    for name in [
        "jobs",
        "events",
        "media_assets",
        "login_attempts",
        "settings",
        "sessions",
        "users",
    ]:
        op.drop_table(name)
