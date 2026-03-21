"""Async SQLite storage for past research reports."""

from __future__ import annotations

import json
from pathlib import Path

import aiosqlite

from kresearch.web.models import ReportDetail, ReportSummary

_DEFAULT_DB = Path.home() / ".kresearch" / "reports.db"

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS reports (
    session_id TEXT PRIMARY KEY,
    query TEXT NOT NULL,
    report TEXT NOT NULL DEFAULT '',
    config_json TEXT NOT NULL DEFAULT '{}',
    source_count INTEGER NOT NULL DEFAULT 0,
    iteration_count INTEGER NOT NULL DEFAULT 0,
    duration_seconds REAL NOT NULL DEFAULT 0.0,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
)
"""


async def init_db(db_path: str = "") -> aiosqlite.Connection:
    path = Path(db_path) if db_path else _DEFAULT_DB
    path.parent.mkdir(parents=True, exist_ok=True)
    db = await aiosqlite.connect(str(path))
    await db.execute(_CREATE_TABLE)
    await db.commit()
    return db


async def save_report(
    db: aiosqlite.Connection, session_id: str, query: str, report: str,
    config_json: str = "{}", source_count: int = 0, iteration_count: int = 0,
    duration_seconds: float = 0.0,
) -> None:
    await db.execute(
        "INSERT OR REPLACE INTO reports "
        "(session_id, query, report, config_json, source_count, iteration_count, duration_seconds) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (session_id, query, report, config_json, source_count, iteration_count, duration_seconds),
    )
    await db.commit()


async def list_reports(db: aiosqlite.Connection) -> list[ReportSummary]:
    cursor = await db.execute(
        "SELECT session_id, query, source_count, iteration_count, "
        "duration_seconds, created_at FROM reports ORDER BY created_at DESC"
    )
    rows = await cursor.fetchall()
    return [
        ReportSummary(
            session_id=r[0], query=r[1], source_count=r[2],
            iteration_count=r[3], duration_seconds=r[4], created_at=r[5],
        )
        for r in rows
    ]


async def get_report(db: aiosqlite.Connection, session_id: str) -> ReportDetail | None:
    cursor = await db.execute(
        "SELECT session_id, query, report, config_json, source_count, "
        "iteration_count, duration_seconds, created_at FROM reports WHERE session_id = ?",
        (session_id,),
    )
    r = await cursor.fetchone()
    if not r:
        return None
    return ReportDetail(
        session_id=r[0], query=r[1], report=r[2], config_json=r[3],
        source_count=r[4], iteration_count=r[5], duration_seconds=r[6], created_at=r[7],
    )


async def delete_report(db: aiosqlite.Connection, session_id: str) -> bool:
    cursor = await db.execute("DELETE FROM reports WHERE session_id = ?", (session_id,))
    await db.commit()
    return cursor.rowcount > 0
