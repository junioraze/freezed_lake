#!/usr/bin/env python3
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from lakehouse_worker import LakehouseWorker, logger
from pyiceberg.schema import Schema, NestedField
from pyiceberg.types import StringType, TimestampType
from pyiceberg.partitioning import PartitionSpec, PartitionField
from pyiceberg.transforms import IdentityTransform, YearTransform, MonthTransform, DayTransform

def main():
    worker = LakehouseWorker()
    
    # Define esquema (igual antes)
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
    
    # Cria namespace e tabela usando o worker
    worker.create_namespace_if_not_exists("raw")
    table = worker.create_table_if_not_exists(
        "raw.replay_logs",
        schema=schema,
        partition_spec=partition_spec,
        location=f"s3://{worker.catalog_bucket}/raw/replay_logs"
    )
    logger.info("Formation concluído.")

if __name__ == "__main__":
    main()