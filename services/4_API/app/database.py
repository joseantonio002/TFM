"""Database access helpers for the news metrics API."""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException
import psycopg
from psycopg.rows import dict_row

from .config import build_postgres_dsn


def get_connection() -> psycopg.Connection[dict[str, Any]]:
  """Open a PostgreSQL connection configured for dictionary rows."""

  try:
    return psycopg.connect(build_postgres_dsn(), row_factory=dict_row)
  except psycopg.OperationalError as exc:
    raise HTTPException(status_code=503, detail="Database connection error") from exc
