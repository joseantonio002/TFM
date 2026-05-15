"""Single-page Streamlit dashboard for media intelligence metrics."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
import os
from typing import Any

import pandas as pd
import plotly.express as px
import requests
import streamlit as st


API_BASE_URL: str = os.getenv("NEWS_API_BASE_URL", "http://localhost:8000").rstrip("/")
REQUEST_TIMEOUT_SECONDS: int = 20
DIMENSION_OPTIONS: dict[str, str] = {
  "Topics": "topic",
  "Threat categories": "threat_category",
}


def build_iso_datetime(input_date: date | None, end_of_day: bool = False) -> str | None:
  """Convert a date input into an ISO UTC datetime string."""

  if input_date is None:
    return None
  selected_time: time = time.max if end_of_day else time.min
  return datetime.combine(input_date, selected_time, tzinfo=timezone.utc).isoformat()


def clean_params(params: dict[str, Any]) -> dict[str, Any]:
  """Remove empty values from API query parameters while preserving lists."""

  cleaned_params: dict[str, Any] = {}
  for key, value in params.items():
    if value is None:
      continue
    if isinstance(value, str) and not value.strip():
      continue
    if isinstance(value, list) and not value:
      continue
    cleaned_params[key] = value
  return cleaned_params


@st.cache_data(show_spinner=False, ttl=60)
def fetch_api_data(endpoint: str, params: dict[str, Any]) -> dict[str, Any]:
  """Fetch JSON data from the metrics API."""

  response: requests.Response = requests.get(
    f"{API_BASE_URL}{endpoint}",
    params=clean_params(params),
    timeout=REQUEST_TIMEOUT_SECONDS,
  )
  response.raise_for_status()
  payload: dict[str, Any] = response.json()
  return payload


def load_dataframe(endpoint: str, params: dict[str, Any]) -> tuple[dict[str, Any] | None, pd.DataFrame]:
  """Load an endpoint payload and convert its data section into a DataFrame."""

  try:
    payload: dict[str, Any] = fetch_api_data(endpoint, params)
  except requests.RequestException as exc:
    st.error(f"Error loading {endpoint}: {exc}")
    return None, pd.DataFrame()

  data_frame: pd.DataFrame = pd.DataFrame(payload.get("data", []))
  return payload, data_frame


def render_header() -> None:
  """Render dashboard page metadata and title."""

  st.set_page_config(page_title="Media Intelligence Dashboard", layout="wide")
  st.title("Media Intelligence Dashboard")
  st.caption(f"Data source: {API_BASE_URL}")


def get_date_range_value() -> tuple[date, date] | None:
  """Render and validate the dashboard date range filter."""

  today: date = date.today()
  default_from: date = today - timedelta(days=7)
  selected_value: date | tuple[date, ...] = st.sidebar.date_input(
    "Date Range",
    value=(default_from, today),
  )

  if not isinstance(selected_value, tuple) or len(selected_value) != 2:
    st.warning("Select a start and end date to load the dashboard.")
    return None
  from_date, to_date = selected_value
  if from_date > to_date:
    st.error("The start date must be lower than or equal to the end date.")
    return None
  return from_date, to_date


def render_sidebar_filters(source_options: list[str]) -> dict[str, Any] | None:
  """Render dashboard filters and return API query parameter values."""

  st.sidebar.header("Filters")
  date_range: tuple[date, date] | None = get_date_range_value()
  if date_range is None:
    return None

  selected_sources: list[str] = st.sidebar.multiselect(
    "Sources",
    options=source_options,
    default=source_options,
  )
  if not selected_sources:
    st.warning("Select at least one source to load the dashboard.")
    return None

  topic_limit: int = st.sidebar.slider("Number of topics to show", min_value=1, max_value=20, value=10)
  from_date, to_date = date_range
  return {
    "from": build_iso_datetime(from_date, end_of_day=False),
    "to": build_iso_datetime(to_date, end_of_day=True),
    "source_name": selected_sources,
    "limit": topic_limit,
  }


def render_metric_cards(summary_frame: pd.DataFrame) -> None:
  """Render total and filtered news counts."""

  total_records: int = 0
  filtered_records: int = 0
  if not summary_frame.empty:
    total_records = int(summary_frame.iloc[0].get("total_records", 0))
    filtered_records = int(summary_frame.iloc[0].get("filtered_records", 0))

  column_1, column_2 = st.columns(2)
  column_1.metric("Total news available", total_records)
  column_2.metric("News matching filters", filtered_records)


def render_dimension_selector(key: str) -> str:
  """Render a per-visualization dimension toggle."""

  selected_label: str = st.radio(
    "Y axis",
    options=list(DIMENSION_OPTIONS.keys()),
    horizontal=True,
    key=key,
  )
  return DIMENSION_OPTIONS[selected_label]


def render_ranking_chart(common_params: dict[str, Any]) -> None:
  """Render the topic/category ranking bar chart."""

  st.subheader("News by topic or threat category")
  dimension: str = render_dimension_selector("ranking_dimension")
  _, ranking_frame = load_dataframe(
    "/metrics/nlp-ranking",
    {**common_params, "dimension": dimension},
  )

  if ranking_frame.empty:
    st.info("No data available for the selected filters.")
    return

  chart_frame: pd.DataFrame = ranking_frame.sort_values("records", ascending=True)
  figure = px.bar(
    chart_frame,
    x="records",
    y="dimension",
    orientation="h",
    labels={"dimension": "Topic / category", "records": "News"},
  )
  figure.update_layout(height=max(420, 28 * len(chart_frame)))
  st.plotly_chart(figure, use_container_width=True)


def build_heatmap_frame(
  matrix_frame: pd.DataFrame,
  value_column: str,
  selected_sources: list[str],
) -> pd.DataFrame:
  """Build a pivoted dimension-by-source frame for heatmap rendering."""

  dimension_order: list[str] = list(
    matrix_frame.groupby("dimension")["records"].sum().sort_values(ascending=False).index
  )
  heatmap_frame: pd.DataFrame = matrix_frame.pivot_table(
    index="dimension",
    columns="source_name",
    values=value_column,
    aggfunc="mean" if value_column == "average_sentiment" else "sum",
    fill_value=0,
  )
  heatmap_frame = heatmap_frame.reindex(index=dimension_order)
  heatmap_frame = heatmap_frame.reindex(columns=selected_sources, fill_value=0)
  return heatmap_frame


def render_records_heatmap(common_params: dict[str, Any], selected_sources: list[str]) -> None:
  """Render the source-by-dimension news-count heatmap."""

  st.subheader("News count by source")
  dimension: str = render_dimension_selector("count_matrix_dimension")
  _, matrix_frame = load_dataframe(
    "/metrics/nlp-source-matrix",
    {**common_params, "dimension": dimension},
  )

  if matrix_frame.empty:
    st.info("No data available for the selected filters.")
    return

  heatmap_frame: pd.DataFrame = build_heatmap_frame(matrix_frame, "records", selected_sources)
  figure = px.imshow(
    heatmap_frame,
    aspect="auto",
    color_continuous_scale="Blues",
    labels={"x": "Source", "y": "Topic / category", "color": "News"},
  )
  figure.update_layout(height=max(420, 28 * len(heatmap_frame)))
  st.plotly_chart(figure, use_container_width=True)


def render_sentiment_heatmap(common_params: dict[str, Any], selected_sources: list[str]) -> None:
  """Render the source-by-dimension average sentiment heatmap."""

  st.subheader("Average sentiment by source")
  dimension: str = render_dimension_selector("sentiment_matrix_dimension")
  _, matrix_frame = load_dataframe(
    "/metrics/nlp-source-matrix",
    {**common_params, "dimension": dimension},
  )

  if matrix_frame.empty:
    st.info("No data available for the selected filters.")
    return

  heatmap_frame: pd.DataFrame = build_heatmap_frame(matrix_frame, "average_sentiment", selected_sources)
  figure = px.imshow(
    heatmap_frame,
    aspect="auto",
    color_continuous_scale="RdYlGn",
    zmin=-1,
    zmax=1,
    labels={"x": "Source", "y": "Topic / category", "color": "Sentiment"},
  )
  figure.update_layout(height=max(420, 28 * len(heatmap_frame)))
  st.plotly_chart(figure, use_container_width=True)


def main() -> None:
  """Run the Streamlit dashboard application."""

  render_header()
  _, sources_frame = load_dataframe("/sources", {})
  if sources_frame.empty or "source_name" not in sources_frame.columns:
    st.error("No sources are available from the API.")
    st.stop()

  source_options: list[str] = sorted(sources_frame["source_name"].dropna().astype(str).tolist())
  filters: dict[str, Any] | None = render_sidebar_filters(source_options)
  if filters is None:
    st.stop()

  common_params: dict[str, Any] = {
    "from": filters["from"],
    "to": filters["to"],
    "source_name": filters["source_name"],
    "limit": filters["limit"],
  }
  summary_params: dict[str, Any] = {
    "from": filters["from"],
    "to": filters["to"],
    "source_name": filters["source_name"],
  }
  _, summary_frame = load_dataframe("/metrics/summary", summary_params)

  render_metric_cards(summary_frame)
  st.divider()
  render_ranking_chart(common_params)
  st.divider()
  render_records_heatmap(common_params, filters["source_name"])
  st.divider()
  render_sentiment_heatmap(common_params, filters["source_name"])


if __name__ == "__main__":
  main()
