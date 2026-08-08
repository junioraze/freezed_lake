from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from collections import defaultdict
from datetime import datetime

@dataclass
class BaseFact:
    sk_fact: str             # Surrogate Key única da linha (PK)
    battle_id: str
    turn: int
    event_order: int
    replay_date: datetime
    timestamp: Optional[int] # <- A CORREÇÃO: Sem "= None" para não quebrar a herança!

@dataclass
class PokemonRevealedDim:
    """Team Pokes Information"""
    sk_pokemon: str          
    battle_id: str
    player: str      
    species: str
    revealed_turn: int
    replay_date: datetime       
    ability: Optional[str] = None
    ability_revealed_turn: Optional[int] = None
    item: Optional[str] = None
    item_revealed_turn: Optional[int] = None
    moves_revealed: List[Dict[str, Any]] = field(default_factory=list)

# Facts

@dataclass
class PlayerActionFact(BaseFact):
    """Unify moves and switch actions"""
    sk_pokemon: str
    action_type: str         
    action_detail: str       
    replay_date: datetime
    # Move Data
    is_ko: bool = False
    is_crit: bool = False
    is_miss: bool = False
    damage_dealt: Optional[int] = None
    effectiveness: Optional[float] = None
    target_sk: Optional[str] = None

@dataclass
class BattleEventFact(BaseFact):
    """Events that derivate from Player Actions or System Mechanics"""
    event_category: str      
    event_detail: str
    replay_date: datetime        
    sk_pokemon: Optional[str] = None  
    source_type: Optional[str] = None 
    source_name: Optional[str] = None 
    parent_action_sk: Optional[str] = None # FK para PlayerActionFact (Relação Causa-Efeito)

# Inner State

@dataclass
class TransientPokemonState:
    """Track Pokemon actual in moment state"""
    hp: int = 100
    max_hp: int = 100
    status: Optional[str] = None
    boosts: Dict[str, int] = field(default_factory=lambda: defaultdict(int))

# State Manager

class BattleState:
    def __init__(self, battle_id: str, replay_date: datetime):
        self.battle_id = battle_id
        self.current_timestamp: Optional[int] = None
        self.turn = 0
        self.event_counter = 0 
        
        self.metadata = {
            'replay_date': replay_date,
            'gametype': None, 'gen': None, 'tier': None, 'winner': None,
            'p1_username': None, 'p1_rating': None,
            'p2_username': None, 'p2_rating': None,
        }
        
        # accum ++
        self.pokemon_info: Dict[str, PokemonRevealedDim] = {}
        self.transient_states: Dict[str, TransientPokemonState] = {}
        self.active_slots: Dict[str, str] = {}
        
        self.actions: List[PlayerActionFact] = []
        self.events: List[BattleEventFact] = []
        
        # Reference to actual action (Parent tracking)
        self._current_action: Optional[PlayerActionFact] = None

    def export_entity(self, entity_attr: str) -> List[Dict]:
        """Export accum++"""
        if entity_attr == 'metadata':
            return [{'battle_id': self.battle_id, **self.metadata}]
        
        if entity_attr == 'pokemon_info':
            return [vars(p) for p in self.pokemon_info.values()]
            
        items = getattr(self, entity_attr, [])
        return [vars(item) for item in items]