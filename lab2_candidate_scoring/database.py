import math
from contextlib import asynccontextmanager
from pathlib import Path

import aiosqlite

from schemas import PredictionResponse

BASE_DIR = Path(__file__).resolve().parent
DATABASE_PATH = BASE_DIR / "candidate_scoring.db"
DB_BUSY_TIMEOUT_MS = 5000


@asynccontextmanager
async def get_db():
    db = await aiosqlite.connect(str(DATABASE_PATH), timeout=DB_BUSY_TIMEOUT_MS / 1000)
    db.row_factory = aiosqlite.Row
    await db.execute(f"PRAGMA busy_timeout={DB_BUSY_TIMEOUT_MS};")
    try:
        yield db
    finally:
        await db.close()


async def init_db() -> None:
    async with get_db() as db:
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS predictions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                request_id TEXT NOT NULL,
                application_id TEXT NOT NULL,
                candidate_id TEXT NOT NULL,
                vacancy_id TEXT NOT NULL,
                match_score REAL NOT NULL,
                match_level TEXT NOT NULL,
                recommendation TEXT NOT NULL,
                model_version TEXT NOT NULL,
                source TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        await db.execute("CREATE INDEX IF NOT EXISTS idx_predictions_request_id ON predictions(request_id)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_predictions_created_at ON predictions(created_at)")
        await db.commit()


def _row_to_prediction(row: aiosqlite.Row) -> PredictionResponse:
    return PredictionResponse(
        request_id=row["request_id"],
        application_id=row["application_id"],
        candidate_id=row["candidate_id"],
        vacancy_id=row["vacancy_id"],
        match_score=row["match_score"],
        match_level=row["match_level"],
        recommendation=row["recommendation"],
        model_version=row["model_version"],
    )


async def save_predictions(items: list[PredictionResponse], source: str) -> None:
    values = [
        (
            item.request_id,
            item.application_id,
            item.candidate_id,
            item.vacancy_id,
            item.match_score,
            item.match_level,
            item.recommendation,
            item.model_version,
            source,
        )
        for item in items
    ]
    async with get_db() as db:
        await db.executemany(
            """
            INSERT INTO predictions (
                request_id, application_id, candidate_id, vacancy_id, match_score,
                match_level, recommendation, model_version, source
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            values,
        )
        await db.commit()


async def get_predictions(limit: int, match_level: str | None = None) -> list[PredictionResponse]:
    query = "SELECT * FROM predictions"
    params: list[object] = []
    if match_level:
        query += " WHERE match_level = ?"
        params.append(match_level)
    query += " ORDER BY id DESC LIMIT ?"
    params.append(limit)
    async with get_db() as db:
        cursor = await db.execute(query, params)
        rows = await cursor.fetchall()
    return [_row_to_prediction(row) for row in rows]


async def get_predictions_by_request_id(request_id: str) -> list[PredictionResponse]:
    async with get_db() as db:
        cursor = await db.execute("SELECT * FROM predictions WHERE request_id = ? ORDER BY id", (request_id,))
        rows = await cursor.fetchall()
    return [_row_to_prediction(row) for row in rows]


async def get_predictions_by_weekday(weekday: str, page: int, per_page: int) -> tuple[list[PredictionResponse], int]:
    weekday_number = {
        "sunday": "0", "monday": "1", "tuesday": "2", "wednesday": "3",
        "thursday": "4", "friday": "5", "saturday": "6",
    }[weekday]
    offset = (page - 1) * per_page
    async with get_db() as db:
        count_cursor = await db.execute(
            "SELECT COUNT(*) AS total FROM predictions WHERE strftime('%w', created_at) = ?", (weekday_number,)
        )
        total = (await count_cursor.fetchone())["total"]
        cursor = await db.execute(
            """SELECT * FROM predictions WHERE strftime('%w', created_at) = ?
               ORDER BY id DESC LIMIT ? OFFSET ?""",
            (weekday_number, per_page, offset),
        )
        rows = await cursor.fetchall()
    return [_row_to_prediction(row) for row in rows], total


def make_pagination_links(weekday: str, page: int, per_page: int, total: int) -> tuple[int, str | None, str | None]:
    total_pages = max(1, math.ceil(total / per_page))
    next_page = f"/predictions/by-weekday?weekday={weekday}&page={page + 1}&per_page={per_page}" if page < total_pages else None
    prev_page = f"/predictions/by-weekday?weekday={weekday}&page={page - 1}&per_page={per_page}" if page > 1 else None
    return total_pages, next_page, prev_page
