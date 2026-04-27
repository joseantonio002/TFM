# Ingestion Config API

API REST para modificar los JSON de configuración de ingestión y regenerar los DAGs afectados cuando corresponde.

## Ejecución

El servicio está definido en `services/docker-compose.yml` como `ingestion-api`.

```bash
docker compose up ingestion-api
```

La API queda disponible en `http://localhost:8001`.

La documentación interactiva de FastAPI queda disponible en `http://localhost:8001/docs`.

## Tests

Desde `services`, ejecuta:

```bash
docker compose run --rm --no-deps \
  -e PYTHONPATH=/app \
  -v ./1_ingestion/ingestion_api/tests:/app/tests:ro \
  -v ./1_ingestion/ingestion_api/requirements-test.txt:/app/requirements-test.txt:ro \
  ingestion-api sh -c "pip install --no-cache-dir -r requirements-test.txt && pytest -q /app/tests"
```

Los tests usan directorios temporales, por lo que no modifican los JSONs ni los DAGs reales.

## Volúmenes

El servicio usa estos directorios dentro del contenedor:

| Ruta | Uso |
| --- | --- |
| `/jsons` | Carpeta desde la que se leen y escriben `seed_list.json`, `connectors.json` y `dags.json` |
| `/dags` | Carpeta donde se crean o eliminan los DAGs Python generados |

En `docker-compose.yml` se montan así:

```yaml
volumes:
  - ./1_ingestion/ingestion_jsons:/jsons
  - ${AIRFLOW_PROJ_DIR:-.}/dags:/dags
```

## Endpoints Generales

| Método | Ruta | Descripción |
| --- | --- | --- |
| `GET` | `/health` | Comprueba que la API está disponible |
| `GET` | `/seed-list` | Devuelve todas las fuentes |
| `GET` | `/connectors` | Devuelve todos los conectores |
| `GET` | `/dags` | Devuelve todos los DAGs configurados |

## Seed List

| Método | Ruta | Descripción |
| --- | --- | --- |
| `GET` | `/seed-list/{seed_id}` | Devuelve una fuente |
| `POST` | `/seed-list/{seed_id}` | Crea una fuente nueva |
| `PUT` | `/seed-list/{seed_id}` | Sustituye una fuente existente con el objeto completo |
| `DELETE` | `/seed-list/{seed_id}` | Elimina una fuente |

Ejemplo de creación:

```bash
curl -X POST "http://localhost:8001/seed-list/NewSource" \
  -H "Content-Type: application/json" \
  -d '{
    "source_name": "New Source",
    "source_type": "TV",
    "source_url": "https://example.com/live.m3u8",
    "source_tags": ["news"],
    "lang": "es",
    "country": "ES",
    "default_connector_id": "TV/RadioES",
    "description": "Example source",
    "is_active": true
  }'
```

Regeneración automática:

Solo se regeneran DAGs al modificar `source_url` con `PUT` y si la fuente queda activa.

Se regeneran los DAGs que usan esa fuente en `seed_ids`.

También se regeneran los DAGs cuyo conector incluye esa fuente en `default_sources`, siempre que el DAG no sobrescriba las fuentes con `seed_ids`.

## Connectors

| Método | Ruta | Descripción |
| --- | --- | --- |
| `GET` | `/connectors/{connector_id}` | Devuelve un conector |
| `POST` | `/connectors/{connector_id}` | Crea un conector nuevo |
| `PUT` | `/connectors/{connector_id}` | Sustituye un conector existente con el objeto completo |
| `DELETE` | `/connectors/{connector_id}` | Elimina un conector |

Los IDs de conector pueden contener `/`. Por ejemplo, el conector `TV/RadioES` se modifica con la ruta `/connectors/TV/RadioES`.

Ejemplo de modificación:

```bash
curl -X PUT "http://localhost:8001/connectors/TV/RadioES" \
  -H "Content-Type: application/json" \
  -d '{
    "docker_image": "connector-tv-radio-image:latest",
    "connector_name": "TV/RadioES",
    "description": "Connector for Spanish TV and radio streams",
    "accepted_source_types": ["TV", "Radio"],
    "default_sources": ["24Horas", "Actualidad360", "RNERadio5TodoNoticiasMurcia"],
    "accepted_params": {
      "t": "total time to ingest in seconds"
    },
    "is_active": true
  }'
```

Regeneración automática:

Solo se regeneran DAGs al modificar `docker_image` o `connector_name` con `PUT` y si el conector queda activo.

Se regeneran los DAGs cuyo `connector_id` coincide con el conector modificado.

## DAGs

| Método | Ruta | Descripción |
| --- | --- | --- |
| `GET` | `/dags/{dag_id}` | Devuelve un DAG configurado |
| `POST` | `/dags/{dag_id}` | Crea un DAG nuevo y genera su fichero `.py` |
| `PUT` | `/dags/{dag_id}` | Sustituye un DAG existente con el objeto completo y regenera su fichero `.py` |
| `DELETE` | `/dags/{dag_id}` | Elimina el DAG del JSON y borra su fichero `.py` generado |

Ejemplo de creación:

```bash
curl -X POST "http://localhost:8001/dags/NewDag" \
  -H "Content-Type: application/json" \
  -d '{
    "task_id": "new_task",
    "connector_id": "TV/RadioES",
    "schedule": "0 */2 * * *",
    "start_date": "datetime(2024, 1, 1)",
    "seed_ids": ["24Horas"],
    "params": {
      "t": 60
    }
  }'
```

Regeneración automática:

Al crear o modificar un elemento de `dags.json`, se pasa solo ese DAG a `generate_dags_from_json()`.

Al eliminar un elemento de `dags.json`, se borra el fichero `/dags/{dag_id}.py` si existe.

## Respuesta De Mutación

Las operaciones `POST`, `PUT` y `DELETE` devuelven una respuesta con esta forma:

```json
{
  "resource": "dags",
  "id": "NewDag",
  "action": "created",
  "affected_dags": ["NewDag"],
  "generated_files": ["/dags/NewDag.py"],
  "deleted_files": [],
  "item": {}
}
```

Campos principales:

| Campo | Descripción |
| --- | --- |
| `resource` | JSON modificado |
| `id` | Clave del elemento modificado |
| `action` | Acción realizada: `created`, `updated` o `deleted` |
| `affected_dags` | DAGs que se han regenerado o eliminado por la operación |
| `generated_files` | Ficheros `.py` generados |
| `deleted_files` | Ficheros `.py` eliminados |
| `item` | Objeto creado, modificado o eliminado |

## Reglas Importantes

No se pueden modificar las claves de ningún elemento. La clave se fija en la ruta, por ejemplo `/dags/TVRadioDag`.

`PUT` requiere enviar el objeto completo, no solo los campos que cambian.

`POST` falla con `409` si la clave ya existe.

`PUT` y `DELETE` fallan con `404` si la clave no existe.

Si se elimina una fuente o un conector, no se modifica `dags.json` ni se regeneran DAGs.

Si se cambia `is_active` a `false` en una fuente o un conector, no se modifica `dags.json` ni se regeneran DAGs.

Es responsabilidad del usuario modificar `dags.json` si elimina o desactiva una fuente o un conector que todavía esté referenciado por algún DAG.

La regeneración en cascada sí se hace cuando se modifica `source_url`, `docker_image` o `connector_name`, porque en esos casos no hace falta modificar las referencias guardadas en `dags.json`.
