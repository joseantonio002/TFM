import json
from typing import Any, Dict

from psycopg2 import sql
from psycopg2.extras import Json


def insert_media_extraction_safe(conn, payload: Dict[str, Any], table_name: str = "news") -> str:
    required_fields = ["id", "source_url", "extracted_at"]
    missing = [field for field in required_fields if field not in payload or payload[field] is None]
    if missing:
        raise ValueError(f"Missing required fields: {', '.join(missing)}")

    source_tags = payload.get("source_tags")
    if isinstance(source_tags, str):
        source_tags = json.loads(source_tags)

    query = sql.SQL("""
        INSERT INTO {table} (
            id,
            source_url,
            airflow_dag_id,
            extracted_at,
            airflow_run_id,
            connector_id,
            connector_name,
            source_name,
            source_type,
            language,
            country,
            source_tags,
            content,
            other,
            nlp_pipeline
        )
        VALUES (
            %(id)s,
            %(source_url)s,
            %(airflow_dag_id)s,
            %(extracted_at)s,
            %(airflow_run_id)s,
            %(connector_id)s,
            %(connector_name)s,
            %(source_name)s,
            %(source_type)s,
            %(language)s,
            %(country)s,
            %(source_tags)s,
            %(content)s,
            %(other)s,
            %(nlp_pipeline)s
        )
        RETURNING id
    """).format(table=sql.Identifier(table_name))

    params = {
        "id": payload["id"],
        "source_url": payload["source_url"],
        "airflow_dag_id": payload.get("airflow_dag_id"),
        "extracted_at": payload["extracted_at"],
        "airflow_run_id": payload.get("airflow_run_id"),
        "connector_id": payload.get("connector_id"),
        "connector_name": payload.get("connector_name"),
        "source_name": payload.get("source_name"),
        "source_type": payload.get("source_type"),
        "language": payload.get("language"),
        "country": payload.get("country"),
        "source_tags": Json(source_tags) if source_tags is not None else None,
        "content": payload.get("content"),
        "other": Json(payload.get("other")) if payload.get("other") is not None else None,
        "nlp_pipeline": Json(payload.get("nlp_pipeline")) if payload.get("nlp_pipeline") is not None else None,
    }

    with conn.cursor() as cur:
        cur.execute(query, params)
        inserted_id = cur.fetchone()[0]
    conn.commit()
    return inserted_id