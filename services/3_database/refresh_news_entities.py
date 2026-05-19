import argparse
import importlib.util
import os
import sys
from pathlib import Path
from typing import Any, Callable

import psycopg2
from psycopg2 import sql
from psycopg2.extras import Json, execute_batch

DEFAULT_BATCH_SIZE: int = 100
NLP_PIPELINE_DIR: Path = Path(__file__).resolve().parent.parent / "2_pipeline_NLP"
NLP_PIPELINE_MAIN_PATH: Path = NLP_PIPELINE_DIR / "main.py"


def parse_args() -> argparse.Namespace:
  """Parse command line arguments for the database refresh script."""
  parser = argparse.ArgumentParser(
    description="Refresh news.nlp_pipeline using the current full NLP pipeline output."
  )
  parser.add_argument("--host", default=os.getenv("NEWSDB_CONTAINER_NAME", "localhost"))
  parser.add_argument("--port", type=int, default=int(os.getenv("POSTGRES_PORT", "5432")))
  parser.add_argument("--dbname", default=os.getenv("POSTGRES_DB", "newsdb"))
  parser.add_argument("--user", default=os.getenv("POSTGRES_USER", "myuser"))
  parser.add_argument("--password", default=os.getenv("POSTGRES_PASSWORD", "mypassword"))
  parser.add_argument("--table", default="news")
  parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
  return parser.parse_args()


def load_nlp_pipeline() -> Callable[[dict[str, Any]], dict[str, Any]]:
  """Load the nlp_pipeline function directly from the NLP pipeline main file."""
  if str(NLP_PIPELINE_DIR) not in sys.path:
    sys.path.insert(0, str(NLP_PIPELINE_DIR))

  spec = importlib.util.spec_from_file_location("news_nlp_pipeline_module", NLP_PIPELINE_MAIN_PATH)
  if spec is None or spec.loader is None:
    raise ImportError(f"Could not load NLP pipeline module from {NLP_PIPELINE_MAIN_PATH}")
  module = importlib.util.module_from_spec(spec)
  spec.loader.exec_module(module)
  return module.nlp_pipeline


def build_updated_nlp_pipeline(content: str, pipeline_function: Callable[[dict[str, Any]], dict[str, Any]]) -> dict[str, Any]:
  """Run the full NLP pipeline and return the replacement nlp_pipeline payload."""
  pipeline_input: dict[str, Any] = {"content": content or ""}
  pipeline_output: dict[str, Any] = pipeline_function(pipeline_input)
  nlp_pipeline = pipeline_output.get("nlp_pipeline", {})
  return nlp_pipeline if isinstance(nlp_pipeline, dict) else {}


def refresh_news_entities(args: argparse.Namespace) -> tuple[int, int]:
  """Refresh the full NLP pipeline payload for every row in the selected news table."""
  pipeline_function = load_nlp_pipeline()
  processed_rows: int = 0
  updated_rows: int = 0
  select_query = sql.SQL("SELECT id, content FROM {table}").format(
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
        for row_id, content in rows:
          processed_rows += 1
          updated_nlp_pipeline = build_updated_nlp_pipeline(content or "", pipeline_function)
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
