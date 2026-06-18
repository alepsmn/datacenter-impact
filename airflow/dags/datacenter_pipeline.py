from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.bash import BashOperator

default_args = {
    'owner': 'airflow',
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

with DAG(
    dag_id='datacenter_pipeline',
    default_args=default_args,
    start_date=datetime(2024, 1, 1),
    schedule_interval='@monthly',
    catchup=False,
) as dag:

    extract_eia = BashOperator(
        task_id='extract_eia',
        bash_command='cd /opt/airflow && python /opt/airflow/scripts/extract_eia.py',
    )

    extract_epri = BashOperator(
        task_id='extract_epri',
        bash_command='cd /opt/airflow && python /opt/airflow/scripts/extract_epri.py',
    )

    upload_gcs = BashOperator(
        task_id='upload_gcs',
        bash_command='cd /opt/airflow && python /opt/airflow/scripts/upload_gcs.py',
    )

    load_bigquery = BashOperator(
        task_id='load_bigquery',
        bash_command='cd /opt/airflow && python /opt/airflow/scripts/load_bigquery.py',
    )

    dbt_run = BashOperator(
        task_id='dbt_run',
        bash_command='dbt run --project-dir /opt/airflow/dbt --profiles-dir /opt/airflow/dbt_profiles',
    )

    dbt_test = BashOperator(
        task_id='dbt_test',
        bash_command='dbt test --project-dir /opt/airflow/dbt --profiles-dir /opt/airflow/dbt_profiles',
    )

    [extract_eia, extract_epri] >> upload_gcs >> load_bigquery >> dbt_run >> dbt_test
