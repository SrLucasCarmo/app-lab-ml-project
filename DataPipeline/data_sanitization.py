#!/usr/bin/env python
"""
data_sanitization.py — Limpeza e sanitização dos dados brutos de fraudes.

Lê os CSVs originais (transações + identidade), faz merge, limpa e valida,
e salva no Minio em ambiente Docker ou salva localmente em ambiente local.

Uso:
    python DataPipeline/data_sanitization.py
"""

from __future__ import annotations

import os
import json
import logging
from pathlib import Path
import pandas as pd
from util.import_minio import MinioImport


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

RAIZ = Path(__file__).resolve().parent.parent
PATHS = CFG["paths"][AMBIENTE_ATUAL]
BUCKET = CFG["bucket"]
FILES = CFG["files"]
FILES_TRANSF = CFG["files_tranformation"][AMBIENTE_ATUAL]
FILES_REPORT = CFG["file_report"]
CLEAN_CFG = CFG["cleaning"]
META = CFG["metadata"]
LIMITATION = CFG["limitation"]



# ---------------------------------------------------------------------------
# Funções utilitárias
# ---------------------------------------------------------------------------

def chunk_control(caminho_arquivo) -> pd.DataFrame:
    """Le arquivo CSV aplicando chunk size configurado e retorna Dataframe"""
    iterador_csv = pd.read_csv(caminho_arquivo, chunksize=LIMITATION["chunk_size"])        
    lista_de_lotes = []    
    contador = 0 
    for chunk in iterador_csv:
        if(contador <= LIMITATION["chunk_count"]):
            lista_de_lotes.append(chunk)
            contador += 1
    df_final = pd.concat(lista_de_lotes, ignore_index=True)
    return df_final

def load_and_merge() -> pd.DataFrame:
    """Carrega identidade inteira e transações em lotes, filtrando antecipadamente."""
    if AMBIENTE_ATUAL == 'docker':
        # 1. Carrega a tabela MENOR (Identidade) inteira para a memória
        logger.info("Carregando identidade em lotes (chunksize): %s", FILES[1])
        minio_ident = MinioImport(BUCKET["raw"][0], '', os.path.join(BUCKET["raw"][1], FILES[1]), '')
        df_ident = minio_ident.ler_csv_minio()

        logger.info("Carregando transações em lotes (chunksize): %s", FILES[0])
        minio_trans = MinioImport(BUCKET["raw"][0], '', os.path.join(BUCKET["raw"][1], FILES[0]), '')
        df_trans_iter = minio_trans.ler_csv_minio() 
    else:
        logger.info("Carregando identidade em lotes (chunksize): %s", FILES[1])
        df_ident = chunk_control(os.path.join(PATHS["raw"], FILES[1]))
        logger.info("Carregando transações em lotes (chunksize): %s", FILES[0])
        df_trans_iter = chunk_control(os.path.join(PATHS["raw"], FILES[0]))
    
    df = df_trans_iter.merge(df_ident, on=META["id_column"], how="left")

    logger.info(
        "Dataset consolidado final: %s linhas | %s colunas",
        f"{df.shape[0]:,}",
        df.shape[1],
    )
    return df


def remove_duplicates(df: pd.DataFrame) -> pd.DataFrame:
    """Remove duplicatas por TransactionID."""
    dup_count = df.duplicated(subset=[META["id_column"]]).sum()
    if dup_count > 0 and CLEAN_CFG["remove_duplicates"]:
        before = len(df)
        df = df.drop_duplicates(subset=[META["id_column"]], keep="first")
        removed = before - len(df)
        logger.info("Duplicatas removidas: %s", removed)
    else:
        logger.info("Sem duplicatas por TransactionID")
    return df

def fix_invalid_values(df: pd.DataFrame) -> pd.DataFrame:
    """Remove valores inválidos (TransactionAmt <= 0, isFraud fora de {0,1})."""
    # TransactionAmt <= 0
    invalid_amt = (df[META["amount_column"]] <= CLEAN_CFG["transaction_amt_min"]).sum()
    if invalid_amt > 0:
        before = len(df)
        df = df[df[META["amount_column"]] > CLEAN_CFG["transaction_amt_min"]].copy()
        removed = before - len(df)
        logger.info("TransactionAmt <= 0 removidos: %s", removed)
    else:
        logger.info("TransactionAmt: todos > 0")

    # isFraud fora de {0,1}
    valid_fraud = CLEAN_CFG["valid_fraud_values"]
    invalid_fraud = (~df[META["target_column"]].isin(valid_fraud)).sum()
    if invalid_fraud > 0:
        before = len(df)
        df = df[df[META["target_column"]].isin(valid_fraud)].copy()
        removed = before - len(df)
        logger.info("isFraud inválido removidos: %s", removed)
    else:
        logger.info("isFraud: todos válidos (0 ou 1)")

    return df

