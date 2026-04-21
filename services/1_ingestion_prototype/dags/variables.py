from datetime import datetime
import json
import pprint

from airflow import DAG
from airflow.operators.python import PythonOperator


def print_airflow_context(**context):
    print("\n" + "=" * 80)
    print("FULL CONTEXT KEYS")
    print("=" * 80)
    print(sorted(context.keys()))

    print("\n" + "=" * 80)
    print("SELECTED VARIABLES")
    print("=" * 80)

    interesting = {
        "dag": context.get("dag"),
        "task": context.get("task"),
        "ti": context.get("ti"),
        "dag_run": context.get("dag_run"),
        "logical_date": context.get("logical_date"),
        "ds": context.get("ds"),
        "ds_nodash": context.get("ds_nodash"),
        "ts": context.get("ts"),
        "ts_nodash": context.get("ts_nodash"),
        "ts_nodash_with_tz": context.get("ts_nodash_with_tz"),
        "run_id": context.get("run_id"),
        "data_interval_start": context.get("data_interval_start"),
        "data_interval_end": context.get("data_interval_end"),
        "params": context.get("params"),
        "var": context.get("var"),
        "conn": context.get("conn"),
    }

    for key, value in interesting.items():
        print(f"{key}: {value}")

    print("\n" + "=" * 80)
    print("OBJECT ATTRIBUTES")
    print("=" * 80)

    dag = context.get("dag")
    task = context.get("task")
    ti = context.get("ti")
    dag_run = context.get("dag_run")

    attrs = {
        "dag.dag_id": getattr(dag, "dag_id", None),
        "task.task_id": getattr(task, "task_id", None),
        "ti.task_id": getattr(ti, "task_id", None),
        "ti.run_id": getattr(ti, "run_id", None),
        "ti.try_number": getattr(ti, "try_number", None),
        "ti.start_date": getattr(ti, "start_date", None),
        "ti.end_date": getattr(ti, "end_date", None),
        "ti.duration": getattr(ti, "duration", None),
        "ti.hostname": getattr(ti, "hostname", None),
        "dag_run.run_id": getattr(dag_run, "run_id", None),
        "dag_run.state": getattr(dag_run, "state", None),
        "dag_run.queued_at": getattr(dag_run, "queued_at", None),
        "dag_run.start_date": getattr(dag_run, "start_date", None),
        "dag_run.end_date": getattr(dag_run, "end_date", None),
        "dag_run.logical_date": getattr(dag_run, "logical_date", None),
        "dag_run.data_interval_start": getattr(dag_run, "data_interval_start", None),
        "dag_run.data_interval_end": getattr(dag_run, "data_interval_end", None),
    }

    for key, value in attrs.items():
        print(f"{key}: {value}")

    print("\n" + "=" * 80)
    print("SAFE JSON-LIKE SNAPSHOT")
    print("=" * 80)

    snapshot = {
        "dag_id": getattr(dag, "dag_id", None),
        "task_id": getattr(task, "task_id", None),
        "run_id": context.get("run_id"),
        "logical_date": str(context.get("logical_date")),
        "ts": context.get("ts"),
        "data_interval_start": str(context.get("data_interval_start")),
        "data_interval_end": str(context.get("data_interval_end")),
        "ti_start_date": str(getattr(ti, "start_date", None)),
        "dag_run_queued_at": str(getattr(dag_run, "queued_at", None)),
        "dag_run_start_date": str(getattr(dag_run, "start_date", None)),
    }

    print(json.dumps(snapshot, indent=2, ensure_ascii=False))

    print("\n" + "=" * 80)
    print("RAW CONTEXT PRETTY PRINT")
    print("=" * 80)
    pprint.pprint(context)


with DAG(
    dag_id="debug_airflow_context",
    start_date=datetime(2026, 4, 18),
    schedule=None,
    catchup=False,
) as dag:

    debug_context = PythonOperator(
        task_id="debug_context",
        python_callable=print_airflow_context,
    )