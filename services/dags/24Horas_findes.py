from datetime import datetime
from airflow import DAG
from airflow.providers.docker.operators.docker import DockerOperator
from docker.types import Mount
import os

with DAG(
  dag_id='24Horas_findes',
  start_date=datetime(2024, 1, 1),
  schedule='0 6,10 * * 0,6',
  catchup=False,
) as dag:

  run_connector = DockerOperator(
    task_id='24Horas_findes_task',
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
 'https://ztnr.rtve.es/ztnr/1694255.m3u8',
 '-t',
 '30',
 '-m',
 'tiny',
 '-news_length',
 'short',
 '-nt',
 '2'],
    environment={'AIRFLOW_DAG_ID': '24Horas_findes',
 'EXTRACTED_AT': '{{ ti.start_date }}',
 'AIRFLOW_RUN_ID': '{{ run_id }}',
 'CONNECTOR_ID': 'TV/RadioES',
 'CONNECTOR_NAME': 'TV/RadioES',
 'SOURCE_NAME': '24 horas',
 'SOURCE_TYPE': 'TV',
 'LANGUAGE': 'es',
 'COUNTRY': 'ES',
 'SOURCE_TAGS': '["news", "television"]'},
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
    environment={'AIRFLOW_DAG_ID': '24Horas_findes',
 'EXTRACTED_AT': '{{ ti.start_date }}',
 'AIRFLOW_RUN_ID': '{{ run_id }}',
 'CONNECTOR_ID': 'TV/RadioES',
 'CONNECTOR_NAME': 'TV/RadioES',
 'SOURCE_NAME': '24 horas',
 'SOURCE_TYPE': 'TV',
 'LANGUAGE': 'es',
 'COUNTRY': 'ES',
 'SOURCE_TAGS': '["news", "television"]'}
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
    environment={**{'AIRFLOW_DAG_ID': '24Horas_findes',
 'EXTRACTED_AT': '{{ ti.start_date }}',
 'AIRFLOW_RUN_ID': '{{ run_id }}',
 'CONNECTOR_ID': 'TV/RadioES',
 'CONNECTOR_NAME': 'TV/RadioES',
 'SOURCE_NAME': '24 horas',
 'SOURCE_TYPE': 'TV',
 'LANGUAGE': 'es',
 'COUNTRY': 'ES',
 'SOURCE_TAGS': '["news", "television"]'},
      "POSTGRES_USER": os.getenv("POSTGRES_USER"),
      "POSTGRES_PASSWORD": os.getenv("POSTGRES_PASSWORD"),
      "POSTGRES_DB": os.getenv("POSTGRES_DB"),
      "NEWSDB_CONTAINER_NAME": os.getenv("NEWSDB_CONTAINER_NAME"),
  }
  )

  run_connector >> pipeline_nlp >> insert_into_db
