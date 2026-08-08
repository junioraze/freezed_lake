# workers/create/silver_layer.py
import os
from pathlib import Path
from obamasnow.worker import LakehouseWorker
from obamasnow.schemas.bronze_layer import all_tables, BronzeTable

_WORKER_NAME = f"{Path(__file__).parent.name}-{Path(__file__).stem}"

def main():
    worker = LakehouseWorker(_WORKER_NAME)
    worker.create_namespace_if_not_exists(BronzeTable.namespace)
    worker.logger.info(f"{_WORKER_NAME} criando namespace '{BronzeTable.namespace}.")
    
    for table in all_tables:
        lh_name = table.lh_name
        schema = table.schema
        partition_spec = table.partition_spec
        worker.logger.info(f"{_WORKER_NAME} criando tabela '{lh_name}'.")
        table = worker.create_table_if_not_exists(
            lh_name,
            schema=schema,
            partition_spec=partition_spec,
            location=f"s3://{worker.catalog_bucket}/{BronzeTable.namespace}/{table.name}"
        )
    worker.logger.info(f"{_WORKER_NAME} concluído.")

if __name__ == "__main__":
    main()