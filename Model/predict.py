#!/usr/bin/env python
"""
predict.py — Script de predição para detecção de fraudes (LightGBM/XGBoost).

Carrega o modelo treinado, scaler e threshold, aplica em novos dados e retorna predições.
Garante alinhamento de features com o scaler treinado.
"""

from __future__ import annotations

import os
import argparse
import json
import logging
import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd
pasta_raiz = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if pasta_raiz not in sys.path:
    sys.path.append(pasta_raiz)
from DataPipeline.util.import_minio import MinioImport

# ---------------------------------------------------------------------------
# Configuração
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

AMBIENTE_ATUAL = os.getenv('AMBIENTE', 'local')

MODEL_CONFIG = Path(__file__).with_name("model_config.json")
with MODEL_CONFIG.open("r", encoding="utf-8") as fh:
    MC = json.load(fh)

RAIZ = Path(__file__).resolve().parent.parent
PASTA_ATUAL = Path(__file__).parent

OUTPUT = MC["output"]
MODEL_PATH = PASTA_ATUAL / OUTPUT["model"]
SCALER_PATH = PASTA_ATUAL / OUTPUT["scaler"]
THRESHOLD_PATH = PASTA_ATUAL / OUTPUT["threshold"]
SCALER_FEATURES_PATH = PASTA_ATUAL / OUTPUT["scaler_report"]

CONFIG_PIPELINE = RAIZ / MC["pipeline"]["config"]["path"] / MC["pipeline"]["config"]["file"]
with CONFIG_PIPELINE.open("r", encoding="utf-8") as fh:
    CPP = json.load(fh)

PATHS = CPP["paths"][AMBIENTE_ATUAL]
FILES_TRANSF = CPP["files_tranformation"][AMBIENTE_ATUAL]
BUCKET = CPP["bucket"]


def load_artifacts():
    """Carrega modelo, scaler, threshold e lista de features do scaler."""
    logger.info("Carregando modelo: %s", MODEL_PATH)
    with MODEL_PATH.open("rb") as f:
        model = pickle.load(f)

    # Se modelo for dict com chave 'model'
    if isinstance(model, dict) and "model" in model:
        model = model["model"]

    # Detectar tipo do modelo
    model_type = type(model).__name__
    logger.info("Tipo do modelo: %s", model_type)

    scaler = None
    scaler_features = None
    if SCALER_PATH.exists():
        logger.info("Carregando scaler: %s", SCALER_PATH)
        with SCALER_PATH.open("rb") as f:
            scaler = pickle.load(f)
    else:
        logger.warning("Scaler não encontrado em %s", SCALER_PATH)

    # Carregar lista de features do scaler
    if SCALER_FEATURES_PATH.exists():
        with SCALER_FEATURES_PATH.open("r") as f:
            scaler_features = json.load(f)
        logger.info("Features do scaler carregadas: %d", len(scaler_features))
    else:
        logger.warning("Lista de features do scaler não encontrada em %s", SCALER_FEATURES_PATH)

    threshold = 0.5
    if THRESHOLD_PATH.exists():
        logger.info("Carregando threshold: %s", THRESHOLD_PATH)
        with THRESHOLD_PATH.open("r") as f:
            threshold = json.load(f).get("optimal_threshold", 0.5)

    return model, scaler, threshold, scaler_features


def align_features(data: pd.DataFrame, scaler_features: list, scaler) -> np.ndarray:
    """
    Alinha as features do DataFrame de entrada com as features esperadas pelo scaler.
    
    Args:
        data: DataFrame de entrada
        scaler_features: Lista de features na ordem que o scaler espera
        scaler: Objeto StandardScaler treinado
    
    Returns:
        Array numpy escalado
    """
    if scaler is None or scaler_features is None:
        logger.warning("Scaler ou features não disponíveis, usando dados como estão")
        return data.values

    # Verificar features faltando
    missing = set(scaler_features) - set(data.columns)
    extra = set(data.columns) - set(scaler_features)
    
    if missing:
        logger.warning("Features faltando no input (preenchendo com 0): %d", len(missing))
        for col in missing:
            data[col] = 0
    
    if extra:
        logger.info("Features extras no input (serão ignoradas): %d", len(extra))
    
    # Reordenar colunas para matchar o scaler
    X_aligned = data[scaler_features].copy()
    
    # Escalar
    X_scaled = scaler.transform(X_aligned)
    logger.info("Features alinhadas e escaladas: %d", X_scaled.shape[1])
    
    return X_scaled


