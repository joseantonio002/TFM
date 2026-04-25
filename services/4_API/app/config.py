"""Configuration helpers for the news metrics API."""

from __future__ import annotations

import os


API_TITLE: str = "News Metrics API"
API_VERSION: str = "1.0.0"
POSTGRES_PORT: int = 5432
NEWS_TABLE_NAME: str = os.getenv("NEWS_TABLE_NAME", "news")


def build_postgres_dsn() -> str:
  """Build the PostgreSQL DSN from environment variables."""

  host: str = os.getenv("NEWSDB_CONTAINER_NAME", "")
  user: str = os.getenv("POSTGRES_USER", "")
  password: str = os.getenv("POSTGRES_PASSWORD", "")
  database: str = os.getenv("POSTGRES_DB", "")
  return f"host={host} port={POSTGRES_PORT} dbname={database} user={user} password={password}"
