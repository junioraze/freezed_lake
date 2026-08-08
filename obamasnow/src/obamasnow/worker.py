# src/obamasnow/worker.py
import os
import requests
import pyarrow as pa
import polars as pl
from pyiceberg.catalog import load_catalog
from pyiceberg.exceptions import NamespaceAlreadyExistsError, TableAlreadyExistsError, NoSuchTableError
from .telemetry import get_logger
import s3fs

class LakehouseWorker:
    """
    Worker responsável pela conexão com o Lakehouse (Polaris + MinIO)
    Centraliza autenticação, carregamento de catálogo e operações de inserção.
    """
    def __init__(self, worker_name="lakehouse_wkr"):
        self.logger = get_logger(worker_name)
        self.polaris_endpoint = os.getenv("POLARIS_ENDPOINT", "http://polaris:8181")
        self.polaris_realm = os.getenv("POLARIS_REALM")
        self.polaris_user = os.getenv("POLARIS_USER")
        self.polaris_pass = os.getenv("POLARIS_PASS")
        self.minio_endpoint = os.getenv("MINIO_ENDPOINT", "http://minio:9000")
        self.minio_user = os.getenv("MINIO_USER")
        self.minio_pass = os.getenv("MINIO_PASS")
        self.catalog_bucket = os.getenv("CATALOG_BUCKET")
        
        # Validação básica
        required = ["polaris_realm", "polaris_user", "polaris_pass", 
                    "minio_user", "minio_pass", "catalog_bucket"]
        for var in required:
            if not getattr(self, var):
                raise EnvironmentError(f"Variável {var.upper()} não definida.")
        
        self._catalog = None  # lazy loading
        self._token = None
        
    def _get_s3_filesystem(self) -> s3fs.S3FileSystem: 
        """Retorna instancia autenticada do lake no protocolo s3"""
        return s3fs.S3FileSystem(
            key=self.minio_user,
            secret=self.minio_pass,
            endpoint_url=self.minio_endpoint,
            use_ssl=False,
            client_kwargs={"region_name": "us-east-1"},
        )
        
    def _get_metadata_location(self, table_identifier: str, location: str) -> str | None:
        "Retorna metadados do target"
        fs = self._get_s3_filesystem()
        bucket = self.catalog_bucket
        if location.startswith(f"s3://{bucket}/"):
            relative_path = location.replace(f"s3://{bucket}/", "")
        else:
            relative_path = location.lstrip("/")
        metadata_dir = f"{bucket}/{relative_path}/metadata"
        if not fs.exists(metadata_dir):
            return None
        files = fs.glob(f"{metadata_dir}/*.metadata.json")
        if not files:
            return None
        # Ordena para pegar a versão mais recente (ex: v2 > v1)
        latest = sorted(files)[-1]  # Ex: lake/raw/replay_logs/metadata/v2.metadata.json
        return f"s3://{latest}"
        
    def get_token(self) -> str:
        """Obtém e cacheia o token OAuth2."""
        if self._token:
            return self._token
        
        url = f"{self.polaris_endpoint}/api/catalog/v1/oauth/tokens"
        payload = {
            "grant_type": "client_credentials",
            "client_id": self.polaris_user,
            "client_secret": self.polaris_pass,
            "scope": "PRINCIPAL_ROLE:ALL",
        }
        headers = {
            "Polaris-Realm": self.polaris_realm,
            "Content-Type": "application/x-www-form-urlencoded",
        }
        resp = requests.post(url, data=payload, headers=headers, timeout=15)
        resp.raise_for_status()
        self._token = resp.json()["access_token"]
        return self._token

    def get_catalog(self):
        """Carrega o catálogo (lazy) com as credenciais S3."""
        if self._catalog:
            return self._catalog
        
        token = self.get_token()
        self._catalog = load_catalog(
            "polaris",
            **{
                "type": "rest",
                "uri": f"{self.polaris_endpoint}/api/catalog/",
                "token": token,
                "warehouse": self.catalog_bucket,  # Localização base no S3
                "s3.endpoint": self.minio_endpoint,
                "s3.access-key-id": self.minio_user,
                "s3.secret-access-key": self.minio_pass,
                "s3.region": "us-east-1",
                "s3.path-style-access": "true",
                "header.X-Iceberg-Access-Delegation": "false",
            }
        )             
        return self._catalog

    def get_table(self, table_identifier: str):
        """Retorna uma tabela existente."""
        catalog = self.get_catalog()
        return catalog.load_table(table_identifier)

    def scan_table(self, table_identifier: str, row_filter=None, select=None) -> pl.LazyFrame:
        """Retorna um LazyFrame com as credenciais S3 configuradas."""
        table = self.get_table(table_identifier)
        
        storage_options = {
                    "s3.endpoint": self.minio_endpoint,
                    "s3.access-key-id": self.minio_user,
                    "s3.secret-access-key": self.minio_pass,
                    "s3.path-style-access": "true",
                    "s3.region": "us-east-1",
                }
        
        # Queria precisar nao fazer isso
        lf = pl.scan_iceberg(table, storage_options=storage_options)
        if row_filter:
            lf = lf.filter(row_filter)
        if select:
            lf = lf.select(select)
        return lf

    def create_namespace_if_not_exists(self, namespace: str):
        """Cria namespace se não existir (ignora AlreadyExists)."""
        catalog = self.get_catalog()
        try:
            catalog.create_namespace(namespace)
            self.logger.info(f"Namespace '{namespace}' criado.")
        except NamespaceAlreadyExistsError:
            self.logger.info(f"Namespace '{namespace}' já existe.")
        except Exception as e:
            self.logger.error(f"Erro ao criar namespace: {e}")
            raise

    def create_table_if_not_exists(self, table_identifier: str, schema, partition_spec, 
                                    sort_order=None, location=None):
        """Cria tabela se não existir (ignora AlreadyExists)."""
        properties = {
            "write.format.default": "parquet",
            "write.parquet.compression-codec": "zstd",   # Alta compressão
            "write.metadata.compression-codec": "gzip",
            "write.target-file-size-bytes": "536870912",  # 512 MB
            "write.metadata.metrics.default": "full",    # Para consultas rápidas
            "read.split.target-size": "128MB",
        }
        catalog = self.get_catalog()
        
        try:
            table = catalog.load_table(table_identifier)
            self.logger.info(f"Tabela '{table_identifier}' já existe no catálogo.")
            return table
        
        except NoSuchTableError:
            self.logger.info(f"Tabela '{table_identifier}' não encontrada no catálogo. Verificando Lakehouse...")
            
            if location:
                metadata_uri = self._get_metadata_location(table_identifier, location)
                if metadata_uri:
                    self.logger.info(f'Metadados de {table_identifier} localizados em {location}')
                    try:
                        table = catalog.register_table(table_identifier, metadata_uri)
                        self.logger.info(f'Tabela {table_identifier} registrada com sucesso.')
                        return table
                    
                    except Exception as e:
                        self.logger.warning('Falha ao registrar a partir dos metadados')
                        
        # fallback caso registro nao funcione
        self.logger.info(f"Criando tabela '{table_identifier}' do zero.")
        try:
            table = catalog.create_table(
                identifier=table_identifier,
                schema=schema,
                partition_spec=partition_spec,
                properties=properties,
                location=location,
                sort_order=sort_order
            )
            self.logger.info(f"Tabela '{table_identifier}' criada.")
            return table
        
        except TableAlreadyExistsError:
            self.logger.info(f"Tabela '{table_identifier}' já existe. Carregando...")
            return catalog.load_table(table_identifier)
        
        except Exception as e:
            self.logger.error(f"Falha crítica ao criar tabela: {e}")
            raise
        
        
        
    def ingest_pyarrow_data(self, table_identifier: str, data: pa.Table, batch_size: int = 10000):
        """
        Garante o contrato de dados: Valida o DataFrame do Polars contra
        o schema do Iceberg, reordena, faz o cast e ingere.
        """
        self.logger.info(f"Iniciando ingestão na tabela {table_identifier}.")
        table = self.get_table(table_identifier)
        table_schema = table.schema().as_arrow()
        schema_field_order = [field.name for field in table_schema]
        
        try:
            data = data.select(schema_field_order)
            batches = data.to_batches(max_chunksize=batch_size)
            total_inserted = 0
            
            for batch in batches:
                batch_table = pa.Table.from_batches([batch])
                batch_casted = batch_table.cast(table_schema)
                table.append(batch_casted)
                total_inserted += batch.num_rows
                self.logger.debug(f"Inserido batch de {batch.num_rows} registros")
                
        except Exception as e:
            self.logger.error(f"Falha no contrato de dados ao ingerir: {e}")
            raise            