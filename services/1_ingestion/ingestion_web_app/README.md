# Ingestion Web App

Aplicacion web en Streamlit para interactuar visualmente con `ingestion-api`.

## Ejecucion

Desde `services`, ejecuta:

```bash
docker compose up ingestion-api ingestion-web-app
```

La interfaz queda disponible en:

```text
http://localhost:8502
```

## Configuracion

La app usa la variable `INGESTION_API_BASE_URL` para localizar la API.

En `docker-compose.yml` queda configurada como:

```yaml
INGESTION_API_BASE_URL: http://ingestion-api:8001
```

## Funcionalidades

La interfaz permite gestionar estos recursos:

| Recurso | API usada |
| --- | --- |
| Fuentes | `/seed-list` |
| Conectores | `/connectors` |
| DAGs | `/dags` |

Para cada recurso se puede:

- Ver una tabla resumen de los elementos actuales.
- Inspeccionar un elemento en formato JSON.
- Crear un elemento nuevo con una plantilla JSON.
- Copiar un elemento existente como plantilla.
- Modificar un elemento existente enviando el objeto completo con `PUT`.
- Eliminar un elemento con confirmacion escribiendo su ID.

## Reglas Importantes

La clave del elemento no se modifica dentro del JSON. La clave se define en el campo de ID de la interfaz.

Las modificaciones usan `PUT`, por lo que hay que enviar siempre el objeto completo.

Eliminar fuentes o conectores no modifica `dags.json` ni regenera DAGs.

Cambiar `is_active` a `false` en fuentes o conectores no modifica `dags.json` ni regenera DAGs.

Cambios en `source_url`, `docker_image` o `connector_name` pueden regenerar DAGs afectados segun las reglas implementadas en `ingestion-api`.

Crear o modificar un DAG regenera su fichero `.py`.

Eliminar un DAG borra su fichero `.py` generado.