def predict(model, scaler, data: pd.DataFrame, threshold: float = 0.5, scaler_features: list = None):
    """Realiza predições nos dados."""
    X_scaled = align_features(data, scaler_features, scaler)

    y_proba = model.predict_proba(X_scaled)[:, 1]
    y_pred = (y_proba >= threshold).astype(int)

    logger.info("Predições: %d fraudulentas / %d total (threshold=%.4f)",
                y_pred.sum(), len(y_pred), threshold)

    return y_pred, y_proba


def save_predictions(data: pd.DataFrame, y_pred: np.ndarray, y_proba: np.ndarray,
                     output_path: Path) -> None:
    """Salva predições no Minio se ambiente docker ou localmente se ambiente local."""
    out = data.copy()
    out["fraud_probability"] = y_proba
    out["fraud_prediction"] = y_pred
    if AMBIENTE_ATUAL == 'docker':
        try:
            logger.info("Salvando predições")
            tmp_parquet = os.path.join("/tmp/", FILES_TRANSF["predict"])
            data.to_parquet(tmp_parquet,index=False)
            bucket_destino = BUCKET['predict'][0]
            obj_destino = os.path.join(BUCKET["predict"][1], FILES_TRANSF["predict"])
            logger.info(f"Fazendo upload para o MinIO: {bucket_destino}/{obj_destino}")
            minio = MinioImport(bucket_destino,tmp_parquet,obj_destino,"application/vnd.apache.parquet")
            minio.salvar_arquivo_minio()
            logger.info("Predições salvas: %s", output_path)
        except Exception:
            logger.error("ERRO: Não foi possivel realizadar o upload do arquivo.")
    else:
        try:
            logger.info("Salvando predições")
            data.to_csv(os.path.join(PATHS["predict"], FILES_TRANSF["predict"]), index=False)
            logger.info("Predições salvas: %s", output_path)
        except Exception:
            logger.error("ERRO: Não foi salvar o arquivo.")

def main():
    if AMBIENTE_ATUAL == 'docker':
        minio_ident = MinioImport(BUCKET["predict"][0], '', os.path.join(BUCKET["predict"][1], FILES_TRANSF["predict"]), '')
        df = minio_ident.ler_parquet_minio()
    else:
        parser = argparse.ArgumentParser(description="Predição de fraude (LightGBM/XGBoost)")
        parser.add_argument("--input", "-i", required=True, help="Arquivo CSV de entrada")
        parser.add_argument("--output", "-o", default="predictions.csv", help="Arquivo CSV de saída")
        parser.add_argument("--threshold", "-t", type=float, default=None, help="Threshold customizado")
        args = parser.parse_args()
        input_path = Path(args.input)
        output_path = Path(args.output)
        if not input_path.exists():
            logger.error("Arquivo não encontrado: %s", input_path)
            sys.exit(1)
        df = pd.read_csv(input_path)

    logger.info("=" * 60)
    logger.info("PREDIÇÃO DE FRAUDE (LightGBM/XGBoost)")
    logger.info("=" * 60)

    # Carregar dados
    logger.info("Carregando dados: %s", input_path)
    df = pd.read_csv(input_path)
    logger.info("Dados: %d linhas x %d colunas", df.shape[0], df.shape[1])

    # Carregar artefatos
    model, scaler, saved_threshold, scaler_features = load_artifacts()

    # Usar threshold customizado se fornecido
    threshold = args.threshold if args.threshold is not None else saved_threshold
    logger.info("Threshold utilizado: %.4f", threshold)

    # Predição
    y_pred, y_proba = predict(model, scaler, df, threshold, scaler_features)

    # Salvar
    save_predictions(df, y_pred, y_proba, output_path)

    logger.info("=" * 60)
    logger.info("PREDIÇÃO CONCLUÍDA")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()