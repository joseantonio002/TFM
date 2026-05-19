import argparse
import importlib
import os
import sys
from pathlib import Path
from typing import Any, Callable

import psycopg2
from psycopg2 import sql
from psycopg2.extras import Json, execute_batch

DEFAULT_BATCH_SIZE: int = 100
NLP_PIPELINE_DIR: Path = Path(__file__).resolve().parent.parent / "2_pipeline_NLP"
StepFunction = Callable[[str], tuple[str, Any]]
NLP_STEPS: dict[str, tuple[str, str]] = {
  "entities": ("nlp_steps.NER.ner_main", "ner_main"),
  "sentiment": ("nlp_steps.pysentimiento.pysentimiento_main", "pysentimiento_main"),
  "threat_classification": ("nlp_steps.threat_classifier.threat_class_main", "threat_class_main"),
  "topics": ("nlp_steps.topics.topics_main", "topics_main"),
}


def parse_args() -> argparse.Namespace:
  """Parse command line arguments for the database refresh script."""
  parser = argparse.ArgumentParser(
    description="Refresh one news.nlp_pipeline step using the current NLP pipeline code."
  )
  parser.add_argument("--host", default=os.getenv("NEWSDB_CONTAINER_NAME", "localhost"))
  parser.add_argument("--port", type=int, default=int(os.getenv("POSTGRES_PORT", "5432")))
  parser.add_argument("--dbname", default=os.getenv("POSTGRES_DB", "newsdb"))
  parser.add_argument("--user", default=os.getenv("POSTGRES_USER", "myuser"))
  parser.add_argument("--password", default=os.getenv("POSTGRES_PASSWORD", "mypassword"))
  parser.add_argument("--table", default="news")
  parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
  parser.add_argument("--step", required=True, choices=sorted(NLP_STEPS))
  return parser.parse_args()


def load_nlp_step(step: str) -> StepFunction:
  """Load the selected NLP step function from the pipeline modules."""
  if str(NLP_PIPELINE_DIR) not in sys.path:
    sys.path.insert(0, str(NLP_PIPELINE_DIR))

  module_path, function_name = NLP_STEPS[step]
  module = importlib.import_module(module_path)
  return getattr(module, function_name)


def build_updated_nlp_pipeline(nlp_pipeline: Any, content: str, step_function: StepFunction) -> dict[str, Any]:
  """Run one NLP step and replace only that step in the nlp_pipeline payload."""
  updated_nlp_pipeline: dict[str, Any] = dict(nlp_pipeline) if isinstance(nlp_pipeline, dict) else {}
  key, value = step_function(content or "")
  updated_nlp_pipeline[key] = value
  return updated_nlp_pipeline


def refresh_news_nlp_step(args: argparse.Namespace) -> tuple[int, int]:
  """Refresh one NLP pipeline step payload for every row in the selected news table."""
  step_function = load_nlp_step(args.step)
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
    with conn.cursor(name="news_nlp_step_cursor", withhold=True) as select_cursor, conn.cursor() as update_cursor:
      select_cursor.itersize = args.batch_size
      select_cursor.execute(select_query)

      while True:
        rows = select_cursor.fetchmany(args.batch_size)
        if not rows:
          break

        update_params: list[dict[str, Any]] = []
        for row_id, content, nlp_pipeline in rows:
          processed_rows += 1
          updated_nlp_pipeline = build_updated_nlp_pipeline(nlp_pipeline, content or "", step_function)
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
  """Run the news NLP step refresh process and print a short summary."""
  args = parse_args()
  processed_rows, updated_rows = refresh_news_nlp_step(args)
  print(f"Processed rows: {processed_rows}")
  print(f"Updated rows: {updated_rows}")


if __name__ == "__main__":
  main()
