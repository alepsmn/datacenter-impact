FROM apache/airflow:2.9.2-python3.12

USER airflow

RUN pip install --no-cache-dir \
    dbt-bigquery==1.11.1 \
    apache-airflow-providers-google==10.20.0 \
    openpyxl \
    python-dotenv
