"""
2_trusted_fraud_data_pipeline.py — DAG Responsavel pela camada trusted (Clen Data).
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
    '2_trusted_fraud_data_pipeline',
    default_args=DEFAULT_ARGS,
    description='Pipeline da camada trusted (Clean Data).',
    schedule_interval='@daily',
    catchup=False,
    max_active_runs=1,
    tags=['fraud', 'pipeline', 'data-engineering','trusted'],
)


def run_data_sanitization():
    """Realiza o tratamento da camada raw e salva no Minio em ambiente Docker ou localmente em ambiente local."""
    logger = logging.getLogger(__name__)
    comando = [
        'python', 
        '/opt/airflow/DataPipeline/data_sanitization.py'
    ]
    result = subprocess.run(
        comando,
        capture_output=True, text=True, check=True, cwd="/opt/airflow"
    )

    if result.returncode != 0:
        logger.error(f"Falha no Processo de sanitização: {result.stderr}")
        raise Exception(f"Falha no Processo de sanitização: {result.stderr}")

    logger.info("Camada trusted salva com sucesso!")
    logger.info(result.stdout)
    return {"status": "success", "layer": "trusted"}


sensor_raw_fraud_data_pipeline = ExternalTaskSensor(
    task_id='sensor_1_raw_fraud_data_pipeline',
    external_dag_id='1_raw_fraud_data_pipeline', 
    external_task_id=None,                     
    allowed_states=['success'],                
    failed_states=['failed'],       
    mode='reschedule',                         
    timeout=3600                              
)

data_sanitization_task = PythonOperator(
    task_id='trusted_data_sanitization',
    python_callable=run_data_sanitization,
    dag=dag,
)

sensor_raw_fraud_data_pipeline >> data_sanitization_task