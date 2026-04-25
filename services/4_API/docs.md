# News Analytics API

API REST para consultar noticias almacenadas en PostgreSQL y obtener métricas agregadas para dashboards.

## Base URL

```http
http://localhost:8000
````

---

# Filtros comunes

La mayoría de endpoints aceptan estos filtros:

| Filtro         | Tipo          | Descripción                                |
| -------------- | ------------- | ------------------------------------------ |
| `from`         | datetime/date | Fecha inicial                              |
| `to`           | datetime/date | Fecha final                                |
| `source_type`  | string        | Tipo de fuente, por ejemplo `Radio` o `TV` |
| `source_name`  | string        | Nombre de la fuente, por ejemplo `esRadio` |
| `country`      | string        | País, por ejemplo `ES`                     |
| `language`     | string        | Idioma, por ejemplo `es`                   |
| `connector_id` | string        | ID del conector, por ejemplo `TV/RadioES`  |

Ejemplo:

```http
GET /metrics/volume?from=2026-04-01&to=2026-04-20&source_type=Radio&country=ES
```

---

# Endpoints

## GET /health

Comprueba si la API está funcionando.

### Filtros

No acepta filtros.

### Respuesta

```json
{
  "status": "ok",
  "service": "news-analytics-api",
  "version": "0.1.0"
}
```

---

## GET /records

Devuelve registros individuales de noticias.

### Filtros

Acepta filtros comunes y además:

| Filtro   | Tipo | Descripción                    |
| -------- | ---- | ------------------------------ |
| `limit`  | int  | Número máximo de registros     |
| `offset` | int  | Desplazamiento para paginación |

### Ejemplo

```http
GET /records?from=2026-04-20&source_type=Radio&limit=10&offset=0
```

### Respuesta

```json
{
  "data": [
    {
      "id": "b550e7e51fef4314a5bdef405733fe57",
      "source_name": "esRadio",
      "source_type": "Radio",
      "language": "es",
      "country": "ES",
      "extracted_at": "2026-04-20T17:47:41Z",
      "duration": 62.12,
      "content_preview": "En el que se servirán...",
      "entities": {
        "PER": ["Marisa"],
        "LOC": ["Alcampo Baco"],
        "ORG": ["Nutra", "Ultra"]
      }
    }
  ],
  "pagination": {
    "limit": 10,
    "offset": 0,
    "total": 1240
  }
}
```

---

## GET /metrics/volume

Devuelve el número de noticias agrupadas por intervalo temporal.

### Filtros

Acepta filtros comunes y además:

| Filtro     | Tipo   | Valores                        |
| ---------- | ------ | ------------------------------ |
| `group_by` | string | `hour`, `day`, `week`, `month` |

### Ejemplo

```http
GET /metrics/volume?from=2026-04-01&to=2026-04-20&group_by=day
```

### Respuesta

```json
{
  "metric": "volume",
  "group_by": "day",
  "data": [
    {
      "date": "2026-04-20",
      "count": 124
    }
  ]
}
```

---

## GET /metrics/duration

Devuelve duración total y media de los registros.

La duración se calcula usando:

```sql
other->>'duration'
```

### Filtros

Acepta filtros comunes y además:

| Filtro     | Tipo   | Valores                        |
| ---------- | ------ | ------------------------------ |
| `group_by` | string | `hour`, `day`, `week`, `month` |

### Ejemplo

```http
GET /metrics/duration?from=2026-04-01&to=2026-04-20&group_by=day
```

### Respuesta

```json
{
  "metric": "duration",
  "unit": "minutes",
  "group_by": "day",
  "data": [
    {
      "date": "2026-04-20",
      "total_minutes": 386.4,
      "avg_minutes": 2.7,
      "items": 143
    }
  ]
}
```

---

## GET /metrics/source-distribution

Devuelve la distribución de noticias por fuente.

### Filtros

Acepta filtros comunes y además:

| Filtro     | Tipo   | Valores                      |
| ---------- | ------ | ---------------------------- |
| `group_by` | string | `source_name`, `source_type` |

### Ejemplo

```http
GET /metrics/source-distribution?from=2026-04-01&group_by=source_name
```

### Respuesta

```json
{
  "metric": "source_distribution",
  "group_by": "source_name",
  "data": [
    {
      "source_name": "esRadio",
      "count": 420,
      "total_minutes": 812.5
    },
    {
      "source_name": "COPE",
      "count": 310,
      "total_minutes": 621.2
    }
  ]
}
```

---

## GET /metrics/entity-ranking

Devuelve ranking de entidades nombradas extraídas del campo `nlp_pipeline`.

### Filtros

Acepta filtros comunes y además:

| Filtro        | Tipo   | Valores                     |
| ------------- | ------ | --------------------------- |
| `entity_type` | string | `PER`, `LOC`, `ORG`, `MISC` |
| `limit`       | int    | Número máximo de entidades  |

### Ejemplo

```http
GET /metrics/entity-ranking?entity_type=ORG&limit=20
```

### Respuesta

```json
{
  "metric": "entity_ranking",
  "entity_type": "ORG",
  "data": [
    {
      "entity": "Ultra",
      "mentions": 32,
      "records": 18
    },
    {
      "entity": "Nutra",
      "mentions": 21,
      "records": 15
    }
  ]
}
```

---

## GET /metrics/keyword-frequency

Devuelve las palabras más frecuentes encontradas en el campo `content`.

### Filtros

Acepta filtros comunes y además:

| Filtro              | Tipo | Descripción                |
| ------------------- | ---- | -------------------------- |
| `limit`             | int  | Número máximo de palabras  |
| `min_length`        | int  | Longitud mínima de palabra |
| `exclude_stopwords` | bool | Excluir palabras comunes   |

### Ejemplo

```http
GET /metrics/keyword-frequency?from=2026-04-01&limit=20&min_length=4&exclude_stopwords=true
```

### Respuesta

```json
{
  "metric": "keyword_frequency",
  "language": "es",
  "data": [
    {
      "keyword": "protestas",
      "count": 56,
      "records": 41
    },
    {
      "keyword": "subvenciones",
      "count": 34,
      "records": 22
    }
  ]
}
```

---

## GET /alerts

Devuelve alertas calculadas a partir de reglas simples.

Ejemplos de reglas:

* Aparición frecuente de palabras como `crisis`, `protesta`, `bloqueo`, `subvención`, `manifestación`.
* Aumento alto de volumen en una fuente.
* Muchas menciones de una misma entidad.

### Filtros

Acepta filtros comunes.

### Ejemplo

```http
GET /alerts?from=2026-04-20&to=2026-04-21
```

### Respuesta

```json
{
  "data": [
    {
      "id": "alert_001",
      "type": "keyword_match",
      "severity": "medium",
      "title": "Aumento de menciones sobre subvenciones",
      "description": "El término 'subvenciones' aparece varias veces en el periodo seleccionado.",
      "created_at": "2026-04-20T18:00:00Z",
      "related_filters": {
        "keyword": "subvenciones",
        "source_type": "Radio"
      }
    }
  ]
}
```

---

# Diseño recomendado

La API debe estar separada de la visualización.

La visualización no debería depender de consultas SQL ni de la estructura interna exacta de la base de datos. Solo debería consumir endpoints estables como:

```http
GET /metrics/volume
GET /metrics/duration
GET /metrics/source-distribution
GET /metrics/entity-ranking
GET /metrics/keyword-frequency
GET /alerts
```

De esta forma, si más adelante cambia el dashboard, se puede reutilizar la misma API.

---

# Ejemplo de servicio en docker-compose

```yaml
news_api:
  build: ./4_api
  container_name: news_api
  environment:
    POSTGRES_HOST: newsdb
    POSTGRES_PORT: 5432
    POSTGRES_DB: newsdb
    POSTGRES_USER: myuser
    POSTGRES_PASSWORD: mypassword
  ports:
    - "8000:8000"
  depends_on:
    newsdb:
      condition: service_healthy
  networks:
    - compose_net
