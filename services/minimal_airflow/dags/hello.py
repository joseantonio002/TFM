from datetime import datetime
from pandas import DataFrame

from airflow.sdk import dag, task


@dag(
    dag_id='hello_world_taskflow',
    start_date=datetime(2024, 1, 1),
    schedule='@daily',
    catchup=False,
    tags=['example'],
)
def hello_world_taskflow():
    @task
    def say_hello():
        print('Hello World')

    say_hello()


dag = hello_world_taskflow()
