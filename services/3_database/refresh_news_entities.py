import argparse
import importlib.util
import os
from pathlib import Path
from typing import Any

import psycopg2
from psycopg2 import sql
from psycopg2.extras import Json, execute_batch

DEFAULT_BATCH_SIZE: int = 100
NER_MAIN_PATH: Path = Path(__file__).resolve().parent.parent / "2_pipeline_NLP" / "nlp_steps" / "NER" / "ner_main.py"


def parse_args() -> argparse.Namespace:
  """Parse command line arguments for the database refresh script."""
  parser = argparse.ArgumentParser(
    description="Refresh news.nlp_pipeline.entities using the current ner_main.py output."
  )
  parser.add_argument("--host", default=os.getenv("NEWSDB_CONTAINER_NAME", "localhost"))
  parser.add_argument("--port", type=int, default=int(os.getenv("POSTGRES_PORT", "5432")))
  parser.add_argument("--dbname", default=os.getenv("POSTGRES_DB", "newsdb"))
  parser.add_argument("--user", default=os.getenv("POSTGRES_USER", "myuser"))
  parser.add_argument("--password", default=os.getenv("POSTGRES_PASSWORD", "mypassword"))
  parser.add_argument("--table", default="news")
  parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
  return parser.parse_args()


def load_ner_main() -> Any:
  """Load the ner_main function directly from the NLP pipeline file."""
  spec = importlib.util.spec_from_file_location("news_ner_main_module", NER_MAIN_PATH)
  if spec is None or spec.loader is None:
    raise ImportError(f"Could not load ner_main module from {NER_MAIN_PATH}")
  module = importlib.util.module_from_spec(spec)
  spec.loader.exec_module(module)
  return module.ner_main


def build_updated_nlp_pipeline(nlp_pipeline: Any, content: str, ner_function: Any) -> dict[str, Any]:
  """Replace the entities section while preserving the rest of nlp_pipeline."""
  updated_nlp_pipeline: dict[str, Any] = dict(nlp_pipeline) if isinstance(nlp_pipeline, dict) else {}
  updated_nlp_pipeline.pop("entities", None)
  updated_nlp_pipeline.update(ner_function(content or ""))
  return updated_nlp_pipeline


def refresh_news_entities(args: argparse.Namespace) -> tuple[int, int]:
  """Refresh the entities payload for every row in the selected news table."""
  ner_function = load_ner_main()
  processed_rows: int = 0
  updated_rows: int = 0
  select_query = sql.SQL("SELECT id, content, nlp_pipeline FROM {table}").format(
    table=sql.Identifier(args.table)
  )
  update_query = sql.SQL("UPDATE {table} SET nlp_pipeline = %(nlp_pipeline)s WHERE id = %(id)s").format(
    table=sql.Identifier(args.table)
  )

  with psycopg2.connect(
    host=args.host,
    port=args.port,
    dbname=args.dbname,
    user=args.user,
    password=args.password
  ) as conn:
    with conn.cursor(name="news_entities_cursor", withhold=True) as select_cursor, conn.cursor() as update_cursor:
      select_cursor.itersize = args.batch_size
      select_cursor.execute(select_query)

      while True:
        rows = select_cursor.fetchmany(args.batch_size)
        if not rows:
          break

        update_params: list[dict[str, Any]] = []
        for row_id, content, nlp_pipeline in rows:
          processed_rows += 1
          updated_nlp_pipeline = build_updated_nlp_pipeline(nlp_pipeline, content or "", ner_function)
          update_params.append({
            "id": row_id,
            "nlp_pipeline": Json(updated_nlp_pipeline)
          })

        execute_batch(
          update_cursor,
          update_query.as_string(conn),
          update_params,
          page_size=args.batch_size
        )
        conn.commit()
        updated_rows += len(update_params)

  return processed_rows, updated_rows


def main() -> None:
  """Run the news entities refresh process and print a short summary."""
  args = parse_args()
  processed_rows, updated_rows = refresh_news_entities(args)
  print(f"Processed rows: {processed_rows}")
  print(f"Updated rows: {updated_rows}")


if __name__ == "__main__":
  main()
