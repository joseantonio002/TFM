from datetime import datetime
from airflow import DAG
from airflow.providers.docker.operators.docker import DockerOperator
from docker.types import Mount
import os
from datetime import datetime
import pendulum

local_tz = pendulum.timezone("Europe/Madrid")

with DAG(
  dag_id='esRadio_esnoticia',
  start_date=datetime(2024, 1, 1).replace(tzinfo=local_tz),
  schedule='0 14 * * 1-5',
  catchup=False,
) as dag:

  run_connector = DockerOperator(
    task_id='esRadio_esnoticia_task',
    image='connector-tv-radio-image:latest',
    api_version="auto",
    auto_remove="force",
    docker_url="unix://var/run/docker.sock",
    network_mode="compose_net",
    mount_tmp_dir=False,
    mounts=[
      Mount(source="raw", target="/outputs/raw", type="volume"),
      Mount(source="common", target="/outputs/common", type="volume"),
    ],
    command=['-i',
 'https://server9.emitironline.com:8822/',
 '-t',
 '60',
 '-m',
 'base',
 '-news_length',
 'medium',
 '-nt',
 '2'],
    environment={'AIRFLOW_DAG_ID': 'esRadio_esnoticia',
 'EXTRACTED_AT': '{{ ti.start_date }}',
 'AIRFLOW_RUN_ID': '{{ run_id }}',
 'CONNECTOR_ID': 'TV/RadioES',
 'CONNECTOR_NAME': 'TV/RadioES',
 'SOURCE_NAME': 'esRadio',
 'SOURCE_TYPE': 'Radio',
 'LANGUAGE': 'es',
 'COUNTRY': 'ES',
 'SOURCE_TAGS': '["news", "radio"]'},
  )

  pipeline_nlp = DockerOperator(
    task_id="pipeline_nlp",
    image="pipeline_nlp:latest",
    api_version="auto",
    auto_remove="force",
    docker_url="unix://var/run/docker.sock",
    network_mode="compose_net",
    mount_tmp_dir=False,
    mounts=[
      Mount(source="common", target="/common", type="volume"),
      Mount(source="common_nlp", target="/outputs_nlp_pipeline", type="volume")
    ],
    environment={'AIRFLOW_DAG_ID': 'esRadio_esnoticia',
 'EXTRACTED_AT': '{{ ti.start_date }}',
 'AIRFLOW_RUN_ID': '{{ run_id }}',
 'CONNECTOR_ID': 'TV/RadioES',
 'CONNECTOR_NAME': 'TV/RadioES',
 'SOURCE_NAME': 'esRadio',
 'SOURCE_TYPE': 'Radio',
 'LANGUAGE': 'es',
 'COUNTRY': 'ES',
 'SOURCE_TAGS': '["news", "radio"]'}
  )

  insert_into_db = DockerOperator(
    task_id="insert_into_db",
    image="insert_into_db:latest",
    api_version="auto",
    auto_remove="force",
    docker_url="unix://var/run/docker.sock",
    network_mode="compose_net",
    mount_tmp_dir=False,
    mounts=[
      Mount(source="common_nlp", target="/common_nlp", type="volume")
    ],
    environment={**{'AIRFLOW_DAG_ID': 'esRadio_esnoticia',
 'EXTRACTED_AT': '{{ ti.start_date }}',
 'AIRFLOW_RUN_ID': '{{ run_id }}',
 'CONNECTOR_ID': 'TV/RadioES',
 'CONNECTOR_NAME': 'TV/RadioES',
 'SOURCE_NAME': 'esRadio',
 'SOURCE_TYPE': 'Radio',
 'LANGUAGE': 'es',
 'COUNTRY': 'ES',
 'SOURCE_TAGS': '["news", "radio"]'},
      "POSTGRES_USER": os.getenv("POSTGRES_USER"),
      "POSTGRES_PASSWORD": os.getenv("POSTGRES_PASSWORD"),
      "POSTGRES_DB": os.getenv("POSTGRES_DB"),
      "NEWSDB_CONTAINER_NAME": os.getenv("NEWSDB_CONTAINER_NAME"),
  }
  )

  run_connector >> pipeline_nlp >> insert_into_db
