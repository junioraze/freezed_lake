from pyiceberg.schema import Schema, NestedField
from pyiceberg.types import StringType, TimestampType
from pyiceberg.partitioning import PartitionSpec, PartitionField
from pyiceberg.transforms import IdentityTransform, DayTransform
from obamasnow.schemas.base import BronzeTable


_replay_logs_schema = Schema(
    NestedField(field_id=1, name="replay_id", type=StringType(), required=True),
    NestedField(field_id=2, name="gen", type=StringType(), required=True),
    NestedField(field_id=3, name="tier", type=StringType(), required=True),
    NestedField(field_id=4, name="replay_timestamp", type=TimestampType(), required=True),
    NestedField(field_id=5, name="raw_log", type=StringType(), required=True),
    NestedField(field_id=6, name="ingestion_timestamp", type=TimestampType(), required=True),
)

_replay_logs_spec = PartitionSpec(
    PartitionField(source_id=2, transform=IdentityTransform(), name="gen", field_id=1000),
    PartitionField(source_id=3, transform=IdentityTransform(), name="tier", field_id=1001),
    PartitionField(source_id=4, transform=DayTransform(), name="day", field_id=1002),
)
#Tabela com dados brutos dos logs, pensar em incluir doc dentro do obj do table definition
_replay_logs = "replay_logs"

replay_logs_table = BronzeTable(
    name=_replay_logs,
    lh_name = f"{BronzeTable.namespace}.{_replay_logs}",
    schema=_replay_logs_schema,
    partition_spec=_replay_logs_spec
)

all_tables = [replay_logs_table]