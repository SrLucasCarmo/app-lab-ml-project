#!/usr/bin/env python
"""
ingestion_data.py — Extrai dados do Keggle e salva na camada raw do minio em ambiente docker ou salva arquivos localmente em ambiente local.
Uso:
    python DataPipeline/ingestion_data.py
"""

from __future__ import annotations

import os
import json
import logging
import sys
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()
import kagglehub
from util.import_minio import MinioImport
import argparse



# ---------------------------------------------------------------------------
# Configuração de logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Carregamento de configuração
# ---------------------------------------------------------------------------
AMBIENTE_ATUAL = os.getenv('AMBIENTE', 'local')

CONFIG_PATH = Path(__file__).with_name("pipeline_config.json")
with CONFIG_PATH.open("r", encoding="utf-8") as fh:
    CFG = json.load(fh)

PATHS = CFG["paths"][AMBIENTE_ATUAL]
BUCKET = CFG["bucket"]
FILES = CFG["files"]
CLEAN_CFG = CFG["cleaning"]
META = CFG["metadata"]
PACOTE = CFG["pacote"]


# ---------------------------------------------------------------------------
# Funções utilitárias
# ---------------------------------------------------------------------------

def credenciais():
    """Verifica credencias do Kaggle"""
    api_token = os.getenv("KAGGLE_API_TOKEN") 
    if not api_token:
        logger.error("ERRO: A variável KAGGLE_API_TOKEN não foi encontrada no container!")
        sys.exit(1)
    logger.info("Credenciais encontradas.")


def download_database():
    """Realiza o download das tabelas via API"""
    api_token = os.getenv("KAGGLE_API_TOKEN")
    os.environ["KAGGLE_API_TOKEN"] = api_token
    logger.info("Iniciando download das tabelas...")  
    try:
        kagglehub.competition_download(
            PACOTE,
            output_dir=PATHS["raw"],
            force_download=True
        )
        logger.info("Arquivos baixados...")
    except Exception:
        logger.error("ERRO: Não foi possivel realizada o download das bases")
        sys.exit(1)


def import_minio():
    """Carrega arquivos baixados para o Minio"""  
    for file in FILES:
        logger.info(f"Realizando importação da tabela {file} no Minio") 
        try: 
            file_bucket = os.path.join(BUCKET["raw"][1], file)
            dir = os.path.join(PATHS["raw"], file)
            minio = MinioImport(BUCKET["raw"][0],dir,file_bucket,'text/csv')
            minio.salvar_arquivo_minio()
        except Exception:
            logger.error("ERRO: Não foi possivel realizar a importação para o Minio")
            sys.exit(1)

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("DATA INGESTION - IEEE-CIS Fraud Detection")
    logger.info("=" * 60)
    if AMBIENTE_ATUAL == 'docker':
        parser = argparse.ArgumentParser(description='Executa métodos da Ingestão')
        parser.add_argument('--acao', type=str, required=True, choices=['logar','baixar', 'salvar'], 
                            help='Qual método você deseja executar?')
        args = parser.parse_args()
        if args.acao == 'logar':
            logger.info("Realizando Validação de credenciais de acesso Kaggle")
            credenciais()
        elif args.acao == 'baixar':
            logger.info("Realizando Download das tabelas do kaggle")
            download_database()
        elif args.acao == 'salvar':
            logger.info("Realizando Importação das tabelas para o Minio")
            import_minio()
    else:
        credenciais()
        download_database()
