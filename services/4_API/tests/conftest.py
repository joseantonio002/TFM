"""Pytest fixtures for live API integration tests."""

from __future__ import annotations

import os
import time
from typing import Any

import pytest
import requests


DEFAULT_BASE_URL: str = "http://localhost:8000"


@pytest.fixture(scope="session")
def base_url() -> str:
  """Return the API base URL under test."""

  return os.getenv("API_BASE_URL", DEFAULT_BASE_URL).rstrip("/")


@pytest.fixture(scope="session")
def api_session() -> requests.Session:
  """Create a reusable HTTP session for the test suite."""

  session: requests.Session = requests.Session()
  yield session
  session.close()


@pytest.fixture(scope="session", autouse=True)
def ensure_api_is_reachable(base_url: str, api_session: requests.Session) -> None:
  """Fail early if the target API is not reachable before running tests."""

  last_exception: Exception | None = None
  for _ in range(30):
    try:
      response: requests.Response = api_session.get(f"{base_url}/health", timeout=10)
      response.raise_for_status()
      payload: dict[str, Any] = response.json()
      assert payload["metric"] == "health"
      return
    except Exception as exc:  # pragma: no cover - retry path
      last_exception = exc
      time.sleep(1)

  raise AssertionError("The API did not become reachable in time") from last_exception
