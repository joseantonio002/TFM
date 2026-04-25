"""Streamlit dashboard for the news metrics API."""

from __future__ import annotations

from datetime import date, datetime, time, timezone
import os
from typing import Any

import pandas as pd
import plotly.express as px
import requests
import streamlit as st


API_BASE_URL: str = os.getenv("NEWS_API_BASE_URL", "http://localhost:8000").rstrip("/")
REQUEST_TIMEOUT_SECONDS: int = 20
DEFAULT_RECORD_FIELDS: str = "id,source_name,source_type,language,country,extracted_at,content"


def build_iso_datetime(input_date: date | None, end_of_day: bool = False) -> str | None:
  """Convert a date input into an ISO UTC datetime string."""

  if input_date is None:
    return None
  selected_time: time = time.max if end_of_day else time.min
  return datetime.combine(input_date, selected_time, tzinfo=timezone.utc).isoformat()


def clean_params(params: dict[str, Any]) -> dict[str, Any]:
  """Remove empty values from the API query parameters."""

  cleaned_params: dict[str, Any] = {}
  for key, value in params.items():
    if value is None:
      continue
    if isinstance(value, str) and not value.strip():
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
    st.error(f"Error consultando {endpoint}: {exc}")
    return None, pd.DataFrame()

  data_frame: pd.DataFrame = pd.DataFrame(payload.get("data", []))
  return payload, data_frame


def summarize_duration(duration_frame: pd.DataFrame) -> tuple[float, float]:
  """Calculate total and weighted average duration from grouped buckets."""

  if duration_frame.empty:
    return 0.0, 0.0

  total_duration: float = float(duration_frame["total_duration"].sum())
  total_records: int = int(duration_frame["records"].sum())
  average_duration: float = total_duration / total_records if total_records > 0 else 0.0
  return total_duration, average_duration


def render_metric_cards(volume_frame: pd.DataFrame, duration_frame: pd.DataFrame) -> None:
  """Render the top summary metrics row."""

  total_records: int = int(volume_frame["records"].sum()) if not volume_frame.empty else 0
  total_duration, average_duration = summarize_duration(duration_frame)
  active_days: int = int(volume_frame["bucket"].nunique()) if not volume_frame.empty else 0

  column_1, column_2, column_3, column_4 = st.columns(4)
  column_1.metric("Registros", total_records)
  column_2.metric("Duracion total", f"{total_duration:.1f}s")
  column_3.metric("Duracion media", f"{average_duration:.1f}s")
  column_4.metric("Buckets activos", active_days)


def render_time_series(volume_frame: pd.DataFrame, duration_frame: pd.DataFrame) -> None:
  """Render the time series charts for volume and duration."""

  column_1, column_2 = st.columns(2)

  with column_1:
    st.subheader("Volumen temporal")
    if volume_frame.empty:
      st.info("No hay datos para mostrar.")
    else:
      chart_frame: pd.DataFrame = volume_frame.copy()
      chart_frame["bucket"] = pd.to_datetime(chart_frame["bucket"])
      figure = px.line(
        chart_frame,
        x="bucket",
        y="records",
        markers=True,
        labels={"bucket": "Fecha", "records": "Registros"},
      )
      st.plotly_chart(figure, use_container_width=True)

  with column_2:
    st.subheader("Duracion temporal")
    if duration_frame.empty:
      st.info("No hay datos para mostrar.")
    else:
      chart_frame = duration_frame.copy()
      chart_frame["bucket"] = pd.to_datetime(chart_frame["bucket"])
      figure = px.bar(
        chart_frame,
        x="bucket",
        y="total_duration",
        labels={"bucket": "Fecha", "total_duration": "Duracion total (s)"},
      )
      st.plotly_chart(figure, use_container_width=True)


def render_distribution_section(
  source_type_frame: pd.DataFrame,
  source_name_frame: pd.DataFrame,
) -> None:
  """Render source distribution charts."""

  column_1, column_2 = st.columns(2)

  with column_1:
    st.subheader("Distribucion por tipo")
    if source_type_frame.empty:
      st.info("No hay datos para mostrar.")
    else:
      figure = px.bar(
        source_type_frame,
        x="source",
        y="records",
        labels={"source": "Tipo", "records": "Registros"},
      )
      st.plotly_chart(figure, use_container_width=True)

  with column_2:
    st.subheader("Top fuentes")
    if source_name_frame.empty:
      st.info("No hay datos para mostrar.")
    else:
      top_sources_frame: pd.DataFrame = source_name_frame.head(10)
      figure = px.bar(
        top_sources_frame,
        x="records",
        y="source",
        orientation="h",
        labels={"source": "Fuente", "records": "Registros"},
      )
      figure.update_layout(yaxis={"categoryorder": "total ascending"})
      st.plotly_chart(figure, use_container_width=True)


