# workers/raw_layer.py
from pathlib import Path
from obamasnow.worker import LakehouseWorker
from pyiceberg.schema import Schema, NestedField
from pyiceberg.types import StringType, TimestampType
from pyiceberg.partitioning import PartitionSpec, PartitionField
from pyiceberg.transforms import IdentityTransform, DayTransform

_WORKER_NAME = f"{Path(__file__).parent.name}-{Path(__file__).stem}"
_NAME_SPACE = "raw"
_TABLE_NAME = "replay_logs"
_LH_TABLE = f"{_NAME_SPACE}.{_TABLE_NAME}"

def main():
    worker = LakehouseWorker(_WORKER_NAME)
    
    schema = Schema(
        NestedField(field_id=1, name="replay_id", type=StringType(), required=True),
        NestedField(field_id=2, name="gen", type=StringType(), required=True),
        NestedField(field_id=3, name="tier", type=StringType(), required=True),
        NestedField(field_id=4, name="replay_timestamp", type=TimestampType(), required=True),
        NestedField(field_id=5, name="raw_log", type=StringType(), required=True),
        NestedField(field_id=6, name="ingestion_timestamp", type=TimestampType(), required=True),
    )
    
    partition_spec = PartitionSpec(
        PartitionField(source_id=2, transform=IdentityTransform(), name="gen", field_id=1000),
        PartitionField(source_id=3, transform=IdentityTransform(), name="tier", field_id=1001),
        PartitionField(source_id=4, transform=DayTransform(), name="day", field_id=1002),
    )
    worker.logger.info(f"{_WORKER_NAME} criando namespace '{_NAME_SPACE}.")
    worker.create_namespace_if_not_exists(_NAME_SPACE)
    worker.logger.info(f"{_WORKER_NAME} criando tabela '{_LH_TABLE}'.")
    table = worker.create_table_if_not_exists(
        _LH_TABLE,
        schema=schema,
        partition_spec=partition_spec,
        location=f"s3://{worker.catalog_bucket}/{_NAME_SPACE}/{_TABLE_NAME}"
    )
    worker.logger.info(f"{_WORKER_NAME} concluído.")

if __name__ == "__main__":
    main()