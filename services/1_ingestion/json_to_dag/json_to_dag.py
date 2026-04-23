"""Utilities to generate Airflow DAG files from JSON config."""

from __future__ import annotations

import json
from pathlib import Path
from pprint import pformat
from typing import Any

from datetime import datetime


def _resolve_path(base_dir: Path, target_path: str) -> Path:
  """Return an absolute path for a module-relative target path."""
  path: Path = Path(target_path)
  if path.is_absolute():
    return path
  return (base_dir / path).resolve()


def _load_json_file(json_path: Path) -> dict[str, Any]:
  """Load and return a JSON object from disk."""
  with json_path.open("r", encoding="utf-8") as file:
    return json.load(file)


def _build_command(seed_ids: list[str], params: dict[str, Any]) -> list[str]:
  """Build the container command from seeds and params."""
  command: list[str] = ["-i", *seed_ids]

  for key, value in params.items():
    flag: str = key if key.startswith("-") else f"-{key}"
    command.extend([flag, str(value)])

  return command


def _build_environment(
  dag_name: str,
  connector_id: str,
  connector_data: dict[str, Any],
  sources_data: list[dict[str, Any]],
) -> dict[str, str]:
  """Build the environment variables passed to the container."""
  return {
    "AIRFLOW_DAG_ID": dag_name,
    "EXTRACTED_AT": "{{ ti.start_date }}",
    "AIRFLOW_RUN_ID": "{{ run_id }}",
    "CONNECTOR_ID": connector_id,
    "CONNECTOR_NAME": str(connector_data["connector_name"]),
    "SOURCE_NAME": "::".join(str(source["source_name"]) for source in sources_data),
    "SOURCE_TYPE": "::".join(str(source["source_type"]) for source in sources_data),
    "LANGUAGE": "::".join(str(source["lang"]) for source in sources_data),
    "COUNTRY": "::".join(str(source["country"]) for source in sources_data),
    "SOURCE_TAGS": "::".join(
      json.dumps(source.get("source_tags", [])) for source in sources_data
    ),
  }


def _render_dag_file(
  dag_name: str,
  task_id: str,
  schedule: str,
  docker_image: str,
  command: list[str],
  environment: dict[str, str],
  start_date: datetime.datetime,
) -> str:
  """Render the Python source for a generated DAG file."""
  command_literal: str = pformat(command, width=88, sort_dicts=False)
  environment_literal: str = pformat(environment, width=88, sort_dicts=False)
  start_date_literal: str = (
    f"datetime({start_date.year}, {start_date.month}, {start_date.day})"
  )

  return f'''from datetime import datetime
from airflow import DAG
from airflow.providers.docker.operators.docker import DockerOperator
from docker.types import Mount

with DAG(
  dag_id={dag_name!r},
  start_date={start_date_literal},
  schedule={schedule!r},
  catchup=False,
) as dag:

  run_connector = DockerOperator(
    task_id={task_id!r},
    image={docker_image!r},
    api_version="auto",
    auto_remove="force",
    docker_url="unix://var/run/docker.sock",
    network_mode="compose_net",
    mounts=[
      Mount(source="raw", target="/outputs/raw", type="volume"),
      Mount(source="common", target="/outputs/common", type="volume"),
    ],
    command={command_literal},
    environment={environment_literal},
  )

  pipeline_nlp = DockerOperator(
    task_id="pipeline_nlp",
    image="pipeline_nlp:latest",
    api_version="auto",
    auto_remove="force",
    docker_url="unix://var/run/docker.sock",
    network_mode="compose_net",
    mounts=[
      Mount(source="common", target="/common", type="volume"),
      Mount(source="common_nlp", target="/outputs_nlp_pipeline", type="volume")
    ],
    environment={environment_literal}
  )

  insert_into_db = DockerOperator(
    task_id="insert_into_db",
    image="insert_into_db:latest",
    api_version="auto",
    auto_remove="force",
    docker_url="unix://var/run/docker.sock",
    network_mode="compose_net",
    mounts=[
      Mount(source="common_nlp", target="/common_nlp", type="volume")
    ],
    environment={environment_literal}
  )

  run_connector >> pipeline_nlp >> insert_into_db
'''


def generate_dags(
  dags_config: dict[str, Any],
  connectors_path: str = "../ingestion_jsons/connectors.json",
  seed_list_path: str = "../ingestion_jsons/seed_list.json",
  output_dir: str = "./dags",
) -> list[str]:
  """Generate DAG Python files from a DAG configuration mapping."""
  base_dir: Path = Path(__file__).resolve().parent
  connectors_file: Path = _resolve_path(base_dir, connectors_path)
  seed_list_file: Path = _resolve_path(base_dir, seed_list_path)
  destination_dir: Path = _resolve_path(base_dir, output_dir)

  connectors_data: dict[str, Any] = _load_json_file(connectors_file)
  seed_list_data: dict[str, Any] = _load_json_file(seed_list_file)
  destination_dir.mkdir(parents=True, exist_ok=True)

  generated_files: list[str] = []
  generated_at: datetime.datetime = datetime.now()

  for dag_name, dag_data in dags_config.items():
    connector_id: str = str(dag_data["connector_id"])
    connector_data: dict[str, Any] = connectors_data[connector_id]

    if not connector_data.get("is_active", False):
      raise ValueError(f"Connector '{connector_id}' is not active")

    seed_ids: list[str] = list(dag_data.get("seed_ids") or connector_data["default_sources"])
    seed_links: list[str] = [seed_list_data[seed_id]["source_url"] for seed_id in seed_ids]
    sources_data: list[dict[str, Any]] = [seed_list_data[seed_id] for seed_id in seed_ids]
    params: dict[str, Any] = dict(dag_data.get("params", {}))

    command: list[str] = _build_command(seed_links, params)
    environment: dict[str, str] = _build_environment(
      dag_name=dag_name,
      connector_id=connector_id,
      connector_data=connector_data,
      sources_data=sources_data,
    )
    dag_source: str = _render_dag_file(
      dag_name=dag_name,
      task_id=str(dag_data["task_id"]),
      schedule=str(dag_data["schedule"]),
      docker_image=str(connector_data["docker_image"]),
      command=command,
      environment=environment,
      start_date=generated_at,
    )

    output_path: Path = destination_dir / f"{dag_name}.py"
    output_path.write_text(dag_source, encoding="utf-8")
    generated_files.append(str(output_path))

  return generated_files


def generate_dags_from_file(
  dags_json_path: str,
  connectors_path: str = "../ingestion_jsons/connectors.json",
  seed_list_path: str = "../ingestion_jsons/seed_list.json",
  output_dir: str = "./dags",
) -> list[str]:
  """Generate DAG files from a JSON file path."""
  base_dir: Path = Path(__file__).resolve().parent
  dags_file: Path = _resolve_path(base_dir, dags_json_path)
  dags_config: dict[str, Any] = _load_json_file(dags_file)

  return generate_dags(
    dags_config=dags_config,
    connectors_path=connectors_path,
    seed_list_path=seed_list_path,
    output_dir=output_dir,
  )


if __name__ == "__main__":
  """Generate DAG files from the default dags.json when run as a script."""
  generate_dags_from_file("../ingestion_jsons/dags.json")
