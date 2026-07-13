#!/usr/bin/env python
"""
predict.py — Script de predição para detecção de fraudes (LightGBM/XGBoost).

Carrega o modelo treinado, scaler e threshold, aplica em novos dados e retorna predições.
Garante alinhamento de features com o scaler treinado.
"""

from __future__ import annotations

import argparse
import json
import logging
import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Configuração
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

MODEL_DIR = Path(__file__).parent
MODEL_PATH = MODEL_DIR / "fraud_model.pkl"
SCALER_PATH = MODEL_DIR / "scaler.pkl"
THRESHOLD_PATH = MODEL_DIR / "threshold.json"
SCALER_FEATURES_PATH = MODEL_DIR / "scaler_features.json"


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
    """Salva predições em CSV."""
    out = data.copy()
    out["fraud_probability"] = y_proba
    out["fraud_prediction"] = y_pred
    out.to_csv(output_path, index=False)
    logger.info("Predições salvas: %s", output_path)


def main():
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