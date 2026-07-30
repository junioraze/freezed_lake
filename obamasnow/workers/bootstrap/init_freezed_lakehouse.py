from pathlib import Path
import s3fs
import requests
from obamasnow.worker import LakehouseWorker

_WORKER_NAME = f"{Path(__file__).parent.name}-{Path(__file__).stem}"

def main():
    worker = LakehouseWorker(_WORKER_NAME)
    logger = worker.logger
    logger.info("Iniciando bootstrap do Lakehouse")

    # 1. Token para chamadas administrativas
    token = worker.get_token()
    session = requests.Session()
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    # 2. Garantir bucket no MinIO
    fs = s3fs.S3FileSystem(
        key=worker.minio_user,
        secret=worker.minio_pass,
        endpoint_url=worker.minio_endpoint,
        use_ssl=False,
        client_kwargs={"region_name": "us-east-1"}
    )
    if not fs.exists(worker.catalog_bucket):
        fs.mkdir(worker.catalog_bucket)
        logger.info(f"Bucket '{worker.catalog_bucket}' criado.")
    else:
        logger.info(f"Bucket '{worker.catalog_bucket}' já existe.")

    # 3. Garantir catálogo no Polaris (idempotente)
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

    # Grant (idempotente)
    grant_url = f"{worker.polaris_endpoint}/api/management/v1/catalogs/{worker.catalog_bucket}/catalog-roles/catalog_admin/grants"
    session.put(grant_url, json={"type": "catalog", "privilege": "CATALOG_MANAGE_CONTENT"}, headers=headers).raise_for_status()
    logger.info("Grant aplicado.")

    # 4. Recuperar tabelas órfãs (descobre dinamicamente)
    metadata_files = fs.glob(f"{worker.catalog_bucket}/**/*.metadata.json")
    if not metadata_files:
        logger.info("Nenhum metadado Iceberg encontrado. Bootstrap concluído.")
        return

    for meta_path in metadata_files:
        parts = meta_path.split("/")
        if len(parts) < 4:
            logger.warning(f"Caminho inválido: {meta_path}, ignorado.")
            continue
        namespace = parts[1]
        table_name = parts[2]
        s3_uri = f"s3://{meta_path}"

        check_url = f"{worker.polaris_endpoint}/api/catalog/v1/{worker.catalog_bucket}/namespaces/{namespace}/tables/{table_name}"
        resp = session.get(check_url, headers=headers)
        if resp.status_code == 200:
            logger.info(f"Tabela '{namespace}.{table_name}' já registrada.")
        elif resp.status_code == 404:
            register_url = f"{worker.polaris_endpoint}/api/catalog/v1/{worker.catalog_bucket}/namespaces/{namespace}/tables"
            reg_resp = session.post(register_url, json={"name": table_name, "metadata-location": s3_uri}, headers=headers)
            reg_resp.raise_for_status()
            logger.info(f"Tabela '{namespace}.{table_name}' registrada com sucesso.")
        else:
            resp.raise_for_status()

    logger.info("Bootstrap concluído com sucesso.")

if __name__ == "__main__":
    main()