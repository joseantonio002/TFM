"""FastAPI application exposing news records and metrics endpoints."""

from __future__ import annotations

from collections import Counter
from datetime import datetime
from enum import Enum
import re
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
WORD_PATTERN: re.Pattern[str] = re.compile(r"\b[^\W_]+\b", re.UNICODE)
STOPWORDS: set[str] = {
  "a", "al", "algo", "algunas", "algunos", "ante", "antes", "como", "con",
  "contra", "cual", "cuando", "de", "del", "desde", "donde", "dos", "e",
  "el", "ella", "ellas", "ellos", "en", "entre", "era", "erais", "eran",
  "eras", "eres", "es", "esa", "esas", "ese", "eso", "esos", "esta",
  "estaba", "estado", "estamos", "estan", "estar", "estas", "este", "esto",
  "estos", "fue", "fueron", "ha", "habia", "han", "hasta", "hay", "la",
  "las", "le", "les", "lo", "los", "mas", "me", "mi", "mis", "muy",
  "no", "nos", "o", "os", "para", "pero", "por", "porque", "que", "quien",
  "se", "si", "sin", "sobre", "son", "su", "sus", "te", "tenia", "tiene",
  "tienen", "to", "tu", "un", "una", "uno", "unos", "y",
}

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


class CommonFilters(BaseModel):
  """Validated common filters shared across records and metrics endpoints."""

  model_config = ConfigDict(populate_by_name=True)

  from_datetime: datetime | None = Field(default=None, alias="from")
  to_datetime: datetime | None = Field(default=None, alias="to")
  source_type: str | None = None
  source_name: str | None = None
  country: str | None = None
  language: str | None = None
  connector_id: str | None = None

  @field_validator("source_type", "source_name", "country", "language", "connector_id")
  @classmethod
  def strip_string_values(cls, value: str | None) -> str | None:
    """Trim string filters and normalize empty values to None."""

    if value is None:
      return None
    stripped_value: str = value.strip()
    return stripped_value or None

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
  source_name: Annotated[str | None, Query()] = None,
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
    clauses.append(sql.SQL("{} = %s").format(build_column_reference("source_name", table_alias)))
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


def tokenize_content(content: str, min_length: int, exclude_stopwords: bool) -> list[str]:
  """Split content into normalized tokens for keyword analysis."""

  tokens: list[str] = []
  for match in WORD_PATTERN.findall(content.lower()):
    if len(match) < min_length:
      continue
    if exclude_stopwords and match in STOPWORDS:
      continue
    tokens.append(match)
  return tokens


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


@app.get("/metrics/keyword-frequency")
def get_keyword_frequency_metrics(
  filters: Annotated[CommonFilters, Depends(get_common_filters)] = None,
  limit: Annotated[int, Query(ge=1, le=1000)] = 20,
  min_length: Annotated[int, Query(ge=1, le=100)] = 4,
  exclude_stopwords: Annotated[bool, Query()] = True,
) -> dict[str, Any]:
  """Return the most frequent keywords found in record content."""

  resolved_filters: CommonFilters = filters or get_common_filters()
  where_sql, parameters = build_common_filters_sql(resolved_filters)
  query: sql.Composable = sql.SQL(
    "SELECT content FROM {}{} ORDER BY extracted_at DESC"
  ).format(
    sql.Identifier(NEWS_TABLE_NAME),
    where_sql,
  )
  rows: list[dict[str, Any]] = execute_query(query, parameters)

  keyword_counter: Counter[str] = Counter()
  record_counter: Counter[str] = Counter()
  for row in rows:
    content: str | None = row.get("content")
    if not content:
      continue
    tokens: list[str] = tokenize_content(content, min_length, exclude_stopwords)
    keyword_counter.update(tokens)
    record_counter.update(set(tokens))

  data: list[dict[str, Any]] = []
  for keyword, frequency in keyword_counter.most_common(limit):
    data.append(
      {
        "keyword": keyword,
        "frequency": frequency,
        "records": record_counter[keyword],
      }
    )

  return {
    "metric": "keyword-frequency",
    "filters": serialize_filters(
      resolved_filters,
      {
        "limit": limit,
        "min_length": min_length,
        "exclude_stopwords": exclude_stopwords,
      },
    ),
    "data": data,
  }
