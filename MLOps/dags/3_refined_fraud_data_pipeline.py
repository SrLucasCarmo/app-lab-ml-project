"""
3_refined_fraud_data_pipeline.py — DAG Responsavel pela camada refined (ABT).
"""

import subprocess
import logging
from datetime import timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.sensors.external_task import ExternalTaskSensor
from airflow.utils.dates import days_ago

DEFAULT_ARGS = {
    'owner': 'labdata',
    'depends_on_past': False,
    'start_date': days_ago(1),
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

dag = DAG(
    '3_refined_fraud_data_pipeline',
    default_args=DEFAULT_ARGS,
    description='Pipeline da camada refined (ABT).',
    schedule_interval='@daily',
    catchup=False,
    max_active_runs=1,
    tags=['fraud', 'pipeline', 'data-engineering','refined'],
)


def run_abt_transform():
    """Realiza tratamento de base e salva no Minio em ambiente Docker ou localmente em ambiente local."""
    logger = logging.getLogger(__name__)
    comando = [
        'python', 
        '/opt/airflow/DataPipeline/abt_transform.py'
    ]
    result = subprocess.run(
        comando,
        capture_output=True, text=True, check=True, cwd="/opt/airflow"
    )

    if result.returncode != 0:
        logger.error(f"Falha no Processo de tratamento: {result.stderr}")
        raise Exception(f"Falha no Processo de tratamento: {result.stderr}")

    logger.info("Camada refined salva com sucesso!")
    logger.info(result.stdout)
    return {"status": "success", "layer": "refined"}


sensor_trusted_fraud_data_pipeline = ExternalTaskSensor(
    task_id='sensor_2_trusted_fraud_data_pipeline',
    external_dag_id='2_trusted_fraud_data_pipeline', 
    external_task_id=None,                     
    allowed_states=['success'],                
    failed_states=['failed'],       
    mode='reschedule',                         
    timeout=3600                              
)

abt_transform_task = PythonOperator(
    task_id='refined_abt_transform',
    python_callable=run_abt_transform,
    dag=dag,
)

sensor_trusted_fraud_data_pipeline >> abt_transform_task