def detect_outliers(df: pd.DataFrame) -> dict[str, dict]:
    """Detecta outliers via IQR (apenas reporta, não remove)."""
    multiplier = CLEAN_CFG["iqr_multiplier"]
    target_cols = [c for c in CLEAN_CFG["outlier_target_cols"] if c in df.columns]
    outliers_info = {}

    for col in target_cols:
        Q1 = df[col].quantile(0.25)
        Q3 = df[col].quantile(0.75)
        IQR = Q3 - Q1
        lower = Q1 - multiplier * IQR
        upper = Q3 + multiplier * IQR
        count = int(((df[col] < lower) | (df[col] > upper)).sum())
        pct = count / len(df) * 100
        outliers_info[col] = {
            "count": count,
            "pct": round(pct, 4),
            "lower_bound": round(float(lower), 4),
            "upper_bound": round(float(upper), 4),
        }
        logger.info("Outliers %s: %s (%.2f%%)", col, count, pct)

    return outliers_info


def validate_business_rules(df: pd.DataFrame) -> dict:
    """Valida regras de negócio e retorna diagnóstico."""
    diag = {}

    # Contagens C* >= 0
    c_cols = [c for c in df.columns if c[0] == "C" and c[1:].isdigit()]
    c_negative = sum(int((df[c] < 0).sum()) for c in c_cols)
    diag["c_negative_total"] = int(c_negative)
    if c_negative == 0:
        logger.info("Variáveis C: todas >= 0")

    # Temporais D*
    d_cols = [c for c in df.columns if c[0] == "D" and c[1:].isdigit()]
    diag["d_cols_count"] = len(d_cols)
    if "D1" in df.columns:
        diag["D1_min"] = float(df["D1"].min())
        diag["D1_max"] = float(df["D1"].max())

    # Target balance
    fraud_counts = df[META["target_column"]].value_counts().sort_index()
    diag["target_legit"] = int(fraud_counts.get(0, 0))
    diag["target_fraud"] = int(fraud_counts.get(1, 0))
    diag["fraud_rate_pct"] = round(diag["target_fraud"] / len(df) * 100, 4)

    logger.info(
        "Target: legit=%s, fraud=%s (%.2f%%)",
        f"{diag['target_legit']:,}",
        f"{diag['target_fraud']:,}",
        diag["fraud_rate_pct"],
    )
    return diag


def validate_categoricals(df: pd.DataFrame) -> list[dict]:
    """Valida colunas categóricas (strip whitespace)."""
    text_cols = df.select_dtypes(include=["object"]).columns.tolist()
    profiles = []

    for col in text_cols:
        df[col] = df[col].str.strip()

        n_unique = int(df[col].nunique())
        n_missing = int(df[col].isnull().sum())
        missing_pct = round(n_missing / len(df) * 100, 4)
        top_values = (
            df[col].value_counts().head(3).index.tolist() if n_unique < 20 else []
        )
        profiles.append(
            {
                "name": col,
                "n_unique": n_unique,
                "n_missing": n_missing,
                "missing_pct": missing_pct,
                "top_values": [str(v) for v in top_values],
            }
        )

    logger.info("Categoricas validadas: %s colunas", len(profiles))
    return profiles


def optimize_dtypes(df: pd.DataFrame) -> dict[str, str]:
    """Otimiza tipos de dados."""
    conversions = {}

    if META["target_column"] in df.columns:
        if df[META["target_column"]].dtype not in (
            "int8", "int16", "int32", "int64", "uint8"
        ):
            df[META["target_column"]] = df[META["target_column"]].astype("int8")
            conversions[META["target_column"]] = "int8"

    if META["time_column"] in df.columns:
        if df[META["time_column"]].dtype not in ("int32", "int64"):
            df[META["time_column"]] = df[META["time_column"]].astype("int32")
            conversions[META["time_column"]] = "int32"

    if META["amount_column"] in df.columns:
        if df[META["amount_column"]].dtype not in ("float32", "float64"):
            df[META["amount_column"]] = df[META["amount_column"]].astype("float32")
            conversions[META["amount_column"]] = "float32"

    # Variáveis C numericas
    c_cols = [c for c in df.columns if c[0] == "C" and c[1:].isdigit()]
    for col in c_cols:
        if not pd.api.types.is_numeric_dtype(df[col]):
            df[col] = pd.to_numeric(df[col], errors="coerce")
            conversions[col] = "numeric (coerced)"

    logger.info("Dtypes otimizados: %s conversões", len(conversions))
    return conversions


