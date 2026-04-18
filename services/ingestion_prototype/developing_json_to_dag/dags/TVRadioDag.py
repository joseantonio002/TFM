import datetime

from airflow import DAG
from airflow.providers.docker.operators.docker import DockerOperator
from docker.types import Mount

with DAG(
  dag_id='TVRadioDag',
  start_date=datetime.datetime(2026, 4, 18, 21, 8, 30),
  schedule='0 0 * * *',
  catchup=False,
) as dag:
  run_connector = DockerOperator(
    task_id='tv_radio_task',
    image='connector-tv-radio-image:latest',
    api_version="auto",
    auto_remove="force",
    docker_url="unix://var/run/docker.sock",
    network_mode="bridge",
    mounts=[
      Mount(source="raw", target="/outputs/raw", type="volume"),
      Mount(source="common", target="/outputs/common", type="volume"),
    ],
    command=['-i',
 'https://d32rw80ytx9uxs.cloudfront.net/v1/master/3722c60a815c199d9c0ef36c5b73da68a62b09d1/cc-vlldndmow4yre/24HES.m3u8',
 'https://amg01821-lovetv-amg01821c27-lg-es-6726.playouts.now.amagi.tv/playlist/amg01821-lovetvfast-lovenews-lges/playlist.m3u8',
 'https://dispatcher.rndfnk.com/crtve/rne5/mur/mp3/high',
 'https://atres-live.ondacero.es/live/ondacero/bitrate_1.m3u8',
 'https://rtvelivestream.rtve.es/rne_r1_main.m3u8',
 'https://server9.emitironline.com:8822/',
 'https://crmlive.redctnet.es/liveedge/orm/orm/playlist.m3u8',
 'https://9laloma.tv/live.m3u8',
 '-t',
 '2',
 '-sw',
 '10'],
    environment={'AIRFLOW_DAG_ID': 'TVRadioDag',
 'EXTRACTED_AT': '{{ ts }}',
 'CONNECTOR_ID': 'TV/RadioES',
 'CONNECTOR_NAME': 'TV/RadioES',
 'SOURCE_NAME': '24 horas::Actualidad 360::RNE Radio 5 Todo Noticias (Murcia)::Onda '
                'Cero (España)::RNE Radio Nacional (General)::esRadio::Onda Regional '
                'de Murcia::9 La Loma TV',
 'SOURCE_TYPE': 'TV::TV::Radio::Radio::Radio::Radio::Radio::TV',
 'LANGUAGE': 'es::es::es::es::es::es::es::es',
 'COUNTRY': 'ES::ES::ES::ES::ES::ES::ES::ES',
 'SOURCE_TAGS': '["news", "television"]::["news", "television"]::["news", "radio", '
                '"murcia"]::["news", "radio"]::["public_radio", "news"]::["news", '
                '"radio"]::["regional_news", "radio", "murcia"]::["local_news", '
                '"television"]'},
  )
