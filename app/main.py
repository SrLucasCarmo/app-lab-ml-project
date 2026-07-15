import os
import streamlit as st 
import pandas as pd
from pathlib import Path
import json
import logging
import numpy as np
import pickle 
import plotly.express as px
import plotly.graph_objects as go

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

with METRICS_PATH.open("r", encoding="utf-8") as fh:
    METRICS = json.load(fh)


precisao = round(METRICS["test_metrics"]["precision"] * 100)
recall = METRICS["test_metrics"]["recall"] * 100 
f1 = METRICS["test_metrics"]["f1"] * 100
roc_auc = METRICS["test_metrics"]["roc_auc"] * 100
pr_auc = METRICS["test_metrics"]["pr_auc"] * 100

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
    df = pd.read_csv(DEMONSTRACAO).sample(100)
    return df
    
    
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
    return X_scaled

def predict(model, X_scaled, threshold: float = 0.5):
    """Realiza predições nos dados."""
    y_proba = model.predict_proba(X_scaled)[:, 1]
    y_pred = (y_proba >= threshold).astype(int)
    logger.info("Predições: %d fraudulentas / %d total (threshold=%.4f)",
                y_pred.sum(), len(y_pred), threshold)
    return y_pred, y_proba

def resumo():
    model, scaler, saved_threshold, metrics = load_model_artifacts()
    df = prepare_data()
    X_scaled = align_features(df,scaler)
    y_pred, y_proba = predict(model,X_scaled)
    return df, X_scaled, y_pred, y_proba

        


# Configuração da página
st.set_page_config(page_title="Detecção de Fraudes - PoC", layout="wide")

# --- SEÇÃO DE INFORMAÇÕES ESTÁTICAS ---
st.title("🛡️ Detecção de Fraudes Financeiras")

st.markdown(f"""
### 📝 Sobre o Projeto
Este projeto tem caráter educacional e demonstra o ciclo de vida de dados aplicado ao Machine Learning, da análise exploratória à estruturação de um pipeline. 
* **Aviso Importante:** Trata-se de um ambiente de estudo (PoC). Os modelos não devem ser aplicados em produção real.

### 🎯 Objetivo de Negócio
Reduzir fraudes sem impactar a experiência do cliente legítimo. Inspirado no case da Vesta (onde 3,5% de fraudes geraram impacto superior a US$ 3 milhões), o modelo foca em minimizar falsos negativos, lidando com desafios como assimetria de dados e as constantes mudanças de táticas dos fraudadores.

### 📈 Desempenho do Modelo
Na base de teste, com a configuração de **Threshold de Score (TS) em 50%**, o modelo alcançou:
* **Capacidade de Intercepção:** Identifica e intercepta **{recall}%** de todas as fraudes.
* **Assertividade:** **{precisao}%** dos alertas de bloqueio são fraudes reais (apenas 15% de falsos positivos).
""")

df_metrics = pd.DataFrame({
    "Métrica": ["Precisão", "Recall", "F1-Score","Roc AUC","PR AUC"],
    "Resultado (Teste) - TS 50%": [f"{precisao}%",f"{recall}%",f"{f1}%",f"{roc_auc}%", f"{pr_auc}%"]
})
st.table(df_metrics.set_index("Métrica"))

st.divider()

st.markdown(f"""
### 🛡️ Analise Overfitting
📝 Indicio de Over Overfitting {METRICS["overfitting_analysis"]["overfitting_detected"]}.
Decrição : {METRICS["overfitting_analysis"]["warnings"]}. 
""")

# --- SEÇÃO DINÂMICA (BOTÃO DE DEMONSTRAÇÃO) ---
st.subheader("Simulação em Tempo Real (Sample 100)")

df, X_scaled, y_pred, y_proba = resumo()
pred = pd.DataFrame(y_pred)
proba = pd.DataFrame(y_proba)

qtd_transacoes = proba[0].count()
qtd_fraudes = (proba[0] >= 0.5).sum()
qtd_fraudes_real = df['isFraud'].sum() 

## Exibição dos Big Numbers
col1, col2, col3 = st.columns(3)
col1.metric("Total de Transações", f"{qtd_transacoes:,}")
col2.metric("Fraudes Detectadas", f"{qtd_fraudes:,}")
col3.metric("Fraudes Reaus", f"{qtd_fraudes_real:,}")

st.subheader("Dados de input do modelo")
st.write("Dados ABT")
st.write(df)

st.write("Dados Pre Processados")
st.write(X_scaled)