def generate_report(
    initial_shape: tuple[int, int],
    df: pd.DataFrame,
    outliers_info: dict,
    categorical_profiles: list[dict],
    steps: list[dict],
) -> dict:
    """Gera relatório completo de limpeza."""
    fraud_counts = df[META["target_column"]].value_counts().sort_index()

    report = {
        "initial_shape": list(initial_shape),
        "final_shape": list(df.shape),
        "rows_removed": initial_shape[0] - df.shape[0],
        "rows_removed_pct": round(
            (initial_shape[0] - df.shape[0]) / initial_shape[0] * 100, 4
        ),
        "steps": steps,
        "outliers": [
            {"column": k, **v} for k, v in outliers_info.items()
        ],
        "categorical_profiles": categorical_profiles,
        "target_distribution": {
            "legitimo": int(fraud_counts.get(0, 0)),
            "fraude": int(fraud_counts.get(1, 0)),
        },
        "target_fraud_rate_pct": round(
            fraud_counts.get(1, 0) / len(df) * 100, 4
        ),
    }
    return report
def save(df: pd.DataFrame):
    """Salva arquivo transformado no Minio em ambiente docker ou salva localmente em ambiente local"""
    if AMBIENTE_ATUAL == 'docker':  
        try: 
            tmp_parquet = os.path.join("/tmp/", FILES_TRANSF["clean_data"])
            logger.info("Salvando base transformada")
            df.to_parquet(tmp_parquet,index=False)
            bucket_destino = BUCKET['trusted'][0]
            obj_destino = os.path.join(BUCKET["trusted"][1], FILES_TRANSF["clean_data"])
            logger.info(f"Fazendo upload para o MinIO: {bucket_destino}/{obj_destino}")
            minio = MinioImport(bucket_destino,tmp_parquet,obj_destino,"application/vnd.apache.parquet")
            minio.salvar_arquivo_minio()

            if os.path.exists(tmp_parquet):
                os.remove(tmp_parquet)
            print("Processo concluído com sucesso!")
        except Exception:
            logger.error("ERRO: Não foi possivel realizadar o upload do arquivo.")
    else:
        try:
            logger.info("Salvando base transformada")
            df.to_csv(os.path.join(PATHS["clean_data"], FILES_TRANSF["clean_data"]), index=False)
            print("Processo concluído com sucesso!")
        except Exception:
            logger.error("ERRO: Não foi salvar o arquivo.")

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    logger.info("=" * 60)
    logger.info("DATA SANITIZATION - Fraud Detection Pipeline")
    logger.info("=" * 60)

    # 1. Load & Merge
    df = load_and_merge()
    initial_shape = df.shape

    steps = []

    # 2. Remove duplicatas
    before = len(df)
    df = remove_duplicates(df)
    if len(df) < before:
        steps.append({
            "step": "Remove duplicates by TransactionID",
            "removed": int(before - len(df)),
            "new_shape": list(df.shape),
            "action": "drop",
        })

    # 3. Fix invalid values
    before = len(df)
    df = fix_invalid_values(df)
    removed = before - len(df)
    if removed > 0:
        steps.append({
            "step": "Remove invalid values (TransactionAmt <= 0, isFraud)",
            "removed": int(removed),
            "new_shape": list(df.shape),
            "action": "drop",
        })

    # 4. Detect outliers
    outliers_info = detect_outliers(df)
    steps.append({
        "step": "Outliers detected (IQR method)",
        "action": "keep for ABT stage (use capping or transformation)",
        "detail": f"{len(outliers_info)} columns checked",
    })

    # 5. Business rules
    validate_business_rules(df)

    # 6. Categoricals
    categorical_profiles = validate_categoricals(df)

    # 7. Optimize dtypes
    optimize_dtypes(df)

    # 8. Generate & save report
    report = generate_report(
        initial_shape, df, outliers_info, categorical_profiles, steps
    )
    save(df)

    output_json = RAIZ / PATHS["clean_data"] / FILES_REPORT["clean_data"]
    logger.info("Exportando relatório: %s", output_json)
    with output_json.open("w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2, ensure_ascii=False)
    
    # Print summary
    print()
    print("=" * 60)
    print("DATA SANITIZATION CONCLUÍDA")
    print("=" * 60)
    print(f"Shape inicial : {initial_shape[0]:,} x {initial_shape[1]}")
    print(f"Shape final   : {df.shape[0]:,} x {df.shape[1]}")
    print(f"Linhas removidas: {report['rows_removed']:,} ({report['rows_removed_pct']:.2f}%)")
    print(f"Taxa de fraude: {report['target_fraud_rate_pct']:.2f}%")
    print(f"Relatório     : {output_json}")
    print("=" * 60)


if __name__ == "__main__":
    main()