FROM python:3.11-slim

WORKDIR /app

# Instalar dependências do sistema
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Copiar requirements e instalar
COPY streaming_pipeline/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copiar código do streaming pipeline
COPY streaming_pipeline/ /app/streaming_pipeline/
COPY Model/ /app/Model/
COPY DataPipeline/pipeline_config.json /app/DataPipeline/pipeline_config.json

# Criar diretórios de dados
RUN mkdir -p /app/streaming_pipeline/data/raw \
    /app/streaming_pipeline/data/clean \
    /app/streaming_pipeline/data/abt \
    /app/streaming_pipeline/data/predictions

# Expor porta Streamlit
EXPOSE 8501

# Comando padrão - Streamlit
CMD ["streamlit", "run", "streaming_pipeline/streamlit_streaming.py", "--server.port=8501", "--server.address=0.0.0.0"]