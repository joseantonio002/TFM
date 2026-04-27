# Documentación de conectores

## 1. Outputs

Los outputs deben almacenarse en las siguientes rutas:

- **Outputs raw:** `/outputs/raw`
- **Outputs finales (esquema común):** `/outputs/common`

### Nombre de los JSON en `/outputs/common`

Los archivos deben seguir este formato:

```text
{AIRFLOW_DAG_ID}_{RUN_ID}_{random_id}.json
````

### Nombre de los outputs en `/outputs/raw`

Se deja libertad en el nombre, pero se recomienda incluir al menos los siguientes campos para facilitar su identificación:

```text
{connector_id}_{airflow_dag_id}_{run_id}_{source_name}
```

---

## 2. Enlaces de entrada

Los enlaces de entrada del script deben ir siempre después del parámetro `-i`.

### Ejemplo

```bash
scrapper.py -i http://enlace1 http://enlace2
```

Es obligatorio que el script principal del conector que se ejecutará desde el `Dockerfile` funcione siempre con este parámetro.

Aunque el conector utilice un único enlace fijo, igualmente debe ejecutarse de esta forma:

```bash
scrapper.py -i http://enlace
```

---

## 3. `ENTRYPOINT` en el Dockerfile

La imagen debe ejecutar el script principal del conector **sin ningún parámetro** y debe construirse usando `ENTRYPOINT`, de forma que permita pasar parámetros al crear el contenedor.

### Ejemplo

```dockerfile
ENTRYPOINT ["python", "main.py"]
```

---

## 4. Esquema común

Debe generarse **un JSON por cada noticia recopilada** con los siguientes campos:

```json
{
  "id": "id aleatorio de la noticia",
  "source_url": "https://24horas.com",
  "canonical_url": "https://24horas.com/noticia/123",

  "airflow_dag_id": "dag id de airflow que lanzó el conector",
  "extracted_at": "datetime de cuando se empezó a ejecutar el script",
  "published_at": "datetime de cuando se publicó la noticia",
  "airflow_run_id": "identificador de la ejecución",

  "connector_id": "id del conector usado para extraer la noticia",
  "connector_name": "nombre del conector",

  "source_name": "24 Horas",
  "source_type": "tv",
  "language": "es",
  "country": "ES",
  "source_tags": ["informativos", "television", "espana"],

  "title": "título de la noticia",
  "content": "texto de la noticia"
}
```

### Campos opcionales

* `canonical_url`: incluir solo si `source_url` no es suficiente.
* `published_at`: incluir solo si está disponible.
* `title`: incluir solo si está disponible.

### Información obtenida de la seed list

Los siguientes campos provienen de la seed list:

* `source_name`
* `source_type`
* `language`
* `country`
* `source_tags`

---

## 5. Uso de variables de entorno para completar el esquema común

Los scripts del conector deben obtener las variables externas de Airflow y de la seed list mediante variables de entorno.

Estas variables se dividen en dos tipos:

---

### a) Variables globales

Son comunes para todos los JSON generados por el conector.

Se asignan directamente como pares clave-valor:

| Campo JSON       | Variable de entorno |
| ---------------- | ------------------- |
| `airflow_dag_id` | `AIRFLOW_DAG_ID`    |
| `airflow_run_id` | `AIRFLOW_RUN_ID`    |
| `extracted_at`   | `EXTRACTED_AT`      |
| `connector_id`   | `CONNECTOR_ID`      |
| `connector_name` | `CONNECTOR_NAME`    |

---

### b) Variables dependientes de la fuente

Cuando el conector recibe múltiples fuentes de entrada, cada JSON debe incluir los datos correspondientes a su fuente específica.

Estas variables se proporcionan como listas en formato string separadas por `::`.

### Ejemplo

```bash
SOURCE_NAME="24 HORAS::OndaCero::Radio RNE"
```

Al programar el conector, se asume que el orden de los valores coincide con el orden de las fuentes pasadas como parámetro al script.

Para cada fuente `i`, los campos del JSON se asignan de la siguiente forma:

| Campo JSON    | Variable         |
| ------------- | ---------------- |
| `source_name` | `SOURCE_NAME[i]` |
| `source_type` | `SOURCE_TYPE[i]` |
| `language`    | `LANGUAGE[i]`    |
| `country`     | `COUNTRY[i]`     |
| `source_tags` | `SOURCE_TAGS[i]` |

