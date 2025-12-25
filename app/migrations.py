from sqlalchemy import text


def ensure_user_role_column(engine) -> None:
    """
    Best-effort migration for adding users.role on existing databases.
    """
    with engine.begin() as conn:
        exists = conn.execute(
            text(
                """
                SELECT 1
                FROM information_schema.columns
                WHERE table_name = 'users'
                  AND column_name = 'role'
                """
            )
        ).scalar()
        if not exists:
            conn.execute(
                text(
                    "ALTER TABLE users ADD COLUMN role VARCHAR(20) NOT NULL DEFAULT 'operator'"
            )
            )


def ensure_user_notification_cooldown_column(engine) -> None:
    """
    Best-effort migration for adding users.notification_cooldown_minutes on existing databases.
    """
    with engine.begin() as conn:
        exists = conn.execute(
            text(
                """
                SELECT 1
                FROM information_schema.columns
                WHERE table_name = 'users'
                  AND column_name = 'notification_cooldown_minutes'
                """
            )
        ).scalar()
        if not exists:
            conn.execute(
                text(
                    "ALTER TABLE users "
                    "ADD COLUMN notification_cooldown_minutes INTEGER NOT NULL DEFAULT 30"
                )
            )


def ensure_device_is_active_column(engine) -> None:
    """
    Best-effort migration for adding devices.is_active on existing databases.
    """
    with engine.begin() as conn:
        exists = conn.execute(
            text(
                """
                SELECT 1
                FROM information_schema.columns
                WHERE table_name = 'devices'
                  AND column_name = 'is_active'
                """
            )
        ).scalar()
        if not exists:
            conn.execute(
                text(
                    "ALTER TABLE devices "
                    "ADD COLUMN is_active BOOLEAN NOT NULL DEFAULT TRUE"
                )
            )


def ensure_device_deactivate_at_column(engine) -> None:
    """
    Best-effort migration for adding devices.deactivate_at on existing databases.
    """
    with engine.begin() as conn:
        exists = conn.execute(
            text(
                """
                SELECT 1
                FROM information_schema.columns
                WHERE table_name = 'devices'
                  AND column_name = 'deactivate_at'
                """
            )
        ).scalar()
        if not exists:
            conn.execute(
                text(
                    "ALTER TABLE devices "
                    "ADD COLUMN deactivate_at TIMESTAMP NULL"
                )
            )
