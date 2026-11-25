"""Persistência local e independente para o histórico oficial da Lotomaster."""
import json
import math
import os
import sqlite3
import threading
from pathlib import Path
from .validation import MAX_CONTEST, validate_draw

# Bound work for corrupt legacy caches; budget exhaustion is an explicit error.
MAX_SCAN_ROWS = 2048
MAX_PAYLOAD_BYTES = 65_536
MAX_RANGE_WIDTH = 500
_PAYLOAD_SELECT = "CASE WHEN length(CAST(payload AS BLOB)) <= ? THEN payload ELSE NULL END AS payload"

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
    payload = json.dumps(draw, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    if len(payload.encode("utf-8")) > MAX_PAYLOAD_BYTES:
        raise ValueError("Concurso excede o limite de armazenamento do cache.")
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
        row = conn.execute(f"SELECT contest, {_PAYLOAD_SELECT} FROM lottery_draws WHERE game=? AND contest=?", (MAX_PAYLOAD_BYTES, game, int(contest))).fetchone()
    return _valid_row(game, row) if row else None


def _valid_row(game, row):
    """Validate legacy rows and bind their payload to the SQLite key."""
    try:
        if type(row["contest"]) is not int:
            return None
        draw = json.loads(row["payload"])
        checked = validate_draw(game, draw, require_game=True, require_special=True)
        if checked["contest"] != row["contest"]:
            return None
        estimated_prize = draw.get("estimated_prize")
        if isinstance(estimated_prize, float) and not math.isfinite(estimated_prize):
            return None
        return {**{k: v for k, v in draw.items() if k not in {"_latest_checked_at", "_known_latest_contest", "source", "warning"}}, **checked}
    except (ValueError, TypeError, KeyError, OverflowError, RecursionError):
        return None


def latest_known_contest(game: str) -> int | None:
    """Highest structurally valid cached contest, not evidence of freshness."""
    draw = latest_draw(game)
    return draw["contest"] if draw else None


def list_draws(game: str, limit: int = 50) -> list[dict]:
    """Return valid rows, or fail explicitly if the bounded scan is exhausted."""
    initialize()
    limit = max(1, min(int(limit), 1000))
    result = []
    with _connect() as conn:
        rows = conn.execute(
            f"SELECT contest, {_PAYLOAD_SELECT} FROM lottery_draws "
            "WHERE game=? AND contest BETWEEN 1 AND ? ORDER BY contest DESC LIMIT ?",
            (MAX_PAYLOAD_BYTES, game, MAX_CONTEST, MAX_SCAN_ROWS + 1),
        )
        for i, row in enumerate(rows):
            if i == MAX_SCAN_ROWS:
                raise RuntimeError("Limite de leitura do cache atingido; muitos registros inválidos ou incompletos.")
            if (draw := _valid_row(game, row)) is not None:
                result.append(draw)
                if len(result) == limit:
                    break
    return result


def list_draws_range(game: str, first_contest: int, last_contest: int) -> list[dict]:
    """Return valid rows from a bounded inclusive contest window."""
    initialize()
    low, high = sorted((int(first_contest), int(last_contest)))
    if low < 1 or high > MAX_CONTEST or high - low + 1 > MAX_RANGE_WIDTH:
        raise ValueError("Janela de concursos inválida ou excessiva.")
    with _connect() as conn:
        # Exact indexed keys prevent malformed fractional keys from expanding
        # the number of rows loaded within a numeric window.
        keys = list(range(high, low - 1, -1))
        placeholders = ",".join("?" for _ in keys)
        rows = conn.execute(
            f"SELECT contest, {_PAYLOAD_SELECT} FROM lottery_draws "
            f"WHERE game=? AND contest IN ({placeholders}) ORDER BY contest DESC",
            (MAX_PAYLOAD_BYTES, game, *keys),
        )
        return [draw for row in rows if (draw := _valid_row(game, row)) is not None]


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
