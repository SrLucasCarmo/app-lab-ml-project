"""
fraud_data_pipeline_ingestion.py — DAG Principal de Ingestão.
"""

from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.utils.dates import days_ago
import os

# ---------------------------------------------------------------------------
# Configuração padrão
# ---------------------------------------------------------------------------
DEFAULT_ARGS = {
    'owner': 'fia-labdata',
    'depends_on_past': False,
    'start_date': days_ago(1),
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

# ---------------------------------------------------------------------------
# DAG Principal: Pipeline Completo de Dados
# ---------------------------------------------------------------------------
dag = DAG(
    'raw_fraud_data_pipeline',
    default_args=DEFAULT_ARGS,
    description='Pipeline de Ingestão das tabelas do Kaggle no Minio.',
    schedule_interval='@daily',
    catchup=False,
    max_active_runs=1,
    tags=['fraud', 'pipeline', 'data-engineering','raw'],
)

def run_credencials(**context):
    """Executa data_sanitization.py - Raw."""
    import subprocess
    import sys
    import logging

    logger = logging.getLogger(__name__)
    #script_path = "/opt/airflow/DataPipeline/ingestion_data.py"
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
        logger.error(f"Data Ingestion falhou: {result.stderr}")
        raise Exception(f"Data Ingestion falhou: {result.stderr}")

    logger.info("Data Ingestion concluída com sucesso")
    logger.info(result.stdout)
    return {"status": "success", "layer": "raw"}

def run_download(**context):
    """Executa data_sanitization.py - Raw."""
    import subprocess
    import sys
    import logging

    logger = logging.getLogger(__name__)
    #script_path = "/opt/airflow/DataPipeline/ingestion_data.py"
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
        logger.error(f"Data Ingestion falhou: {result.stderr}")
        raise Exception(f"Data Ingestion falhou: {result.stderr}")

    logger.info("Data Ingestion concluída com sucesso")
    logger.info(result.stdout)
    return {"status": "success", "layer": "raw"}

def run_ingestion(**context):
    """Executa data_sanitization.py - Raw."""
    import subprocess
    import sys
    import logging

    logger = logging.getLogger(__name__)
    #script_path = "/opt/airflow/DataPipeline/ingestion_data.py"
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
        logger.error(f"Data Ingestion falhou: {result.stderr}")
        raise Exception(f"Data Ingestion falhou: {result.stderr}")

    logger.info("Data Ingestion concluída com sucesso")
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