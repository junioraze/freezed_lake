from dataclasses import dataclass
from typing import Optional, Final
from pyiceberg.schema import Schema
from pyiceberg.partitioning import PartitionSpec
from pyiceberg.table.sorting import SortOrder

@dataclass
class TableDefinition:
    """
    Agrupa a definição estrutural de uma tabela Iceberg.
    """
    name: str 
    lh_name: str
    schema: Schema
    partition_spec: Optional[PartitionSpec] = None 
    sort_order: Optional[SortOrder] = None 
    
@dataclass
class BronzeTable(TableDefinition):
    namespace: Final[str] = 'bronze'
    
    
@dataclass
class SilverTable(TableDefinition):
    namespace: Final[str] = 'silver'
    