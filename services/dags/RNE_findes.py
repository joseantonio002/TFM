from datetime import datetime
from airflow import DAG
from airflow.providers.docker.operators.docker import DockerOperator
from docker.types import Mount
import os
from datetime import datetime
import pendulum

local_tz = pendulum.timezone("Europe/Madrid")

with DAG(
  dag_id='RNE_findes',
  start_date=datetime(2024, 1, 1).replace(tzinfo=local_tz),
  schedule='0 14,23 * * 0,6',
  catchup=False,
) as dag:

  run_connector = DockerOperator(
    task_id='RNE_findes_task',
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
 'https://dispatcher.rndfnk.com/crtve/rne5/mur/mp3/high',
 '-t',
 '30',
 '-m',
 'base',
 '-news_length',
 'short',
 '-nt',
 '2'],
    environment={'AIRFLOW_DAG_ID': 'RNE_findes',
 'EXTRACTED_AT': '{{ ti.start_date }}',
 'AIRFLOW_RUN_ID': '{{ run_id }}',
 'CONNECTOR_ID': 'TV/RadioES',
 'CONNECTOR_NAME': 'TV/RadioES',
 'SOURCE_NAME': 'RNE Radio 5 Todo Noticias (Murcia)',
 'SOURCE_TYPE': 'Radio',
 'LANGUAGE': 'es',
 'COUNTRY': 'ES',
 'SOURCE_TAGS': '["news", "radio", "murcia"]'},
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
    environment={'AIRFLOW_DAG_ID': 'RNE_findes',
 'EXTRACTED_AT': '{{ ti.start_date }}',
 'AIRFLOW_RUN_ID': '{{ run_id }}',
 'CONNECTOR_ID': 'TV/RadioES',
 'CONNECTOR_NAME': 'TV/RadioES',
 'SOURCE_NAME': 'RNE Radio 5 Todo Noticias (Murcia)',
 'SOURCE_TYPE': 'Radio',
 'LANGUAGE': 'es',
 'COUNTRY': 'ES',
 'SOURCE_TAGS': '["news", "radio", "murcia"]'}
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
    environment={**{'AIRFLOW_DAG_ID': 'RNE_findes',
 'EXTRACTED_AT': '{{ ti.start_date }}',
 'AIRFLOW_RUN_ID': '{{ run_id }}',
 'CONNECTOR_ID': 'TV/RadioES',
 'CONNECTOR_NAME': 'TV/RadioES',
 'SOURCE_NAME': 'RNE Radio 5 Todo Noticias (Murcia)',
 'SOURCE_TYPE': 'Radio',
 'LANGUAGE': 'es',
 'COUNTRY': 'ES',
 'SOURCE_TAGS': '["news", "radio", "murcia"]'},
      "POSTGRES_USER": os.getenv("POSTGRES_USER"),
      "POSTGRES_PASSWORD": os.getenv("POSTGRES_PASSWORD"),
      "POSTGRES_DB": os.getenv("POSTGRES_DB"),
      "NEWSDB_CONTAINER_NAME": os.getenv("NEWSDB_CONTAINER_NAME"),
  }
  )

  run_connector >> pipeline_nlp >> insert_into_db
