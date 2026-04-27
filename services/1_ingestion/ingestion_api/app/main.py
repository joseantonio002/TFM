"""FastAPI service to manage ingestion configuration JSON files."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from threading import Lock
from typing import Annotated, Any

from fastapi import Body, FastAPI, HTTPException, status


def _add_json_to_dag_path() -> None:
  """Add the json_to_dag module directory to the Python import path."""
  current_file: Path = Path(__file__).resolve()
  candidate_paths: list[Path] = [
    current_file.parents[1] / "json_to_dag",
    current_file.parents[2] / "json_to_dag",
  ]

  for candidate_path in candidate_paths:
    if candidate_path.exists():
      sys.path.insert(0, str(candidate_path))
      return


_add_json_to_dag_path()
from json_to_dag import generate_dags_from_json  # noqa: E402


JSON_DIR: Path = Path(os.getenv("INGESTION_JSONS_DIR", "/jsons"))
DAGS_DIR: Path = Path(os.getenv("DAGS_OUTPUT_DIR", "/dags"))

SEED_LIST_RESOURCE: str = "seed_list"
CONNECTORS_RESOURCE: str = "connectors"
DAGS_RESOURCE: str = "dags"

RESOURCE_FILES: dict[str, str] = {
  SEED_LIST_RESOURCE: "seed_list.json",
  CONNECTORS_RESOURCE: "connectors.json",
  DAGS_RESOURCE: "dags.json",
}
REQUIRED_FIELDS: dict[str, set[str]] = {
  SEED_LIST_RESOURCE: {
    "source_name",
    "source_type",
    "source_url",
    "source_tags",
    "lang",
    "country",
    "default_connector_id",
    "description",
    "is_active",
  },
  CONNECTORS_RESOURCE: {
    "connector_name",
    "docker_image",
    "default_sources",
    "is_active",
  },
  DAGS_RESOURCE: {
    "connector_id",
    "task_id",
    "schedule",
    "start_date",
  },
}
LIST_FIELDS: dict[str, set[str]] = {
  SEED_LIST_RESOURCE: {"source_tags"},
  CONNECTORS_RESOURCE: {"accepted_sources", "accepted_source_types", "default_sources"},
  DAGS_RESOURCE: {"seed_ids"},
}
DICT_FIELDS: dict[str, set[str]] = {
  CONNECTORS_RESOURCE: {"accepted_params"},
  DAGS_RESOURCE: {"params"},
}
STRING_FIELDS: dict[str, set[str]] = {
  SEED_LIST_RESOURCE: {
    "source_name",
    "source_type",
    "source_url",
    "lang",
    "country",
    "default_connector_id",
    "description",
  },
  CONNECTORS_RESOURCE: {"connector_name", "docker_image", "description"},
  DAGS_RESOURCE: {"connector_id", "task_id", "schedule", "start_date"},
}
BOOLEAN_FIELDS: dict[str, set[str]] = {
  SEED_LIST_RESOURCE: {"is_active"},
  CONNECTORS_RESOURCE: {"is_active"},
}
CONNECTOR_REGENERATION_FIELDS: set[str] = {"docker_image", "connector_name"}
CONFIG_LOCK: Lock = Lock()

app: FastAPI = FastAPI(title="Ingestion Config API", version="1.0.0")


def _config_path(resource_name: str) -> Path:
  """Return the path for a managed JSON resource."""
  return JSON_DIR / RESOURCE_FILES[resource_name]


def _load_config(resource_name: str) -> dict[str, Any]:
  """Load a managed JSON resource from disk."""
  config_path: Path = _config_path(resource_name)

  try:
    with config_path.open("r", encoding="utf-8") as config_file:
      loaded_config: Any = json.load(config_file)
  except FileNotFoundError as exc:
    raise HTTPException(
      status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
      detail=f"Configuration file not found: {config_path}",
    ) from exc
  except json.JSONDecodeError as exc:
    raise HTTPException(
      status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
      detail=f"Configuration file is not valid JSON: {config_path}",
    ) from exc

  if not isinstance(loaded_config, dict):
    raise HTTPException(
      status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
      detail=f"Configuration file must contain a JSON object: {config_path}",
    )

  return loaded_config


def _save_config(resource_name: str, config_data: dict[str, Any]) -> None:
  """Save a managed JSON resource to disk atomically."""
  config_path: Path = _config_path(resource_name)
  temporary_path: Path = config_path.with_name(f".{config_path.name}.tmp")
  serialized_config: str = json.dumps(config_data, indent=2, ensure_ascii=False)

  config_path.parent.mkdir(parents=True, exist_ok=True)
  temporary_path.write_text(f"{serialized_config}\n", encoding="utf-8")
  temporary_path.replace(config_path)


def _validate_item_id(item_id: str, resource_name: str) -> None:
  """Validate that the URL path contains a usable item id."""
  if item_id.strip():
    return

  raise HTTPException(
    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
    detail=f"{resource_name} item id cannot be empty",
  )


def _validate_dag_id(dag_id: str) -> None:
  """Validate that a DAG id can be safely mapped to one DAG file."""
  if "/" not in dag_id and "\\" not in dag_id and ".." not in dag_id:
    return

  raise HTTPException(
    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
    detail="DAG ids cannot contain path separators or '..'",
  )


def _validate_field_type(
  resource_name: str,
  item_data: dict[str, Any],
  field_name: str,
  expected_type: type[Any],
) -> None:
  """Validate one optional field type when the field is present."""
  if field_name not in item_data or isinstance(item_data[field_name], expected_type):
    return

  raise HTTPException(
    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
    detail=f"Field '{field_name}' in {resource_name} must be {expected_type.__name__}",
  )


def _validate_item(resource_name: str, item_id: str, item_data: dict[str, Any]) -> None:
  """Validate the payload for a managed JSON resource item."""
  _validate_item_id(item_id, resource_name)
  if resource_name == DAGS_RESOURCE:
    _validate_dag_id(item_id)

  missing_fields: list[str] = sorted(REQUIRED_FIELDS[resource_name] - set(item_data.keys()))
  if missing_fields:
    raise HTTPException(
      status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
      detail=f"Missing required fields in {resource_name}: {', '.join(missing_fields)}",
    )

  for field_name in STRING_FIELDS.get(resource_name, set()):
    _validate_field_type(resource_name, item_data, field_name, str)
  for field_name in LIST_FIELDS.get(resource_name, set()):
    _validate_field_type(resource_name, item_data, field_name, list)
  for field_name in DICT_FIELDS.get(resource_name, set()):
    _validate_field_type(resource_name, item_data, field_name, dict)
  for field_name in BOOLEAN_FIELDS.get(resource_name, set()):
    _validate_field_type(resource_name, item_data, field_name, bool)


def _response_payload(
  resource_name: str,
  item_id: str,
  action: str,
  item_data: dict[str, Any] | None = None,
  affected_dags: list[str] | None = None,
  generated_files: list[str] | None = None,
  deleted_files: list[str] | None = None,
) -> dict[str, Any]:
  """Build a consistent mutation response payload."""
  response: dict[str, Any] = {
    "resource": resource_name,
    "id": item_id,
    "action": action,
    "affected_dags": affected_dags or [],
    "generated_files": generated_files or [],
    "deleted_files": deleted_files or [],
  }

  if item_data is not None:
    response["item"] = item_data

  return response


def _generate_dags(dags_data: dict[str, Any]) -> list[str]:
  """Generate DAG files for the provided DAG config entries."""
  if not dags_data:
    return []

  try:
    return generate_dags_from_json(
      input_json=dags_data,
      connectors_path=str(_config_path(CONNECTORS_RESOURCE)),
      seed_list_path=str(_config_path(SEED_LIST_RESOURCE)),
      output_dir=str(DAGS_DIR),
    )
  except Exception as exc:
    raise HTTPException(
      status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
      detail=f"Unable to generate DAG files: {exc}",
    ) from exc


def _delete_dag_file(dag_id: str) -> list[str]:
  """Delete the generated DAG file for a DAG id when it exists."""
  _validate_dag_id(dag_id)
  dag_path: Path = (DAGS_DIR / f"{dag_id}.py").resolve()
  dags_root: Path = DAGS_DIR.resolve()

  if dags_root not in dag_path.parents:
    raise HTTPException(
      status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
      detail="DAG file path is outside the configured DAG directory",
    )

  if not dag_path.exists():
    return []

  dag_path.unlink()
  return [str(dag_path)]


def _dag_uses_seed(
  seed_id: str,
  dag_data: dict[str, Any],
  connectors_data: dict[str, Any],
) -> bool:
  """Return whether a DAG uses a seed directly or through connector defaults."""
  explicit_seed_ids: Any = dag_data.get("seed_ids")
  if explicit_seed_ids:
    return seed_id in explicit_seed_ids

  connector_id: str = str(dag_data.get("connector_id", ""))
  connector_data: Any = connectors_data.get(connector_id, {})
  if not isinstance(connector_data, dict):
    return False

  default_sources: Any = connector_data.get("default_sources", [])
  return isinstance(default_sources, list) and seed_id in default_sources


def _affected_dags_for_seed(seed_id: str) -> dict[str, Any]:
  """Return DAG config entries affected by a seed source_url change."""
  dags_data: dict[str, Any] = _load_config(DAGS_RESOURCE)
  connectors_data: dict[str, Any] = _load_config(CONNECTORS_RESOURCE)
  affected_dags: dict[str, Any] = {}

  for dag_id, dag_data in dags_data.items():
    if isinstance(dag_data, dict) and _dag_uses_seed(seed_id, dag_data, connectors_data):
      affected_dags[dag_id] = dag_data

  return affected_dags


def _affected_dags_for_connector(connector_id: str) -> dict[str, Any]:
  """Return DAG config entries affected by a connector change."""
  dags_data: dict[str, Any] = _load_config(DAGS_RESOURCE)
  affected_dags: dict[str, Any] = {}

  for dag_id, dag_data in dags_data.items():
    if isinstance(dag_data, dict) and str(dag_data.get("connector_id")) == connector_id:
      affected_dags[dag_id] = dag_data

  return affected_dags


def _connector_regeneration_needed(
  current_item: dict[str, Any],
  updated_item: dict[str, Any],
) -> bool:
  """Return whether a connector update must regenerate dependent DAGs."""
  if updated_item.get("is_active") is False:
    return False

  return any(
    current_item.get(field_name) != updated_item.get(field_name)
    for field_name in CONNECTOR_REGENERATION_FIELDS
  )


def _seed_regeneration_needed(
  current_item: dict[str, Any],
  updated_item: dict[str, Any],
) -> bool:
  """Return whether a seed update must regenerate dependent DAGs."""
  if updated_item.get("is_active") is False:
    return False

  return current_item.get("source_url") != updated_item.get("source_url")


@app.get("/health")
def health() -> dict[str, str]:
  """Return the API health status."""
  return {"status": "ok"}


@app.get("/seed-list")
def list_seeds() -> dict[str, Any]:
  """Return all seed_list entries."""
  return _load_config(SEED_LIST_RESOURCE)


@app.get("/seed-list/{seed_id:path}")
def get_seed(seed_id: str) -> dict[str, Any]:
  """Return one seed_list entry by id."""
  seeds_data: dict[str, Any] = _load_config(SEED_LIST_RESOURCE)
  if seed_id not in seeds_data:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Seed not found")

  return seeds_data[seed_id]


@app.post("/seed-list/{seed_id:path}", status_code=status.HTTP_201_CREATED)
def create_seed(
  seed_id: str,
  seed_data: Annotated[dict[str, Any], Body(...)],
) -> dict[str, Any]:
  """Create one seed_list entry without regenerating DAGs."""
  _validate_item(SEED_LIST_RESOURCE, seed_id, seed_data)

  with CONFIG_LOCK:
    seeds_data: dict[str, Any] = _load_config(SEED_LIST_RESOURCE)
    if seed_id in seeds_data:
      raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Seed already exists")

    seeds_data[seed_id] = seed_data
    _save_config(SEED_LIST_RESOURCE, seeds_data)

  return _response_payload(SEED_LIST_RESOURCE, seed_id, "created", seed_data)


@app.put("/seed-list/{seed_id:path}")
def update_seed(
  seed_id: str,
  seed_data: Annotated[dict[str, Any], Body(...)],
) -> dict[str, Any]:
  """Replace one seed_list entry and regenerate DAGs when source_url changes."""
  _validate_item(SEED_LIST_RESOURCE, seed_id, seed_data)

  with CONFIG_LOCK:
    seeds_data: dict[str, Any] = _load_config(SEED_LIST_RESOURCE)
    if seed_id not in seeds_data:
      raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Seed not found")

    current_seed: dict[str, Any] = dict(seeds_data[seed_id])
    should_generate: bool = _seed_regeneration_needed(current_seed, seed_data)
    affected_dags: dict[str, Any] = _affected_dags_for_seed(seed_id) if should_generate else {}

    seeds_data[seed_id] = seed_data
    _save_config(SEED_LIST_RESOURCE, seeds_data)

    try:
      generated_files: list[str] = _generate_dags(affected_dags)
    except HTTPException:
      seeds_data[seed_id] = current_seed
      _save_config(SEED_LIST_RESOURCE, seeds_data)
      raise

  return _response_payload(
    SEED_LIST_RESOURCE,
    seed_id,
    "updated",
    seed_data,
    affected_dags=list(affected_dags.keys()),
    generated_files=generated_files,
  )


@app.delete("/seed-list/{seed_id:path}")
def delete_seed(seed_id: str) -> dict[str, Any]:
  """Delete one seed_list entry without modifying DAG config or files."""
  _validate_item_id(seed_id, SEED_LIST_RESOURCE)

  with CONFIG_LOCK:
    seeds_data: dict[str, Any] = _load_config(SEED_LIST_RESOURCE)
    if seed_id not in seeds_data:
      raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Seed not found")

    deleted_seed: dict[str, Any] = dict(seeds_data.pop(seed_id))
    _save_config(SEED_LIST_RESOURCE, seeds_data)

  return _response_payload(SEED_LIST_RESOURCE, seed_id, "deleted", deleted_seed)


@app.get("/connectors")
def list_connectors() -> dict[str, Any]:
  """Return all connector entries."""
  return _load_config(CONNECTORS_RESOURCE)


@app.get("/connectors/{connector_id:path}")
def get_connector(connector_id: str) -> dict[str, Any]:
  """Return one connector entry by id."""
  connectors_data: dict[str, Any] = _load_config(CONNECTORS_RESOURCE)
  if connector_id not in connectors_data:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Connector not found")

  return connectors_data[connector_id]


@app.post("/connectors/{connector_id:path}", status_code=status.HTTP_201_CREATED)
def create_connector(
  connector_id: str,
  connector_data: Annotated[dict[str, Any], Body(...)],
) -> dict[str, Any]:
  """Create one connector entry without regenerating DAGs."""
  _validate_item(CONNECTORS_RESOURCE, connector_id, connector_data)

  with CONFIG_LOCK:
    connectors_data: dict[str, Any] = _load_config(CONNECTORS_RESOURCE)
    if connector_id in connectors_data:
      raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Connector already exists")

    connectors_data[connector_id] = connector_data
    _save_config(CONNECTORS_RESOURCE, connectors_data)

  return _response_payload(CONNECTORS_RESOURCE, connector_id, "created", connector_data)


@app.put("/connectors/{connector_id:path}")
def update_connector(
  connector_id: str,
  connector_data: Annotated[dict[str, Any], Body(...)],
) -> dict[str, Any]:
  """Replace one connector and regenerate DAGs when selected fields change."""
  _validate_item(CONNECTORS_RESOURCE, connector_id, connector_data)

  with CONFIG_LOCK:
    connectors_data: dict[str, Any] = _load_config(CONNECTORS_RESOURCE)
    if connector_id not in connectors_data:
      raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Connector not found")

    current_connector: dict[str, Any] = dict(connectors_data[connector_id])
    should_generate: bool = _connector_regeneration_needed(current_connector, connector_data)
    affected_dags: dict[str, Any] = _affected_dags_for_connector(connector_id) if should_generate else {}

    connectors_data[connector_id] = connector_data
    _save_config(CONNECTORS_RESOURCE, connectors_data)

    try:
      generated_files: list[str] = _generate_dags(affected_dags)
    except HTTPException:
      connectors_data[connector_id] = current_connector
      _save_config(CONNECTORS_RESOURCE, connectors_data)
      raise

  return _response_payload(
    CONNECTORS_RESOURCE,
    connector_id,
    "updated",
    connector_data,
    affected_dags=list(affected_dags.keys()),
    generated_files=generated_files,
  )


@app.delete("/connectors/{connector_id:path}")
def delete_connector(connector_id: str) -> dict[str, Any]:
  """Delete one connector entry without modifying DAG config or files."""
  _validate_item_id(connector_id, CONNECTORS_RESOURCE)

  with CONFIG_LOCK:
    connectors_data: dict[str, Any] = _load_config(CONNECTORS_RESOURCE)
    if connector_id not in connectors_data:
      raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Connector not found")

    deleted_connector: dict[str, Any] = dict(connectors_data.pop(connector_id))
    _save_config(CONNECTORS_RESOURCE, connectors_data)

  return _response_payload(CONNECTORS_RESOURCE, connector_id, "deleted", deleted_connector)


@app.get("/dags")
def list_dags() -> dict[str, Any]:
  """Return all DAG config entries."""
  return _load_config(DAGS_RESOURCE)


@app.get("/dags/{dag_id:path}")
def get_dag(dag_id: str) -> dict[str, Any]:
  """Return one DAG config entry by id."""
  dags_data: dict[str, Any] = _load_config(DAGS_RESOURCE)
  if dag_id not in dags_data:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="DAG not found")

  return dags_data[dag_id]


@app.post("/dags/{dag_id:path}", status_code=status.HTTP_201_CREATED)
def create_dag(
  dag_id: str,
  dag_data: Annotated[dict[str, Any], Body(...)],
) -> dict[str, Any]:
  """Create one DAG config entry and generate its DAG file."""
  _validate_item(DAGS_RESOURCE, dag_id, dag_data)

  with CONFIG_LOCK:
    dags_data: dict[str, Any] = _load_config(DAGS_RESOURCE)
    if dag_id in dags_data:
      raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="DAG already exists")

    generated_files: list[str] = _generate_dags({dag_id: dag_data})
    dags_data[dag_id] = dag_data
    _save_config(DAGS_RESOURCE, dags_data)

  return _response_payload(
    DAGS_RESOURCE,
    dag_id,
    "created",
    dag_data,
    affected_dags=[dag_id],
    generated_files=generated_files,
  )


@app.put("/dags/{dag_id:path}")
def update_dag(
  dag_id: str,
  dag_data: Annotated[dict[str, Any], Body(...)],
) -> dict[str, Any]:
  """Replace one DAG config entry and regenerate its DAG file."""
  _validate_item(DAGS_RESOURCE, dag_id, dag_data)

  with CONFIG_LOCK:
    dags_data: dict[str, Any] = _load_config(DAGS_RESOURCE)
    if dag_id not in dags_data:
      raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="DAG not found")

    generated_files: list[str] = _generate_dags({dag_id: dag_data})
    dags_data[dag_id] = dag_data
    _save_config(DAGS_RESOURCE, dags_data)

  return _response_payload(
    DAGS_RESOURCE,
    dag_id,
    "updated",
    dag_data,
    affected_dags=[dag_id],
    generated_files=generated_files,
  )


@app.delete("/dags/{dag_id:path}")
def delete_dag(dag_id: str) -> dict[str, Any]:
  """Delete one DAG config entry and its generated DAG file."""
  _validate_item_id(dag_id, DAGS_RESOURCE)
  _validate_dag_id(dag_id)

  with CONFIG_LOCK:
    dags_data: dict[str, Any] = _load_config(DAGS_RESOURCE)
    if dag_id not in dags_data:
      raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="DAG not found")

    deleted_dag: dict[str, Any] = dict(dags_data.pop(dag_id))
    _save_config(DAGS_RESOURCE, dags_data)
    deleted_files: list[str] = _delete_dag_file(dag_id)

  return _response_payload(
    DAGS_RESOURCE,
    dag_id,
    "deleted",
    deleted_dag,
    affected_dags=[dag_id],
    deleted_files=deleted_files,
  )
