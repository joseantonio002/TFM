Quiero que programes una API REST en Python usando FastAPI para consultar métricas de noticias almacenadas en una base de datos PostgreSQL. Guarda todo lo relacionado con la API (código, entorno de python, Dockerfile...) en @services/4_API

Contexto:
La API se ejecutará dentro de un contenedor Docker dentro de el docker compose @services/docker-compose.yml.
La base de datos PostgreSQL ya existe en el mismo compose con este servicio newsdb:

La API debe conectarse a Postgres usando variables de entorno, dichas variables se van a pasar en el docker compose y son:
POSTGRES_USER
POSTGRES_PASSWORD
POSTGRES_DB
NEWSDB_CONTAINER_NAME


Requisitos técnicos:
- Usar FastAPI.
- Usar uvicorn como servidor.
- Usar SQLAlchemy o psycopg para acceder a PostgreSQL.?????????????
- Crear Dockerfile para la API.
- Crear requirements.txt.
- La API debe escuchar en 0.0.0.0:8000.
- No añadas nada de seguridad, ni CORS ni nada, solamente los endpoints
- Añadir endpoint /health.
- El código debe estar preparado para ejecutarse dentro del docker-compose usando la red compose_net.
- No debe acceder directamente a localhost para conectar con Postgres. Debe usar el hostname.

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

Los campos other y nlp_pipeline son JSONB. En other existe duration. En nlp_pipeline existe una estructura parecida a:
{
  "entities": {
    "PER": ["Persona 1"],
    "LOC": ["Madrid"],
    "ORG": ["Empresa"],
    "MISC": ["Otro término"]
  }
}

En @services/3_database/init/01-schema.sql tienes la definición de la tabla. Te dejo un ejemplo de una fila ya cargada:
```
id             | c00ba563a1c24515874340da7a029b37
source_url     | https://rtvelivestream.rtve.es/rne_r1_main.m3u8
airflow_dag_id | TVRadioDag
extracted_at   | 2026-04-23 10:31:59.799549+00
airflow_run_id | manual__2026-04-23T10:31:58.982470+00:00
connector_id   | TV/RadioES
connector_name | TV/RadioES
source_name    | RNE Radio Nacional (General)
source_type    | Radio
language       | es
country        | ES
source_tags    | ["public_radio", "news"]
content        | Y tibia al izquierdo eso significaría caso de ser rotura mínimo 5 semanas de baja con lo que diría dios a la temporada en cuanto al fútbol club Barcelona y habrá que ver el grado de rotura de esta lesión y sobre todo esperar que no tenga afectado el tendón que eso sería el peor escenario que haría perderse ya el mundial Pues ahí hemos adentro Germán cualquier novedad nos pides paso hasta luego perfecto sola huelgas guerra hay preocupación mundo convulsión pero también hay alguna luz Y es precisamente lo que está pasando la Universidad del Calá España y el español celebrando sus letras el escritor mexicano Gonzalo Velorio Te recibiré el paraninfo de la Universidad del Calá el Cervantes hace su discurso en este instante Con los pies metidos debajo y las patas delanteras de la silla para no caer en la tentación de levantar mi y abandonar la tarea Escribiendo lo que acaso sin yo saberlo ya escribieron otros Mire el mi hermano mayor que me llevaba 22 años los mismos que le llevo yo a mi primo Benito Gonzalo Velorio también una llamada a la Unión entre las letras y España esos lazos que hay entre España y México
other          | {"end": 81.0, "start": 0.0, "duration": 81.0}
nlp_pipeline   | {"entities": {"LOC": ["Universidad del Calá España", "Universidad del Calá", "España", "España", "México"], "ORG": ["Barcelona", "Unión"], "PER": ["Gonzalo Velorio Te", "Cervantes", "Escribiendo", "Mire", "Benito Gonzalo Velorio"], "MISC": ["mundial Pues", "Germán", "Con los pies metidos debajo"]}}
created_at     | 2026-04-23 10:36:22.269841+00
```

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
- fields Filtro único para /records, campos que nos queremos traer

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
- ejemplo de servicio para añadir a @services/docker-compose.yml
- README corto explicando cómo levantar la API
