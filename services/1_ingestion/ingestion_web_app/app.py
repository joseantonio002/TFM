"""Streamlit web app for the ingestion configuration API."""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
from typing import Any

import requests
import streamlit as st


API_BASE_URL: str = os.getenv("INGESTION_API_BASE_URL", "http://localhost:8001").rstrip("/")
REQUEST_TIMEOUT_SECONDS: int = 20


@dataclass(frozen=True)
class ResourceConfig:
  """UI metadata for one ingestion API resource."""

  key: str
  label: str
  endpoint: str
  id_label: str
  description: str
  mutation_note: str


RESOURCE_CONFIGS: dict[str, ResourceConfig] = {
  "seed_list": ResourceConfig(
    key="seed_list",
    label="Fuentes",
    endpoint="/seed-list",
    id_label="Seed ID",
    description="Gestiona las fuentes de datos de seed_list.json.",
    mutation_note="Solo los cambios de source_url regeneran DAGs afectados si la fuente queda activa.",
  ),
  "connectors": ResourceConfig(
    key="connectors",
    label="Conectores",
    endpoint="/connectors",
    id_label="Connector ID",
    description="Gestiona los conectores de connectors.json.",
    mutation_note="Solo los cambios de docker_image o connector_name regeneran DAGs afectados si el conector queda activo.",
  ),
  "dags": ResourceConfig(
    key="dags",
    label="DAGs",
    endpoint="/dags",
    id_label="DAG ID",
    description="Gestiona las entradas de dags.json y sus ficheros Python generados.",
    mutation_note="Crear o modificar un DAG regenera su fichero. Eliminar un DAG borra su .py generado.",
  ),
}

RESOURCE_ORDER: list[str] = ["seed_list", "connectors", "dags"]

RESOURCE_TEMPLATES: dict[str, dict[str, Any]] = {
  "seed_list": {
    "source_name": "New Source",
    "source_type": "TV",
    "source_url": "https://example.com/live.m3u8",
    "source_tags": ["news"],
    "lang": "es",
    "country": "ES",
    "default_connector_id": "TV/RadioES",
    "description": "Describe la fuente de datos",
    "is_active": True,
  },
  "connectors": {
    "docker_image": "connector-image:latest",
    "connector_name": "ConnectorName",
    "description": "Describe el conector y sus parametros",
    "accepted_source_types": ["TV", "Radio"],
    "default_sources": ["SourceId"],
    "accepted_params": {
      "t": "total time to ingest in seconds",
    },
    "is_active": True,
  },
  "dags": {
    "task_id": "new_task",
    "connector_id": "TV/RadioES",
    "schedule": "0 */2 * * *",
    "start_date": "datetime(2024, 1, 1)",
    "seed_ids": ["SourceId"],
    "params": {
      "t": 60,
    },
  },
}


def format_json(data: dict[str, Any]) -> str:
  """Return a stable pretty JSON string for editor widgets."""
  return json.dumps(data, indent=2, ensure_ascii=False)


def parse_json_payload(raw_payload: str) -> tuple[dict[str, Any] | None, str | None]:
  """Parse a JSON editor payload and return data or an error message."""
  try:
    payload: Any = json.loads(raw_payload)
  except json.JSONDecodeError as exc:
    return None, f"JSON invalido: {exc}"

  if not isinstance(payload, dict):
    return None, "El payload debe ser un objeto JSON."

  return payload, None


def build_url(endpoint: str) -> str:
  """Build an absolute API URL for an endpoint."""
  return f"{API_BASE_URL}{endpoint}"


def request_api(
  method: str,
  endpoint: str,
  payload: dict[str, Any] | None = None,
) -> tuple[bool, dict[str, Any]]:
  """Send one request to the ingestion API and return the decoded response."""
  try:
    response: requests.Response = requests.request(
      method=method,
      url=build_url(endpoint),
      json=payload,
      timeout=REQUEST_TIMEOUT_SECONDS,
    )
  except requests.RequestException as exc:
    return False, {"detail": f"No se pudo conectar con la API: {exc}"}

  try:
    response_payload: Any = response.json()
  except ValueError:
    response_payload = {"detail": response.text}

  if not isinstance(response_payload, dict):
    response_payload = {"data": response_payload}

  if response.ok:
    return True, response_payload

  return False, {
    "status_code": response.status_code,
    "detail": response_payload.get("detail", response_payload),
  }


