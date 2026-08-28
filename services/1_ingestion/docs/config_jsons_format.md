# Program JSON Files

The program will use the following JSON files:

* `seed_list.json` → list of data sources.
* `connectors.json` → list of connectors and their associated image.
* `dags.json` → each entry represents an Airflow DAG.

---

## `dags.json`

Each entry represents an Airflow DAG.

Within each DAG:

* Parameters such as `schedule` and other configuration values are obtained from their corresponding entry in this file.

### Source of truth

The sources of truth must always be respected:

* Sources must be defined in `seed_list.json`.
* Connectors must be defined in `connectors.json`.
* DAGs must only reference that information.

---

# `seed_list.json` Schema

The main key corresponds to the seed ID.

```json
{
  "tv_24h_es": {
    "source_name": "24 Horas",
    "source_type": "tv",
    "source_url": "https://www.rtve.es/play/videos/telediario-24-horas/",
    "lang": "es",
    "country": "ES",
    "is_active": true,
    "default_connector_id": "tv_radio_es",
    "description": "RTVE news program",
    "source_tags": [
      "news",
      "television",
      "spain"
    ]
  }
}
```

---

# `connectors.json` Schema

```json
{
  "connector_id": {
    "description": "Explains how the connector works, which parameters it accepts, and any relevant details. It must not be a short description.",
    "connector_name": "TV/RadioES",
    "docker_image": "TV_Radio_image",
    "accepted_sources": [
      "24horas",
      "actualidad"
    ],
    "accepted_source_types": [
      "tv",
      "radio"
    ],
    "default_sources": [seed_id1, seed_id2],
    "accepted_params": {
      "example": "Example parameter that performs X. Possible values: [value1, value2]",
      "example2": "Example parameter that performs Y. Integer type"
    },
    "is_active": true
  }
}
```

## Optional fields

* `accepted_sources`
* `accepted_source_types`
* `accepted_params`

## Required fields

* `default_sources`

### `default_sources` behavior

It must contain one or more seeds that the connector will read by default.

If sources are later specified in `dags.json`, they **override** `default_sources`.

---

# `dags.json` Schema

```json
{
  "dag_id": {
    "connector_id": "connector ID",
    "task_id": "Airflow task ID",
    "schedule": "task schedule in Airflow format",
    "start_date": "point from which Airflow starts determining when to create the first DAG Run; use the same string that would be specified directly in the DAG",
    "seed_ids": [seed_id1, seed_id2],
    "params": {
      "parameter1": "value",
      "parameter2": "value"
    }
  }
}
```

> Note: `dags.json` does not have an `is_active` field because this is managed through the Airflow UI.

## Field descriptions

* `connector_id` → used to obtain the corresponding connector image.
* `task_id` → task identifier in Airflow.
* `schedule` → execution schedule in Airflow format.
* `seed_ids` *(optional)* → list of seeds that will be passed as parameters. The `seed_id` is stored, and the corresponding URL is later retrieved from `seed_list.json -> source_url`.
* `params` *(optional)* → parameters sent when creating the container.

---

## `seed_ids` behavior

If `seed_ids` is defined:

* it overrides the default sources defined in `connectors.json`
* the sources will be validated using:

  * `accepted_sources`
  * `accepted_source_types`

---

# Important Rule

**One or more sources must always be passed as parameters.**

If no source is specified in the DAG, the sources defined in `default_sources` within `connectors.json` will be used automatically.

---





# Ficheros JSON del programa

El programa utilizará los siguientes ficheros JSON:

- `seed_list.json` → lista de las fuentes de datos.
- `connectors.json` → lista de conectores y su imagen asociada.
- `dags.json` → cada entrada representa un DAG de Airflow.

---

## `dags.json`

Cada entrada representa un DAG de Airflow.

Dentro de cada DAG:

- Los parámetros como `schedule` y otros valores de configuración se obtienen desde su entrada correspondiente en este fichero. 

### Fuente de verdad

Se deben respetar siempre las fuentes de verdad:

- Las fuentes deben definirse en `seed_list.json`.
- Los conectores deben definirse en `connectors.json`.
- Los DAGs únicamente deben referenciar esa información.

---

# Esquema de `seed_list.json`

La clave principal corresponde al ID de la seed.

```json
{
  "tv_24h_es": {
    "source_name": "24 Horas",
    "source_type": "tv",
    "source_url": "https://www.rtve.es/play/videos/telediario-24-horas/",
    "lang": "es",
    "country": "ES",
    "is_active": true,
    "default_connector_id": "tv_radio_es",
    "description": "Programa informativo de RTVE",
    "source_tags": [
      "informativos",
      "television",
      "espana"
    ]
  }
}
````

---

# Esquema de `connectors.json`

```json
{
  "connector_id": {
    "description": "Explica cómo funciona el conector, qué parámetros acepta y cualquier detalle relevante. No debe ser una descripción breve.",
    "connector_name": "TV/RadioES",
    "docker_image": "TV_Radio_image",
    "accepted_sources": [
      "24horas",
      "actualidad"
    ],
    "accepted_source_types": [
      "tv",
      "radio"
    ],
    "default_sources": [seed_id1, seed_id2],
    "accepted_params": {
      "example": "Parámetro de ejemplo que hace X. Posibles valores: [value1, value2]",
      "example2": "Parámetro de ejemplo que hace Y. Tipo entero"
    },
    "is_active": true
  }
}
```

## Campos opcionales

* `accepted_sources`
* `accepted_source_types`
* `accepted_params`

## Campos obligatorios

* `default_sources`

### Comportamiento de `default_sources`

Debe contener una o más seeds que el conector leerá por defecto.

Si posteriormente se especifican fuentes en `dags.json`, estas **sobrescriben** `default_sources`.

---

# Esquema de `dags.json`

```json
{
  "dag_id": {
    "connector_id": "id del conector",
    "task_id": "task id en Airflow",
    "schedule": "schedule de la tarea en formato Airflow",
    "start_date": "punto desde el que Airflow empieza a medir cuándo crear el primer DAG Run, poner cadena de texto con lo que se pondría en el propio dag",
    "seed_ids": [seed_id1, seed_id2],
    "params": {
      "parametro1": "valor",
      "parametro2": "valor"
    }
  }
}
```

>Nota: dags.json no tiene campo is_active porque eso se maneja desde la airflow UI

## Descripción de campos

* `connector_id` → se utiliza para obtener la imagen correspondiente del conector.
* `task_id` → identificador de la tarea en Airflow.
* `schedule` → planificación de ejecución en formato Airflow.
* `seed_ids` *(opcional)* → lista de seeds que se pasarán como parámetro. Se guarda el seed_id y en base a eso se extrae posteriormente el enlace especificado en seed_list.json->source_url
* `params` *(opcional)* → parámetros enviados durante la creación del contenedor.



---

## Comportamiento de `seed_ids`

Si se define `seed_ids`:

* sobrescribe las fuentes por defecto definidas en `connectors.json`
* se validará que las fuentes sean correctas usando:

  * `accepted_sources`
  * `accepted_source_types`

---

# Regla importante

**Siempre hay que pasar por parámetro una o varias fuentes.**

Si no se especifica ninguna fuente en el DAG, se utilizarán automáticamente las definidas en `default_sources` dentro de `connectors.json`.
