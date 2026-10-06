import os
import sqlite3
from contextlib import closing
from pathlib import Path


DB_PATH = os.getenv(
    "DATABASE_PATH",
    str(Path(__file__).with_name("electricity.db"))
)


def get_connection():
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def init_db():
    with closing(get_connection()) as conn:
        with conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id TEXT PRIMARY KEY,
                    room_number TEXT,
                    phone_number TEXT,
                    state TEXT NOT NULL DEFAULT 'new',
                    enabled INTEGER NOT NULL DEFAULT 1
                )
            """)


def get_user(user_id):
    with closing(get_connection()) as conn:
        row = conn.execute(
            """
            SELECT user_id, room_number, phone_number, state, enabled
            FROM users
            WHERE user_id = ?
            """,
            (user_id,)
        ).fetchone()

    if row is None:
        return None

    return {
        "user_id": row["user_id"],
        "room_number": row["room_number"],
        "phone_number": row["phone_number"],
        "state": row["state"],
        "enabled": bool(row["enabled"]),
    }


def create_user(user_id):
    with closing(get_connection()) as conn:
        with conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO users (user_id, state)
                VALUES (?, 'new')
                """,
                (user_id,)
            )


def update_state(user_id, state):
    with closing(get_connection()) as conn:
        with conn:
            conn.execute(
                "UPDATE users SET state = ? WHERE user_id = ?",
                (state, user_id)
            )


def update_room(user_id, room_number):
    with closing(get_connection()) as conn:
        with conn:
            conn.execute(
                "UPDATE users SET room_number = ? WHERE user_id = ?",
                (room_number, user_id)
            )


def update_phone(user_id, phone_number):
    with closing(get_connection()) as conn:
        with conn:
            conn.execute(
                """
                UPDATE users
                SET phone_number = ?, state = 'ready', enabled = 1
                WHERE user_id = ?
                """,
                (phone_number, user_id)
            )


def set_enabled(user_id, enabled):
    with closing(get_connection()) as conn:
        with conn:
            conn.execute(
                "UPDATE users SET enabled = ? WHERE user_id = ?",
                (int(enabled), user_id)
            )


def get_enabled_users():
    with closing(get_connection()) as conn:
        rows = conn.execute(
            """
            SELECT user_id, room_number, phone_number
            FROM users
            WHERE enabled = 1
              AND state = 'ready'
              AND room_number IS NOT NULL
              AND phone_number IS NOT NULL
            """
        ).fetchall()

    return [
        {
            "user_id": row["user_id"],
            "room_number": row["room_number"],
            "phone_number": row["phone_number"],
        }
        for row in rows
    ]
