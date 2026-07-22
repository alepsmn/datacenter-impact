"""DAG de orquestación del pipeline ELT datacenter-impact.

Flujo:  [extract_eia, extract_epri] → upload_gcs → load_bigquery → dbt run → dbt test

Decisiones de diseño (ver docs/CI-Y-ORQUESTACION.md):

- **Snapshot completo, no incremental.** Cada ejecución reconstruye el dataset
  entero: la carga a BigQuery usa `WRITE_TRUNCATE`, así que reejecutar deja la
  tabla en el mismo estado en vez de duplicar filas. Es idempotente por diseño,
  que es lo que permite reintentar una tarea sin miedo.
- **Fechas parametrizadas, no hardcodeadas.** La ventana de EIA vive en `params`
  y se inyecta al script como variables de entorno. Se puede lanzar el DAG con
  otra ventana desde la UI ("Trigger DAG w/ config") sin tocar código.
- **BashOperator, a propósito.** Los pasos son procesos independientes (los
  scripts y el CLI de dbt) que corren en la misma imagen. Un `PythonOperator`
  obligaría a importar los scripts dentro del worker de Airflow, acoplando el
  proceso de la orquesta al del pipeline y compartiendo su espacio de memoria.
  El aislamiento por proceso es aquí más honesto y el coste (arrancar un
  intérprete) es despreciable frente a la duración de cada tarea.
"""

from datetime import datetime, timedelta

from airflow.models.param import Param
from airflow.operators.bash import BashOperator

from airflow import DAG

# Rutas dentro del contenedor (montadas por docker-compose.yml).
AIRFLOW_HOME = "/opt/airflow"
SCRIPTS = f"{AIRFLOW_HOME}/scripts"
DBT_PROJECT = f"{AIRFLOW_HOME}/dbt"
DBT_PROFILES = f"{AIRFLOW_HOME}/dbt_profiles"

default_args = {
    "owner": "airflow",
    # Reintentos a nivel tarea: cubren fallos transitorios que el retry interno
    # del script no alcanza (worker reiniciado, credencial que expira, red del
    # contenedor). Son seguros porque cada tarea es idempotente.
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
    # Corta una tarea colgada en vez de dejarla ocupando un slot del pool.
    "execution_timeout": timedelta(minutes=30),
}

with DAG(
    dag_id="datacenter_pipeline",
    description="ELT: EIA + EPRI → GCS → BigQuery → dbt",
    default_args=default_args,
    start_date=datetime(2024, 1, 1),
    schedule="@monthly",
    # Sin catchup: el pipeline es un snapshot del estado actual de las fuentes,
    # no una serie de particiones por fecha. Rellenar el histórico ejecutaría
    # N veces exactamente el mismo trabajo.
    catchup=False,
    max_active_runs=1,
    tags=["elt", "bigquery", "dbt"],
    doc_md=__doc__,
    params={
        "eia_start": Param(
            "2015-01",
            type="string",
            pattern=r"^\d{4}-\d{2}$",
            description="Inicio de la ventana EIA (YYYY-MM)",
        ),
        "eia_end": Param(
            "2024-12",
            type="string",
            pattern=r"^\d{4}-\d{2}$",
            description="Fin de la ventana EIA (YYYY-MM)",
        ),
    },
) as dag:

    extract_eia = BashOperator(
        task_id="extract_eia",
        bash_command=f"cd {AIRFLOW_HOME} && python {SCRIPTS}/extract_eia.py",
        # Los params llegan al script como env vars, que es como config.py los
        # lee. `append_env=True` es imprescindible: sin él, `env` REEMPLAZA el
        # entorno entero y el script se quedaría sin EIA_API_KEY ni credenciales.
        env={
            "EIA_START": "{{ params.eia_start }}",
            "EIA_END": "{{ params.eia_end }}",
        },
        append_env=True,
    )

    extract_epri = BashOperator(
        task_id="extract_epri",
        bash_command=f"cd {AIRFLOW_HOME} && python {SCRIPTS}/extract_epri.py",
    )

    upload_gcs = BashOperator(
        task_id="upload_gcs",
        bash_command=f"cd {AIRFLOW_HOME} && python {SCRIPTS}/upload_gcs.py",
    )

    load_bigquery = BashOperator(
        task_id="load_bigquery",
        bash_command=f"cd {AIRFLOW_HOME} && python {SCRIPTS}/load_bigquery.py",
    )

    dbt_run = BashOperator(
        task_id="dbt_run",
        bash_command=(
            f"dbt run --project-dir {DBT_PROJECT} --profiles-dir {DBT_PROFILES}"
        ),
    )

    # dbt test al final: si los datos cargados violan una regla declarada
    # (clave duplicada, sector fuera de la lista), el DAG queda en rojo y el
    # dato malo no pasa desapercibido aguas abajo.
    dbt_test = BashOperator(
        task_id="dbt_test",
        bash_command=(
            f"dbt test --project-dir {DBT_PROJECT} --profiles-dir {DBT_PROFILES}"
        ),
    )

    [extract_eia, extract_epri] >> upload_gcs >> load_bigquery >> dbt_run >> dbt_test
