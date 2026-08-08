from pyiceberg.schema import Schema, NestedField
from pyiceberg.types import (
    StringType,
    TimestampType,
    IntegerType,
    LongType,
    DoubleType,
    BooleanType,
    ListType,
    StructType,
)
from pyiceberg.partitioning import PartitionSpec, PartitionField
from pyiceberg.transforms import DayTransform, IdentityTransform
from pyiceberg.table.sorting import SortOrder, SortField, SortDirection
from obamasnow.schemas.base import SilverTable

# =============================================================================
# SCHEMA: SILVER METADATA
# =============================================================================
_silver_metadata_schema = Schema(
    NestedField(field_id=1, name="battle_id", type=StringType(), required=True),
    NestedField(field_id=2, name="replay_date", type=TimestampType(), required=True),
    NestedField(field_id=3, name="gametype", type=StringType(), required=False),
    NestedField(field_id=4, name="gen", type=StringType(), required=False),
    NestedField(field_id=5, name="tier", type=StringType(), required=False),
    NestedField(field_id=6, name="winner", type=StringType(), required=False),
    NestedField(field_id=7, name="p1_username", type=StringType(), required=False),
    NestedField(field_id=8, name="p1_rating", type=IntegerType(), required=False),
    NestedField(field_id=9, name="p2_username", type=StringType(), required=False),
    NestedField(field_id=10, name="p2_rating", type=IntegerType(), required=False),
)

_silver_metadata_spec = PartitionSpec(
    PartitionField(source_id=2, transform=DayTransform(), name="replay_date_day", field_id=1000),
)

_silver_metadata_order = SortOrder(
    SortField(source_id=1, transform=IdentityTransform(), direction=SortDirection.ASC)
)
_metadata_name = "metadata"
silver_metadata_table = SilverTable(
    name=_metadata_name,
    lh_name = f"{SilverTable.namespace}.{_metadata_name}",
    schema=_silver_metadata_schema,
    partition_spec=_silver_metadata_spec,
    sort_order=_silver_metadata_order,
)

# =============================================================================
# SCHEMA: SILVER POKEMON_INFO
# =============================================================================
_move_struct = StructType(
    NestedField(field_id=1, name="move", type=StringType(), required=True),
    NestedField(field_id=2, name="turn", type=IntegerType(), required=True),
)

_silver_pokemon_schema = Schema(
    NestedField(field_id=1, name="sk_pokemon", type=StringType(), required=True),
    NestedField(field_id=2, name="battle_id", type=StringType(), required=True),
    NestedField(field_id=3, name="player", type=StringType(), required=True),
    NestedField(field_id=4, name="species", type=StringType(), required=True),
    NestedField(field_id=5, name="revealed_turn", type=IntegerType(), required=True),
    NestedField(field_id=6, name="replay_date", type=TimestampType(), required=True),
    NestedField(field_id=7, name="ability", type=StringType(), required=False),
    NestedField(field_id=8, name="ability_revealed_turn", type=IntegerType(), required=False),
    NestedField(field_id=9, name="item", type=StringType(), required=False),
    NestedField(field_id=10, name="item_revealed_turn", type=IntegerType(), required=False),
    NestedField(
        field_id=11,
        name="moves_revealed",
        type=ListType(element_id=12,element_type=_move_struct, element_required=True),
        required=False,
    ),
)

_silver_pokemon_spec = PartitionSpec(
    PartitionField(source_id=6, transform=DayTransform(), name="replay_date_day", field_id=1000),
)

_silver_pokemon_order = SortOrder(
    SortField(source_id=2, transform=IdentityTransform(), direction=SortDirection.ASC)
)
_pokemon_info = "pokemon_info"
silver_pokemon_table = SilverTable(
    name=_pokemon_info,
    lh_name = f"{SilverTable.namespace}.{_pokemon_info}",
    schema=_silver_pokemon_schema,
    partition_spec=_silver_pokemon_spec,
    sort_order=_silver_pokemon_order,
)