@st.cache_data(show_spinner=False, ttl=10)
def fetch_resource(endpoint: str) -> dict[str, Any]:
  """Fetch all entries for one resource from the ingestion API."""
  response: requests.Response = requests.get(
    build_url(endpoint),
    timeout=REQUEST_TIMEOUT_SECONDS,
  )
  response.raise_for_status()
  payload: Any = response.json()
  if not isinstance(payload, dict):
    raise ValueError("La API no devolvio un objeto JSON.")
  return payload


def render_page_style() -> None:
  """Apply small visual refinements to the Streamlit app."""
  st.markdown(
    """
    <style>
      .block-container {padding-top: 2rem;}
      div[data-testid="stMetric"] {
        background: #f8fafc;
        border: 1px solid #e2e8f0;
        border-radius: 14px;
        padding: 14px;
      }
      .small-note {
        color: #475569;
        font-size: 0.92rem;
      }
    </style>
    """,
    unsafe_allow_html=True,
  )


def render_header() -> None:
  """Render the application header."""
  st.set_page_config(page_title="Ingestion Config Manager", layout="wide")
  render_page_style()
  st.title("Gestor visual de ingestion")
  st.caption(f"API configurada: {API_BASE_URL}")


def render_api_status() -> None:
  """Render the API connection status in the sidebar."""
  success, payload = request_api("GET", "/health")
  if success:
    st.sidebar.success("ingestion-api disponible")
    return

  st.sidebar.error("ingestion-api no responde")
  st.sidebar.json(payload)


def render_resource_selector() -> ResourceConfig:
  """Render the resource selector and return the selected resource config."""
  selected_label: str = st.sidebar.radio(
    "Recurso",
    options=[RESOURCE_CONFIGS[key].label for key in RESOURCE_ORDER],
    index=0,
  )

  for resource_key in RESOURCE_ORDER:
    config: ResourceConfig = RESOURCE_CONFIGS[resource_key]
    if config.label == selected_label:
      return config

  return RESOURCE_CONFIGS[RESOURCE_ORDER[0]]


def summarize_item(resource_key: str, item_id: str, item_data: Any) -> dict[str, Any]:
  """Build one compact table row for a resource item."""
  if not isinstance(item_data, dict):
    return {"id": item_id, "valor": str(item_data)}

  if resource_key == "seed_list":
    return {
      "id": item_id,
      "nombre": item_data.get("source_name", ""),
      "tipo": item_data.get("source_type", ""),
      "pais": item_data.get("country", ""),
      "activo": item_data.get("is_active", ""),
      "connector": item_data.get("default_connector_id", ""),
    }

  if resource_key == "connectors":
    return {
      "id": item_id,
      "nombre": item_data.get("connector_name", ""),
      "imagen": item_data.get("docker_image", ""),
      "activo": item_data.get("is_active", ""),
      "default_sources": len(item_data.get("default_sources", [])),
    }

  return {
    "id": item_id,
    "task_id": item_data.get("task_id", ""),
    "connector": item_data.get("connector_id", ""),
    "schedule": item_data.get("schedule", ""),
    "seed_ids": len(item_data.get("seed_ids", [])),
  }


def render_metrics(resource_key: str, resource_data: dict[str, Any]) -> None:
  """Render quick summary metrics for the selected resource."""
  total_items: int = len(resource_data)
  active_items: int = 0
  inactive_items: int = 0

  for item_data in resource_data.values():
    if not isinstance(item_data, dict) or "is_active" not in item_data:
      continue
    if item_data["is_active"] is True:
      active_items += 1
    elif item_data["is_active"] is False:
      inactive_items += 1

  column_1, column_2, column_3 = st.columns(3)
  column_1.metric("Elementos", total_items)
  if resource_key == "dags":
    column_2.metric("Con seed_ids explicitos", sum(1 for item in resource_data.values() if isinstance(item, dict) and item.get("seed_ids")))
    column_3.metric("Con defaults del conector", sum(1 for item in resource_data.values() if isinstance(item, dict) and not item.get("seed_ids")))
    return

  column_2.metric("Activos", active_items)
  column_3.metric("Inactivos", inactive_items)


