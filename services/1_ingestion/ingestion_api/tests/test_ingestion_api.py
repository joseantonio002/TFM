"""Tests for the ingestion configuration API mutation rules."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient
from httpx import Response
import pytest

from app import main


@dataclass
class ApiTestContext:
  """Container for test client and temporary config paths."""

  client: TestClient
  json_dir: Path
  dags_dir: Path


def _seed_list_config() -> dict[str, Any]:
  """Return a seed_list configuration used by the tests."""
  return {
    "SeedA": {
      "source_name": "Seed A",
      "source_type": "TV",
      "source_url": "https://example.com/seed-a.m3u8",
      "source_tags": ["news"],
      "lang": "es",
      "country": "ES",
      "default_connector_id": "ConnectorA",
      "description": "Seed A description",
      "is_active": True,
    },
    "SeedB": {
      "source_name": "Seed B",
      "source_type": "Radio",
      "source_url": "https://example.com/seed-b.m3u8",
      "source_tags": ["radio"],
      "lang": "es",
      "country": "ES",
      "default_connector_id": "ConnectorA",
      "description": "Seed B description",
      "is_active": True,
    },
    "SeedC": {
      "source_name": "Seed C",
      "source_type": "TV",
      "source_url": "https://example.com/seed-c.m3u8",
      "source_tags": ["other"],
      "lang": "es",
      "country": "ES",
      "default_connector_id": "ConnectorB",
      "description": "Seed C description",
      "is_active": True,
    },
  }


def _connectors_config() -> dict[str, Any]:
  """Return a connectors configuration used by the tests."""
  return {
    "ConnectorA": {
      "docker_image": "connector-a:old",
      "connector_name": "Connector A",
      "description": "Connector A description",
      "accepted_source_types": ["TV", "Radio"],
      "default_sources": ["SeedA", "SeedB"],
      "accepted_params": {"t": "seconds"},
      "is_active": True,
    },
    "ConnectorB": {
      "docker_image": "connector-b:old",
      "connector_name": "Connector B",
      "description": "Connector B description",
      "accepted_source_types": ["TV"],
      "default_sources": ["SeedC"],
      "accepted_params": {},
      "is_active": True,
    },
  }


def _dags_config() -> dict[str, Any]:
  """Return a dags configuration used by the tests."""
  return {
    "ExplicitDag": {
      "task_id": "explicit_task",
      "connector_id": "ConnectorA",
      "schedule": "0 * * * *",
      "start_date": "datetime(2024, 1, 1)",
      "seed_ids": ["SeedA"],
      "params": {"t": 60},
    },
    "DefaultDag": {
      "task_id": "default_task",
      "connector_id": "ConnectorA",
      "schedule": "0 */2 * * *",
      "start_date": "datetime(2024, 1, 1)",
      "params": {"t": 30},
    },
    "OverriddenDag": {
      "task_id": "overridden_task",
      "connector_id": "ConnectorA",
      "schedule": "0 */3 * * *",
      "start_date": "datetime(2024, 1, 1)",
      "seed_ids": ["SeedC"],
      "params": {"t": 20},
    },
    "OtherConnectorDag": {
      "task_id": "other_task",
      "connector_id": "ConnectorB",
      "schedule": "0 */4 * * *",
      "start_date": "datetime(2024, 1, 1)",
      "params": {"t": 10},
    },
  }


def _write_json(json_path: Path, data: dict[str, Any]) -> None:
  """Write JSON data to a path using the repository formatting style."""
  json_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def _read_json(json_path: Path) -> dict[str, Any]:
  """Read JSON object data from a path."""
  loaded_data: Any = json.loads(json_path.read_text(encoding="utf-8"))
  assert isinstance(loaded_data, dict)
  return loaded_data


def _updated_seed(seed_id: str, **overrides: Any) -> dict[str, Any]:
  """Return one seed payload with optional overridden fields."""
  seed_data: dict[str, Any] = dict(_seed_list_config()[seed_id])
  seed_data.update(overrides)
  return seed_data


def _updated_connector(connector_id: str, **overrides: Any) -> dict[str, Any]:
  """Return one connector payload with optional overridden fields."""
  connector_data: dict[str, Any] = dict(_connectors_config()[connector_id])
  connector_data.update(overrides)
  return connector_data


def _updated_dag(dag_id: str, **overrides: Any) -> dict[str, Any]:
  """Return one DAG payload with optional overridden fields."""
  dag_data: dict[str, Any] = dict(_dags_config()[dag_id])
  dag_data.update(overrides)
  return dag_data


@pytest.fixture()
def api_context(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> ApiTestContext:
  """Create a TestClient that reads and writes temporary JSON files."""
  json_dir: Path = tmp_path / "jsons"
  dags_dir: Path = tmp_path / "dags"
  json_dir.mkdir()
  dags_dir.mkdir()

  _write_json(json_dir / "seed_list.json", _seed_list_config())
  _write_json(json_dir / "connectors.json", _connectors_config())
  _write_json(json_dir / "dags.json", _dags_config())

  monkeypatch.setattr(main, "JSON_DIR", json_dir)
  monkeypatch.setattr(main, "DAGS_DIR", dags_dir)

  return ApiTestContext(
    client=TestClient(main.app),
    json_dir=json_dir,
    dags_dir=dags_dir,
  )


@pytest.fixture()
def generation_calls(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
  """Record calls to generate_dags_from_json without writing DAG files."""
  calls: list[dict[str, Any]] = []

  def fake_generate_dags_from_json(
    input_json: dict[str, Any],
    connectors_path: str = "../ingestion_jsons/connectors.json",
    seed_list_path: str = "../ingestion_jsons/seed_list.json",
    output_dir: str = "../../dags",
  ) -> list[str]:
    """Record the generator call and return deterministic file paths."""
    calls.append(
      {
        "input_json": input_json,
        "connectors_path": connectors_path,
        "seed_list_path": seed_list_path,
        "output_dir": output_dir,
      }
    )
    return [str(Path(output_dir) / f"{dag_id}.py") for dag_id in input_json]

  monkeypatch.setattr(main, "generate_dags_from_json", fake_generate_dags_from_json)
  return calls


def test_create_dag_generates_only_created_dag(
  api_context: ApiTestContext,
  generation_calls: list[dict[str, Any]],
) -> None:
  """Verify DAG creation persists the item and regenerates only that DAG."""
  new_dag: dict[str, Any] = {
    "task_id": "new_task",
    "connector_id": "ConnectorA",
    "schedule": "15 * * * *",
    "start_date": "datetime(2024, 2, 1)",
    "seed_ids": ["SeedA"],
    "params": {"t": 90},
  }

  response: Response = api_context.client.post("/dags/NewDag", json=new_dag)

  assert response.status_code == 201
  assert response.json()["affected_dags"] == ["NewDag"]
  assert list(generation_calls[0]["input_json"].keys()) == ["NewDag"]
  assert _read_json(api_context.json_dir / "dags.json")["NewDag"] == new_dag


def test_update_dag_keeps_key_and_generates_only_updated_dag(
  api_context: ApiTestContext,
  generation_calls: list[dict[str, Any]],
) -> None:
  """Verify DAG updates replace the existing key and do not rename it."""
  updated_dag: dict[str, Any] = _updated_dag(
    "ExplicitDag",
    task_id="renamed_task",
    schedule="30 * * * *",
  )

  response: Response = api_context.client.put("/dags/ExplicitDag", json=updated_dag)

  dags_data: dict[str, Any] = _read_json(api_context.json_dir / "dags.json")
  assert response.status_code == 200
  assert "ExplicitDag" in dags_data
  assert "renamed_task" not in dags_data
  assert dags_data["ExplicitDag"] == updated_dag
  assert list(generation_calls[0]["input_json"].keys()) == ["ExplicitDag"]


def test_delete_dag_removes_config_and_generated_file(api_context: ApiTestContext) -> None:
  """Verify DAG deletion removes the JSON entry and generated Python file."""
  dag_file: Path = api_context.dags_dir / "ExplicitDag.py"
  dag_file.write_text("# generated dag\n", encoding="utf-8")

  response: Response = api_context.client.delete("/dags/ExplicitDag")

  assert response.status_code == 200
  assert "ExplicitDag" not in _read_json(api_context.json_dir / "dags.json")
  assert not dag_file.exists()
  assert response.json()["deleted_files"] == [str(dag_file.resolve())]


def test_seed_source_url_update_regenerates_explicit_and_default_dags(
  api_context: ApiTestContext,
  generation_calls: list[dict[str, Any]],
) -> None:
  """Verify source_url changes affect explicit seed_ids and connector defaults."""
  updated_seed: dict[str, Any] = _updated_seed(
    "SeedA",
    source_url="https://example.com/seed-a-new.m3u8",
  )

  response: Response = api_context.client.put("/seed-list/SeedA", json=updated_seed)

  generated_dags: set[str] = set(generation_calls[0]["input_json"].keys())
  assert response.status_code == 200
  assert generated_dags == {"ExplicitDag", "DefaultDag"}
  assert set(response.json()["affected_dags"]) == {"ExplicitDag", "DefaultDag"}


def test_seed_source_url_update_ignores_defaults_when_dag_overrides_seed_ids(
  api_context: ApiTestContext,
  generation_calls: list[dict[str, Any]],
) -> None:
  """Verify default_sources are ignored when a DAG defines seed_ids."""
  updated_seed: dict[str, Any] = _updated_seed(
    "SeedB",
    source_url="https://example.com/seed-b-new.m3u8",
  )

  response: Response = api_context.client.put("/seed-list/SeedB", json=updated_seed)

  generated_dags: set[str] = set(generation_calls[0]["input_json"].keys())
  assert response.status_code == 200
  assert generated_dags == {"DefaultDag"}
  assert response.json()["affected_dags"] == ["DefaultDag"]


def test_seed_update_without_source_url_change_does_not_regenerate(
  api_context: ApiTestContext,
  generation_calls: list[dict[str, Any]],
) -> None:
  """Verify seed changes outside source_url do not regenerate DAG files."""
  updated_seed: dict[str, Any] = _updated_seed("SeedA", description="New description")

  response: Response = api_context.client.put("/seed-list/SeedA", json=updated_seed)

  assert response.status_code == 200
  assert generation_calls == []
  assert response.json()["affected_dags"] == []


def test_seed_deactivation_does_not_regenerate_even_when_url_changes(
  api_context: ApiTestContext,
  generation_calls: list[dict[str, Any]],
) -> None:
  """Verify setting is_active to false does not cascade DAG regeneration."""
  updated_seed: dict[str, Any] = _updated_seed(
    "SeedA",
    source_url="https://example.com/inactive-seed-a.m3u8",
    is_active=False,
  )

  response: Response = api_context.client.put("/seed-list/SeedA", json=updated_seed)

  assert response.status_code == 200
  assert generation_calls == []
  assert response.json()["affected_dags"] == []


def test_connector_image_update_regenerates_matching_connector_dags(
  api_context: ApiTestContext,
  generation_calls: list[dict[str, Any]],
) -> None:
  """Verify docker_image changes regenerate DAGs that use the connector."""
  updated_connector: dict[str, Any] = _updated_connector(
    "ConnectorA",
    docker_image="connector-a:new",
  )

  response: Response = api_context.client.put("/connectors/ConnectorA", json=updated_connector)

  generated_dags: set[str] = set(generation_calls[0]["input_json"].keys())
  assert response.status_code == 200
  assert generated_dags == {"ExplicitDag", "DefaultDag", "OverriddenDag"}
  assert set(response.json()["affected_dags"]) == {
    "ExplicitDag",
    "DefaultDag",
    "OverriddenDag",
  }


def test_connector_name_update_with_inactive_connector_does_not_regenerate(
  api_context: ApiTestContext,
  generation_calls: list[dict[str, Any]],
) -> None:
  """Verify setting connector is_active to false blocks regeneration."""
  updated_connector: dict[str, Any] = _updated_connector(
    "ConnectorA",
    connector_name="Inactive Connector A",
    is_active=False,
  )

  response: Response = api_context.client.put("/connectors/ConnectorA", json=updated_connector)

  assert response.status_code == 200
  assert generation_calls == []
  assert response.json()["affected_dags"] == []


def test_connector_update_without_regeneration_fields_does_not_regenerate(
  api_context: ApiTestContext,
  generation_calls: list[dict[str, Any]],
) -> None:
  """Verify connector fields outside docker_image and connector_name do not cascade."""
  updated_connector: dict[str, Any] = _updated_connector(
    "ConnectorA",
    description="New connector description",
  )

  response: Response = api_context.client.put("/connectors/ConnectorA", json=updated_connector)

  assert response.status_code == 200
  assert generation_calls == []
  assert response.json()["affected_dags"] == []


def test_delete_seed_does_not_regenerate_or_modify_dags(
  api_context: ApiTestContext,
  generation_calls: list[dict[str, Any]],
) -> None:
  """Verify seed deletion does not cascade into dags.json or generated files."""
  original_dags: dict[str, Any] = _read_json(api_context.json_dir / "dags.json")

  response: Response = api_context.client.delete("/seed-list/SeedA")

  assert response.status_code == 200
  assert generation_calls == []
  assert _read_json(api_context.json_dir / "dags.json") == original_dags


def test_delete_connector_does_not_regenerate_or_modify_dags(
  api_context: ApiTestContext,
  generation_calls: list[dict[str, Any]],
) -> None:
  """Verify connector deletion does not cascade into dags.json or generated files."""
  original_dags: dict[str, Any] = _read_json(api_context.json_dir / "dags.json")

  response: Response = api_context.client.delete("/connectors/ConnectorA")

  assert response.status_code == 200
  assert generation_calls == []
  assert _read_json(api_context.json_dir / "dags.json") == original_dags


def test_create_seed_and_connector_do_not_regenerate(
  api_context: ApiTestContext,
  generation_calls: list[dict[str, Any]],
) -> None:
  """Verify creating non-DAG resources does not trigger DAG regeneration."""
  new_seed: dict[str, Any] = _updated_seed("SeedA", source_name="New Seed")
  new_connector: dict[str, Any] = _updated_connector(
    "ConnectorA",
    connector_name="New Connector",
  )

  seed_response: Response = api_context.client.post("/seed-list/NewSeed", json=new_seed)
  connector_response: Response = api_context.client.post("/connectors/NewConnector", json=new_connector)

  assert seed_response.status_code == 201
  assert connector_response.status_code == 201
  assert generation_calls == []


def test_duplicate_create_and_missing_update_return_errors(
  api_context: ApiTestContext,
  generation_calls: list[dict[str, Any]],
) -> None:
  """Verify duplicate POST and missing PUT are rejected without regeneration."""
  duplicate_response: Response = api_context.client.post(
    "/seed-list/SeedA",
    json=_updated_seed("SeedA"),
  )
  missing_response: Response = api_context.client.put(
    "/dags/MissingDag",
    json=_updated_dag("ExplicitDag"),
  )

  assert duplicate_response.status_code == 409
  assert missing_response.status_code == 404
  assert generation_calls == []


def test_real_dag_generation_on_dag_create(api_context: ApiTestContext) -> None:
  """Verify a DAG POST writes a real generated Python file."""
  new_dag: dict[str, Any] = {
    "task_id": "real_generation_task",
    "connector_id": "ConnectorA",
    "schedule": "5 * * * *",
    "start_date": "datetime(2024, 3, 1)",
    "seed_ids": ["SeedA"],
    "params": {"t": 120},
  }

  response: Response = api_context.client.post("/dags/RealGeneratedDag", json=new_dag)
  generated_file: Path = api_context.dags_dir / "RealGeneratedDag.py"
  generated_source: str = generated_file.read_text(encoding="utf-8")

  assert response.status_code == 201
  assert generated_file.exists()
  assert "dag_id='RealGeneratedDag'" in generated_source
  assert "start_date=datetime(2024, 3, 1)" in generated_source
  assert "connector-a:old" in generated_source
  assert "https://example.com/seed-a.m3u8" in generated_source


def test_generator_failure_rolls_back_seed_update(
  api_context: ApiTestContext,
  monkeypatch: pytest.MonkeyPatch,
) -> None:
  """Verify JSON changes are rolled back if DAG regeneration fails."""
  original_seed: dict[str, Any] = _read_json(api_context.json_dir / "seed_list.json")["SeedA"]

  def failing_generate_dags_from_json(
    input_json: dict[str, Any],
    connectors_path: str = "../ingestion_jsons/connectors.json",
    seed_list_path: str = "../ingestion_jsons/seed_list.json",
    output_dir: str = "../../dags",
  ) -> list[str]:
    """Raise an error to simulate a generation failure."""
    raise RuntimeError("generation failed")

  monkeypatch.setattr(main, "generate_dags_from_json", failing_generate_dags_from_json)

  response: Response = api_context.client.put(
    "/seed-list/SeedA",
    json=_updated_seed("SeedA", source_url="https://example.com/failing.m3u8"),
  )

  assert response.status_code == 422
  assert _read_json(api_context.json_dir / "seed_list.json")["SeedA"] == original_seed


def test_connector_path_ids_can_contain_slashes(
  api_context: ApiTestContext,
  generation_calls: list[dict[str, Any]],
) -> None:
  """Verify connector ids with path separators are supported by the API route."""
  connector_payload: dict[str, Any] = _updated_connector("ConnectorA")

  response: Response = api_context.client.post("/connectors/TV/RadioES", json=connector_payload)

  connectors_data: dict[str, Any] = _read_json(api_context.json_dir / "connectors.json")
  assert response.status_code == 201
  assert connectors_data["TV/RadioES"] == connector_payload
  assert generation_calls == []


def test_dag_ids_reject_path_separators(api_context: ApiTestContext) -> None:
  """Verify DAG ids cannot escape the DAG output directory."""
  response: Response = api_context.client.post("/dags/Invalid/Dag", json=_updated_dag("ExplicitDag"))

  assert response.status_code == 422


def test_generator_receives_mounted_config_paths(
  api_context: ApiTestContext,
  generation_calls: list[dict[str, Any]],
) -> None:
  """Verify generation calls receive the configured JSON and DAG directories."""
  response: Response = api_context.client.put(
    "/connectors/ConnectorA",
    json=_updated_connector("ConnectorA", docker_image="connector-a:path-check"),
  )

  assert response.status_code == 200
  assert generation_calls[0]["connectors_path"] == str(api_context.json_dir / "connectors.json")
  assert generation_calls[0]["seed_list_path"] == str(api_context.json_dir / "seed_list.json")
  assert generation_calls[0]["output_dir"] == str(api_context.dags_dir)
