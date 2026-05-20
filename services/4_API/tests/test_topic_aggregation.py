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
