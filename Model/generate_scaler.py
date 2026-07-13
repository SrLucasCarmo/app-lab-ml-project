#!/usr/bin/env python
"""
generate_scaler.py — Gera e salva o StandardScaler treinado no ABT.

Executa uma vez para criar scaler.pkl baseado no ABT treinado.
"""

from __future__ import annotations

import os
import logging
import pickle
import sys
from pathlib import Path
import json

import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler
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

CONFIG_PATH = Path(__file__).with_name("model_config.json")

with CONFIG_PATH.open("r", encoding="utf-8") as fh:
    CFG = json.load(fh)
BUCKET = CFG["bucket"]
ABT_PATH = Path(__file__).parent.parent / "Dados" / "abt.csv"
SCALER_OUTPUT = Path(__file__).parent / "scaler.pkl"
MODEL_DIR = Path(__file__).parent

# Configuração do pipeline (mesma do abt_transform)
TARGET_COL = "isFraud"
TEST_SIZE = 0.2
RANDOM_STATE = 42
STRATIFY = True


def load_abt() -> pd.DataFrame:
    logger.info("Carregando ABT: %s", ABT_PATH)
    minio_ident = MinioImport(BUCKET["refined"][0], '', os.path.join(BUCKET["refined"][1], "abt_data.parquet"), '')
    df = minio_ident.ler_parquet_minio()
    logger.info("ABT: %s linhas x %s colunas", f"{df.shape[0]:,}", df.shape[1])
    return df

def split_data(df: pd.DataFrame):
    """Split igual ao train.py e abt_transform.py."""
    X = df.drop(columns=[TARGET_COL])
    y = df[TARGET_COL]

    from sklearn.model_selection import train_test_split

    X_trainval, X_test, y_trainval, y_test = train_test_split(
        X, y, test_size=TEST_SIZE, random_state=RANDOM_STATE,
        stratify=y if STRATIFY else None
    )

    VAL_SPLIT = 0.1
    val_size = VAL_SPLIT / (1 - TEST_SIZE)
    X_train, X_val, y_train, y_val = train_test_split(
        X_trainval, y_trainval, test_size=val_size,
        random_state=RANDOM_STATE, stratify=y_trainval if STRATIFY else None
    )

    logger.info("Split: train=%s, val=%s, test=%s",
                f"{len(X_train):,}", f"{len(X_val):,}", f"{len(X_test):,}")
    logger.info("Fraude: train=%.2f%%, val=%.2f%%, test=%.2f%%",
                y_train.mean()*100, y_val.mean()*100, y_test.mean()*100)
    return X_train, X_val, X_test, y_train, y_val, y_test

def main():
    logger.info("=" * 60)
    logger.info("GERANDO SCALER TRAINADO NO ABT")
    logger.info("=" * 60)

    # 1. Carregar ABT
    df = load_abt()

    # 2. Split
    X_train, X_val, X_test, y_train, y_val, y_test = split_data(df)

    # 3. Combinar treino + validação (como no train.py final)
    X_trainval = pd.concat([X_train, X_val], axis=0)
    y_trainval = pd.concat([y_train, y_val], axis=0)

    # 4. Treinar scaler no treino + validação
    feature_cols = [c for c in X_trainval.columns if c != TARGET_COL]

    logger.info("Treinando StandardScaler em %d features...", len(feature_cols))
    scaler = StandardScaler()
    scaler.fit(X_trainval[feature_cols])

    # 5. Verificar
    X_scaled = scaler.transform(X_trainval[feature_cols])
    logger.info("Scaler treinado: media=%.4f, std=%.4f",
                X_scaled.mean().mean(), X_scaled.std().mean())

    # 6. Salvar
    with open(SCALER_OUTPUT, "wb") as f:
        pickle.dump(scaler, f)
    logger.info("Scaler salvo: %s", SCALER_OUTPUT)

    # 7. Salvar também lista de features para validação
    features_file = MODEL_DIR / "scaler_features.json"
    with open(features_file, "w") as f:
        json.dump(feature_cols, f, indent=2)
    logger.info("Lista de features salva: %s", features_file)

    logger.info("=" * 60)
    logger.info("SCALER GERADO COM SUCESSO")
    logger.info("=" * 60)

if __name__ == "__main__":
    import json
    main()