def render_last_mutation() -> None:
  """Render the latest mutation result stored in session state."""
  last_mutation: dict[str, Any] | None = st.session_state.get("last_mutation")
  if not last_mutation:
    return

  if last_mutation["success"]:
    st.success(last_mutation["message"])
  else:
    st.error(last_mutation["message"])
  with st.expander("Ver respuesta de la API", expanded=not last_mutation["success"]):
    st.json(last_mutation["payload"])


def store_mutation_result(success: bool, action: str, payload: dict[str, Any]) -> None:
  """Store a mutation result and refresh cached API data."""
  if success:
    affected_dags: list[str] = list(payload.get("affected_dags", []))
    generated_files: list[str] = list(payload.get("generated_files", []))
    deleted_files: list[str] = list(payload.get("deleted_files", []))
    summary_parts: list[str] = [action]
    if affected_dags:
      summary_parts.append(f"DAGs afectados: {', '.join(affected_dags)}")
    if generated_files:
      summary_parts.append(f"ficheros generados: {len(generated_files)}")
    if deleted_files:
      summary_parts.append(f"ficheros eliminados: {len(deleted_files)}")
    message: str = " | ".join(summary_parts)
    fetch_resource.clear()
  else:
    message = f"La operacion fallo: {payload.get('detail', payload)}"

  st.session_state["last_mutation"] = {
    "success": success,
    "message": message,
    "payload": payload,
  }
  st.rerun()


def render_resource_table(config: ResourceConfig, resource_data: dict[str, Any]) -> None:
  """Render the current resource data table."""
  st.subheader(f"{config.label} actuales")
  if not resource_data:
    st.info("No hay elementos configurados para este recurso.")
    return

  rows: list[dict[str, Any]] = [
    summarize_item(config.key, item_id, item_data)
    for item_id, item_data in resource_data.items()
  ]
  st.dataframe(rows, use_container_width=True, hide_index=True)


def choose_existing_item(
  config: ResourceConfig,
  resource_data: dict[str, Any],
  widget_key: str,
) -> str | None:
  """Render an item selector for resources that already have entries."""
  if not resource_data:
    return None

  item_ids: list[str] = sorted(resource_data.keys())
  return st.selectbox(
    config.id_label,
    options=item_ids,
    key=f"selected_{config.key}_{widget_key}",
  )


def render_editor_tab(config: ResourceConfig, resource_data: dict[str, Any]) -> None:
  """Render the PUT editor for an existing item."""
  st.subheader("Modificar elemento existente")
  st.markdown(f"<p class='small-note'>{config.mutation_note}</p>", unsafe_allow_html=True)
  selected_id: str | None = choose_existing_item(config, resource_data, "edit")
  if selected_id is None:
    st.info("No hay elementos para modificar.")
    return

  current_item: Any = resource_data[selected_id]
  if not isinstance(current_item, dict):
    st.error("El elemento seleccionado no es un objeto JSON editable.")
    return

  with st.form(f"edit_form_{config.key}_{selected_id}"):
    raw_payload: str = st.text_area(
      "Objeto JSON completo",
      value=format_json(current_item),
      height=360,
      key=f"edit_payload_{config.key}_{selected_id}",
    )
    submitted: bool = st.form_submit_button("Guardar cambios", type="primary")

  if not submitted:
    return

  payload, error_message = parse_json_payload(raw_payload)
  if error_message:
    st.error(error_message)
    return

  success, response_payload = request_api("PUT", f"{config.endpoint}/{selected_id}", payload)
  store_mutation_result(success, f"{config.label}: {selected_id} actualizado", response_payload)


