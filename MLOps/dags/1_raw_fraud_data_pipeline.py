"""
1_raw_fraud_data_pipeline.py — DAG Principal de Ingestão.
"""
import subprocess
import logging
from datetime import timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.utils.dates import days_ago
import os

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
    '1_raw_fraud_data_pipeline',
    default_args=DEFAULT_ARGS,
    description='Pipeline de Ingestão das tabelas do Kaggle no Minio em ambiente Docker ou localmente em ambiente local.',
    schedule_interval='@daily',
    catchup=False,
    max_active_runs=1,
    tags=['fraud', 'pipeline', 'data-engineering','raw'],
)

def run_credencials():
    """Realiza validação das credencias de API Token do Kaggle"""
    logger = logging.getLogger(__name__)
    comando = [
        'python', 
        '/opt/airflow/DataPipeline/ingestion_data.py', 
        '--acao', 'logar', 
    ]
    result = subprocess.run(
        comando,
        capture_output=True, text=True, check=True, cwd="/opt/airflow"
    )

    if result.returncode != 0:
        logger.error(f"Falha de credencial: {result.stderr}")
        raise Exception(f"Falha de credencial: {result.stderr}")

    logger.info("Credencial validada com sucesso!")
    logger.info(result.stdout)
    return {"status": "success", "layer": "raw"}

def run_download():
    """Realizada o download das bases do Kaggle"""
    logger = logging.getLogger(__name__)
    comando = [
        'python', 
        '/opt/airflow/DataPipeline/ingestion_data.py', 
        '--acao', 'baixar', 
    ]
    result = subprocess.run(
        comando,
        capture_output=True, text=True, check=True, cwd="/opt/airflow"
    )

    if result.returncode != 0:
        logger.error(f"Download falhou: {result.stderr}")
        raise Exception(f"Download falhou: {result.stderr}")

    logger.info("Download concluido com sucesso!")
    logger.info(result.stdout)
    return {"status": "success", "layer": "raw"}

def run_ingestion():
    """Realizada a ingestão dos dados de acordo com o ambiente."""
    logger = logging.getLogger(__name__)
    comando = [
        'python', 
        '/opt/airflow/DataPipeline/ingestion_data.py', 
        '--acao', 'salvar', 
    ]
    result = subprocess.run(
        comando,
        capture_output=True, text=True, check=True, cwd="/opt/airflow"
    )

    if result.returncode != 0:
        logger.error(f"Falha na Ingestão: {result.stderr}")
        raise Exception(f"Falha na Ingestão: {result.stderr}")

    logger.info("Ingestão concluida com sucesso!")
    logger.info(result.stdout)
    return {"status": "success", "layer": "raw"}


credencial_task = PythonOperator(
    task_id='raw_credencials',
    python_callable=run_credencials,
    dag=dag,
)
download_task = PythonOperator(
    task_id='raw_download',
    python_callable=run_download,
    dag=dag,
)
ingestion_task = PythonOperator(
    task_id='raw_ingestion',
    python_callable=run_ingestion,
    dag=dag,
)

credencial_task >> download_task >> ingestion_task