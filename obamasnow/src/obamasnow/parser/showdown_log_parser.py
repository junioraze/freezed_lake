from datetime import datetime
from typing import List, Tuple, Optional, Dict
from obamasnow.parser.models import BattleState, PokemonRevealedDim, PlayerActionFact, BattleEventFact, TransientPokemonState
from obamasnow.parser.log_parser import EventLogParser

class ShowdownLogParser(EventLogParser):
    """
    Parser especializado focado em Data Mesh, Fog of War e Relações Relacionais (PK/FK).
    """

    def __init__(self):
        super().__init__(state_class=BattleState, event_separator='|')
        self._register_handlers()

    def _register_handlers(self) -> None:
        self.register(['turn', 'timestamp', 'player', 'win', 'gametype', 'tier', 'gen'], self._handle_metadata)
        self.register(['switch', 'drag', 'replace'], self._handle_switch)
        self.register(['move'], self._handle_move)
        self.register(['crit', 'supereffective', 'resisted', 'immune', 'miss'], self._handle_action_modifier)
        self.register(['damage', 'heal'], self._handle_hp_change)
        self.register(['faint'], self._handle_faint)
        self.register([
            'status', 'curestatus', 'boost', 'unboost', 'item', 'enditem', 
            'ability', 'activate', 'cant', 'weather', 'fieldstart', 
            'fieldend', 'sidestart', 'sideend'
        ], self._handle_generic_event)

    # ========== MÉTODOS CORE ==========

    def parse(self, log_rows: List[List[str]], battle_id: str, replay_date: datetime) -> BattleState:
        state = BattleState(battle_id, replay_date)
        for row in log_rows:
            state.event_counter += 1
            self.parse_line(state, row)
        return state

    def parse_batch(self, batch_logs: List[Tuple[List[List[str]], str, datetime]]) -> Dict[str, List[Dict]]:
        accumulators = {"metadata": [], "pokemon_info": [], "actions": [], "events": []}
        for log_rows, battle_id, replay_date in batch_logs:
            try:
                state = self.parse(log_rows, battle_id, replay_date)
                accumulators["metadata"].extend(state.export_entity('metadata'))
                accumulators["pokemon_info"].extend(state.export_entity('pokemon_info'))
                accumulators["actions"].extend(state.export_entity('actions'))
                accumulators["events"].extend(state.export_entity('events'))
            except Exception as e:
                print(f"Warning: Falha no batch para {battle_id}: {e}")
        return accumulators

    # ========== HELPERS & SURROGATE KEYS ==========

    def _get_or_create_pokemon(self, state: BattleState, raw_slot: str, species: str = 'unknown') -> Optional[str]:
        if not raw_slot or not raw_slot.strip(): return None
        
        clean_raw = raw_slot.strip()
        player = clean_raw[:2] if len(clean_raw) >= 2 else 'unknown'
        
        if ':' in clean_raw:
            pokemon_identity = clean_raw.split(':', 1)[1].strip()
        else:
            pokemon_identity = clean_raw
        
        # Usando a função base do parser para gerar a dimensão
        sk = self.generate_sk(state.battle_id, player, pokemon_identity)
        
        if sk not in state.pokemon_info:
            state.pokemon_info[sk] = PokemonRevealedDim(
                sk_pokemon=sk, battle_id=state.battle_id, player=player, 
                species=species, revealed_turn=state.turn, replay_date=state.metadata['replay_date']
            )
            state.transient_states[sk] = TransientPokemonState()
        elif species != 'unknown' and state.pokemon_info[sk].species == 'unknown':
            state.pokemon_info[sk].species = species
                
        return sk

    def _extract_from_tags(self, state: BattleState, params: List[str], default_sk: Optional[str] = None) -> Tuple[Optional[str], Optional[str]]:
        stype, sname = None, None
        owner_raw = None
        
        for p in params:
            if p.startswith('[from] '):
                raw_source = p.replace('[from] ', '').strip()
                if ':' in raw_source:
                    stype, sname = raw_source.split(':', 1)
                    stype, sname = stype.strip(), sname.strip()
                else:
                    stype, sname = 'effect', raw_source
            elif p.startswith('[of] '):
                owner_raw = p.replace('[of] ', '').strip()
                
        owner_sk = self._get_or_create_pokemon(state, owner_raw) if owner_raw else default_sk
        
        if owner_sk and stype in ('item', 'ability') and sname:
            info = state.pokemon_info.get(owner_sk)
            if info:
                if stype == 'item' and not info.item:
                    info.item = sname
                    info.item_revealed_turn = state.turn
                elif stype == 'ability' and not info.ability:
                    info.ability = sname
                    info.ability_revealed_turn = state.turn
                    
        return stype, sname

    # ========== HANDLERS CONSOLIDADOS ==========

    def _handle_metadata(self, state: BattleState, typ: str, params: List[str]):
        if typ == 'turn':
            state.turn = int(params[0])
            state._current_action = None # Limpa a ação atual a cada novo turno
        elif typ == 'timestamp' and params and params[0].isdigit():
            state.current_timestamp = int(params[0])
        elif typ == 'player' and len(params) >= 2:
            player = params[0].strip()
            state.metadata[f"{player}_username"] = params[1].strip()
            if len(params) > 3 and params[3].isdigit():
                state.metadata[f"{player}_rating"] = int(params[3])
        elif typ == 'win':
            winner_name = params[0].strip()
            if winner_name == state.metadata.get('p1_username'):
                state.metadata['winner'] = 'p1'
            elif winner_name == state.metadata.get('p2_username'):
                state.metadata['winner'] = 'p2'
            else:
                state.metadata['winner'] = winner_name
        elif typ in ('gametype', 'tier', 'gen'):
            state.metadata[typ] = params[0]

    def _handle_switch(self, state: BattleState, typ: str, params: List[str]):
        species = params[1].split(',')[0].strip()
        sk_pokemon = self._get_or_create_pokemon(state, params[0], species)
        if not sk_pokemon: return
        
        sk_fact = self.generate_sk(state.battle_id, state.event_counter)
        action = PlayerActionFact(
            sk_fact=sk_fact, battle_id=state.battle_id, turn=state.turn, event_order=state.event_counter,
            timestamp=state.current_timestamp, sk_pokemon=sk_pokemon, 
            action_type='SWITCH', action_detail=species, replay_date=state.metadata['replay_date']
        )
        state.actions.append(action)
        state._current_action = action # Registra a troca como a ação pai vigente

    def _handle_move(self, state: BattleState, typ: str, params: List[str]):
        move_name = params[1].strip()
        sk_pokemon = self._get_or_create_pokemon(state, params[0])
        if not sk_pokemon: return

        info = state.pokemon_info[sk_pokemon]
        if not any(m['move'] == move_name for m in info.moves_revealed):
            info.moves_revealed.append({"move": move_name, "turn": state.turn})

        target_sk = self._get_or_create_pokemon(state, params[2]) if len(params) > 2 else None
        
        sk_fact = self.generate_sk(state.battle_id, state.event_counter)
        action = PlayerActionFact(
            sk_fact=sk_fact, battle_id=state.battle_id, turn=state.turn, event_order=state.event_counter,
            timestamp=state.current_timestamp, sk_pokemon=sk_pokemon, action_type='MOVE', 
            action_detail=move_name, target_sk=target_sk, replay_date=state.metadata['replay_date']
        )
        state.actions.append(action)
        state._current_action = action # Registra o move como a ação pai vigente

    def _handle_action_modifier(self, state: BattleState, typ: str, params: List[str]):
        if not state._current_action: return
        
        modifiers = {
            'crit': ('is_crit', True), 'miss': ('is_miss', True), 'immune': ('is_immune', True),
            'supereffective': ('effectiveness', 2.0), 'resisted': ('effectiveness', 0.5)
        }
        attr, val = modifiers.get(typ, (None, None))
        if attr: setattr(state._current_action, attr, val)

    def _handle_hp_change(self, state: BattleState, typ: str, params: List[str]):
        sk = self._get_or_create_pokemon(state, params[0])
        if not sk: return
        
        hp_str = params[1].split()[0]
        hp_val = int(hp_str.split('/')[0]) if hp_str.split('/')[0].isdigit() else 0
        
        transient = state.transient_states[sk]
        diff = abs(transient.hp - hp_val)
        transient.hp = hp_val
        
        source_type, source_name = self._extract_from_tags(state, params, default_sk=sk)

        if typ == 'damage' and state._current_action and not source_type and state._current_action.target_sk == sk:
            state._current_action.damage_dealt = diff
            state._current_action.is_ko = (hp_val <= 0)
        else:
            sk_fact = self.generate_sk(state.battle_id, state.event_counter)
            parent_sk = state._current_action.sk_fact if state._current_action else None
            
            state.events.append(BattleEventFact(
                sk_fact=sk_fact, battle_id=state.battle_id, turn=state.turn, event_order=state.event_counter,
                timestamp=state.current_timestamp, event_category=typ.upper(), 
                event_detail=str(diff), sk_pokemon=sk, 
                source_type=source_type or 'indirect', source_name=source_name,
                parent_action_sk=parent_sk,
                replay_date=state.metadata['replay_date']
            ))

    def _handle_faint(self, state: BattleState, typ: str, params: List[str]):
        sk = self._get_or_create_pokemon(state, params[0])
        if sk: state.transient_states[sk].hp = 0

    def _handle_generic_event(self, state: BattleState, typ: str, params: List[str]):
        pokemon_targeted_events = {'status', 'curestatus', 'boost', 'unboost', 'item', 'enditem', 'ability', 'activate', 'cant'}
        
        sk = None
        if typ in pokemon_targeted_events and len(params) > 0:
            sk = self._get_or_create_pokemon(state, params[0])
            
        detail = params[1].strip() if len(params) > 1 else (params[0] if params else "")
        source_type, source_name = self._extract_from_tags(state, params, default_sk=sk)
        
        if typ == 'activate':
            if detail.startswith('ability:'):
                source_type = 'ability'
                detail = detail.replace('ability:', '').strip()
            elif detail.startswith('item:'):
                source_type = 'item'
                detail = detail.replace('item:', '').strip()

        if sk:
            if typ in ('status', 'curestatus'):
                state.transient_states[sk].status = detail if typ == 'status' else None
            elif typ in ('boost', 'unboost') and len(params) > 2:
                amount = int(params[2])
                state.transient_states[sk].boosts[detail] += amount if typ == 'boost' else -amount
            elif typ in ('item', 'enditem') or (typ == 'activate' and source_type == 'item'):
                info = state.pokemon_info[sk]
                if not info.item:
                    info.item = detail
                    info.item_revealed_turn = state.turn
            elif typ == 'ability' or (typ == 'activate' and source_type == 'ability'):
                info = state.pokemon_info[sk]
                if not info.ability:
                    info.ability = detail
                    info.ability_revealed_turn = state.turn

        sk_fact = self.generate_sk(state.battle_id, state.event_counter)
        parent_sk = state._current_action.sk_fact if state._current_action else None
        
        state.events.append(BattleEventFact(
            sk_fact=sk_fact, battle_id=state.battle_id, turn=state.turn, event_order=state.event_counter,
            timestamp=state.current_timestamp, event_category=typ.upper(), 
            event_detail=detail, sk_pokemon=sk, source_type=source_type, source_name=source_name,
            parent_action_sk=parent_sk,
            replay_date=state.metadata['replay_date']
        ))