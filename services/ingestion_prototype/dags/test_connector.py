from airflow import DAG
from airflow.providers.docker.operators.docker import DockerOperator
from docker.types import Mount
from datetime import datetime

with DAG(
    dag_id="testdag",
    start_date=datetime(2024, 1, 1),
    schedule=None,
    catchup=False,
) as dag:

    run_test_connector = DockerOperator(
        task_id="test_task",
        image="test_connector:latest",
        api_version="auto",
        auto_remove="never",
        docker_url="unix://var/run/docker.sock",
        network_mode="bridge",
        mounts=[
            Mount(
                source="raw",
                target="/outputs/raw",
                type="volume",
            ),
            Mount(
                source="common",
                target="/outputs/common",
                type="volume",
            ),
        ],
    )