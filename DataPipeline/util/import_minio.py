import os
import io
from minio import Minio
from minio.error import S3Error
import pandas as pd

class MinioImport():
    def __init__(self,bucket,caminho_arquivo,arquivo_minio,type):
        self.bucket = bucket
        self.caminho_arquivo = caminho_arquivo
        self.arquivo_minio = arquivo_minio
        self.type = type

    def salvar_arquivo_minio(self):
        # 1. Configurar a conexão com o MinIO no Docker
        endpoint = os.getenv("MINIO_ENDPOINT", "minio:9000")
        if endpoint.startswith("http://"):
            endpoint = endpoint.replace("http://", "")
        client = Minio(
            endpoint=endpoint,
            access_key=os.getenv("MINIO_ACCESS_KEY", "minioadmin"),
            secret_key=os.getenv("MINIO_SECRET_KEY", "minioadmin"),
            secure=False  # Obrigatório ser False em ambiente local sem HTTPS
        )

        try:
            # 2. Verificar se o bucket existe e criar caso não exista
            if not client.bucket_exists(self.bucket):
                client.make_bucket(self.bucket)
                print(f"Bucket '{self.bucket}' criado com sucesso!")
            else:
                print(f"Bucket '{self.bucket}' já existe.")
            # 3. Fazer o upload do arquivo
            client.fput_object(
                bucket_name=self.bucket,
                object_name=self.arquivo_minio,
                file_path=self.caminho_arquivo,
                content_type=self.type
            )
            print(f"Arquivo '{self.arquivo_minio}' salvo com sucesso no MinIO!")

        except S3Error as err:
            print(f"Ocorreu um erro ao conectar com o MinIO: {err}")
        except FileNotFoundError:
            print("Erro: O arquivo CSV não foi encontrado no caminho especificado.")

    def ler_csv_minio(self, chuck_size):
        endpoint = os.getenv("MINIO_ENDPOINT", "minio:9000")
        if endpoint.startswith("http://"):
            endpoint = endpoint.replace("http://", "")
        client = Minio(
            endpoint=endpoint,
            access_key=os.getenv("MINIO_ACCESS_KEY", "minioadmin"),
            secret_key=os.getenv("MINIO_SECRET_KEY", "minioadmin"),
            secure=False  # Obrigatório ser False em ambiente local sem HTTPS
        )

        try:
            resposta = client.get_object(self.bucket, self.arquivo_minio)
            iterador_csv = pd.read_csv(resposta, chunksize=chuck_size)        
            lista_de_lotes = []    
            contador = 0 
            for chunk in iterador_csv:
                if(contador <= 3):
                    lista_de_lotes.append(chunk)
                    contador += 1
            df_final = pd.concat(lista_de_lotes, ignore_index=True)
            return df_final
        except Exception as erro:
            print(f"Ocorreu um erro durante o processamento: {erro}")
            
        finally:
            if 'resposta' in locals():
                resposta.close()
                resposta.release_conn()

    def ler_parquet_minio(self):
        endpoint = os.getenv("MINIO_ENDPOINT", "minio:9000")
        if endpoint.startswith("http://"):
            endpoint = endpoint.replace("http://", "")        
        client = Minio(
            endpoint=endpoint,
            access_key=os.getenv("MINIO_ACCESS_KEY", "minioadmin"),
            secret_key=os.getenv("MINIO_SECRET_KEY", "minioadmin"),
            secure=False  # Obrigatório ser False em ambiente local sem HTTPS
        )

        try:
            resposta = client.get_object(self.bucket, self.arquivo_minio)
            buffer_memoria = io.BytesIO(resposta.read())
            df_final = pd.read_parquet(buffer_memoria)
            return df_final

        except Exception as erro:
            print(f"Ocorreu um erro durante a leitura do Parquet: {erro}")
            
        finally:
            if 'resposta' in locals():
                resposta.close()
                resposta.release_conn()