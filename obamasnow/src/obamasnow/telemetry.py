# src/obamasnow/telemetry.py
import logging

def get_logger(worker_name: str) -> logging.Logger:
    """
    Trocar futuramente para OpenTelemetry (TraceProvider, LogProvider).
    """
    logger = logging.getLogger(worker_name)
    
    if not logger.handlers:
        handler = logging.StreamHandler()
        # Formato que facilita o parse por ferramentas de observabilidade
        formatter = logging.Formatter(
            '%(asctime)s - [%(name)s] - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        
    return logger