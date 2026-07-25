#!/usr/bin/env python3

import os
import sys
import logging
import requests
from pyiceberg.catalog import load_catalog
from pyiceberg.exceptions import TableAlreadyExistsError, NamespaceAlreadyExistsError
from pyiceberg.schema import Schema, NestedField
from pyiceberg.types import (
    StringType,
    TimestampType
)
from pyiceberg.partitioning import PartitionSpec, PartitionField
from pyiceberg.transforms import IdentityTransform, DayTransform, MonthTransform, YearTransform
from dotenv import load_dotenv; load_dotenv()
# Configuração de logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# =============================================
# 1. CONFIGURAÇÕES VIA VARIÁVEIS DE AMBIENTE
# =============================================

# --- Polaris ---
# Endpoint da API REST do Polaris (dentro da rede lakehouse_net)
POLARIS_ENDPOINT = os.getenv("POLARIS_ENDPOINT", "http://polaris:8181")
POLARIS_REALM = os.getenv("POLARIS_REALM")       # Realm definido no Terraform
POLARIS_USER = os.getenv("POLARIS_USER")         # Client ID
POLARIS_PASS = os.getenv("POLARIS_PASS")         # Client Secret

# --- MinIO ---
MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "http://minio:9000")
MINIO_USER = os.getenv("MINIO_USER")             # Access Key
MINIO_PASS = os.getenv("MINIO_PASS")             # Secret Key

# --- Catálogo / Bucket ---
# Este é o nome do catálogo/bucket criado pelo Terraform (var.catalog_bucket)
CATALOG_BUCKET = os.getenv("CATALOG_BUCKET")


REQUIRED_VARS = [
    "POLARIS_REALM", "POLARIS_USER", "POLARIS_PASS",
    "MINIO_USER", "MINIO_PASS", "CATALOG_BUCKET"
]

for var in REQUIRED_VARS:
    if not os.getenv(var):
        logger.error(f"Variável de ambiente {var} não definida. Abortando.")
        sys.exit(1)

logger.info(f"Conectando ao catálogo: {CATALOG_BUCKET}")
logger.info(f"Polaris Endpoint: {POLARIS_ENDPOINT}")
logger.info(f"MinIO Endpoint: {MINIO_ENDPOINT}")


# =============================================
# 2. AUTENTICAÇÃO OAuth2 (igual ao Terraform)
# =============================================

def get_polaris_token() -> str:
    """
    Obtém um token de acesso OAuth2 do Polaris usando o fluxo client_credentials.
    Exatamente o mesmo procedimento usado no null_resource do Terraform.
    """
    token_url = f"{POLARIS_ENDPOINT}/api/catalog/v1/oauth/tokens"
    
    payload = {
        "grant_type": "client_credentials",
        "client_id": POLARIS_USER,
        "client_secret": POLARIS_PASS,
        "scope": "PRINCIPAL_ROLE:ALL",
    }
    
    headers = {
        "Polaris-Realm": POLARIS_REALM,
        "Content-Type": "application/x-www-form-urlencoded",
    }
    
    logger.info(f"Solicitando token OAuth2 em {token_url}")
    try:
        response = requests.post(token_url, data=payload, headers=headers, timeout=15)
        response.raise_for_status()
        token_data = response.json()
        token = token_data.get("access_token")
        if not token:
            raise ValueError("Token não encontrado.")
        logger.info("Token OAuth2 obtido com sucesso.")
        return token
    except requests.exceptions.RequestException as e:
        logger.error(f"Falha ao obter token OAuth2: {e}")
        if hasattr(e, "response") and e.response:
            logger.error(f"Resposta: {e.response.text}")
        sys.exit(1)


# =============================================
# 3. CONEXÃO COM O CATÁLOGO (PyIceberg)
# =============================================

def get_catalog(token: str):
    """
    Carrega o catálogo Polaris via REST, passando as credenciais S3
    para que o Iceberg saiba onde escrever os arquivos.
    """
    catalog = load_catalog(
        "polaris",
        **{
            "type": "rest",
            "uri": f"{POLARIS_ENDPOINT}/api/catalog/",
            "token": token,
            "warehouse": CATALOG_BUCKET,  # Localização base no S3
            "s3.endpoint": MINIO_ENDPOINT,
            "s3.access-key-id": MINIO_USER,
            "s3.secret-access-key": MINIO_PASS,
            "s3.region": "us-east-1",
            "s3.path-style-access": "true",
            "headers.X-Iceberg-Access-Delegation": "none",
        }                                              
    )
    logger.info(f"Catálogo '{CATALOG_BUCKET}' carregado com sucesso.")
    return catalog


# =============================================
# 4. DEFINIÇÃO DO ESQUEMA E PARTIÇÕES
# =============================================

