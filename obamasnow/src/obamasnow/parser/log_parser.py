import hashlib
from typing import List, Tuple, Optional, Dict, Callable, Any, Type
import logging

class EventLogParser:
    """
    Motor base para processamento de logs baseados em eventos.
    Utiliza Registry Pattern e fornece utilitários comuns de Data Engineering.
    """
    
    def __init__(self, state_class: Type, event_separator: str = '|'):
        self.state_class = state_class
        self.event_separator = event_separator
        self.handlers: Dict[str, Callable] = {}
        self._fallback_handler: Optional[Callable] = None
        
    def register(self, event_types: List[str], handler: Callable) -> None:
        """Registra um único handler para múltiplos tipos de eventos."""
        for event_type in event_types:
            self.handlers[event_type] = handler
            
    def register_fallback(self, handler: Callable) -> None:
        self._fallback_handler = handler

    @staticmethod
    def generate_sk(*args: Any) -> str:
        """
        Gera uma Surrogate Key determinística (MD5) combinando n argumentos.
        Essencial para Data Mesh / Lakehouse.
        """
        hash_input = "_".join(str(arg).strip() for arg in args).encode('utf-8')
        return hashlib.md5(hash_input).hexdigest()
        
    def parse_line(self, state: Any, row: List[str]) -> None:
        if not row or len(row) < 2:
            return
            
        original_type = row[1].strip()
        params = [x.strip() for x in row[2:]]
        
        normalized = original_type.replace('-', '').replace(':', '').lower()
        if normalized == 't':
            normalized = 'timestamp'
            
        handler = self.handlers.get(normalized, self._fallback_handler)
        if handler:
            try:
                handler(state, normalized, params)
            except Exception as e:
                logging.error(f"Falha ao processar a tag [{original_type}]. Motivo: {e}")
        
    def parse(self, log_rows: Any, *args, **kwargs) -> Any:
        raise NotImplementedError()
        
    def parse_batch(self, batch_logs: List[Any], *args, **kwargs) -> Any:
        raise NotImplementedError()