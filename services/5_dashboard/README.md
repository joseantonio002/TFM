# Media Intelligence Dashboard

Dashboard de una sola pagina en Streamlit para explorar topics, categorias de amenaza y sentimiento desde la API de noticias.

## Que muestra

- total de noticias disponibles y noticias que cumplen los filtros
- ranking horizontal de topics o categorias de amenaza
- ranking horizontal de las 10 entidades NER mas mencionadas por tipo (`PER`, `LOC`, `ORG`, `MISC`)
- heatmap de topics/categorias por fuente con numero de noticias
- heatmap de topics/categorias por fuente con sentimiento medio `positive - negative`
- evolucion diaria del nivel de alerta o sentimiento para un topic seleccionado, con volumen diario de noticias de fondo
- grafo de coocurrencia entre topics visibles, con grosor de arista proporcional a noticias compartidas

## Filtros

- rango de fechas, por defecto los ultimos 7 dias
- selector multiple de fuentes por `source_name`, por defecto todas las fuentes
- pool de candidatos de topics, de `1` a `100`, usado para elegir entre los topics mas importantes
- selector multiple de topics visibles, maximo `25` y minimo `1`, no necesariamente consecutivos
- buscador de topic para la evolucion temporal, limitado a los topics visibles seleccionados

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
