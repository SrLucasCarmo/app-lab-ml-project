"""
4_model_fraud_data_pipeline.py — DAG Responsavel pelo Treinamento do Modelo , geração dos artefatos e Predição sobre base ABT.

"""
import subprocess
from pathlib import Path
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
    '4_model_fraud_data_pipeline',
    default_args=DEFAULT_ARGS,
    description='Pipeline da camada model (modelo , artefatos e predições).',
    schedule_interval='@daily',
    catchup=False,
    max_active_runs=1,
    tags=['fraud', 'pipeline', 'data-engineering','model'],
)

def check_model_artifacts():
    """Verifica se todos os artefatos do modelo existem."""
    logger = logging.getLogger(__name__)
    logger.info("Verificando artefatos do modelo...")

    required_files = [
        "/opt/airflow/Model/fraud_model.pkl",
        "/opt/airflow/Model/scaler.pkl",
    ]

    missing = []
    for f in required_files:
        if not Path(f).exists():
            missing.append(f)

    if missing:
        raise Exception(f"Artefatos do modelo ausentes: {missing}")
    logger.info("Todos os artefatos do modelo presentes")
    return {"status": "success", "layer": "model"}


def run_model_generate():
    """Gera Modelo localmento no formato pkl."""
    logger = logging.getLogger(__name__)
    comando = [
        'python', 
        '/opt/airflow/Model/train.py'
    ]
    result = subprocess.run(
        comando,
        capture_output=True, text=True, check=True, cwd="/opt/airflow"
    )

    if result.returncode != 0:
        logger.error(f"Falha na geração do Modelo: {result.stderr}")
        raise Exception(f"Falha na geração do Modelo: {result.stderr}")

    logger.info("Modelo gerado com sucesso!")
    logger.info(result.stdout)
    return {"status": "success", "layer": "model"}


def run_preprocess_generate ():
    """Gera o pré processador localmento no formato pkl."""
    logger = logging.getLogger(__name__)
    comando = [
        'python', 
        '/opt/airflow/Model/generate_scaler.py'
    ]
    result = subprocess.run(
        comando,
        capture_output=True, text=True, check=True, cwd="/opt/airflow"
    )

    if result.returncode != 0:
        logger.error(f"Falha na geração do Scaler: {result.stderr}")
        raise Exception(f"Falha na geração do Scaler: {result.stderr}")

    logger.info("Scaler gerado com sucesso!")
    logger.info(result.stdout)
    return {"status": "success", "layer": "model"}

def run_inference():
    """Executa predição usando o modelo já treinado (fraud_model.pkl) e salva no Minio em ambiente docker ou localmente em ambiente local."""
    logger = logging.getLogger(__name__)
    check_model_artifacts()
    comando = [
        'python', 
        '/opt/airflow/Model/predict.py'
    ]
    result = subprocess.run(
        comando,
        capture_output=True, text=True, check=True, cwd="/opt/airflow"
    )

    if result.returncode != 0:
        logger.error(f"Falha na inferência: {result.stderr}")
        raise Exception(f"Falha na inferência: {result.stderr}")
    
    logger.info("Inferência salva com sucesso!")
    logger.info(result.stdout)
    return {"status": "success", "layer": "model"}


# ---------------------------------------------------------------------------
# Definição das Tasks
# ---------------------------------------------------------------------------
##check_artifacts = PythonOperator(
##    task_id='check_model_artifacts',
##    python_callable=check_model_artifacts,
##    dag=dag,
##)

sensor_refined_fraud_data_pipeline = ExternalTaskSensor(
    task_id='sensor_3_refined_fraud_data_pipeline',
    external_dag_id='3_refined_fraud_data_pipeline', 
    external_task_id=None,                     
    allowed_states=['success'],                
    failed_states=['failed'],       
    mode='reschedule',                         
    timeout=3600                              
)

model_generate_task = PythonOperator(
    task_id='model_generate',
    python_callable=run_model_generate,
    dag=dag,
)

preprocess_generate_task = PythonOperator(
    task_id='preprocess_generate',
    python_callable=run_preprocess_generate,
    dag=dag,
)

inference_task = PythonOperator(
    task_id='inferance_generate',
    python_callable=run_inference,
    dag=dag,
)



sensor_refined_fraud_data_pipeline >> model_generate_task >> preprocess_generate_task >> inference_task