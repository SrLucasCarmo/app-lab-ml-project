"""
fraud_data_pipeline.py — DAG Principal: Pipeline Completo de Dados (Raw -> Clean -> ABT -> Inference).

USA O MODELO JÁ TREINADO (fraud_model.pkl) — NÃO RETREINA.
"""

from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.sensors.external_task import ExternalTaskSensor
from airflow.utils.dates import days_ago

# ---------------------------------------------------------------------------
# Configuração padrão
# ---------------------------------------------------------------------------
DEFAULT_ARGS = {
    'owner': 'fia-labdata',
    'depends_on_past': False,
    'start_date': days_ago(1),
    'email_on_failure': True,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

# ---------------------------------------------------------------------------
# DAG Principal: Pipeline Completo de Dados
# ---------------------------------------------------------------------------
dag = DAG(
    'refined_fraud_data_pipeline',
    default_args=DEFAULT_ARGS,
    description='Pipeline completo: Raw -> Clear -> ABT -> Inference (usa modelo já treinado)',
    schedule_interval='@daily',
    catchup=False,
    max_active_runs=1,
    tags=['fraud', 'pipeline', 'data-engineering','refined'],
)

# ---------------------------------------------------------------------------
# Funções de cada etapa (usando a mesma lógica dos scripts existentes)
# ---------------------------------------------------------------------------
def check_model_artifacts(**context):
    """Verifica se todos os artefatos do modelo existem."""
    from pathlib import Path
    import logging

    logger = logging.getLogger(__name__)
    logger.info("Verificando artefatos do modelo...")

    required_files = [
        "/opt/airflow/Model/fraud_model.pkl",
        "/opt/airflow/Model/scaler.pkl",
        "/opt/airflow/Model/threshold.json",
    ]

    missing = []
    for f in required_files:
        if not Path(f).exists():
            missing.append(f)

    if missing:
        raise Exception(f"Artefatos do modelo ausentes: {missing}")

    logger.info("Todos os artefatos do modelo presentes")
    return {"status": "success", "artifacts_checked": len(required_files)}


def run_abt_transform(**context):
    """Executa abt_transform.py - Clean -> ABT."""
    import subprocess
    import sys
    import logging

    logger = logging.getLogger(__name__)
    #script_path = "/opt/airflow/DataPipeline/ingestion_data.py"
    comando = [
        'python', 
        '/opt/airflow/DataPipeline/abt_transform.py'
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
    return {"status": "success", "layer": "trusted"}

def run_inference(**context):
    """Executa predição usando o modelo já treinado (fraud_model.pkl)."""
    import subprocess
    import sys
    import logging
    import json
    import pandas as pd
    from pathlib import Path

    logger = logging.getLogger(__name__)
    logger.info("Executando Inferência com modelo treinado...")

    # Verificar se modelo existe
    model_path = Path("/opt/airflow/Model/fraud_model.pkl")
    if not model_path.exists():
        raise Exception(f"Modelo não encontrado em {model_path}")

    # Verificar se ABT existe
    abt_path = Path("/opt/airflow/Dados/abt.csv")
    if not abt_path.exists():
        raise Exception(f"ABT não encontrada em {abt_path}")

    # Executar predict.py na ABT
    script_path = "/opt/airflow/Model/predict.py"
    output_path = "/opt/airflow/Dados/predictions_latest.csv"

    result = subprocess.run([
        sys.executable, script_path,
        "--input", "/opt/airflow/Dados/abt.csv",
        "--output", output_path
    ], capture_output=True, text=True, cwd="/opt/airflow")

    if result.returncode != 0:
        logger.error(f"Inferência falhou: {result.stderr}")
        raise Exception(f"Inferência falhou: {result.stderr}")

    logger.info("Inferência concluída com sucesso")
    logger.info(result.stdout)

    # Salvar métricas de inferência para XCom
    try:
        preds = pd.read_csv(output_path)
        n_total = len(preds)
        n_fraud = preds['fraud_prediction'].sum() if 'fraud_prediction' in preds.columns else 0
        pct_fraud = n_fraud / n_total * 100 if n_total > 0 else 0

        return {
            "status": "success",
            "predictions_file": output_path,
            "n_total": int(n_total),
            "n_fraud": int(n_fraud),
            "fraud_rate_pct": round(pct_fraud, 2)
        }
    except Exception as e:
        logger.warning(f"Não foi possível calcular métricas: {e}")
        return {"status": "success", "predictions_file": output_path}


def save_predictions_to_minio(**context):
    """Salva predições no MinIO (opcional - requer minio client)."""
    import logging
    logger = logging.getLogger(__name__)
    logger.info("Salvando predições no MinIO...")

    # TODO: Implementar upload para MinIO se necessário
    logger.info("Upload para MinIO (simulado)")
    return {"status": "success", "note": "MinIO upload placeholder"}


# ---------------------------------------------------------------------------
# Definição das Tasks
# ---------------------------------------------------------------------------
##check_artifacts = PythonOperator(
##    task_id='check_model_artifacts',
##    python_callable=check_model_artifacts,
##    dag=dag,
##)

sensor_trusted_fraud_data_pipeline = ExternalTaskSensor(
    task_id='sensor_trusted_fraud_data_pipeline',
    external_dag_id='trusted_fraud_data_pipeline', 
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

##inference_task = PythonOperator(
##    task_id='run_inference',
##    python_callable=run_inference,
##    dag=dag,
##)
##
##minio_task = PythonOperator(
##    task_id='save_to_minio',
##    python_callable=save_predictions_to_minio,
##    dag=dag,
##)

# ---------------------------------------------------------------------------
# Dependências: Check artifacts -> Sanitize -> ABT -> Inference -> MinIO
# ---------------------------------------------------------------------------
#check_artifacts >> sanitize_task >> abt_task >> inference_task >> minio_task
sensor_trusted_fraud_data_pipeline >> abt_transform_task