def get_schema() -> Schema:
    """
    Esquema da camada RAW.
    """
    return Schema(
        # ID 1: Identificador único do replay
        NestedField(field_id=1, name="replay_id", type=StringType(), required=True),
        
        # ID 2: Geração
        NestedField(field_id=2, name="gen", type=StringType(), required=True),
        
        # ID 3: Tier
        NestedField(field_id=3, name="tier", type=StringType(), required=True),
        
        # ID 4: Timestamp original da partida
        NestedField(field_id=4, name="replay_timestamp", type=TimestampType(), required=True),
        
        # ID 5: O arquivo de log
        NestedField(field_id=5, name="raw_log", type=StringType(), required=True),
        
        # ID 6: Quando o worker processou
        NestedField(field_id=6, name="ingestion_timestamp", type=TimestampType(), required=True),
    )

def get_partition_spec() -> PartitionSpec:
    """
    1. gen (identidade)
    2. tier (identidade) 
    3. year (derivado do replay_timestamp)
    4. month (derivado do replay_timestamp)
    5. day (derivado do replay_timestamp)
    """
    return PartitionSpec(
        # 1. Partição por Geração (ex: gen4ou)
        PartitionField(
            source_id=2,                    # Coluna 'gen'
            transform=IdentityTransform(),
            name="gen",
            field_id=1000
        ),
        # 2. Partição por Tier (ex: [Gen 4] OU)
        PartitionField(
            source_id=3,                    # Coluna 'tier'
            transform=IdentityTransform(),
            name="tier",
            field_id=1001
        ),
        # 3. Partição por ANO (ex: 2026)
        PartitionField(
            source_id=4,                    # Coluna 'replay_timestamp'
            transform=YearTransform(),
            name="year",
            field_id=1002
        ),
        # 4. Partição por MÊS (ex: 07)
        PartitionField(
            source_id=4,                    # Coluna 'replay_timestamp'
            transform=MonthTransform(),
            name="month",
            field_id=1003
        ),
        # 5. Partição por DIA (ex: 23)
        PartitionField(
            source_id=4,                    # Coluna 'replay_timestamp'
            transform=DayTransform(),
            name="day",
            field_id=1004
        ),
    )

# =============================================
# 5. CRIAÇÃO DA TABELA (IDEMPOTENTE)
# =============================================

def main():
    # 1. Obter token OAuth2
    token = get_polaris_token()
    
    # 2. Carregar catálogo
    catalog = get_catalog(token)
    
    # 3. Definir identificador da tabela (namespace.tabela)
    namespace = "raw"
    try:
        catalog.create_namespace(namespace)
        logger.info(f"Namespace {namespace} criado com sucesso.")
    except NamespaceAlreadyExistsError:
        logger.info(f"Namespace {namespace} já existe. Criado com sucesso")
    except Exception as e:
        logger.error(f"Falha ao criar/carregar namespace {namespace}: {e}")
        sys.exit(1)
        
    table_name = "replay_logs"
    full_identifier = f"{namespace}.{table_name}"
    
    logger.info(f"Verificando/Criando tabela: {full_identifier}")
    
    # 4. Carregar esquema e partições
    schema = get_schema()
    partition_spec = get_partition_spec()
    
    # 5. Localização física dos dados no MinIO
    location = f"s3://{CATALOG_BUCKET}/{namespace}/{table_name}"
    
    # 6. Propriedades adicionais da tabela
    properties = {
        "write.format.default": "parquet",
        "write.parquet.compression-codec": "zstd",   # Alta compressão
        "write.metadata.compression-codec": "gzip",
        "write.metadata.metrics.default": "full",    # Para consultas rápidas
        "read.split.target-size": "128MB",
    }
    
    # 7. Cria tabela
    try:
        table = catalog.create_table(
            identifier=full_identifier,
            schema=schema,
            partition_spec=partition_spec,
            properties=properties,
        )
        logger.info(f"Tabela '{full_identifier}' criada com sucesso!")
        logger.info(f"   Localização: {location}")
        
    except TableAlreadyExistsError:
        # Tabela já existe - carregar e exibir informações
        logger.info(f"Tabela '{full_identifier}' já existe. Carregada com sucesso.")
        
        # (Opcional) Verificar se o esquema atual corresponde ao esperado
        # Aqui você poderia adicionar lógica de migração (ALTER TABLE) no futuro.
    
    except Exception as e:
        #Ignora erro de nao ter STS
        if "Credential vending was requested" not in str(e):
            logger.error(f"Falha ao criar/carregar a tabela: {e}")
            sys.exit(1)
    
    logger.info("Formation concluído com sucesso.")


if __name__ == "__main__":
    main()