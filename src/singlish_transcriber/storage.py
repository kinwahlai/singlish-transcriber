"""SQLite persistence for meetings, speakers, and transcript turns."""

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

DEFAULT_DB_PATH = Path.home() / ".local" / "share" / "singlish-transcriber" / "db.sqlite"

SCHEMA = """
CREATE TABLE IF NOT EXISTS meetings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    filename TEXT NOT NULL,
    recorded_at TEXT,
    duration_seconds REAL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS speakers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    meeting_id INTEGER NOT NULL REFERENCES meetings(id),
    label TEXT NOT NULL,
    display_name TEXT
);

CREATE TABLE IF NOT EXISTS turns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    meeting_id INTEGER NOT NULL REFERENCES meetings(id),
    speaker_id INTEGER NOT NULL REFERENCES speakers(id),
    start_seconds REAL NOT NULL,
    end_seconds REAL NOT NULL,
    text TEXT NOT NULL
);
"""


def get_connection(db_path: str | Path = DEFAULT_DB_PATH) -> sqlite3.Connection:
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def ingest_meeting(
    conn: sqlite3.Connection,
    filename: str,
    duration_seconds: float,
    turns: list[dict],
) -> int:
    """Store a meeting and its diarized/transcribed turns. Returns the new meeting id.

    Each call creates a new meeting row, even for a filename ingested before - re-ingestion
    is treated as an intentional new processing run, not a duplicate to reject or merge.
    """
    created_at = datetime.now(UTC).isoformat()
    cur = conn.execute(
        "INSERT INTO meetings (filename, recorded_at, duration_seconds, created_at) "
        "VALUES (?, NULL, ?, ?)",
        (filename, duration_seconds, created_at),
    )
    meeting_id = cur.lastrowid

    speaker_ids: dict[str, int] = {}
    for turn in turns:
        label = turn["speaker_id"]
        if label not in speaker_ids:
            cur = conn.execute(
                "INSERT INTO speakers (meeting_id, label, display_name) VALUES (?, ?, NULL)",
                (meeting_id, label),
            )
            speaker_ids[label] = cur.lastrowid

        conn.execute(
            "INSERT INTO turns (meeting_id, speaker_id, start_seconds, end_seconds, text) "
            "VALUES (?, ?, ?, ?, ?)",
            (meeting_id, speaker_ids[label], turn["start"], turn["end"], turn["text"]),
        )

    conn.commit()
    return meeting_id


def get_meeting_transcript(conn: sqlite3.Connection, meeting_id: int) -> dict:
    """Retrieve a stored meeting and its turns, ordered by start time.

    Raises KeyError if no meeting with that id exists.
    """
    meeting_row = conn.execute(
        "SELECT id, filename, recorded_at, duration_seconds, created_at FROM meetings WHERE id = ?",
        (meeting_id,),
    ).fetchone()
    if meeting_row is None:
        raise KeyError(f"no meeting with id {meeting_id}")

    turn_rows = conn.execute(
        """
        SELECT turns.start_seconds, turns.end_seconds, turns.text,
               speakers.label, speakers.display_name
        FROM turns
        JOIN speakers ON speakers.id = turns.speaker_id
        WHERE turns.meeting_id = ?
        ORDER BY turns.start_seconds
        """,
        (meeting_id,),
    ).fetchall()

    return {
        "id": meeting_row["id"],
        "filename": meeting_row["filename"],
        "duration_seconds": meeting_row["duration_seconds"],
        "created_at": meeting_row["created_at"],
        "turns": [
            {
                "start": row["start_seconds"],
                "end": row["end_seconds"],
                "speaker_label": row["label"],
                "speaker_display_name": row["display_name"],
                "text": row["text"],
            }
            for row in turn_rows
        ],
    }


def list_meetings(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        "SELECT id, filename, duration_seconds, created_at FROM meetings ORDER BY created_at"
    ).fetchall()
    return [dict(row) for row in rows]