# =============================================================================
# SCHEMA: SILVER ACTIONS
# =============================================================================
_silver_actions_schema = Schema(
    NestedField(field_id=1, name="sk_fact", type=StringType(), required=True),
    NestedField(field_id=2, name="battle_id", type=StringType(), required=True),
    NestedField(field_id=3, name="turn", type=IntegerType(), required=True),
    NestedField(field_id=4, name="event_order", type=IntegerType(), required=True),
    NestedField(field_id=5, name="timestamp", type=LongType(), required=False),
    NestedField(field_id=6, name="replay_date", type=TimestampType(), required=True),
    NestedField(field_id=7, name="sk_pokemon", type=StringType(), required=True),
    NestedField(field_id=8, name="action_type", type=StringType(), required=True),
    NestedField(field_id=9, name="action_detail", type=StringType(), required=True),
    NestedField(field_id=10, name="is_ko", type=BooleanType(), required=False),
    NestedField(field_id=11, name="is_crit", type=BooleanType(), required=False),
    NestedField(field_id=12, name="is_miss", type=BooleanType(), required=False),
    NestedField(field_id=13, name="damage_dealt", type=IntegerType(), required=False),
    NestedField(field_id=14, name="effectiveness", type=DoubleType(), required=False),
    NestedField(field_id=15, name="target_sk", type=StringType(), required=False),
)

_silver_actions_spec = PartitionSpec(
    PartitionField(source_id=6, transform=DayTransform(), name="replay_date_day", field_id=1000),
)

_silver_actions_order = SortOrder(
    SortField(source_id=2, transform=IdentityTransform(), direction=SortDirection.ASC),
    SortField(source_id=3, transform=IdentityTransform(), direction=SortDirection.ASC),
    SortField(source_id=4, transform=IdentityTransform(), direction=SortDirection.ASC),
)

_actions = "actions"
silver_actions_table = SilverTable(
    name=_actions,
    lh_name = f"{SilverTable.namespace}.{_actions}",
    schema=_silver_actions_schema,
    partition_spec=_silver_actions_spec,
    sort_order=_silver_actions_order,
)

# =============================================================================
# SCHEMA: SILVER EVENTS
# =============================================================================
_silver_events_schema = Schema(
    NestedField(field_id=1, name="sk_fact", type=StringType(), required=True),
    NestedField(field_id=2, name="battle_id", type=StringType(), required=True),
    NestedField(field_id=3, name="turn", type=IntegerType(), required=True),
    NestedField(field_id=4, name="event_order", type=IntegerType(), required=True),
    NestedField(field_id=5, name="timestamp", type=LongType(), required=False),
    NestedField(field_id=6, name="replay_date", type=TimestampType(), required=True),
    NestedField(field_id=7, name="event_category", type=StringType(), required=True),
    NestedField(field_id=8, name="event_detail", type=StringType(), required=True),
    NestedField(field_id=9, name="sk_pokemon", type=StringType(), required=False),
    NestedField(field_id=10, name="source_type", type=StringType(), required=False),
    NestedField(field_id=11, name="source_name", type=StringType(), required=False),
    NestedField(field_id=12, name="parent_action_sk", type=StringType(), required=False),
)

_silver_events_spec = PartitionSpec(
    PartitionField(source_id=6, transform=DayTransform(), name="replay_date_day", field_id=1000),
)

_silver_events_order = SortOrder(
    SortField(source_id=2, transform=IdentityTransform(), direction=SortDirection.ASC),
    SortField(source_id=3, transform=IdentityTransform(), direction=SortDirection.ASC),
    SortField(source_id=4, transform=IdentityTransform(), direction=SortDirection.ASC),
)

_events = "events"
silver_events_table = SilverTable(
    name=_events,
    lh_name=f"{SilverTable.namespace}.{_events}",
    schema=_silver_events_schema,
    partition_spec=_silver_events_spec,
    sort_order=_silver_events_order,
)

all_tables = [silver_pokemon_table, silver_metadata_table,
              silver_events_table, silver_actions_table]