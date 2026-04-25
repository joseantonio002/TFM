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
- `source_name`: filtra por nombre de fuente
- `country`: filtra por pais
- `language`: filtra por idioma
- `connector_id`: filtra por conector

Ejemplo:

```text
?from=2026-04-20T00:00:00Z&to=2026-04-25T23:59:59Z&language=es&country=ES
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

## `GET /metrics/keyword-frequency`

Devuelve las palabras mas frecuentes encontradas en `content`. Este endpoint calcula la frecuencia en Python a partir de los registros filtrados.

### Parametros

- Filtros comunes
- `limit`: numero maximo de palabras devueltas. Rango `1-1000`. Por defecto `20`
- `min_length`: longitud minima de palabra. Rango `1-100`. Por defecto `4`
- `exclude_stopwords`: si vale `true`, excluye stopwords comunes en espanol. Por defecto `true`

### Significado de los campos de salida

- `keyword`: palabra detectada
- `frequency`: numero total de apariciones
- `records`: numero de registros distintos donde aparece

### Ejemplo

```http
GET /metrics/keyword-frequency?language=es&limit=10&min_length=5&exclude_stopwords=true
```

### Respuesta

```json
{
  "metric": "keyword-frequency",
  "filters": {
    "language": "es",
    "limit": 10,
    "min_length": 5,
    "exclude_stopwords": true
  },
  "data": [
    {
      "keyword": "guerra",
      "frequency": 14,
      "records": 9
    },
    {
      "keyword": "mexico",
      "frequency": 11,
      "records": 7
    }
  ]
}
```

## Errores esperables

- `422 Unprocessable Entity`: parametro invalido, por ejemplo un `group_by` no permitido o un `fields` con columnas no soportadas
- `503 Service Unavailable`: error de conexion con PostgreSQL

## Notas de uso

- Todos los resultados se devuelven en JSON.
- Los registros de `/records` se ordenan por `extracted_at DESC`.
- Las metricas temporales usan `DATE_TRUNC` sobre `extracted_at`.
- Si no se informa `NEWS_TABLE_NAME`, la API consulta la tabla `news`.
