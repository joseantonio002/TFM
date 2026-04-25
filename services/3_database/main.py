import os
import json
from insert import insert_media_extraction
import psycopg2

INPUT_DIR_PATH: str = "/common_nlp"

def load_metadata_from_environment() -> tuple[str, str]:
  return os.environ.get("AIRFLOW_DAG_ID", ""), os.environ.get("AIRFLOW_RUN_ID", "")


if __name__ == "__main__":
  dag_id, run_id = load_metadata_from_environment()
  with psycopg2.connect(
    host=os.getenv("NEWSDB_CONTAINER_NAME"),
    port=5432,
    user=os.getenv("POSTGRES_USER"),
    password=os.getenv("POSTGRES_PASSWORD"),
    dbname=os.getenv("POSTGRES_DB")
  ) as conn:
    for file_name in os.listdir(INPUT_DIR_PATH):
      if file_name.startswith(f"{dag_id}_{run_id}_"):
        with open(os.path.join(INPUT_DIR_PATH, file_name), "r") as f:
          input_json = json.load(f)
          insert_media_extraction(conn, input_json, table_name="news")
        # delete the input file after processing
        os.remove(os.path.join(INPUT_DIR_PATH, file_name))