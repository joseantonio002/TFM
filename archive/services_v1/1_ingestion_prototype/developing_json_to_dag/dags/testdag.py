from datetime import datetime
from airflow import DAG
from airflow.providers.docker.operators.docker import DockerOperator
from docker.types import Mount

with DAG(
  dag_id='testdag',
  start_date=datetime(2026, 4, 20),
  schedule='0 0 * * *',
  catchup=False,
) as dag:
  run_connector = DockerOperator(
    task_id='test_task',
    image='test_connector:latest',
    api_version="auto",
    auto_remove="force",
    docker_url="unix://var/run/docker.sock",
    network_mode="bridge",
    mounts=[
      Mount(source="raw", target="/outputs/raw", type="volume"),
      Mount(source="common", target="/outputs/common", type="volume"),
    ],
    command=['-i',
 'https://d32rw80ytx9uxs.cloudfront.net/v1/master/3722c60a815c199d9c0ef36c5b73da68a62b09d1/cc-vlldndmow4yre/24HES.m3u8'],
    environment={'AIRFLOW_DAG_ID': 'testdag',
 'EXTRACTED_AT': '{{ ti.start_date }}',
 'AIRFLOW_RUN_ID': '{{ run_id }}',
 'CONNECTOR_ID': 'TestConector',
 'CONNECTOR_NAME': 'Test conector',
 'SOURCE_NAME': '24 horas',
 'SOURCE_TYPE': 'TV',
 'LANGUAGE': 'es',
 'COUNTRY': 'ES',
 'SOURCE_TAGS': '["news", "television"]'},
  )