```



## 1º) Prompt para tu agente

```text
Quiero que programes una API REST en Python usando FastAPI para consultar métricas de noticias almacenadas en una base de datos PostgreSQL.

Contexto:
La API se ejecutará dentro de un contenedor Docker dentro de un docker-compose.
La base de datos PostgreSQL ya existe en el mismo compose con este servicio:

service name: newsdb
database: newsdb
user: myuser
password: mypassword
host: newsdb
port: 5432

La API debe conectarse a Postgres usando variables de entorno, no valores hardcodeados.

Variables esperadas:
POSTGRES_HOST=newsdb
POSTGRES_PORT=5432
POSTGRES_DB=newsdb
POSTGRES_USER=myuser
POSTGRES_PASSWORD=mypassword

Requisitos técnicos:
- Usar Python 3.11 o superior.
- Usar FastAPI.
- Usar uvicorn como servidor.
- Usar SQLAlchemy o psycopg para acceder a PostgreSQL.
- Separar el código en una estructura limpia:
  - app/main.py
  - app/db.py
  - app/models.py o app/schemas.py
  - app/routers/
  - app/services/
- Crear Dockerfile para la API.
- Crear requirements.txt.
- La API debe escuchar en 0.0.0.0:8000.
- Añadir CORS básico para permitir acceso desde un frontend web.
- Añadir endpoint /health.
- El código debe estar preparado para ejecutarse dentro del docker-compose usando la red compose_net.
- No debe acceder directamente a localhost para conectar con Postgres. Debe usar el hostname newsdb.

