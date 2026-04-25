# News Metrics API

API REST en FastAPI para consultar registros y metricas de la tabla `news` en PostgreSQL.

## Estructura

- `app/main.py`: endpoints y queries
- `app/config.py`: configuracion por variables de entorno
- `app/database.py`: conexion a PostgreSQL
- `Dockerfile`: imagen de la API
- `requirements.txt`: dependencias Python
- `docker-compose.service.example.yml`: ejemplo de servicio para `services/docker-compose.yml`

## Variables de entorno

- `POSTGRES_USER`
- `POSTGRES_PASSWORD`
- `POSTGRES_DB`
- `NEWSDB_CONTAINER_NAME`
- `NEWS_TABLE_NAME` opcional, por defecto `news`

## Levantar la API

1. Anade el servicio de `docker-compose.service.example.yml` a `services/docker-compose.yml`.
2. Desde `services/`, ejecuta `docker compose up --build news-api`.
3. La API quedara disponible en `http://localhost:8000`.

## Endpoints

- `GET /health`
- `GET /records`
- `GET /metrics/volume`
- `GET /metrics/duration`
- `GET /metrics/source-distribution`
- `GET /metrics/entity-ranking`
- `GET /metrics/keyword-frequency`

## Tests

Los tests son de integracion y llaman a la API ya levantada.

1. Crea o activa un entorno virtual en `services/4_API`.
2. Instala dependencias de test con `pip install -r requirements-test.txt`.
3. Asegurate de que `news-api` esta corriendo en Docker Compose.
4. Ejecuta `pytest tests -v`.

Si la API no esta en `http://localhost:8000`, define `API_BASE_URL` antes de lanzar `pytest`.
