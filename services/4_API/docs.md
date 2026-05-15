# API REST de metricas de noticias

Esta API expone endpoints para consultar registros individuales y metricas calculadas sobre la tabla `news` en PostgreSQL.

Base URL por defecto:

```text
http://localhost:8000
```

Formato general de respuesta:

```json
{
  "metric": "nombre-metrica",
  "filters": {},
  "data": []
}
```

## Filtros comunes

Los siguientes filtros estan disponibles en casi todos los endpoints:

- `from`: fecha/hora inicial en formato ISO 8601
- `to`: fecha/hora final en formato ISO 8601
- `source_type`: filtra por tipo de fuente
- `source_name`: filtra por nombre de fuente. Puede repetirse para consultar varias fuentes
- `country`: filtra por pais
- `language`: filtra por idioma
- `connector_id`: filtra por conector

Ejemplo:

```text
?from=2026-04-20T00:00:00Z&to=2026-04-25T23:59:59Z&source_name=24%20horas&source_name=RNE
```

## `GET /health`

Comprueba que la API esta levantada y que puede conectarse a PostgreSQL.

### Parametros

No tiene parametros.

### Ejemplo

```http
GET /health
```

### Respuesta

```json
{
  "metric": "health",
  "filters": {},
  "data": [
    {
      "status": "ok"
    }
  ]
}
```

## `GET /records`

Devuelve registros individuales paginados de la tabla `news`.

### Parametros

- Filtros comunes
- `limit`: numero maximo de resultados. Rango `1-1000`. Por defecto `100`
- `offset`: desplazamiento para paginacion. Minimo `0`. Por defecto `0`
- `fields`: lista de columnas separadas por comas para limitar los campos devueltos

### Campos permitidos en `fields`

- `id`
- `source_url`
- `airflow_dag_id`
- `extracted_at`
- `airflow_run_id`
- `connector_id`
- `connector_name`
- `source_name`
- `source_type`
- `language`
- `country`
- `source_tags`
- `content`
- `other`
- `nlp_pipeline`
- `created_at`

### Ejemplo

```http
GET /records?language=es&source_type=Radio&limit=2&fields=id,source_name,extracted_at,other
```

### Respuesta

```json
{
  "metric": "records",
  "filters": {
    "language": "es",
    "source_type": "Radio",
    "limit": 2,
    "offset": 0,
    "fields": ["id", "source_name", "extracted_at", "other"]
  },
  "data": [
    {
      "id": "c00ba563a1c24515874340da7a029b37",
      "source_name": "RNE Radio Nacional (General)",
      "extracted_at": "2026-04-23T10:31:59.799549+00:00",
      "other": {
        "end": 81.0,
        "start": 0.0,
        "duration": 81.0
      }
    }
  ]
}
```

## `GET /sources`

Devuelve las fuentes disponibles para selectores del dashboard.

### Parametros

No tiene parametros.

### Ejemplo

```http
GET /sources
```

### Respuesta

```json
{
  "metric": "sources",
  "filters": {},
  "data": [
    {
      "source_name": "24 horas",
      "records": 120
    },
    {
      "source_name": "RNE",
      "records": 95
    }
  ]
}
```

## `GET /metrics/summary`

Devuelve el numero total de noticias en la tabla y el numero de noticias que cumplen los filtros enviados.

### Parametros

- Filtros comunes

### Ejemplo

```http
GET /metrics/summary?from=2026-05-08T00:00:00Z&to=2026-05-15T23:59:59Z&source_name=24%20horas
```

### Respuesta

```json
{
  "metric": "summary",
  "filters": {
    "from": "2026-05-08T00:00:00+00:00",
    "to": "2026-05-15T23:59:59+00:00",
    "source_name": ["24 horas"]
  },
  "data": [
    {
      "total_records": 3500,
      "filtered_records": 42
    }
  ]
}
```

## `GET /metrics/volume`

Devuelve el numero de registros agrupados por ventana temporal.

### Parametros

- Filtros comunes
- `group_by`: agrupacion temporal. Valores permitidos: `hour`, `day`, `week`, `month`

### Ejemplo

```http
GET /metrics/volume?from=2026-04-20T00:00:00Z&to=2026-04-25T23:59:59Z&group_by=day
```

### Respuesta

```json
{
  "metric": "volume",
  "filters": {
    "from": "2026-04-20T00:00:00+00:00",
    "to": "2026-04-25T23:59:59+00:00",
    "group_by": "day"
  },
  "data": [
    {
      "bucket": "2026-04-23T00:00:00+00:00",
      "records": 15
    }
  ]
}
```

## `GET /metrics/duration`

Devuelve la duracion total y media agrupada por tiempo. La duracion se extrae de `other.duration`.

### Parametros

- Filtros comunes
- `group_by`: agrupacion temporal. Valores permitidos: `hour`, `day`, `week`, `month`

### Ejemplo

```http
GET /metrics/duration?language=es&group_by=day
```

### Respuesta

