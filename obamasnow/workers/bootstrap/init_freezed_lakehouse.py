from pathlib import Path
import s3fs
import requests
from obamasnow.worker import LakehouseWorker
from pyiceberg.exceptions import NoSuchTableError, NamespaceAlreadyExistsError
from collections import defaultdict #odio de instanciar key:value vazio
_WORKER_NAME = f"{Path(__file__).parent.name}-{Path(__file__).stem}"

def main():
    worker = LakehouseWorker(_WORKER_NAME)
    logger = worker.logger
    logger.info("Iniciando bootstrap do Lakehouse")

    # Garantir bucket no MinIO (s3fs)
    fs = s3fs.S3FileSystem(
        key=worker.minio_user,
        secret=worker.minio_pass,
        endpoint_url=worker.minio_endpoint,
        use_ssl=False,
        client_kwargs={"region_name": "us-east-1"},
    )
    if not fs.exists(worker.catalog_bucket):
        fs.mkdir(worker.catalog_bucket)
        logger.info(f"Bucket '{worker.catalog_bucket}' criado.")
    else:
        logger.info(f"Bucket '{worker.catalog_bucket}' já existe.")

    # Token para criar catalogo direto
    token = worker.get_token()
    session = requests.Session()
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    # Garantir catálogo no Polaris
    url = f"{worker.polaris_endpoint}/api/management/v1/catalogs"
    payload = {
        "name": worker.catalog_bucket,
        "type": "INTERNAL",
        "storageType": "S3",
        "properties": {
            "default-base-location": f"s3://{worker.catalog_bucket}",
            "table-default.s3.endpoint": worker.minio_endpoint,
            "table-default.s3.endpoint-internal": worker.minio_endpoint,
            "table-default.s3.path-style-access": "true",
            "table-default.s3.region": "us-east-1",
        },
        "storageConfigInfo": {
            "storageType": "S3",
            "allowedLocations": [f"s3://{worker.catalog_bucket}"],
            "endpoint": worker.minio_endpoint,
            "endpointInternal": worker.minio_endpoint,
            "pathStyleAccess": True,
            "region": "us-east-1",
            "stsUnavailable": True,
            "roleArn": "arn:aws:iam::000000000000:role/dummy",
        },
    }
    resp = session.post(url, json=payload, headers=headers)
    if resp.status_code == 409:
        logger.info(f"Catálogo '{worker.catalog_bucket}' já existe.")
    else:
        resp.raise_for_status()
        logger.info(f"Catálogo '{worker.catalog_bucket}' criado.")

    # Grant 
    grant_url = f"{worker.polaris_endpoint}/api/management/v1/catalogs/{worker.catalog_bucket}/catalog-roles/catalog_admin/grants"
    session.put(
        grant_url,
        json={"type": "catalog", "privilege": "CATALOG_MANAGE_CONTENT"},
        headers=headers,
    ).raise_for_status()
    logger.info("Grant aplicado.")

    # Recuperar metadados se existir
    logger.info("Procurando metadados Iceberg órfãos no S3...")
    metadata_files = fs.glob(f"{worker.catalog_bucket}/**/*.metadata.json")

    if not metadata_files:
        logger.info("Nenhum metadado Iceberg encontrado. Bootstrap concluído.")
        return

    # Obtém o catálogo através do worker validando o REST e habilitando PyIceberg
    catalog = worker.get_catalog()
    registered_count = 0
    logger.info(f"Paths: {metadata_files}")
    tables_metadata = defaultdict(list)
    
    for meta_path in metadata_files:
        # Exemplo: lake/raw/replay_logs/metadata/v1.metadata.json
        parts = meta_path.split("/")
        if len(parts) < 4:
            logger.warning(f"Caminho inválido: {meta_path}, ignorado.")
            continue

        namespace = parts[1]
        table_name = parts[2]
        #agrupa para buscar a ultima versao
        tables_metadata[((namespace, table_name))].append(meta_path)
        
    for (namespace, table_name), paths in tables_metadata.items():    
        last_metadata_path = sorted(paths)[-1]
        table_identifier = f"{namespace}.{table_name}"
        s3_uri = f"s3://{last_metadata_path}"  

        # Garante que o namespace existe
        worker.create_namespace_if_not_exists(namespace)

        # Verifica se a tabela já está registrada
        try:
            catalog.load_table(table_identifier)
            logger.info(f"Tabela '{table_identifier}' já registrada.")
        except NoSuchTableError:
            # REGISTRA a tabela apontando para o metadado existente
            try:
                catalog.register_table(table_identifier, s3_uri)
                logger.info(f"Tabela '{namespace}.{table_name}' registrada com sucesso (metadado: {last_metadata_path}).")
                registered_count += 1
            except Exception as e:
                logger.error(f"Falha ao registrar tabela '{table_identifier}': {e}")

    logger.info(f"Bootstrap concluído. {registered_count} tabelas registradas a partir de metadados órfãos.")

if __name__ == "__main__":
    main()