def render_create_tab(config: ResourceConfig, resource_data: dict[str, Any]) -> None:
  """Render the POST form for a new item."""
  st.subheader("Crear nuevo elemento")
  template_source: str = st.radio(
    "Plantilla inicial",
    options=["Plantilla vacia", "Copiar elemento seleccionado"],
    horizontal=True,
    key=f"template_source_{config.key}",
  )
  selected_id: str | None = None
  template_payload: dict[str, Any] = RESOURCE_TEMPLATES[config.key]

  if template_source == "Copiar elemento seleccionado" and resource_data:
    selected_id = choose_existing_item(config, resource_data, "create_template")
    if selected_id and isinstance(resource_data[selected_id], dict):
      template_payload = resource_data[selected_id]

  with st.form(f"create_form_{config.key}"):
    new_item_id: str = st.text_input(config.id_label, key=f"new_id_{config.key}")
    raw_payload: str = st.text_area(
      "Objeto JSON completo",
      value=format_json(template_payload),
      height=360,
      key=f"create_payload_{config.key}_{selected_id or 'default'}",
    )
    submitted: bool = st.form_submit_button("Crear elemento", type="primary")

  if not submitted:
    return

  if not new_item_id.strip():
    st.error("La clave del elemento no puede estar vacia.")
    return

  payload, error_message = parse_json_payload(raw_payload)
  if error_message:
    st.error(error_message)
    return

  success, response_payload = request_api("POST", f"{config.endpoint}/{new_item_id.strip()}", payload)
  store_mutation_result(success, f"{config.label}: {new_item_id.strip()} creado", response_payload)


def render_delete_tab(config: ResourceConfig, resource_data: dict[str, Any]) -> None:
  """Render the DELETE form for an existing item."""
  st.subheader("Eliminar elemento")
  st.warning(
    "Eliminar fuentes o conectores no modifica dags.json. "
    "Si algun DAG referencia el elemento eliminado, debes actualizarlo manualmente."
  )
  selected_id: str | None = choose_existing_item(config, resource_data, "delete")
  if selected_id is None:
    st.info("No hay elementos para eliminar.")
    return

  st.json(resource_data[selected_id])
  confirmation: str = st.text_input(
    f"Escribe {selected_id} para confirmar",
    key=f"delete_confirmation_{config.key}_{selected_id}",
  )
  delete_disabled: bool = confirmation != selected_id
  if st.button("Eliminar definitivamente", disabled=delete_disabled, type="primary"):
    success, response_payload = request_api("DELETE", f"{config.endpoint}/{selected_id}")
    store_mutation_result(success, f"{config.label}: {selected_id} eliminado", response_payload)


def render_resource_detail(config: ResourceConfig, resource_data: dict[str, Any]) -> None:
  """Render a read-only JSON viewer for one selected resource item."""
  st.subheader("Detalle")
  selected_id: str | None = choose_existing_item(config, resource_data, "detail")
  if selected_id is None:
    st.info("No hay elementos para inspeccionar.")
    return

  st.json(resource_data[selected_id])


def load_resource_data(config: ResourceConfig) -> dict[str, Any]:
  """Load a resource and render a useful error if the API call fails."""
  try:
    return fetch_resource(config.endpoint)
  except requests.RequestException as exc:
    st.error(f"Error consultando {config.endpoint}: {exc}")
  except ValueError as exc:
    st.error(str(exc))
  return {}


def render_rules_panel() -> None:
  """Render the important mutation rules panel."""
  with st.sidebar.expander("Reglas de modificacion", expanded=False):
    st.markdown(
      """
      - Las claves no se editan dentro del JSON: se fijan con la ruta.
      - `PUT` siempre envia el objeto completo.
      - Borrar o desactivar fuentes/conectores no modifica `dags.json`.
      - Cambios en `source_url`, `docker_image` o `connector_name` regeneran DAGs afectados.
      - Borrar un DAG elimina su fichero `.py` generado.
      """
    )


def main() -> None:
  """Run the ingestion configuration web application."""
  render_header()
  st.sidebar.header("Configuracion")
  render_api_status()
  render_rules_panel()
  config: ResourceConfig = render_resource_selector()

  st.markdown(f"### {config.label}")
  st.write(config.description)
  render_last_mutation()

  resource_data: dict[str, Any] = load_resource_data(config)
  render_metrics(config.key, resource_data)
  render_resource_table(config, resource_data)

  detail_tab, edit_tab, create_tab, delete_tab = st.tabs([
    "Detalle",
    "Modificar",
    "Crear",
    "Eliminar",
  ])

  with detail_tab:
    render_resource_detail(config, resource_data)
  with edit_tab:
    render_editor_tab(config, resource_data)
  with create_tab:
    render_create_tab(config, resource_data)
  with delete_tab:
    render_delete_tab(config, resource_data)


if __name__ == "__main__":
  main()
