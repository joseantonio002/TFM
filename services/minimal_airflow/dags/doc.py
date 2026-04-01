from airflow import DAG
from airflow.providers.docker.operators.docker import DockerOperator
from datetime import datetime

with DAG(
    dag_id="test_docker_hello_world",
    start_date=datetime(2024, 1, 1),
    schedule=None,
    catchup=False,
) as dag:

    run_hello_world = DockerOperator(
        task_id="run_hello_world",
        image="hello-world",              # imagen a ejecutar
        api_version="auto",
        auto_remove="force",                # elimina el contenedor al terminar
        command=None,                    # hello-world ya tiene CMD
        docker_url="unix://var/run/docker.sock",  # conexión al daemon Docker
        network_mode="bridge",
    )