```json
{
  "metric": "duration",
  "filters": {
    "language": "es",
    "group_by": "day"
  },
  "data": [
    {
      "bucket": "2026-04-23T00:00:00+00:00",
      "total_duration": 1240.0,
      "average_duration": 82.67,
      "records": 15
    }
  ]
}
```

## `GET /metrics/source-distribution`

Devuelve la distribucion de noticias agrupada por fuente.

### Parametros

- Filtros comunes
- `group_by`: campo por el que agrupar. Valores permitidos: `source_name`, `source_type`

### Ejemplo

```http
GET /metrics/source-distribution?country=ES&group_by=source_name
```

### Respuesta

```json
{
  "metric": "source-distribution",
  "filters": {
    "country": "ES",
    "group_by": "source_name"
  },
  "data": [
    {
      "source": "RNE Radio Nacional (General)",
      "records": 20
    },
    {
      "source": "Cadena SER",
      "records": 12
    }
  ]
}
```

## `GET /metrics/entity-ranking`

Devuelve un ranking de entidades extraidas desde `nlp_pipeline.entities`.

### Parametros

- Filtros comunes
- `entity_type`: tipo de entidad. Valores permitidos: `PER`, `LOC`, `ORG`, `MISC`
- `limit`: numero maximo de entidades devueltas. Rango `1-1000`. Por defecto `20`

### Significado de los campos de salida

- `entity`: texto de la entidad
- `mentions`: numero total de menciones
- `records`: numero de registros distintos donde aparece la entidad

### Ejemplo

```http
GET /metrics/entity-ranking?entity_type=LOC&language=es&limit=5
```

### Respuesta

```json
{
  "metric": "entity-ranking",
  "filters": {
    "language": "es",
    "entity_type": "LOC",
    "limit": 5
  },
  "data": [
    {
      "entity": "Espana",
      "mentions": 18,
      "records": 11
    },
    {
      "entity": "Madrid",
      "mentions": 12,
      "records": 8
    }
  ]
}
```

## `GET /metrics/nlp-ranking`

Devuelve el ranking de topics o categorias de amenaza extraidas desde `nlp_pipeline`.

### Parametros

- Filtros comunes
- `dimension`: dimension NLP. Valores permitidos: `topic`, `threat_category`
- `limit`: numero maximo de dimensiones devueltas. Rango `1-20`. Por defecto `10`

Cuando `dimension=topic`, se excluyen los topics presentes en `app/topic_stopwords.txt` antes de calcular el ranking.

### Significado de los campos de salida

- `dimension`: topic o categoria
- `records`: numero de noticias distintas donde aparece

### Ejemplo

```http
GET /metrics/nlp-ranking?dimension=topic&limit=10&source_name=24%20horas
```

### Respuesta

```json
{
  "metric": "nlp-ranking",
  "filters": {
    "source_name": ["24 horas"],
    "dimension": "topic",
    "limit": 10
  },
  "data": [
    {
      "dimension": "submarinistas",
      "records": 5
    },
    {
      "dimension": "rescate",
      "records": 4
    }
  ]
}
```

## `GET /metrics/nlp-source-matrix`

Devuelve una matriz larga de topics o categorias por fuente, con conteos de noticias y sentimiento medio.

### Parametros

- Filtros comunes
- `dimension`: dimension NLP. Valores permitidos: `topic`, `threat_category`
- `limit`: numero maximo de dimensiones usadas. Rango `1-20`. Por defecto `10`

El campo `average_sentiment` se calcula como `positive - negative` usando `nlp_pipeline.sentiment`, por lo que su rango esperado es `-1` a `1`.

### Significado de los campos de salida

- `dimension`: topic o categoria
- `source_name`: fuente
- `records`: numero de noticias distintas
- `average_sentiment`: media de `positive - negative`

### Ejemplo

```http
GET /metrics/nlp-source-matrix?dimension=threat_category&limit=10
```

### Respuesta

```json
{
  "metric": "nlp-source-matrix",
  "filters": {
    "dimension": "threat_category",
    "limit": 10
  },
  "data": [
    {
      "dimension": "general",
      "source_name": "24 horas",
      "records": 18,
      "average_sentiment": -0.12
    },
    {
      "dimension": "politics",
      "source_name": "RNE",
      "records": 10,
      "average_sentiment": 0.08
    }
  ]
}
```

## Errores esperables

- `422 Unprocessable Entity`: parametro invalido, por ejemplo un `group_by`, `dimension` o `fields` no soportado
- `503 Service Unavailable`: error de conexion con PostgreSQL

## Notas de uso

- Todos los resultados se devuelven en JSON.
- Los registros de `/records` se ordenan por `extracted_at DESC`.
- Las metricas temporales usan `DATE_TRUNC` sobre `extracted_at`.
- Las metricas de topics excluyen los valores definidos en `app/topic_stopwords.txt`.
- Si no se informa `NEWS_TABLE_NAME`, la API consulta la tabla `news`.
