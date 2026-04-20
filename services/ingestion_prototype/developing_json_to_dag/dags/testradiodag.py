from datetime import datetime
from airflow import DAG
from airflow.providers.docker.operators.docker import DockerOperator
from docker.types import Mount

with DAG(
  dag_id='testradiodag',
  start_date=datetime(2026, 4, 20),
  schedule='0 0 * * *',
  catchup=False,
) as dag:
  run_connector = DockerOperator(
    task_id='test_task2',
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
 'https://atres-live.ondacero.es/live/ondacero/bitrate_1.m3u8',
 'https://rtvelivestream.rtve.es/rne_r1_main.m3u8',
 '-t',
 '60',
 '-sw',
 '5'],
    environment={'AIRFLOW_DAG_ID': 'testradiodag',
 'EXTRACTED_AT': '{{ ts }}',
 'CONNECTOR_ID': 'TestConector',
 'CONNECTOR_NAME': 'Test conector',
 'SOURCE_NAME': 'Onda Cero (España)::RNE Radio Nacional (General)',
 'SOURCE_TYPE': 'Radio::Radio',
 'LANGUAGE': 'es::es',
 'COUNTRY': 'ES::ES',
 'SOURCE_TAGS': '["news", "radio"]::["public_radio", "news"]'},
  )
