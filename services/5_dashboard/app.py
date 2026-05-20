"""Single-page Streamlit dashboard for media intelligence metrics."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
import math
import os
from typing import Any

import networkx as nx
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests
import streamlit as st


API_BASE_URL: str = os.getenv("NEWS_API_BASE_URL", "http://localhost:8000").rstrip("/")
REQUEST_TIMEOUT_SECONDS: int = 20
DIMENSION_OPTIONS: dict[str, str] = {
  "Topics": "topic",
  "Threat categories": "threat_category",
}
ENTITY_OPTIONS: list[str] = ["PER", "LOC", "ORG"]
ENTITY_TYPE_COLORS: dict[str, str] = {
  "PER": "#4C5FD5",
  "LOC": "#1F9D6E",
  "ORG": "#D87A22",
}
TIMELINE_METRIC_OPTIONS: dict[str, str] = {
  "Alert level": "alert",
  "Sentiment": "sentiment",
}
ALERT_LEVELS: list[str] = ["info", "low", "medium", "high", "critical"]


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

  from_date, to_date = date_range
  base_topic_params: dict[str, Any] = {
    "from": build_iso_datetime(from_date, end_of_day=False),
    "to": build_iso_datetime(to_date, end_of_day=True),
    "source_name": selected_sources,
  }
  topic_candidate_limit: int = st.sidebar.slider(
    "Topic candidate pool",
    min_value=1,
    max_value=100,
    value=25,
  )
  _, topic_candidates_frame = load_dataframe(
    "/metrics/nlp-ranking",
    {**base_topic_params, "dimension": "topic", "limit": topic_candidate_limit},
  )
  if topic_candidates_frame.empty or "dimension" not in topic_candidates_frame.columns:
    st.warning("No topic candidates are available for the selected filters.")
    return None

  topic_options: list[str] = topic_candidates_frame["dimension"].dropna().astype(str).tolist()
  default_topics: list[str] = topic_options[: min(25, len(topic_options))]
  selected_topics: list[str] = st.sidebar.multiselect(
    "Topics to display",
    options=topic_options,
    default=default_topics,
    max_selections=25,
  )
  if not selected_topics:
    st.warning("Select at least one topic to load the dashboard.")
    return None

  return {
    "from": base_topic_params["from"],
    "to": base_topic_params["to"],
    "source_name": selected_sources,
    "limit": len(selected_topics),
    "candidate_limit": topic_candidate_limit,
    "selected_topic": selected_topics,
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


def render_entity_ranking_chart(base_params: dict[str, Any]) -> None:
  """Render the top named entities by entity type."""

  st.subheader("Top named entities")
  selected_entity_type: str = st.radio(
    "Entity type",
    options=ENTITY_OPTIONS,
    horizontal=True,
    key="entity_ranking_type",
  )
  _, entity_frame = load_dataframe(
    "/metrics/entity-ranking",
    {**base_params, "entity_type": selected_entity_type, "limit": 10},
  )
  if entity_frame.empty:
    st.info("No entities available for the selected filters.")
    return

  chart_frame: pd.DataFrame = entity_frame.sort_values("mentions", ascending=True)
  figure = px.bar(
    chart_frame,
    x="mentions",
    y="entity",
    orientation="h",
    labels={"entity": "Entity", "mentions": "Mentions", "records": "News"},
    hover_data={"records": True, "mentions": True, "entity": False},
  )
  figure.update_layout(height=max(420, 32 * len(chart_frame)))
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

  sentiment_frame: pd.DataFrame = build_heatmap_frame(matrix_frame, "average_sentiment", selected_sources)
  records_frame: pd.DataFrame = build_heatmap_frame(matrix_frame, "records", selected_sources).reindex_like(sentiment_frame)
  hover_records: list[list[list[int]]] = [[[int(value)] for value in row] for row in records_frame.to_numpy()]
  figure = go.Figure(
    data=go.Heatmap(
      z=sentiment_frame.to_numpy(),
      x=list(sentiment_frame.columns),
      y=list(sentiment_frame.index),
      customdata=hover_records,
      colorscale="RdYlGn",
      zmin=-1,
      zmax=1,
      colorbar={"title": "Sentiment"},
      hovertemplate=(
        "Topic / category: %{y}<br>"
        "Source: %{x}<br>"
        "Sentiment: %{z:.3f}<br>"
        "News: %{customdata[0]}<extra></extra>"
      ),
    )
  )
  figure.update_layout(
    height=max(420, 28 * len(sentiment_frame)),
    xaxis_title="Source",
    yaxis_title="Topic / category",
  )
  figure.update_yaxes(autorange="reversed")
  st.plotly_chart(figure, use_container_width=True)


def render_timeline_metric_selector(key: str) -> str:
  """Render the topic timeline metric selector."""

  selected_label: str = st.radio(
    "Metric",
    options=list(TIMELINE_METRIC_OPTIONS.keys()),
    horizontal=True,
    key=key,
  )
  return TIMELINE_METRIC_OPTIONS[selected_label]


def render_topic_timeline_chart(common_params: dict[str, Any]) -> None:
  """Render daily alert or sentiment evolution for one selected topic."""

  st.subheader("Daily alert level or sentiment by topic")
  _, ranking_frame = load_dataframe(
    "/metrics/nlp-ranking",
    {**common_params, "dimension": "topic"},
  )
  if ranking_frame.empty or "dimension" not in ranking_frame.columns:
    st.info("No topic options available for the selected filters.")
    return

  topic_options: list[str] = ranking_frame["dimension"].dropna().astype(str).tolist()
  if not topic_options:
    st.info("No topic options available for the selected filters.")
    return
  if st.session_state.get("topic_timeline_topic") not in topic_options:
    st.session_state["topic_timeline_topic"] = topic_options[0]

  selected_topic: str = st.selectbox(
    "Topic",
    options=topic_options,
    key="topic_timeline_topic",
  )
  selected_metric: str = render_timeline_metric_selector("topic_timeline_metric")
  timeline_params: dict[str, Any] = {
    "from": common_params.get("from"),
    "to": common_params.get("to"),
    "source_name": common_params.get("source_name"),
    "topic": selected_topic,
  }
  _, timeline_frame = load_dataframe("/metrics/topic-timeline", timeline_params)
  if timeline_frame.empty:
    st.info("No timeline data available for the selected topic.")
    return

  timeline_frame["bucket"] = pd.to_datetime(timeline_frame["bucket"]).dt.date
  timeline_frame["records"] = timeline_frame["records"].fillna(0).astype(int)
  figure = make_subplots(specs=[[{"secondary_y": True}]])
  figure.add_bar(
    x=timeline_frame["bucket"],
    y=timeline_frame["records"],
    name="News",
    marker_color="rgba(250, 128, 114, 0.35)",
    hovertemplate="Date: %{x}<br>News: %{y}<extra></extra>",
    secondary_y=True,
  )

  if selected_metric == "alert":
    alert_scores: pd.Series = pd.to_numeric(timeline_frame["alert_score"], errors="coerce")
    line_values: pd.Series = alert_scores.where(timeline_frame["records"] > 0)
    figure.add_trace(
      go.Scatter(
        x=timeline_frame["bucket"],
        y=line_values,
        mode="lines+markers",
        name="Alert level",
        customdata=timeline_frame[["alert_level", "records"]].to_numpy(),
        line={"color": "#4C5FD5", "width": 3},
        marker={"size": 8},
        hovertemplate=(
          "Date: %{x}<br>"
          "Alert level: %{customdata[0]}<extra></extra>"
        ),
      ),
      secondary_y=False,
    )
    figure.update_yaxes(
      title_text="Alert level",
      tickmode="array",
      tickvals=list(range(1, len(ALERT_LEVELS) + 1)),
      ticktext=ALERT_LEVELS,
      range=[0.7, 5.3],
      secondary_y=False,
    )
  else:
    line_values = timeline_frame["average_sentiment"].where(timeline_frame["records"] > 0)
    figure.add_trace(
      go.Scatter(
        x=timeline_frame["bucket"],
        y=line_values,
        mode="lines+markers",
        name="Sentiment",
        customdata=timeline_frame[["records"]].to_numpy(),
        line={"color": "#1F7A5C", "width": 3},
        marker={"size": 8},
        hovertemplate=(
          "Date: %{x}<br>"
          "Sentiment: %{y:.3f}<extra></extra>"
        ),
      ),
      secondary_y=False,
    )
    figure.update_yaxes(title_text="Sentiment", range=[-1, 1], secondary_y=False)

  figure.update_yaxes(visible=False, showgrid=False, secondary_y=True)
  figure.update_layout(
    height=500,
    hovermode="x unified",
    bargap=0.1,
    xaxis_title="Date",
    legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "xanchor": "right", "x": 1},
  )
  st.plotly_chart(figure, use_container_width=True)


def scale_value(value: int, min_value: int, max_value: int, min_size: float, max_size: float) -> float:
  """Scale an integer value into a bounded visual size."""

  if max_value <= min_value:
    return (min_size + max_size) / 2
  return min_size + ((value - min_value) / (max_value - min_value)) * (max_size - min_size)


def render_topic_cooccurrence_graph(common_params: dict[str, Any]) -> None:
  """Render a Neo4j-like topic co-occurrence graph."""

  st.subheader("Topic co-occurrence graph")
  min_cooccurrences: int = st.slider(
    "Minimum shared news",
    min_value=1,
    max_value=20,
    value=2,
    key="topic_graph_min_cooccurrences",
  )
  try:
    payload: dict[str, Any] = fetch_api_data(
      "/metrics/topic-cooccurrence",
      {**common_params, "min_cooccurrences": min_cooccurrences},
    )
  except requests.RequestException as exc:
    st.error(f"Error loading /metrics/topic-cooccurrence: {exc}")
    return

  graph_data: dict[str, Any] = payload.get("data", {})
  nodes: list[dict[str, Any]] = graph_data.get("nodes", [])
  edges: list[dict[str, Any]] = graph_data.get("edges", [])
  if not nodes:
    st.info("No topic co-occurrence data available for the selected filters.")
    return

  graph = nx.Graph()
  for node in nodes:
    graph.add_node(node["dimension"], records=int(node["records"]))
  for edge in edges:
    graph.add_edge(edge["source"], edge["target"], weight=int(edge["weight"]))

  if len(graph.nodes) == 1:
    positions: dict[str, tuple[float, float]] = {next(iter(graph.nodes)): (0.0, 0.0)}
  else:
    positions = nx.spring_layout(graph, seed=42, k=1 / math.sqrt(max(len(graph.nodes), 1)))

  figure = go.Figure()
  max_edge_weight: int = max([int(edge["weight"]) for edge in edges], default=1)
  for edge in edges:
    source: str = edge["source"]
    target: str = edge["target"]
    weight: int = int(edge["weight"])
    source_x, source_y = positions[source]
    target_x, target_y = positions[target]
    line_width: float = scale_value(weight, 1, max_edge_weight, 1.2, 8.0)
    figure.add_trace(
      go.Scatter(
        x=[source_x, target_x],
        y=[source_y, target_y],
        mode="lines",
        line={"width": line_width, "color": "rgba(95, 111, 138, 0.45)"},
        hoverinfo="skip",
        showlegend=False,
      )
    )
    figure.add_trace(
      go.Scatter(
        x=[(source_x + target_x) / 2],
        y=[(source_y + target_y) / 2],
        mode="markers",
        marker={"size": max(8, line_width * 2), "color": "rgba(0, 0, 0, 0)"},
        text=[f"{source} + {target}<br>Shared news: {weight}"],
        hovertemplate="%{text}<extra></extra>",
        showlegend=False,
      )
    )

  node_records: list[int] = [int(graph.nodes[node]["records"]) for node in graph.nodes]
  min_records: int = min(node_records)
  max_records: int = max(node_records)
  node_x: list[float] = []
  node_y: list[float] = []
  node_sizes: list[float] = []
  node_text: list[str] = []
  node_colors: list[int] = []
  for node in graph.nodes:
    x_position, y_position = positions[node]
    records: int = int(graph.nodes[node]["records"])
    node_x.append(x_position)
    node_y.append(y_position)
    node_sizes.append(scale_value(records, min_records, max_records, 18, 48))
    node_colors.append(records)
    node_text.append(f"Topic: {node}<br>News: {records}<br>Connections: {graph.degree[node]}")

  figure.add_trace(
    go.Scatter(
      x=node_x,
      y=node_y,
      mode="markers+text",
      text=list(graph.nodes),
      textposition="top center",
      marker={
        "size": node_sizes,
        "color": node_colors,
        "colorscale": "Viridis",
        "line": {"width": 1.5, "color": "white"},
        "colorbar": {"title": "News"},
      },
      customdata=node_text,
      hovertemplate="%{customdata}<extra></extra>",
      showlegend=False,
    )
  )
  figure.update_layout(
    height=650,
    margin={"l": 10, "r": 10, "t": 20, "b": 10},
    xaxis={"visible": False},
    yaxis={"visible": False},
    plot_bgcolor="white",
  )
  st.plotly_chart(figure, use_container_width=True)


def render_entity_cooccurrence_graph(base_params: dict[str, Any]) -> None:
  """Render a Neo4j-like co-occurrence graph for PER/LOC/ORG entities."""

  st.subheader("Entity co-occurrence graph")
  min_cooccurrences: int = st.slider(
    "Minimum shared news",
    min_value=1,
    max_value=20,
    value=2,
    key="entity_graph_min_cooccurrences",
  )
  try:
    payload: dict[str, Any] = fetch_api_data(
      "/metrics/entity-cooccurrence",
      {**base_params, "limit": 50, "min_cooccurrences": min_cooccurrences},
    )
  except requests.RequestException as exc:
    st.error(f"Error loading /metrics/entity-cooccurrence: {exc}")
    return

  graph_data: dict[str, Any] = payload.get("data", {})
  nodes: list[dict[str, Any]] = graph_data.get("nodes", [])
  edges: list[dict[str, Any]] = graph_data.get("edges", [])
  if not nodes:
    st.info("No entity co-occurrence data available for the selected filters.")
    return

  graph = nx.Graph()
  for node in nodes:
    node_key: str = f"{node['entity_type']}:{node['entity']}"
    graph.add_node(
      node_key,
      label=node["entity"],
      entity_type=node["entity_type"],
      records=int(node["records"]),
      mentions=int(node["mentions"]),
    )
  for edge in edges:
    source_key = f"{edge['source_type']}:{edge['source']}"
    target_key = f"{edge['target_type']}:{edge['target']}"
    if source_key in graph and target_key in graph:
      graph.add_edge(source_key, target_key, weight=int(edge["weight"]))

  if len(graph.nodes) == 1:
    positions: dict[str, tuple[float, float]] = {next(iter(graph.nodes)): (0.0, 0.0)}
  else:
    positions = nx.spring_layout(graph, seed=42, k=1 / math.sqrt(max(len(graph.nodes), 1)))

  figure = go.Figure()
  edge_weights: list[int] = [int(graph.edges[edge]["weight"]) for edge in graph.edges]
  max_edge_weight: int = max(edge_weights, default=1)
  for source_key, target_key, edge_data in graph.edges(data=True):
    weight: int = int(edge_data["weight"])
    source_x, source_y = positions[source_key]
    target_x, target_y = positions[target_key]
    line_width: float = scale_value(weight, 1, max_edge_weight, 1.2, 8.0)
    source_label: str = str(graph.nodes[source_key]["label"])
    target_label: str = str(graph.nodes[target_key]["label"])
    figure.add_trace(
      go.Scatter(
        x=[source_x, target_x],
        y=[source_y, target_y],
        mode="lines",
        line={"width": line_width, "color": "rgba(95, 111, 138, 0.45)"},
        hoverinfo="skip",
        showlegend=False,
      )
    )
    figure.add_trace(
      go.Scatter(
        x=[(source_x + target_x) / 2],
        y=[(source_y + target_y) / 2],
        mode="markers",
        marker={"size": max(8, line_width * 2), "color": "rgba(0, 0, 0, 0)"},
        text=[f"{source_label} + {target_label}<br>Shared news: {weight}"],
        hovertemplate="%{text}<extra></extra>",
        showlegend=False,
      )
    )

  node_records: list[int] = [int(graph.nodes[node]["records"]) for node in graph.nodes]
  min_records: int = min(node_records)
  max_records: int = max(node_records)
  for entity_type in ENTITY_OPTIONS:
    node_keys: list[str] = [node for node in graph.nodes if graph.nodes[node]["entity_type"] == entity_type]
    if not node_keys:
      continue
    node_x: list[float] = []
    node_y: list[float] = []
    node_sizes: list[float] = []
    node_labels: list[str] = []
    node_text: list[str] = []
    for node_key in node_keys:
      x_position, y_position = positions[node_key]
      records = int(graph.nodes[node_key]["records"])
      mentions = int(graph.nodes[node_key]["mentions"])
      label = str(graph.nodes[node_key]["label"])
      node_x.append(x_position)
      node_y.append(y_position)
      node_sizes.append(scale_value(records, min_records, max_records, 18, 48))
      node_labels.append(label)
      node_text.append(
        f"Entity: {label}<br>Type: {entity_type}<br>News: {records}<br>Mentions: {mentions}<br>Connections: {graph.degree[node_key]}"
      )
    figure.add_trace(
      go.Scatter(
        x=node_x,
        y=node_y,
        mode="markers+text",
        text=node_labels,
        textposition="top center",
        name=entity_type,
        marker={
          "size": node_sizes,
          "color": ENTITY_TYPE_COLORS[entity_type],
          "line": {"width": 1.5, "color": "white"},
        },
        customdata=node_text,
        hovertemplate="%{customdata}<extra></extra>",
      )
    )

  figure.update_layout(
    height=650,
    margin={"l": 10, "r": 10, "t": 20, "b": 10},
    xaxis={"visible": False},
    yaxis={"visible": False},
    plot_bgcolor="white",
    legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "xanchor": "right", "x": 1},
  )
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
    "selected_topic": filters["selected_topic"],
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
  render_entity_ranking_chart(summary_params)
  st.divider()
  render_entity_cooccurrence_graph(summary_params)
  st.divider()
  render_records_heatmap(common_params, filters["source_name"])
  st.divider()
  render_sentiment_heatmap(common_params, filters["source_name"])
  st.divider()
  render_topic_timeline_chart(common_params)
  st.divider()
  render_topic_cooccurrence_graph(common_params)


if __name__ == "__main__":
  main()
