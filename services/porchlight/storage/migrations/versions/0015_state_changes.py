"""Bounded transactional UI invalidations without private payloads."""

from alembic import op

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None

TOPICS = {
    "events": "activity,cameras",
    "analyses": "activity",
    "media_assets": "activity,cameras",
    "camera_metadata": "cameras",
    "camera_commands": "cameras,health",
    "integration_state": "cameras,settings,health",
    "settings": "settings,health",
    "jobs": "activity,settings,health",
    "recording_scans": "settings,health",
    "recording_references": "settings,health",
    "live_captures": "library,health",
    "notifications": "notifications",
    "notification_rules": "notifications",
    "notification_outbox": "notifications,health",
    "saved_views": "activity",
    "push_devices": "notifications,health",
    "push_deliveries": "notifications,health",
}


def upgrade() -> None:
    op.execute(
        "CREATE TABLE state_changes(id INTEGER PRIMARY KEY AUTOINCREMENT, topics TEXT NOT NULL)"
    )
    for table, topics in TOPICS.items():
        for operation in ("INSERT", "UPDATE", "DELETE"):
            op.execute(
                f"CREATE TRIGGER ui_{table}_{operation.lower()} AFTER {operation} ON {table} BEGIN "
                f"INSERT INTO state_changes(topics) VALUES('{topics}'); "
                "DELETE FROM state_changes WHERE id <= (SELECT MAX(id)-512 FROM state_changes); END"
            )


def downgrade() -> None:
    for table in TOPICS:
        for operation in ("insert", "update", "delete"):
            op.execute(f"DROP TRIGGER ui_{table}_{operation}")
    op.execute("DROP TABLE state_changes")
