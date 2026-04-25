# News Dashboard

Dashboard prototipo en Streamlit para explorar la API de noticias.

## Que muestra

- volumen temporal
- duracion total y media
- distribucion por tipo y fuente
- ranking de entidades
- keywords frecuentes
- tabla de registros recientes

## Variable de entorno

- `NEWS_API_BASE_URL`: URL base de la API. En Docker Compose debe ser `http://news-api:8000`

## Ejecucion local

1. Instala dependencias con `pip install -r requirements.txt`.
2. Exporta `NEWS_API_BASE_URL` si hace falta.
3. Ejecuta `streamlit run app.py`.

## Ejecucion con Docker Compose

1. Anade el servicio de `docker-compose.service.example.yml` a `services/docker-compose.yml`.
2. Ejecuta `docker compose up --build news-dashboard` desde `services/`.
3. Abre `http://localhost:8501`.
