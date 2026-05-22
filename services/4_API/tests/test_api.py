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


def test_sources_endpoint(base_url: str, api_session: requests.Session) -> None:
  """Verify that available sources are returned for dashboard filters."""

  response: requests.Response = api_session.get(f"{base_url}/sources", timeout=10)

  assert response.status_code == 200
  payload: dict[str, Any] = response.json()
  assert payload["metric"] == "sources"
  assert isinstance(payload["data"], list)
  for row in payload["data"]:
    assert set(row.keys()) == {"source_name", "records"}
    assert isinstance(row["source_name"], str)
    assert isinstance(row["records"], int)


def test_summary_metrics_endpoint(base_url: str, api_session: requests.Session) -> None:
  """Verify that summary metrics expose total and filtered counts."""

  response: requests.Response = api_session.get(f"{base_url}/metrics/summary", timeout=10)

  assert response.status_code == 200
  payload: dict[str, Any] = response.json()
  assert payload["metric"] == "summary"
  assert isinstance(payload["data"], list)
  assert len(payload["data"]) == 1
  row: dict[str, Any] = payload["data"][0]
  assert set(row.keys()) == {"total_records", "filtered_records"}
  assert isinstance(row["total_records"], int)
  assert isinstance(row["filtered_records"], int)


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


def test_category_breakdown_endpoint(base_url: str, api_session: requests.Session) -> None:
  """Verify that category breakdown returns top topics or entities."""

  response: requests.Response = api_session.get(
    f"{base_url}/metrics/category-breakdown",
    params={"threat_category": "unknown", "breakdown": "entity", "limit": 5},
    timeout=10,
  )

  assert response.status_code == 200
  payload: dict[str, Any] = response.json()
  assert payload["metric"] == "category-breakdown"
  assert payload["filters"]["threat_category"] == "unknown"
  assert payload["filters"]["breakdown"] == "entity"
  assert payload["filters"]["limit"] == 5
  assert isinstance(payload["data"], list)
  assert len(payload["data"]) <= 5
  for row in payload["data"]:
    assert set(row.keys()) == {"item", "item_type", "records", "mentions"}
    assert isinstance(row["item"], str)
    assert isinstance(row["item_type"], str)
    assert isinstance(row["records"], int)
    assert isinstance(row["mentions"], int)


def test_nlp_ranking_endpoint(base_url: str, api_session: requests.Session) -> None:
  """Verify that NLP ranking returns topics or threat categories."""

  response: requests.Response = api_session.get(
    f"{base_url}/metrics/nlp-ranking",
    params={"dimension": "topic", "limit": 5},
    timeout=10,
  )

  assert response.status_code == 200
  payload: dict[str, Any] = response.json()
  assert payload["metric"] == "nlp-ranking"
  assert payload["filters"]["dimension"] == "topic"
  assert payload["filters"]["limit"] == 5
  assert isinstance(payload["data"], list)
  assert len(payload["data"]) <= 5
  for row in payload["data"]:
    assert set(row.keys()) == {"dimension", "records"}
    assert isinstance(row["dimension"], str)
    assert isinstance(row["records"], int)


def test_nlp_source_matrix_endpoint(base_url: str, api_session: requests.Session) -> None:
  """Verify that NLP source matrix returns counts and average sentiment."""

  response: requests.Response = api_session.get(
    f"{base_url}/metrics/nlp-source-matrix",
    params={"dimension": "threat_category", "limit": 5},
    timeout=10,
  )

  assert response.status_code == 200
  payload: dict[str, Any] = response.json()
  assert payload["metric"] == "nlp-source-matrix"
  assert payload["filters"]["dimension"] == "threat_category"
  assert payload["filters"]["limit"] == 5
  assert isinstance(payload["data"], list)
  for row in payload["data"]:
    assert set(row.keys()) == {"dimension", "source_name", "records", "average_sentiment"}
    assert isinstance(row["dimension"], str)
    assert isinstance(row["source_name"], str)
    assert isinstance(row["records"], int)
    assert isinstance(row["average_sentiment"], (int, float))


def test_sentiment_distribution_endpoint(base_url: str, api_session: requests.Session) -> None:
  """Verify that sentiment distribution returns individual source scores."""

  response: requests.Response = api_session.get(
    f"{base_url}/metrics/sentiment-distribution",
    params={"dimension": "threat_category", "selected_dimension": "unknown", "max_records": 5},
    timeout=10,
  )

  assert response.status_code == 200
  payload: dict[str, Any] = response.json()
  assert payload["metric"] == "sentiment-distribution"
  assert payload["filters"]["dimension"] == "threat_category"
  assert payload["filters"]["selected_dimension"] == "unknown"
  assert payload["filters"]["max_records"] == 5
  assert isinstance(payload["data"], list)
  assert len(payload["data"]) <= 5
  for row in payload["data"]:
    assert set(row.keys()) == {"dimension", "source_name", "sentiment_score"}
    assert isinstance(row["dimension"], str)
    assert isinstance(row["source_name"], str)
    assert isinstance(row["sentiment_score"], (int, float))


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
