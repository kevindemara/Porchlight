"""Separate owner labels and transactional searchable wording; retain all AI revisions."""

import sqlalchemy as sa
from alembic import op

revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None


def rebuild_search(include_labels: bool) -> None:
    for name in ("insert", "delete", "update"):
        op.execute(f"DROP TRIGGER event_search_{name}")
    op.execute("DROP TABLE event_search")
    columns = "summary,note,corrected_summary" + (",labels_summary" if include_labels else "")
    op.execute(
        f"CREATE VIRTUAL TABLE event_search USING fts5({columns}, "
        "content='events', content_rowid='rowid', tokenize='trigram')"
    )
    old = ",".join(f"old.{column}" for column in columns.split(","))
    new = ",".join(f"new.{column}" for column in columns.split(","))
    insert = f"INSERT INTO event_search(rowid,{columns}) VALUES(new.rowid,{new}); "
    remove = (
        f"INSERT INTO event_search(event_search,rowid,{columns}) VALUES('delete',old.rowid,{old}); "
    )
    op.execute(f"CREATE TRIGGER event_search_insert AFTER INSERT ON events BEGIN {insert}END")
    op.execute(f"CREATE TRIGGER event_search_delete AFTER DELETE ON events BEGIN {remove}END")
    op.execute(
        f"CREATE TRIGGER event_search_update AFTER UPDATE OF {columns} ON events "
        f"BEGIN {remove}{insert}END"
    )
    op.execute("INSERT INTO event_search(event_search) VALUES('rebuild')")


def upgrade() -> None:
    op.add_column("events", sa.Column("corrected_entities", sa.JSON(), nullable=True))
    op.add_column("events", sa.Column("labels_summary", sa.Text(), nullable=True))
    op.add_column(
        "events", sa.Column("correction_revision", sa.Integer(), nullable=False, server_default="0")
    )
    op.add_column("events", sa.Column("correction_based_on", sa.Integer(), nullable=True))
    op.add_column("events", sa.Column("correction_updated_at", sa.String(), nullable=True))
    rebuild_search(True)


def downgrade() -> None:
    rebuild_search(False)
    for column in (
        "corrected_entities",
        "labels_summary",
        "correction_revision",
        "correction_based_on",
        "correction_updated_at",
    ):
        op.drop_column("events", column)
