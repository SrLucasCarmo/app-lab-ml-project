import os
import streamlit as st 
import pandas as pd
import pickle 
from pathlib import Path
import json
import logging
import numpy as np

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

AMBIENTE_ATUAL = os.getenv('AMBIENTE', 'local')
RAIZ = Path(__file__).resolve().parent
PASTA_ATUAL = Path(__file__).parent

APP_CONFIG = Path(__file__).with_name("app_config.json")
with APP_CONFIG.open("r", encoding="utf-8") as fh:
    AC = json.load(fh)

MODEL_DIR = AC["model"]["config"]["path"]

MODEL_CONFIG = RAIZ / MODEL_DIR / AC["model"]["config"]["file"] 
with MODEL_CONFIG.open("r", encoding="utf-8") as fh:
    MC = json.load(fh)

CONFIG_PIPELINE = RAIZ / AC["pipeline"]["config"]["path"] / AC["pipeline"]["config"]["file"]
with CONFIG_PIPELINE.open("r", encoding="utf-8") as fh:
    CPP = json.load(fh)


OUTPUT = MC["output"]
MODEL_PATH = RAIZ / MODEL_DIR / OUTPUT["model"]
SCALER_PATH = RAIZ / MODEL_DIR / OUTPUT["scaler"]
THRESHOLD_PATH = RAIZ / MODEL_DIR / OUTPUT["threshold"]
METRICS_PATH = RAIZ / MODEL_DIR / OUTPUT["metrics"]
DEMONSTRACAO = RAIZ / 'Dados/demonstration.csv'
SCALER_REPORT = RAIZ / MODEL_DIR / OUTPUT["scaler_report"]

with SCALER_REPORT.open("r", encoding="utf-8") as fh:
    SCALER_FEATURES = json.load(fh)
# ---------------------------------------------------------------------------
# Funções utilitárias
# ---------------------------------------------------------------------------
@st.cache_resource
def load_model_artifacts():
    """Carrega modelo, scaler e threshold."""
    try:
        with open(MODEL_PATH, "rb") as f:
            model = pickle.load(f)

        # Se for dict, extrair modelo
        if isinstance(model, dict) and "model" in model:
            model = model["model"]

        scaler = None
        if Path(SCALER_PATH).exists():
            with open(SCALER_PATH, "rb") as f:
                scaler = pickle.load(f)

        threshold = 0.5
        if Path(THRESHOLD_PATH).exists():
            with open(THRESHOLD_PATH, "r") as f:
                threshold = json.load(f).get("optimal_threshold", 0.5)

        metrics = {}
        if Path(METRICS_PATH).exists():
            with open(METRICS_PATH, "r") as f:
                metrics = json.load(f)

        return model, scaler, threshold, metrics

    except Exception as e:
        st.error(f"Erro ao carregar artefatos: {e}")
        return None, None, 0.5, {}
    
def prepare_data():
    if Path(SCALER_PATH).exists():
        with open(SCALER_PATH, "rb") as file:
            load_preprocessor = pickle.load(file)
    df = pd.read_csv(DEMONSTRACAO).sample(5)
    return df, load_preprocessor
    
    
def align_features(data: pd.DataFrame, scaler):
    if scaler is None or SCALER_FEATURES is None:
        logger.warning("Scaler ou features não disponíveis, usando dados como estão")
        return data.values

    missing = set(SCALER_FEATURES) - set(data.columns)
    extra = set(data.columns) - set(SCALER_FEATURES)
    
    if missing:
        logger.warning("Features faltando no input (preenchendo com 0): %d", len(missing))
        for col in missing:
            data[col] = 0
    
    if extra:
        logger.info("Features extras no input (serão ignoradas): %d", len(extra))
    
    # Reordenar colunas para matchar o scaler
    X_aligned = data[SCALER_FEATURES].copy()
    # Escalar
    X_scaled = scaler.transform(X_aligned)
    logger.info("Features alinhadas e escaladas: %d", X_scaled.shape[1])
    return data, X_scaled

def predict(model, X_scaled, threshold: float = 0.5):
    """Realiza predições nos dados."""
    y_proba = model.predict_proba(X_scaled)[:, 1]
    y_pred = (y_proba >= threshold).astype(int)
    logger.info("Predições: %d fraudulentas / %d total (threshold=%.4f)",
                y_pred.sum(), len(y_pred), threshold)
    return y_pred, y_proba


st.header("")
st.write("")

## -----------
## BIG NUMBERS
## -----------

a, b, c = st.columns(3)
a.metric("****", "215k", "-15%")
b.metric("****", "25%", "12%")
c.metric("***", "R$1500", "3%")


model, scaler, saved_threshold, metrics = load_model_artifacts()
df, load_scaler = prepare_data()
data, X_scaled = align_features(df,load_scaler)
y_pred, y_proba = predict(model,X_scaled,0.5)

if st.button("🔮 Prever", type="primary"):
    model, scaler, saved_threshold, metrics = load_model_artifacts()
    df, load_scaler = prepare_data()
    data, X_scaled = align_features(df,load_scaler)
    y_pred, y_proba = predict(model,X_scaled,0.5)

## -----------
## DATA PROCESS
## -----------

st.subheader("Dados de input do modelo")
st.write("Dados ABT")
st.write(df)

st.write("Dados Pre Processados")
st.write(X_scaled)
st.write("Dados de Inferência")
st.write(f"Predições: {y_pred.sum()} fraudulentas / {len(y_pred)} total)")
