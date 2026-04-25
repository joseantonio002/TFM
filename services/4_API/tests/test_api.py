"""Integration tests for the live news metrics API."""

from __future__ import annotations

from typing import Any

import requests


def test_health_endpoint(base_url: str, api_session: requests.Session) -> None:
  """Verify that the health endpoint responds with the expected contract."""

  response: requests.Response = api_session.get(f"{base_url}/health", timeout=10)

  assert response.status_code == 200
  payload: dict[str, Any] = response.json()
  assert payload["metric"] == "health"
  assert payload["filters"] == {}
  assert isinstance(payload["data"], list)
  assert payload["data"][0]["status"] == "ok"


def test_records_endpoint_returns_selected_fields(
  base_url: str,
  api_session: requests.Session,
) -> None:
  """Verify that records can be paginated and restricted to selected fields."""

  response: requests.Response = api_session.get(
    f"{base_url}/records",
    params={"limit": 2, "fields": "id,source_name,extracted_at"},
    timeout=10,
  )

  assert response.status_code == 200
  payload: dict[str, Any] = response.json()
  assert payload["metric"] == "records"
  assert payload["filters"]["limit"] == 2
  assert payload["filters"]["fields"] == ["id", "source_name", "extracted_at"]
  assert isinstance(payload["data"], list)
  assert len(payload["data"]) <= 2
  for record in payload["data"]:
    assert set(record.keys()) == {"id", "source_name", "extracted_at"}


def test_records_endpoint_rejects_unsupported_fields(
  base_url: str,
  api_session: requests.Session,
) -> None:
  """Verify that invalid field names are rejected with a validation error."""

  response: requests.Response = api_session.get(
    f"{base_url}/records",
    params={"fields": "id,invalid_field"},
    timeout=10,
  )

  assert response.status_code == 422
  payload: dict[str, Any] = response.json()
  assert "Unsupported field" in payload["detail"]


def test_volume_metrics_endpoint(base_url: str, api_session: requests.Session) -> None:
  """Verify that the volume metric returns grouped record counts."""

  response: requests.Response = api_session.get(
    f"{base_url}/metrics/volume",
    params={"group_by": "day"},
    timeout=10,
  )

  assert response.status_code == 200
  payload: dict[str, Any] = response.json()
  assert payload["metric"] == "volume"
  assert payload["filters"]["group_by"] == "day"
  assert isinstance(payload["data"], list)
  for row in payload["data"]:
    assert set(row.keys()) == {"bucket", "records"}
    assert isinstance(row["records"], int)
    assert row["records"] >= 0


def test_duration_metrics_endpoint(base_url: str, api_session: requests.Session) -> None:
  """Verify that duration metrics expose totals and averages by bucket."""

  response: requests.Response = api_session.get(
    f"{base_url}/metrics/duration",
    params={"group_by": "day"},
    timeout=10,
  )

  assert response.status_code == 200
  payload: dict[str, Any] = response.json()
  assert payload["metric"] == "duration"
  assert payload["filters"]["group_by"] == "day"
  assert isinstance(payload["data"], list)
  for row in payload["data"]:
    assert set(row.keys()) == {"bucket", "total_duration", "average_duration", "records"}
    assert isinstance(row["records"], int)
    assert row["records"] >= 0
    assert isinstance(row["total_duration"], (int, float))
    assert isinstance(row["average_duration"], (int, float))


def test_source_distribution_endpoint(base_url: str, api_session: requests.Session) -> None:
  """Verify that source distribution returns grouped counts by source type."""

  response: requests.Response = api_session.get(
    f"{base_url}/metrics/source-distribution",
    params={"group_by": "source_type"},
    timeout=10,
  )

  assert response.status_code == 200
  payload: dict[str, Any] = response.json()
  assert payload["metric"] == "source-distribution"
  assert payload["filters"]["group_by"] == "source_type"
  assert isinstance(payload["data"], list)
  for row in payload["data"]:
    assert set(row.keys()) == {"source", "records"}
    assert isinstance(row["records"], int)


def test_entity_ranking_endpoint(base_url: str, api_session: requests.Session) -> None:
  """Verify that entity ranking returns entity, mentions and record counts."""

  response: requests.Response = api_session.get(
    f"{base_url}/metrics/entity-ranking",
    params={"entity_type": "LOC", "limit": 5},
    timeout=10,
  )

  assert response.status_code == 200
  payload: dict[str, Any] = response.json()
  assert payload["metric"] == "entity-ranking"
  assert payload["filters"]["entity_type"] == "LOC"
  assert payload["filters"]["limit"] == 5
  assert isinstance(payload["data"], list)
  assert len(payload["data"]) <= 5
  for row in payload["data"]:
    assert set(row.keys()) == {"entity", "mentions", "records"}
    assert isinstance(row["entity"], str)
    assert isinstance(row["mentions"], int)
    assert isinstance(row["records"], int)


def test_keyword_frequency_endpoint(base_url: str, api_session: requests.Session) -> None:
  """Verify that keyword frequency returns the expected aggregate shape."""

  response: requests.Response = api_session.get(
    f"{base_url}/metrics/keyword-frequency",
    params={"limit": 5, "min_length": 4, "exclude_stopwords": "true"},
    timeout=10,
  )

  assert response.status_code == 200
  payload: dict[str, Any] = response.json()
  assert payload["metric"] == "keyword-frequency"
  assert payload["filters"]["limit"] == 5
  assert payload["filters"]["min_length"] == 4
  assert payload["filters"]["exclude_stopwords"] is True
  assert isinstance(payload["data"], list)
  assert len(payload["data"]) <= 5
  for row in payload["data"]:
    assert set(row.keys()) == {"keyword", "frequency", "records"}
    assert isinstance(row["keyword"], str)
    assert isinstance(row["frequency"], int)
    assert isinstance(row["records"], int)


def test_invalid_group_by_returns_validation_error(
  base_url: str,
  api_session: requests.Session,
) -> None:
  """Verify that invalid enum values are rejected by FastAPI validation."""

  response: requests.Response = api_session.get(
    f"{base_url}/metrics/volume",
    params={"group_by": "year"},
    timeout=10,
  )

  assert response.status_code == 422


def test_invalid_date_range_returns_validation_error(
  base_url: str,
  api_session: requests.Session,
) -> None:
  """Verify that inverted date ranges are rejected."""

  response: requests.Response = api_session.get(
    f"{base_url}/records",
    params={
      "from": "2026-04-26T00:00:00Z",
      "to": "2026-04-20T00:00:00Z",
    },
    timeout=10,
  )

  assert response.status_code == 422
