"""Persistência local e independente para o histórico oficial da Lotomaster."""
import json
import os
import sqlite3
import threading
from pathlib import Path

_DEFAULT_DB = (
    Path(os.getenv("TMPDIR", "/tmp")) / ".lotomaster.sqlite3"
    if os.getenv("VERCEL") == "1"
    else Path(__file__).resolve().parent.parent / ".lotomaster.sqlite3"
)
DB_PATH = Path(os.getenv("LOTOMASTER_DB_PATH", str(_DEFAULT_DB))).expanduser()
_init_lock = threading.Lock()
_initialized = False


def _connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(str(DB_PATH), timeout=20)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA busy_timeout=20000")
    return connection


def initialize():
    global _initialized
    if _initialized:
        return
    with _init_lock:
        if _initialized:
            return
        with _connect() as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute(
                """CREATE TABLE IF NOT EXISTS lottery_draws (
                    game TEXT NOT NULL,
                    contest INTEGER NOT NULL,
                    draw_date TEXT,
                    payload TEXT NOT NULL,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (game, contest)
                )"""
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_lottery_draws_game_contest ON lottery_draws(game, contest DESC)")
        _initialized = True


def save_draw(draw: dict) -> None:
    initialize()
    payload = json.dumps(draw, ensure_ascii=False, separators=(",", ":"))
    with _connect() as conn:
        conn.execute(
            """INSERT INTO lottery_draws(game, contest, draw_date, payload, updated_at)
               VALUES(?, ?, ?, ?, CURRENT_TIMESTAMP)
               ON CONFLICT(game, contest) DO UPDATE SET
                 draw_date=excluded.draw_date, payload=excluded.payload, updated_at=CURRENT_TIMESTAMP""",
            (draw["game"], int(draw["contest"]), draw.get("draw_date"), payload),
        )


def get_draw(game: str, contest: int) -> dict | None:
    initialize()
    with _connect() as conn:
        row = conn.execute("SELECT payload FROM lottery_draws WHERE game=? AND contest=?", (game, int(contest))).fetchone()
    return json.loads(row["payload"]) if row else None


def list_draws(game: str, limit: int = 50) -> list[dict]:
    initialize()
    limit = max(1, min(int(limit), 1000))
    with _connect() as conn:
        rows = conn.execute(
            "SELECT payload FROM lottery_draws WHERE game=? ORDER BY contest DESC LIMIT ?",
            (game, limit),
        ).fetchall()
    return [json.loads(row["payload"]) for row in rows]


def latest_draw(game: str) -> dict | None:
    draws = list_draws(game, 1)
    return draws[0] if draws else None


def clear_for_tests() -> None:
    """Auxiliar de testes: remove apenas o banco indicado por LOTOMASTER_DB_PATH."""
    global _initialized
    if DB_PATH.exists():
        DB_PATH.unlink()
    for suffix in ("-wal", "-shm"):
        candidate = Path(str(DB_PATH) + suffix)
        if candidate.exists():
            candidate.unlink()
    _initialized = False
