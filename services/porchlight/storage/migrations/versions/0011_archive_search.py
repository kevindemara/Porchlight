"""Transactional substring full-text index for saved descriptions and notes."""

from alembic import op

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "CREATE VIRTUAL TABLE event_search USING fts5(summary, note, corrected_summary, "
        "content='events', content_rowid='rowid', tokenize='trigram')"
    )
    op.execute(
        "CREATE TRIGGER event_search_insert AFTER INSERT ON events BEGIN "
        "INSERT INTO event_search(rowid,summary,note,corrected_summary) "
        "VALUES(new.rowid,new.summary,new.note,new.corrected_summary); END"
    )
    op.execute(
        "CREATE TRIGGER event_search_delete AFTER DELETE ON events BEGIN "
        "INSERT INTO event_search(event_search,rowid,summary,note,corrected_summary) "
        "VALUES('delete',old.rowid,old.summary,old.note,old.corrected_summary); END"
    )
    op.execute(
        "CREATE TRIGGER event_search_update AFTER UPDATE OF summary,note,corrected_summary "
        "ON events BEGIN "
        "INSERT INTO event_search(event_search,rowid,summary,note,corrected_summary) "
        "VALUES('delete',old.rowid,old.summary,old.note,old.corrected_summary); "
        "INSERT INTO event_search(rowid,summary,note,corrected_summary) "
        "VALUES(new.rowid,new.summary,new.note,new.corrected_summary); END"
    )
    op.execute("INSERT INTO event_search(event_search) VALUES('rebuild')")


def downgrade() -> None:
    for name in ("insert", "delete", "update"):
        op.execute(f"DROP TRIGGER event_search_{name}")
    op.execute("DROP TABLE event_search")