La tabla de noticias ya existe en Postgres. Asume que se llama news, pero deja el nombre configurable con una constante o variable si es posible.

Campos disponibles en la tabla:
- id
- source_url
- airflow_dag_id
- extracted_at
- airflow_run_id
- connector_id
- connector_name
- source_name
- source_type
- language
- country
- source_tags
- content
- other
- nlp_pipeline

Los campos other y nlp_pipeline pueden ser JSONB. En other existe duration. En nlp_pipeline existe una estructura parecida a:
{
  "entities": {
    "PER": ["Persona 1"],
    "LOC": ["Madrid"],
    "ORG": ["Empresa"],
    "MISC": ["Otro término"]
  }
}

Endpoints que quiero:

1. GET /health
Devuelve estado de la API.

2. GET /records
Devuelve registros individuales paginados.
Filtros:
- from
- to
- source_type
- source_name
- country
- language
- connector_id
- limit
- offset

3. GET /metrics/volume
Devuelve número de noticias agrupadas por tiempo.
Filtros:
- from
- to
- source_type
- source_name
- country
- language
- connector_id
- group_by: hour, day, week, month

4. GET /metrics/duration
Devuelve duración total y media agrupada por tiempo.
La duración sale de other->>'duration'.
Filtros:
- from
- to
- source_type
- source_name
- country
- language
- connector_id
- group_by: hour, day, week, month

5. GET /metrics/source-distribution
Devuelve distribución por fuente.
Filtros:
- from
- to
- source_type
- source_name
- country
- language
- connector_id
- group_by: source_name o source_type

6. GET /metrics/entity-ranking
Devuelve ranking de entidades extraídas desde nlp_pipeline.
Filtros:
- from
- to
- source_type
- source_name
- country
- language
- connector_id
- entity_type: PER, LOC, ORG, MISC
- limit

Debe devolver:
- entity
- mentions
- records

7. GET /metrics/keyword-frequency
Devuelve palabras más frecuentes del campo content.
Para prototipo puede hacerse en Python leyendo los registros filtrados.
Filtros:
- from
- to
- source_type
- source_name
- country
- language
- connector_id
- limit
- min_length
- exclude_stopwords

8. GET /alerts
Devuelve alertas simples calculadas a partir de reglas básicas.
Para prototipo implementar al menos:
- keyword_spike o keyword_match basado en palabras como crisis, protesta, bloqueo, subvención, manifestación.
- source_volume_spike si una fuente tiene muchos registros.
Filtros:
- from
- to
- source_type
- source_name
- country
- language
- connector_id

Requisitos de diseño:
- Crear una función reutilizable para aplicar filtros comunes a las queries.
- Validar parámetros con Pydantic/FastAPI Query.
- Devolver JSON limpio y estable.
- Manejar errores de conexión a la base de datos.
- Usar respuestas consistentes:
  {
    "metric": "...",
    "filters": {...},
    "data": [...]
  }

También quiero que generes:
- Dockerfile
- requirements.txt
- ejemplo de servicio para añadir al docker-compose
- README corto explicando cómo levantar la API

Ejemplo de servicio docker-compose esperado:

news_api:
  build: ./4_api
  container_name: news_api
  environment:
    POSTGRES_HOST: newsdb
    POSTGRES_PORT: 5432
    POSTGRES_DB: newsdb
    POSTGRES_USER: myuser
    POSTGRES_PASSWORD: mypassword
  ports:
    - "8000:8000"
  depends_on:
    newsdb:
      condition: service_healthy
  networks:
    - compose_net
```