def render_semantic_section(entity_frame: pd.DataFrame, keyword_frame: pd.DataFrame) -> None:
  """Render entities and keywords charts."""

  column_1, column_2 = st.columns(2)

  with column_1:
    st.subheader("Ranking de entidades")
    if entity_frame.empty:
      st.info("No hay entidades para mostrar.")
    else:
      figure = px.bar(
        entity_frame,
        x="mentions",
        y="entity",
        orientation="h",
        labels={"entity": "Entidad", "mentions": "Menciones"},
      )
      figure.update_layout(yaxis={"categoryorder": "total ascending"})
      st.plotly_chart(figure, use_container_width=True)

  with column_2:
    st.subheader("Keywords frecuentes")
    if keyword_frame.empty:
      st.info("No hay keywords para mostrar.")
    else:
      figure = px.bar(
        keyword_frame,
        x="frequency",
        y="keyword",
        orientation="h",
        labels={"keyword": "Keyword", "frequency": "Frecuencia"},
      )
      figure.update_layout(yaxis={"categoryorder": "total ascending"})
      st.plotly_chart(figure, use_container_width=True)


def render_records_table(records_frame: pd.DataFrame) -> None:
  """Render the recent records table."""

  st.subheader("Registros recientes")
  if records_frame.empty:
    st.info("No hay registros para mostrar.")
    return

  formatted_frame: pd.DataFrame = records_frame.copy()
  if "content" in formatted_frame.columns:
    formatted_frame["content"] = formatted_frame["content"].fillna("").astype(str).str.slice(0, 180)
  st.dataframe(formatted_frame, use_container_width=True, hide_index=True)


def render_sidebar_filters() -> dict[str, Any]:
  """Render the sidebar filters and return the API params."""

  st.sidebar.header("Filtros")
  today: date = date.today()
  default_from: date = today.replace(day=max(1, today.day - 7))

  from_date: date | None = st.sidebar.date_input("Desde", value=default_from)
  to_date: date | None = st.sidebar.date_input("Hasta", value=today)
  source_type: str = st.sidebar.text_input("Source type")
  source_name: str = st.sidebar.text_input("Source name")
  country: str = st.sidebar.text_input("Country")
  language: str = st.sidebar.text_input("Language")
  connector_id: str = st.sidebar.text_input("Connector ID")
  group_by: str = st.sidebar.selectbox("Agrupar por", options=["hour", "day", "week", "month"], index=1)
  entity_type: str = st.sidebar.selectbox("Tipo de entidad", options=["PER", "LOC", "ORG", "MISC"], index=1)
  keyword_limit: int = st.sidebar.slider("Top keywords", min_value=5, max_value=30, value=10)
  entity_limit: int = st.sidebar.slider("Top entidades", min_value=5, max_value=30, value=10)
  records_limit: int = st.sidebar.slider("Registros a mostrar", min_value=5, max_value=50, value=10)

  return {
    "from": build_iso_datetime(from_date, end_of_day=False),
    "to": build_iso_datetime(to_date, end_of_day=True),
    "source_type": source_type,
    "source_name": source_name,
    "country": country,
    "language": language,
    "connector_id": connector_id,
    "group_by": group_by,
    "entity_type": entity_type,
    "keyword_limit": keyword_limit,
    "entity_limit": entity_limit,
    "records_limit": records_limit,
  }


def render_header() -> None:
  """Render the dashboard title and context."""

  st.set_page_config(page_title="News Metrics Dashboard", layout="wide")
  st.title("Dashboard de noticias")
  st.caption(f"Fuente de datos: {API_BASE_URL}")


def main() -> None:
  """Run the Streamlit dashboard application."""

  render_header()
  filters: dict[str, Any] = render_sidebar_filters()
  common_params: dict[str, Any] = {
    "from": filters["from"],
    "to": filters["to"],
    "source_type": filters["source_type"],
    "source_name": filters["source_name"],
    "country": filters["country"],
    "language": filters["language"],
    "connector_id": filters["connector_id"],
  }

  volume_payload, volume_frame = load_dataframe(
    "/metrics/volume",
    {**common_params, "group_by": filters["group_by"]},
  )
  duration_payload, duration_frame = load_dataframe(
    "/metrics/duration",
    {**common_params, "group_by": filters["group_by"]},
  )
  _, source_type_frame = load_dataframe(
    "/metrics/source-distribution",
    {**common_params, "group_by": "source_type"},
  )
  _, source_name_frame = load_dataframe(
    "/metrics/source-distribution",
    {**common_params, "group_by": "source_name"},
  )
  _, entity_frame = load_dataframe(
    "/metrics/entity-ranking",
    {
      **common_params,
      "entity_type": filters["entity_type"],
      "limit": filters["entity_limit"],
    },
  )
  _, keyword_frame = load_dataframe(
    "/metrics/keyword-frequency",
    {
      **common_params,
      "limit": filters["keyword_limit"],
      "min_length": 4,
      "exclude_stopwords": True,
    },
  )
  _, records_frame = load_dataframe(
    "/records",
    {
      **common_params,
      "limit": filters["records_limit"],
      "offset": 0,
      "fields": DEFAULT_RECORD_FIELDS,
    },
  )

  if volume_payload is None or duration_payload is None:
    st.stop()

  render_metric_cards(volume_frame, duration_frame)

  overview_tab, semantic_tab, records_tab = st.tabs(["Overview", "Semantica", "Registros"])

  with overview_tab:
    render_time_series(volume_frame, duration_frame)
    render_distribution_section(source_type_frame, source_name_frame)

  with semantic_tab:
    render_semantic_section(entity_frame, keyword_frame)

  with records_tab:
    render_records_table(records_frame)


if __name__ == "__main__":
  main()
