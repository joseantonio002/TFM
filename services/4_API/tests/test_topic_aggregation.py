"""Unit tests for NLP topic aggregation helpers."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

from app import main


def test_load_topic_aggregation_pairs_normalizes_and_deduplicates(
  tmp_path: Path,
  monkeypatch: pytest.MonkeyPatch,
) -> None:
  """Verify topic aggregation mappings are normalized and duplicate variants ignored."""

  aggregations_path: Path = tmp_path / "topic_aggregations.txt"
  aggregations_path.write_text(
    "Pedro Sánchez <- Sánchez | Pedro | Pedro Sánchez\n"
    "invalid line\n"
    "vox <- box | BOX | vox\n",
    encoding="utf-8",
  )
  monkeypatch.setattr(main, "TOPIC_AGGREGATIONS_PATH", aggregations_path)
  main.load_topic_aggregation_pairs.cache_clear()

  variants, canonicals = main.load_topic_aggregation_pairs()

  assert variants == ["sánchez", "pedro", "pedro sánchez", "box", "vox"]
  assert canonicals == ["pedro sánchez", "pedro sánchez", "pedro sánchez", "vox", "vox"]
  main.load_topic_aggregation_pairs.cache_clear()


def test_nlp_ranking_topic_passes_aggregation_after_stopwords(
  monkeypatch: pytest.MonkeyPatch,
) -> None:
  """Verify topic ranking uses aggregation parameters in addition to stopwords."""

  captured_parameters: dict[str, list[Any]] = {}

  def fake_execute_query(query: Any, parameters: list[Any]) -> list[dict[str, Any]]:
    """Capture query parameters and return a minimal API payload row."""

    captured_parameters["parameters"] = parameters
    return [{"dimension": "pedro sánchez", "records": 16}]

  monkeypatch.setattr(main, "load_topic_stopwords", lambda: ["noise"])
  monkeypatch.setattr(
    main,
    "load_topic_aggregation_pairs",
    lambda: (
      ["sánchez", "pedro", "pedro sánchez"],
      ["pedro sánchez", "pedro sánchez", "pedro sánchez"],
    ),
  )
  monkeypatch.setattr(main, "execute_query", fake_execute_query)

  payload: dict[str, Any] = main.get_nlp_ranking_metrics(
    filters=main.CommonFilters(),
    dimension=main.NlpDimension.topic,
    limit=10,
  )

  assert payload["data"] == [{"dimension": "pedro sánchez", "records": 16}]
  assert captured_parameters["parameters"] == [
    ["sánchez", "pedro", "pedro sánchez"],
    ["pedro sánchez", "pedro sánchez", "pedro sánchez"],
    ["noise"],
    10,
  ]


def test_topic_timeline_uses_selected_aggregated_topic(
  monkeypatch: pytest.MonkeyPatch,
) -> None:
  """Verify topic timeline filters by the selected normalized topic."""

  captured_parameters: dict[str, list[Any]] = {}

  def fake_execute_query(query: Any, parameters: list[Any]) -> list[dict[str, Any]]:
    """Capture query parameters and return a minimal timeline row."""

    captured_parameters["parameters"] = parameters
    return [
      {
        "bucket": "2026-05-01",
        "records": 16,
        "average_sentiment": 0.2,
        "alert_score": 3,
        "alert_level": "medium",
      }
    ]

  from_datetime: datetime = datetime(2026, 5, 1, tzinfo=timezone.utc)
  to_datetime: datetime = datetime(2026, 5, 2, tzinfo=timezone.utc)
  monkeypatch.setattr(main, "load_topic_stopwords", lambda: ["noise"])
  monkeypatch.setattr(
    main,
    "load_topic_aggregation_pairs",
    lambda: (["sánchez", "pedro"], ["pedro sánchez", "pedro sánchez"]),
  )
  monkeypatch.setattr(main, "execute_query", fake_execute_query)

  payload: dict[str, Any] = main.get_topic_timeline_metrics(
    topic=" Pedro Sánchez ",
    filters=main.CommonFilters(**{"from": from_datetime, "to": to_datetime}),
  )

  assert payload["data"][0]["records"] == 16
  assert captured_parameters["parameters"] == [
    ["sánchez", "pedro"],
    ["pedro sánchez", "pedro sánchez"],
    from_datetime,
    to_datetime,
    ["noise"],
    "pedro sánchez",
    from_datetime,
    to_datetime,
  ]


def test_topic_timeline_query_uses_daily_alert_mode(
  monkeypatch: pytest.MonkeyPatch,
) -> None:
  """Verify topic timeline computes alert level by daily frequency."""

  captured_query: dict[str, Any] = {}

  def fake_execute_query(query: Any, parameters: list[Any]) -> list[dict[str, Any]]:
    """Capture rendered query object for SQL structure assertions."""

    captured_query["query"] = str(query)
    return []

  from_datetime: datetime = datetime(2026, 5, 1, tzinfo=timezone.utc)
  to_datetime: datetime = datetime(2026, 5, 2, tzinfo=timezone.utc)
  monkeypatch.setattr(main, "load_topic_stopwords", lambda: [])
  monkeypatch.setattr(main, "load_topic_aggregation_pairs", lambda: ([], []))
  monkeypatch.setattr(main, "execute_query", fake_execute_query)

  main.get_topic_timeline_metrics(
    topic="pedro sánchez",
    filters=main.CommonFilters(**{"from": from_datetime, "to": to_datetime}),
  )

  assert "daily_alert_mode" in captured_query["query"]
  assert "alert_records DESC" in captured_query["query"]


def test_alert_score_expression_uses_threat_level() -> None:
  """Verify alert scores are derived from threat level, not threat category."""

  expression_text: str = str(main.build_alert_score_expression("n"))

  assert "level" in expression_text
  assert "category" not in expression_text


def test_topic_cooccurrence_uses_visible_topics_and_minimum_weight(
  monkeypatch: pytest.MonkeyPatch,
) -> None:
  """Verify co-occurrence graph returns nodes and edges from visible topics."""

  captured_parameters: list[list[Any]] = []

  def fake_execute_query(query: Any, parameters: list[Any]) -> list[dict[str, Any]]:
    """Return node rows for the first query and edge rows for the second query."""

    captured_parameters.append(parameters)
    if len(captured_parameters) == 1:
      return [{"dimension": "pedro sánchez", "records": 16}]
    return [{"source": "gobierno", "target": "pedro sánchez", "weight": 7}]

  monkeypatch.setattr(main, "load_topic_stopwords", lambda: ["noise"])
  monkeypatch.setattr(
    main,
    "load_topic_aggregation_pairs",
    lambda: (["sánchez", "pedro"], ["pedro sánchez", "pedro sánchez"]),
  )
  monkeypatch.setattr(main, "execute_query", fake_execute_query)

  payload: dict[str, Any] = main.get_topic_cooccurrence_metrics(
    filters=main.CommonFilters(),
    limit=10,
    min_cooccurrences=3,
  )

  assert payload["data"]["nodes"] == [{"dimension": "pedro sánchez", "records": 16}]
  assert payload["data"]["edges"] == [{"source": "gobierno", "target": "pedro sánchez", "weight": 7}]
  assert captured_parameters[0] == [["sánchez", "pedro"], ["pedro sánchez", "pedro sánchez"], ["noise"], 10]
  assert captured_parameters[1] == [["sánchez", "pedro"], ["pedro sánchez", "pedro sánchez"], ["noise"], 10, 3]


def test_nlp_ranking_topic_accepts_selected_topics(
  monkeypatch: pytest.MonkeyPatch,
) -> None:
  """Verify selected topics are passed after stopword filtering."""

  captured_parameters: dict[str, list[Any]] = {}

  def fake_execute_query(query: Any, parameters: list[Any]) -> list[dict[str, Any]]:
    """Capture query parameters and return a selected-topic row."""

    captured_parameters["parameters"] = parameters
    return [{"dimension": "vox", "records": 10}]

  monkeypatch.setattr(main, "load_topic_stopwords", lambda: ["noise"])
  monkeypatch.setattr(main, "load_topic_aggregation_pairs", lambda: (["box"], ["vox"]))
  monkeypatch.setattr(main, "execute_query", fake_execute_query)

  payload: dict[str, Any] = main.get_nlp_ranking_metrics(
    filters=main.CommonFilters(),
    dimension=main.NlpDimension.topic,
    limit=100,
    selected_topic=[" VOX "],
  )

  assert payload["data"] == [{"dimension": "vox", "records": 10}]
  assert captured_parameters["parameters"] == [["box"], ["vox"], ["noise"], ["vox"], 100]


def test_selected_topics_rejects_more_than_display_cap() -> None:
  """Verify selected topic filters cannot exceed the dashboard display cap."""

  selected_topics: list[str] = [f"topic {index}" for index in range(26)]

  with pytest.raises(Exception):
    main.normalize_selected_topics(selected_topics)
