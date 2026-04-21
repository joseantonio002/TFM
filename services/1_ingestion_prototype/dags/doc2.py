from airflow import DAG
from airflow.providers.docker.operators.docker import DockerOperator
from datetime import datetime

with DAG(
    dag_id="test_docker_runpy2",
    start_date=datetime(2024, 1, 1),
    schedule=None,
    catchup=False,
) as dag:

    run_runpy2 = DockerOperator(
        task_id="run_runpy2",
        image="runpy2",
        api_version="auto",
        auto_remove="never",
        command=["hola mundo"],
        docker_url="unix://var/run/docker.sock",
        network_mode="bridge",
    )