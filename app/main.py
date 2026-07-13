import streamlit as st 
import pandas as pd
import pickle 
from pathlib import Path
import json
import logging

MODEL_DIR = Path(__file__).parent / "Model"
MODEL_PATH = MODEL_DIR / "fraud_model.pkl"
SCALER_PATH = MODEL_DIR / "scaler.pkl"
THRESHOLD_PATH = MODEL_DIR / "threshold.json"
METRICS_PATH = MODEL_DIR / "training_metrics.json"

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
    
def prepare_data(df):
    model, scaler, saved_threshold, metrics = load_model_artifacts()
    try:
        load_preprocessor = pickle.load(open(scaler, 'rb'))
        load_model = pickle.load(open(model, 'rb'))
    except Exception as expection_error:
        logging.error(expection_error)

    df_processed = load_preprocessor.transform(df)
    X_tratada = pd.DataFrame(df_processed)
    return X_tratada

st.header("Predição de Churn - TELCO")
st.write("Churn rate, ou simplesmente churn, é uma métrica de negócios que mede a taxa de clientes," \
"assinantes ou usuários que deixam de fazer negócios com uma empresa ou cancelam seus serviços em um determinado" \
"período de tempo. Em português, o termo pode ser traduzido como taxa de rotatividade ou taxa de evasão de clientes.")

## -----------
## BIG NUMBERS
## -----------

a, b, c = st.columns(3)
a.metric("**Clientes Ativos**", "215k", "-15%")
b.metric("**Churn Rate**", "25%", "12%")
c.metric("**LTV médio**", "R$1500", "3%")

## -----------
## USER INPUT FEATURES
## -----------
st.sidebar.header("Selecione as características do cliente")

def user_input_features():
    st.header("🔍 Predição Compra")
    st.info("Insira os valores das principais features para predição individual")

    # Formulário simplificado com features principais
    col1, col2, col3 = st.columns(3)

    with col1:
        transaction_amt = st.number_input("TransactionAmt", min_value=0.0, value=100.0, step=10.0)
        product_cd = st.selectbox("ProductCD", ["W", "C", "R", "H", "S"])
        card1 = st.number_input("card1", min_value=0, value=10000)

    with col2:
        card4 = st.selectbox("card4", ["visa", "mastercard", "discover"])
        card6 = st.selectbox("card6", ["credit", "debit"])
        addr1 = st.number_input("addr1", min_value=0, value=100)

    with col3:
        device_type = st.selectbox("DeviceType", ["mobile", "desktop"])
        p_emaildomain = st.selectbox("P_emaildomain", ["gmail.com", "yahoo.com", "outlook.com", "outros"])
        c1 = st.number_input("C1", min_value=0, value=1)
    with st.expander("🔧 Features Avançadas (opcional)"):
        col1, col2 = st.columns(2)
        with col1:
            c2 = st.number_input("C2", min_value=0, value=0)
            c3 = st.number_input("C3", min_value=0, value=0)
            d1 = st.number_input("D1", min_value=0, value=30)
        with col2:
            v1 = st.number_input("V1", value=0.0)
            v2 = st.number_input("V2", value=0.0)
            v3 = st.number_input("V3", value=0.0)
    if st.button("🔮 Prever", type="primary"):
        # Criar DataFrame com features
        input_data = {
            "TransactionAmt": transaction_amt,
            "ProductCD": product_cd,
            "card1": card1,
            "card4": card4,
            "card6": card6,
            "addr1": addr1,
            "DeviceType": device_type,
            "P_emaildomain": p_emaildomain,
            "C1": c1,
            "C2": c2,
            "C3": c3,
            "D1": d1,
            "V1": v1,
            "V2": v2,
            "V3": v3,
        }
        df_input = pd.DataFrame([input_data])
    return df_input

def predict(model, scaler, df: pd.DataFrame, threshold: float):
    """Realiza predições."""
    X = df.copy()

    if scaler is not None:
        X_scaled = scaler.transform(X)
    else:
        X_scaled = X.values

    y_proba = model.predict_proba(X_scaled)[:, 1]
    y_pred = (y_proba >= threshold).astype(int)

    return y_pred, y_proba

model, scaler, saved_threshold, metrics = load_model_artifacts()
df = user_input_features()

## -----------
## DATA PROCESS
## -----------

st.subheader("Dados de input do modelo")
st.write("Dados brutos")
st.write(df)

df_processed = prepare_data(df)
st.write("Dados tratados")
st.write(df_processed)

## -----------
## MODEL
## -----------

with st.spinner("Calculando..."):
    y_pred, y_proba = predict(model, scaler, df, 0.5)

# Resultado
prob = y_proba[0]
pred = y_pred[0]

if pred == 1:
    st.error(f"🚨 **FRAUDE DETECTADA**")
else:
    st.success(f"✅ **TRANSAÇÃO LEGÍTIMA**")

st.metric("Probabilidade de Fraude", f"{prob:.2%}")
st.progress(prob)