"""FastAPI application exposing news records and metrics endpoints."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from functools import lru_cache
from pathlib import Path
from typing import Any, Annotated

from fastapi import Depends, FastAPI, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator
from psycopg import sql

from .config import API_TITLE, API_VERSION, NEWS_TABLE_NAME
from .database import get_connection


DEFAULT_RECORD_FIELDS: list[str] = [
  "id",
  "source_url",
  "airflow_dag_id",
  "extracted_at",
  "airflow_run_id",
  "connector_id",
  "connector_name",
  "source_name",
  "source_type",
  "language",
  "country",
  "source_tags",
  "content",
  "other",
  "nlp_pipeline",
]
ALLOWED_RECORD_FIELDS: set[str] = set(DEFAULT_RECORD_FIELDS + ["created_at"])
TOPIC_STOPWORDS_PATH: Path = Path(__file__).with_name("topic_stopwords.txt")
TOPIC_AGGREGATIONS_PATH: Path = Path(__file__).with_name("topic_aggregations.txt")

app: FastAPI = FastAPI(title=API_TITLE, version=API_VERSION)


class TimeGroupBy(str, Enum):
  """Supported time grouping values for time-series metrics."""

  hour = "hour"
  day = "day"
  week = "week"
  month = "month"


class SourceDistributionGroupBy(str, Enum):
  """Supported fields for source distribution aggregation."""

  source_name = "source_name"
  source_type = "source_type"


class EntityType(str, Enum):
  """Supported entity types extracted by the NLP pipeline."""

  per = "PER"
  loc = "LOC"
  org = "ORG"
  misc = "MISC"


class NlpDimension(str, Enum):
  """Supported NLP dimensions for dashboard aggregations."""

  topic = "topic"
  threat_category = "threat_category"


class CommonFilters(BaseModel):
  """Validated common filters shared across records and metrics endpoints."""

  model_config = ConfigDict(populate_by_name=True)

  from_datetime: datetime | None = Field(default=None, alias="from")
  to_datetime: datetime | None = Field(default=None, alias="to")
  source_type: str | None = None
  source_name: list[str] | None = None
  country: str | None = None
  language: str | None = None
  connector_id: str | None = None

  @field_validator("source_type", "country", "language", "connector_id")
  @classmethod
  def strip_string_values(cls, value: str | None) -> str | None:
    """Trim string filters and normalize empty values to None."""

    if value is None:
      return None
    stripped_value: str = value.strip()
    return stripped_value or None

  @field_validator("source_name")
  @classmethod
  def strip_source_names(cls, value: list[str] | None) -> list[str] | None:
    """Trim source-name filters and normalize empty lists to None."""

    if value is None:
      return None
    source_names: list[str] = []
    for source_name in value:
      stripped_source_name: str = source_name.strip()
      if stripped_source_name and stripped_source_name not in source_names:
        source_names.append(stripped_source_name)
    return source_names or None

  @model_validator(mode="after")
  def validate_date_range(self) -> "CommonFilters":
    """Ensure the lower date bound does not exceed the upper bound."""

    if self.from_datetime and self.to_datetime and self.from_datetime > self.to_datetime:
      raise ValueError("'from' must be lower than or equal to 'to'")
    return self


def get_common_filters(
  from_datetime: Annotated[datetime | None, Query(alias="from")] = None,
  to_datetime: Annotated[datetime | None, Query(alias="to")] = None,
  source_type: Annotated[str | None, Query()] = None,
  source_name: Annotated[list[str] | None, Query()] = None,
  country: Annotated[str | None, Query()] = None,
  language: Annotated[str | None, Query()] = None,
  connector_id: Annotated[str | None, Query()] = None,
) -> CommonFilters:
  """Create a validated common filters object from query parameters."""

  try:
    return CommonFilters(
      **{
        "from": from_datetime,
        "to": to_datetime,
        "source_type": source_type,
        "source_name": source_name,
        "country": country,
        "language": language,
        "connector_id": connector_id,
      }
    )
  except ValidationError as exc:
    error_messages: list[str] = [error.get("msg", "Invalid query parameters") for error in exc.errors()]
    raise HTTPException(status_code=422, detail=error_messages) from exc


def build_column_reference(column_name: str, table_alias: str | None = None) -> sql.Composable:
  """Build a safe SQL column reference with an optional table alias."""

  if table_alias is None:
    return sql.Identifier(column_name)
  return sql.SQL("{}.{}").format(sql.Identifier(table_alias), sql.Identifier(column_name))


def build_time_bucket_expression(group_by: TimeGroupBy, table_alias: str | None = None) -> sql.Composable:
  """Build the SQL expression used to group records by time bucket."""

  return sql.SQL("DATE_TRUNC({}, {})").format(
    sql.Literal(group_by.value),
    build_column_reference("extracted_at", table_alias),
  )


def build_duration_expression(table_alias: str | None = None) -> sql.Composable:
  """Build the SQL expression used to extract numeric duration from JSONB."""

  return sql.SQL("NULLIF({} ->> 'duration', '')::double precision").format(
    build_column_reference("other", table_alias)
  )


def build_common_filters_sql(
  filters: CommonFilters,
  table_alias: str | None = None,
) -> tuple[sql.Composable, list[Any]]:
  """Build the reusable WHERE clause and ordered parameters for shared filters."""

  clauses: list[sql.Composable] = []
  parameters: list[Any] = []

  if filters.from_datetime is not None:
    clauses.append(sql.SQL("{} >= %s").format(build_column_reference("extracted_at", table_alias)))
    parameters.append(filters.from_datetime)
  if filters.to_datetime is not None:
    clauses.append(sql.SQL("{} <= %s").format(build_column_reference("extracted_at", table_alias)))
    parameters.append(filters.to_datetime)
  if filters.source_type is not None:
    clauses.append(sql.SQL("{} = %s").format(build_column_reference("source_type", table_alias)))
    parameters.append(filters.source_type)
  if filters.source_name is not None:
    clauses.append(sql.SQL("{} = ANY(%s::text[])").format(build_column_reference("source_name", table_alias)))
    parameters.append(filters.source_name)
  if filters.country is not None:
    clauses.append(sql.SQL("{} = %s").format(build_column_reference("country", table_alias)))
    parameters.append(filters.country)
  if filters.language is not None:
    clauses.append(sql.SQL("{} = %s").format(build_column_reference("language", table_alias)))
    parameters.append(filters.language)
  if filters.connector_id is not None:
    clauses.append(sql.SQL("{} = %s").format(build_column_reference("connector_id", table_alias)))
    parameters.append(filters.connector_id)

  if not clauses:
    return sql.SQL(""), parameters
  return sql.SQL(" WHERE ") + sql.SQL(" AND ").join(clauses), parameters


def serialize_filters(filters: CommonFilters, extra_filters: dict[str, Any] | None = None) -> dict[str, Any]:
  """Serialize filters into a clean and stable response payload."""

  serialized_filters: dict[str, Any] = filters.model_dump(by_alias=True, exclude_none=True)
  if extra_filters:
    serialized_filters.update(extra_filters)
  return serialized_filters


def parse_record_fields(fields: str | None) -> list[str]:
  """Parse and validate the optional comma-separated records field list."""

  if fields is None or not fields.strip():
    return DEFAULT_RECORD_FIELDS

  selected_fields: list[str] = []
  for raw_field in fields.split(","):
    field_name: str = raw_field.strip()
    if not field_name:
      continue
    if field_name not in ALLOWED_RECORD_FIELDS:
      raise ValueError(f"Unsupported field '{field_name}'")
    if field_name not in selected_fields:
      selected_fields.append(field_name)

  if not selected_fields:
    raise ValueError("At least one valid field must be provided")
  return selected_fields


def resolve_record_fields(fields: str | None) -> list[str]:
  """Validate the fields parameter and convert errors into HTTP 422 responses."""

  try:
    return parse_record_fields(fields)
  except ValueError as exc:
    raise HTTPException(status_code=422, detail=str(exc)) from exc


def normalize_selected_topics(selected_topics: list[str] | None) -> list[str] | None:
  """Normalize selected topic filters and enforce the dashboard display cap."""

  if selected_topics is None:
    return None
  normalized_topics: list[str] = []
  for selected_topic in selected_topics:
    normalized_topic: str = selected_topic.strip().lower()
    if normalized_topic and normalized_topic not in normalized_topics:
      normalized_topics.append(normalized_topic)
  if len(normalized_topics) > 25:
    raise HTTPException(status_code=422, detail="At most 25 selected topics are allowed")
  return normalized_topics or None


@lru_cache(maxsize=1)
def load_topic_stopwords() -> list[str]:
  """Load normalized topic stopwords used to exclude noisy NLP topics."""

  if not TOPIC_STOPWORDS_PATH.exists():
    return []
  stopwords: list[str] = []
  for raw_stopword in TOPIC_STOPWORDS_PATH.read_text(encoding="utf-8").splitlines():
    stopword: str = raw_stopword.strip().lower()
    if stopword and stopword not in stopwords:
      stopwords.append(stopword)
  return stopwords


@lru_cache(maxsize=1)
def load_topic_aggregation_pairs() -> tuple[list[str], list[str]]:
  """Load topic variants and their canonical aggregation labels."""

  if not TOPIC_AGGREGATIONS_PATH.exists():
    return [], []
  variants: list[str] = []
  canonicals: list[str] = []
  seen_variants: set[str] = set()
  for raw_line in TOPIC_AGGREGATIONS_PATH.read_text(encoding="utf-8").splitlines():
    if "<-" not in raw_line:
      continue
    raw_canonical, raw_variants = raw_line.split("<-", maxsplit=1)
    canonical: str = raw_canonical.strip().lower()
    if not canonical:
      continue
    for raw_variant in raw_variants.split("|"):
      variant: str = raw_variant.strip().lower()
      if variant and variant not in seen_variants:
        variants.append(variant)
        canonicals.append(canonical)
        seen_variants.add(variant)
  return variants, canonicals


def build_sentiment_score_expression(table_alias: str | None = None) -> sql.Composable:
  """Build the SQL expression for positive-minus-negative sentiment score."""

  nlp_pipeline_column: sql.Composable = build_column_reference("nlp_pipeline", table_alias)
  return sql.SQL(
    "COALESCE(NULLIF({} -> 'sentiment' ->> 'positive', '')::double precision, 0) - "
    "COALESCE(NULLIF({} -> 'sentiment' ->> 'negative', '')::double precision, 0)"
  ).format(nlp_pipeline_column, nlp_pipeline_column)


def build_threat_category_expression(table_alias: str | None = None) -> sql.Composable:
  """Build the SQL expression for normalized threat-classification category."""

  return sql.SQL(
    "COALESCE(NULLIF(LOWER(TRIM({} -> 'threat_classification' ->> 'category')), ''), 'unknown')"
  ).format(build_column_reference("nlp_pipeline", table_alias))


def build_alert_level_expression(table_alias: str | None = None) -> sql.Composable:
  """Build the SQL expression for normalized threat-classification alert level."""

  return sql.SQL(
    "COALESCE(NULLIF(LOWER(TRIM({} -> 'threat_classification' ->> 'level')), ''), 'info')"
  ).format(build_column_reference("nlp_pipeline", table_alias))


def build_alert_score_expression(table_alias: str | None = None) -> sql.Composable:
  """Build the SQL expression mapping threat levels to ordered alert scores."""

  alert_level_expression: sql.Composable = build_alert_level_expression(table_alias)
  return sql.SQL(
    "CASE {} "
    "WHEN 'info' THEN 1 "
    "WHEN 'low' THEN 2 "
    "WHEN 'medium' THEN 3 "
    "WHEN 'high' THEN 4 "
    "WHEN 'critical' THEN 5 "
    "ELSE NULL END"
  ).format(alert_level_expression)


def execute_query(query: sql.Composable, parameters: list[Any]) -> list[dict[str, Any]]:
  """Execute a SQL query and return all rows as dictionaries."""

  with get_connection() as connection:
    with connection.cursor() as cursor:
      cursor.execute(query, parameters)
      return list(cursor.fetchall())


@app.get("/health")
def health() -> dict[str, Any]:
  """Return the API health including a basic database reachability check."""

  with get_connection() as connection:
    with connection.cursor() as cursor:
      cursor.execute("SELECT 1 AS status")
      cursor.fetchone()

  return {
    "metric": "health",
    "filters": {},
    "data": [{"status": "ok"}],
  }


@app.get("/records")
def get_records(
  filters: Annotated[CommonFilters, Depends(get_common_filters)] = None,
  limit: Annotated[int, Query(ge=1, le=1000)] = 100,
  offset: Annotated[int, Query(ge=0)] = 0,
  fields: Annotated[str | None, Query()] = None,
) -> dict[str, Any]:
  """Return paginated individual records from the news table."""

  resolved_filters: CommonFilters = filters or get_common_filters()
  selected_fields: list[str] = resolve_record_fields(fields)
  where_sql, parameters = build_common_filters_sql(resolved_filters)
  query: sql.Composable = sql.SQL(
    "SELECT {} FROM {}{} ORDER BY extracted_at DESC LIMIT %s OFFSET %s"
  ).format(
    sql.SQL(", ").join([sql.Identifier(field_name) for field_name in selected_fields]),
    sql.Identifier(NEWS_TABLE_NAME),
    where_sql,
  )
  rows: list[dict[str, Any]] = execute_query(query, parameters + [limit, offset])

  return {
    "metric": "records",
    "filters": serialize_filters(
      resolved_filters,
      {"limit": limit, "offset": offset, "fields": selected_fields},
    ),
    "data": rows,
  }


@app.get("/sources")
def get_sources() -> dict[str, Any]:
  """Return the available source names for dashboard selection."""

  query: sql.Composable = sql.SQL(
    "SELECT source_name, COUNT(*)::int AS records "
    "FROM {} WHERE source_name IS NOT NULL AND TRIM(source_name) <> '' "
    "GROUP BY source_name ORDER BY source_name ASC"
  ).format(sql.Identifier(NEWS_TABLE_NAME))
  rows: list[dict[str, Any]] = execute_query(query, [])

  return {
    "metric": "sources",
    "filters": {},
    "data": rows,
  }


@app.get("/metrics/summary")
def get_summary_metrics(
  filters: Annotated[CommonFilters, Depends(get_common_filters)] = None,
) -> dict[str, Any]:
  """Return total and filtered news counts for dashboard summary cards."""

  resolved_filters: CommonFilters = filters or get_common_filters()
  where_sql, parameters = build_common_filters_sql(resolved_filters)
  query: sql.Composable = sql.SQL(
    "SELECT "
    "(SELECT COUNT(*)::int FROM {}) AS total_records, "
    "(SELECT COUNT(*)::int FROM {}{}) AS filtered_records"
  ).format(
    sql.Identifier(NEWS_TABLE_NAME),
    sql.Identifier(NEWS_TABLE_NAME),
    where_sql,
  )
  rows: list[dict[str, Any]] = execute_query(query, parameters)

  return {
    "metric": "summary",
    "filters": serialize_filters(resolved_filters),
    "data": rows,
  }


@app.get("/metrics/volume")
def get_volume_metrics(
  filters: Annotated[CommonFilters, Depends(get_common_filters)] = None,
  group_by: Annotated[TimeGroupBy, Query()] = TimeGroupBy.day,
) -> dict[str, Any]:
  """Return the number of news records grouped by time bucket."""

  resolved_filters: CommonFilters = filters or get_common_filters()
  bucket_expression: sql.Composable = build_time_bucket_expression(group_by)
  where_sql, parameters = build_common_filters_sql(resolved_filters)
  query: sql.Composable = sql.SQL(
    "SELECT {} AS bucket, COUNT(*)::int AS records "
    "FROM {}{} GROUP BY bucket ORDER BY bucket ASC"
  ).format(
    bucket_expression,
    sql.Identifier(NEWS_TABLE_NAME),
    where_sql,
  )
  rows: list[dict[str, Any]] = execute_query(query, parameters)

  return {
    "metric": "volume",
    "filters": serialize_filters(resolved_filters, {"group_by": group_by.value}),
    "data": rows,
  }


@app.get("/metrics/duration")
def get_duration_metrics(
  filters: Annotated[CommonFilters, Depends(get_common_filters)] = None,
  group_by: Annotated[TimeGroupBy, Query()] = TimeGroupBy.day,
) -> dict[str, Any]:
  """Return total and average duration grouped by time bucket."""

  resolved_filters: CommonFilters = filters or get_common_filters()
  bucket_expression: sql.Composable = build_time_bucket_expression(group_by)
  duration_expression: sql.Composable = build_duration_expression()
  where_sql, parameters = build_common_filters_sql(resolved_filters)
  query: sql.Composable = sql.SQL(
    "SELECT {} AS bucket, "
    "COALESCE(SUM({}), 0)::double precision AS total_duration, "
    "COALESCE(AVG({}), 0)::double precision AS average_duration, "
    "COUNT(*)::int AS records "
    "FROM {}{} GROUP BY bucket ORDER BY bucket ASC"
  ).format(
    bucket_expression,
    duration_expression,
    duration_expression,
    sql.Identifier(NEWS_TABLE_NAME),
    where_sql,
  )
  rows: list[dict[str, Any]] = execute_query(query, parameters)

  return {
    "metric": "duration",
    "filters": serialize_filters(resolved_filters, {"group_by": group_by.value}),
    "data": rows,
  }


@app.get("/metrics/source-distribution")
def get_source_distribution_metrics(
  filters: Annotated[CommonFilters, Depends(get_common_filters)] = None,
  group_by: Annotated[SourceDistributionGroupBy, Query()] = SourceDistributionGroupBy.source_name,
) -> dict[str, Any]:
  """Return record distribution grouped by source name or source type."""

  resolved_filters: CommonFilters = filters or get_common_filters()
  grouped_column: sql.Composable = build_column_reference(group_by.value)
  where_sql, parameters = build_common_filters_sql(resolved_filters)
  query: sql.Composable = sql.SQL(
    "SELECT {} AS source, COUNT(*)::int AS records "
    "FROM {}{} GROUP BY source ORDER BY records DESC, source ASC"
  ).format(
    grouped_column,
    sql.Identifier(NEWS_TABLE_NAME),
    where_sql,
  )
  rows: list[dict[str, Any]] = execute_query(query, parameters)

  return {
    "metric": "source-distribution",
    "filters": serialize_filters(resolved_filters, {"group_by": group_by.value}),
    "data": rows,
  }


@app.get("/metrics/entity-ranking")
def get_entity_ranking_metrics(
  filters: Annotated[CommonFilters, Depends(get_common_filters)] = None,
  entity_type: Annotated[EntityType, Query()] = EntityType.per,
  limit: Annotated[int, Query(ge=1, le=1000)] = 20,
) -> dict[str, Any]:
  """Return the ranking of extracted entities for the selected entity type."""

  resolved_filters: CommonFilters = filters or get_common_filters()
  where_sql, parameters = build_common_filters_sql(resolved_filters, table_alias="n")
  entity_expression: sql.Composable = sql.SQL(
    "jsonb_array_elements_text(COALESCE({} -> 'entities' -> {}, '[]'::jsonb))"
  ).format(
    build_column_reference("nlp_pipeline", "n"),
    sql.Literal(entity_type.value),
  )
  query: sql.Composable = sql.SQL(
    "SELECT ranked.entity, COUNT(*)::int AS mentions, COUNT(DISTINCT ranked.id)::int AS records "
    "FROM ("
    "SELECT {} AS id, {} AS entity FROM {} AS {}{}"
    ") AS ranked "
    "GROUP BY ranked.entity ORDER BY mentions DESC, records DESC, ranked.entity ASC LIMIT %s"
  ).format(
    build_column_reference("id", "n"),
    entity_expression,
    sql.Identifier(NEWS_TABLE_NAME),
    sql.Identifier("n"),
    where_sql,
  )
  rows: list[dict[str, Any]] = execute_query(query, parameters + [limit])

  return {
    "metric": "entity-ranking",
    "filters": serialize_filters(
      resolved_filters,
      {"entity_type": entity_type.value, "limit": limit},
    ),
    "data": rows,
  }


@app.get("/metrics/nlp-ranking")
def get_nlp_ranking_metrics(
  filters: Annotated[CommonFilters, Depends(get_common_filters)] = None,
  dimension: Annotated[NlpDimension, Query()] = NlpDimension.topic,
  limit: Annotated[int, Query(ge=1, le=100)] = 10,
  selected_topic: Annotated[list[str] | None, Query()] = None,
) -> dict[str, Any]:
  """Return top NLP topics or threat categories by distinct news records."""

  resolved_filters: CommonFilters = filters or get_common_filters()
  where_sql, parameters = build_common_filters_sql(resolved_filters, table_alias="n")
  selected_topics: list[str] | None = normalize_selected_topics(selected_topic)

  if dimension == NlpDimension.topic:
    topic_aggregation_variants, topic_aggregation_canonicals = load_topic_aggregation_pairs()
    selected_topic_filter_sql: sql.Composable = sql.SQL(" WHERE dimension = ANY(%s::text[])") if selected_topics else sql.SQL("")
    selected_topic_parameters: list[Any] = [selected_topics] if selected_topics else []
    query: sql.Composable = sql.SQL(
      "WITH topic_aggregation AS ("
      "SELECT * FROM unnest(%s::text[], %s::text[]) AS t(variant, canonical)"
      "), exploded AS ("
      "SELECT {} AS id, LOWER(TRIM(topic.value)) AS dimension "
      "FROM {} AS {} "
      "CROSS JOIN LATERAL jsonb_array_elements_text("
      "COALESCE({} -> 'topics', '[]'::jsonb)"
      ") AS topic(value){}"
      "), filtered AS ("
      "SELECT * FROM exploded WHERE dimension <> '' AND NOT (dimension = ANY(%s::text[]))"
      "), normalized AS ("
      "SELECT COALESCE(a.canonical, f.dimension) AS dimension, f.id "
      "FROM filtered AS f LEFT JOIN topic_aggregation AS a ON f.dimension = a.variant"
      ") "
      "SELECT dimension, COUNT(DISTINCT id)::int AS records "
      "FROM normalized{} "
      "GROUP BY dimension ORDER BY records DESC, dimension ASC LIMIT %s"
    ).format(
      build_column_reference("id", "n"),
      sql.Identifier(NEWS_TABLE_NAME),
      sql.Identifier("n"),
      build_column_reference("nlp_pipeline", "n"),
      where_sql,
      selected_topic_filter_sql,
    )
    rows: list[dict[str, Any]] = execute_query(
      query,
      [topic_aggregation_variants, topic_aggregation_canonicals]
      + parameters
      + [load_topic_stopwords()]
      + selected_topic_parameters
      + [limit],
    )
  else:
    category_expression: sql.Composable = build_threat_category_expression("n")
    query = sql.SQL(
      "SELECT {} AS dimension, COUNT(*)::int AS records "
      "FROM {} AS {}{} GROUP BY dimension ORDER BY records DESC, dimension ASC LIMIT %s"
    ).format(
      category_expression,
      sql.Identifier(NEWS_TABLE_NAME),
      sql.Identifier("n"),
      where_sql,
    )
    rows = execute_query(query, parameters + [limit])

  return {
    "metric": "nlp-ranking",
    "filters": serialize_filters(
      resolved_filters,
      {"dimension": dimension.value, "limit": limit, "selected_topic": selected_topics},
    ),
    "data": rows,
  }


@app.get("/metrics/nlp-source-matrix")
def get_nlp_source_matrix_metrics(
  filters: Annotated[CommonFilters, Depends(get_common_filters)] = None,
  dimension: Annotated[NlpDimension, Query()] = NlpDimension.topic,
  limit: Annotated[int, Query(ge=1, le=25)] = 10,
  selected_topic: Annotated[list[str] | None, Query()] = None,
) -> dict[str, Any]:
  """Return NLP topic/category counts and average sentiment by source."""

  resolved_filters: CommonFilters = filters or get_common_filters()
  where_sql, parameters = build_common_filters_sql(resolved_filters, table_alias="n")
  selected_topics: list[str] | None = normalize_selected_topics(selected_topic)
  source_expression: sql.Composable = sql.SQL(
    "COALESCE(NULLIF(TRIM({}), ''), 'unknown')"
  ).format(build_column_reference("source_name", "n"))
  sentiment_expression: sql.Composable = build_sentiment_score_expression("n")

  if dimension == NlpDimension.topic:
    topic_aggregation_variants, topic_aggregation_canonicals = load_topic_aggregation_pairs()
    selected_topic_filter_sql: sql.Composable = sql.SQL(" WHERE dimension = ANY(%s::text[])") if selected_topics else sql.SQL("")
    selected_topic_parameters: list[Any] = [selected_topics] if selected_topics else []
    query: sql.Composable = sql.SQL(
      "WITH topic_aggregation AS ("
      "SELECT * FROM unnest(%s::text[], %s::text[]) AS t(variant, canonical)"
      "), exploded AS ("
      "SELECT {} AS id, {} AS source_name, LOWER(TRIM(topic.value)) AS dimension, "
      "{} AS sentiment_score FROM {} AS {} "
      "CROSS JOIN LATERAL jsonb_array_elements_text("
      "COALESCE({} -> 'topics', '[]'::jsonb)"
      ") AS topic(value){}"
      "), filtered AS ("
      "SELECT * FROM exploded WHERE dimension <> '' AND NOT (dimension = ANY(%s::text[]))"
      "), normalized AS ("
      "SELECT COALESCE(a.canonical, f.dimension) AS dimension, f.id, f.source_name, f.sentiment_score "
      "FROM filtered AS f LEFT JOIN topic_aggregation AS a ON f.dimension = a.variant"
      "), top_dimensions AS ("
      "SELECT dimension, COUNT(DISTINCT id)::int AS records FROM normalized "
      "{} GROUP BY dimension ORDER BY records DESC, dimension ASC LIMIT %s"
      ") "
      "SELECT n.dimension, n.source_name, COUNT(DISTINCT n.id)::int AS records, "
      "COALESCE(AVG(n.sentiment_score), 0)::double precision AS average_sentiment "
      "FROM normalized AS n INNER JOIN top_dimensions AS t ON n.dimension = t.dimension "
      "GROUP BY n.dimension, n.source_name, t.records "
      "ORDER BY t.records DESC, n.dimension ASC, n.source_name ASC"
    ).format(
      build_column_reference("id", "n"),
      source_expression,
      sentiment_expression,
      sql.Identifier(NEWS_TABLE_NAME),
      sql.Identifier("n"),
      build_column_reference("nlp_pipeline", "n"),
      where_sql,
      selected_topic_filter_sql,
    )
    rows: list[dict[str, Any]] = execute_query(
      query,
      [topic_aggregation_variants, topic_aggregation_canonicals]
      + parameters
      + [load_topic_stopwords()]
      + selected_topic_parameters
      + [limit],
    )
  else:
    category_expression: sql.Composable = build_threat_category_expression("n")
    query = sql.SQL(
      "WITH categorized AS ("
      "SELECT {} AS id, {} AS source_name, {} AS dimension, {} AS sentiment_score "
      "FROM {} AS {}{}"
      "), top_dimensions AS ("
      "SELECT dimension, COUNT(DISTINCT id)::int AS records FROM categorized "
      "GROUP BY dimension ORDER BY records DESC, dimension ASC LIMIT %s"
      ") "
      "SELECT c.dimension, c.source_name, COUNT(DISTINCT c.id)::int AS records, "
      "COALESCE(AVG(c.sentiment_score), 0)::double precision AS average_sentiment "
      "FROM categorized AS c INNER JOIN top_dimensions AS t ON c.dimension = t.dimension "
      "GROUP BY c.dimension, c.source_name, t.records "
      "ORDER BY t.records DESC, c.dimension ASC, c.source_name ASC"
    ).format(
      build_column_reference("id", "n"),
      source_expression,
      category_expression,
      sentiment_expression,
      sql.Identifier(NEWS_TABLE_NAME),
      sql.Identifier("n"),
      where_sql,
    )
    rows = execute_query(query, parameters + [limit])

  return {
    "metric": "nlp-source-matrix",
    "filters": serialize_filters(
      resolved_filters,
      {"dimension": dimension.value, "limit": limit, "selected_topic": selected_topics},
    ),
    "data": rows,
  }


@app.get("/metrics/topic-timeline")
def get_topic_timeline_metrics(
  topic: Annotated[str, Query(min_length=1)],
  filters: Annotated[CommonFilters, Depends(get_common_filters)] = None,
) -> dict[str, Any]:
  """Return daily alert, sentiment and record counts for one aggregated topic."""

  resolved_filters: CommonFilters = filters or get_common_filters()
  if resolved_filters.from_datetime is None or resolved_filters.to_datetime is None:
    raise HTTPException(status_code=422, detail="Both 'from' and 'to' are required for topic timeline")

  normalized_topic: str = topic.strip().lower()
  if not normalized_topic:
    raise HTTPException(status_code=422, detail="Topic must not be empty")

  where_sql, parameters = build_common_filters_sql(resolved_filters, table_alias="n")
  topic_aggregation_variants, topic_aggregation_canonicals = load_topic_aggregation_pairs()
  sentiment_expression: sql.Composable = build_sentiment_score_expression("n")
  alert_score_expression: sql.Composable = build_alert_score_expression("n")
  query: sql.Composable = sql.SQL(
    "WITH topic_aggregation AS ("
    "SELECT * FROM unnest(%s::text[], %s::text[]) AS t(variant, canonical)"
    "), exploded AS ("
    "SELECT {} AS id, DATE_TRUNC('day', {})::date AS bucket, "
    "LOWER(TRIM(topic.value)) AS dimension, {} AS sentiment_score, {} AS alert_score "
    "FROM {} AS {} "
    "CROSS JOIN LATERAL jsonb_array_elements_text("
    "COALESCE({} -> 'topics', '[]'::jsonb)"
    ") AS topic(value){}"
    "), filtered AS ("
    "SELECT * FROM exploded WHERE dimension <> '' AND NOT (dimension = ANY(%s::text[]))"
    "), normalized AS ("
    "SELECT COALESCE(a.canonical, f.dimension) AS dimension, f.id, f.bucket, "
    "f.sentiment_score, f.alert_score "
    "FROM filtered AS f LEFT JOIN topic_aggregation AS a ON f.dimension = a.variant"
    "), selected AS ("
    "SELECT * FROM normalized WHERE dimension = %s"
    "), daily_alerts AS ("
    "SELECT bucket, alert_score, COUNT(DISTINCT id)::int AS alert_records "
    "FROM selected WHERE alert_score IS NOT NULL GROUP BY bucket, alert_score"
    "), daily_alert_mode AS ("
    "SELECT DISTINCT ON (bucket) bucket, alert_score "
    "FROM daily_alerts ORDER BY bucket, alert_records DESC, alert_score DESC"
    "), aggregated AS ("
    "SELECT bucket, COUNT(DISTINCT id)::int AS records, "
    "AVG(sentiment_score)::double precision AS average_sentiment "
    "FROM selected GROUP BY bucket"
    "), days AS ("
    "SELECT generate_series("
    "DATE_TRUNC('day', %s::timestamptz), "
    "DATE_TRUNC('day', %s::timestamptz), "
    "INTERVAL '1 day'"
    ")::date AS bucket"
    ") "
    "SELECT d.bucket, COALESCE(a.records, 0)::int AS records, "
    "a.average_sentiment, m.alert_score, "
    "CASE m.alert_score "
    "WHEN 1 THEN 'info' "
    "WHEN 2 THEN 'low' "
    "WHEN 3 THEN 'medium' "
    "WHEN 4 THEN 'high' "
    "WHEN 5 THEN 'critical' "
    "ELSE NULL END AS alert_level "
    "FROM days AS d "
    "LEFT JOIN aggregated AS a ON d.bucket = a.bucket "
    "LEFT JOIN daily_alert_mode AS m ON d.bucket = m.bucket "
    "ORDER BY d.bucket ASC"
  ).format(
    build_column_reference("id", "n"),
    build_column_reference("extracted_at", "n"),
    sentiment_expression,
    alert_score_expression,
    sql.Identifier(NEWS_TABLE_NAME),
    sql.Identifier("n"),
    build_column_reference("nlp_pipeline", "n"),
    where_sql,
  )
  rows: list[dict[str, Any]] = execute_query(
    query,
    [topic_aggregation_variants, topic_aggregation_canonicals]
    + parameters
    + [load_topic_stopwords(), normalized_topic, resolved_filters.from_datetime, resolved_filters.to_datetime],
  )

  return {
    "metric": "topic-timeline",
    "filters": serialize_filters(resolved_filters, {"topic": normalized_topic}),
    "data": rows,
  }


@app.get("/metrics/topic-cooccurrence")
def get_topic_cooccurrence_metrics(
  filters: Annotated[CommonFilters, Depends(get_common_filters)] = None,
  limit: Annotated[int, Query(ge=1, le=100)] = 10,
  min_cooccurrences: Annotated[int, Query(ge=1, le=100)] = 2,
  selected_topic: Annotated[list[str] | None, Query()] = None,
) -> dict[str, Any]:
  """Return a topic co-occurrence graph for the visible top topics."""

  resolved_filters: CommonFilters = filters or get_common_filters()
  where_sql, parameters = build_common_filters_sql(resolved_filters, table_alias="n")
  selected_topics: list[str] | None = normalize_selected_topics(selected_topic)
  topic_aggregation_variants, topic_aggregation_canonicals = load_topic_aggregation_pairs()
  selected_topic_filter_sql: sql.Composable = sql.SQL(" WHERE dimension = ANY(%s::text[])") if selected_topics else sql.SQL("")
  selected_topic_parameters: list[Any] = [selected_topics] if selected_topics else []
  query_parameters: list[Any] = (
    [topic_aggregation_variants, topic_aggregation_canonicals]
    + parameters
    + [load_topic_stopwords()]
    + selected_topic_parameters
    + [limit]
  )
  node_query: sql.Composable = sql.SQL(
    "WITH topic_aggregation AS ("
    "SELECT * FROM unnest(%s::text[], %s::text[]) AS t(variant, canonical)"
    "), exploded AS ("
    "SELECT {} AS id, LOWER(TRIM(topic.value)) AS dimension "
    "FROM {} AS {} "
    "CROSS JOIN LATERAL jsonb_array_elements_text("
    "COALESCE({} -> 'topics', '[]'::jsonb)"
    ") AS topic(value){}"
    "), filtered AS ("
    "SELECT * FROM exploded WHERE dimension <> '' AND NOT (dimension = ANY(%s::text[]))"
    "), normalized AS ("
    "SELECT DISTINCT COALESCE(a.canonical, f.dimension) AS dimension, f.id "
    "FROM filtered AS f LEFT JOIN topic_aggregation AS a ON f.dimension = a.variant"
    "), top_dimensions AS ("
    "SELECT dimension, COUNT(DISTINCT id)::int AS records FROM normalized "
    "{} GROUP BY dimension ORDER BY records DESC, dimension ASC LIMIT %s"
    ") "
    "SELECT dimension, records FROM top_dimensions ORDER BY records DESC, dimension ASC"
  ).format(
    build_column_reference("id", "n"),
    sql.Identifier(NEWS_TABLE_NAME),
    sql.Identifier("n"),
    build_column_reference("nlp_pipeline", "n"),
    where_sql,
    selected_topic_filter_sql,
  )
  edge_query: sql.Composable = sql.SQL(
    "WITH topic_aggregation AS ("
    "SELECT * FROM unnest(%s::text[], %s::text[]) AS t(variant, canonical)"
    "), exploded AS ("
    "SELECT {} AS id, LOWER(TRIM(topic.value)) AS dimension "
    "FROM {} AS {} "
    "CROSS JOIN LATERAL jsonb_array_elements_text("
    "COALESCE({} -> 'topics', '[]'::jsonb)"
    ") AS topic(value){}"
    "), filtered AS ("
    "SELECT * FROM exploded WHERE dimension <> '' AND NOT (dimension = ANY(%s::text[]))"
    "), normalized AS ("
    "SELECT DISTINCT COALESCE(a.canonical, f.dimension) AS dimension, f.id "
    "FROM filtered AS f LEFT JOIN topic_aggregation AS a ON f.dimension = a.variant"
    "), top_dimensions AS ("
    "SELECT dimension, COUNT(DISTINCT id)::int AS records FROM normalized "
    "{} GROUP BY dimension ORDER BY records DESC, dimension ASC LIMIT %s"
    "), visible AS ("
    "SELECT n.id, n.dimension FROM normalized AS n "
    "INNER JOIN top_dimensions AS t ON n.dimension = t.dimension"
    ") "
    "SELECT left_topic.dimension AS source, right_topic.dimension AS target, "
    "COUNT(DISTINCT left_topic.id)::int AS weight "
    "FROM visible AS left_topic "
    "INNER JOIN visible AS right_topic "
    "ON left_topic.id = right_topic.id AND left_topic.dimension < right_topic.dimension "
    "GROUP BY left_topic.dimension, right_topic.dimension "
    "HAVING COUNT(DISTINCT left_topic.id) >= %s "
    "ORDER BY weight DESC, source ASC, target ASC"
  ).format(
    build_column_reference("id", "n"),
    sql.Identifier(NEWS_TABLE_NAME),
    sql.Identifier("n"),
    build_column_reference("nlp_pipeline", "n"),
    where_sql,
    selected_topic_filter_sql,
  )
  nodes: list[dict[str, Any]] = execute_query(node_query, query_parameters)
  edges: list[dict[str, Any]] = execute_query(edge_query, query_parameters + [min_cooccurrences])

  return {
    "metric": "topic-cooccurrence",
    "filters": serialize_filters(
      resolved_filters,
      {"limit": limit, "min_cooccurrences": min_cooccurrences, "selected_topic": selected_topics},
    ),
    "data": {"nodes": nodes, "edges": edges},
  }
