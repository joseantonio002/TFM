from datetime import datetime
from airflow import DAG
from airflow.providers.docker.operators.docker import DockerOperator
from docker.types import Mount
import os

with DAG(
  dag_id='TVRadioDag',
  start_date=datetime(2024, 1, 1),
  schedule='0 */2 * * *',
  catchup=False,
) as dag:

  run_connector = DockerOperator(
    task_id='tv_radio_task',
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
 'https://amg01821-lovetv-amg01821c27-lg-es-6726.playouts.now.amagi.tv/playlist/amg01821-lovetvfast-lovenews-lges/playlist.m3u8',
 'https://9laloma.tv/live.m3u8',
 'https://dispatcher.rndfnk.com/crtve/rne5/mur/mp3/high',
 'https://atres-live.ondacero.es/live/ondacero/bitrate_1.m3u8',
 'https://rtvelivestream.rtve.es/rne_r1_main.m3u8',
 'https://server9.emitironline.com:8822/',
 'https://crmlive.redctnet.es/liveedge/orm/orm/playlist.m3u8',
 '-t',
 '60'],
    environment={'AIRFLOW_DAG_ID': 'TVRadioDag',
 'EXTRACTED_AT': '{{ ti.start_date }}',
 'AIRFLOW_RUN_ID': '{{ run_id }}',
 'CONNECTOR_ID': 'TV/RadioES',
 'CONNECTOR_NAME': 'TV/RadioES',
 'SOURCE_NAME': '24 horas::Actualidad 360::9 La Loma TV::RNE Radio 5 Todo Noticias '
                '(Murcia)::Onda Cero (España)::RNE Radio Nacional '
                '(General)::esRadio::Onda Regional de Murcia',
 'SOURCE_TYPE': 'TV::TV::TV::Radio::Radio::Radio::Radio::Radio',
 'LANGUAGE': 'es::es::es::es::es::es::es::es',
 'COUNTRY': 'ES::ES::ES::ES::ES::ES::ES::ES',
 'SOURCE_TAGS': '["news", "television"]::["news", "television"]::["local_news", '
                '"television"]::["news", "radio", "murcia"]::["news", '
                '"radio"]::["public_radio", "news"]::["news", '
                '"radio"]::["regional_news", "radio", "murcia"]'},
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
    environment={'AIRFLOW_DAG_ID': 'TVRadioDag',
 'EXTRACTED_AT': '{{ ti.start_date }}',
 'AIRFLOW_RUN_ID': '{{ run_id }}',
 'CONNECTOR_ID': 'TV/RadioES',
 'CONNECTOR_NAME': 'TV/RadioES',
 'SOURCE_NAME': '24 horas::Actualidad 360::9 La Loma TV::RNE Radio 5 Todo Noticias '
                '(Murcia)::Onda Cero (España)::RNE Radio Nacional '
                '(General)::esRadio::Onda Regional de Murcia',
 'SOURCE_TYPE': 'TV::TV::TV::Radio::Radio::Radio::Radio::Radio',
 'LANGUAGE': 'es::es::es::es::es::es::es::es',
 'COUNTRY': 'ES::ES::ES::ES::ES::ES::ES::ES',
 'SOURCE_TAGS': '["news", "television"]::["news", "television"]::["local_news", '
                '"television"]::["news", "radio", "murcia"]::["news", '
                '"radio"]::["public_radio", "news"]::["news", '
                '"radio"]::["regional_news", "radio", "murcia"]'}
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
    environment={**{'AIRFLOW_DAG_ID': 'TVRadioDag',
 'EXTRACTED_AT': '{{ ti.start_date }}',
 'AIRFLOW_RUN_ID': '{{ run_id }}',
 'CONNECTOR_ID': 'TV/RadioES',
 'CONNECTOR_NAME': 'TV/RadioES',
 'SOURCE_NAME': '24 horas::Actualidad 360::9 La Loma TV::RNE Radio 5 Todo Noticias '
                '(Murcia)::Onda Cero (España)::RNE Radio Nacional '
                '(General)::esRadio::Onda Regional de Murcia',
 'SOURCE_TYPE': 'TV::TV::TV::Radio::Radio::Radio::Radio::Radio',
 'LANGUAGE': 'es::es::es::es::es::es::es::es',
 'COUNTRY': 'ES::ES::ES::ES::ES::ES::ES::ES',
 'SOURCE_TAGS': '["news", "television"]::["news", "television"]::["local_news", '
                '"television"]::["news", "radio", "murcia"]::["news", '
                '"radio"]::["public_radio", "news"]::["news", '
                '"radio"]::["regional_news", "radio", "murcia"]'},
      "POSTGRES_USER": os.getenv("POSTGRES_USER"),
      "POSTGRES_PASSWORD": os.getenv("POSTGRES_PASSWORD"),
      "POSTGRES_DB": os.getenv("POSTGRES_DB"),
      "NEWSDB_CONTAINER_NAME": os.getenv("NEWSDB_CONTAINER_NAME"),
  }
  )

  run_connector >> pipeline_nlp >> insert_into_db
