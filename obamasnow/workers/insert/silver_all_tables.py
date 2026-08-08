from pathlib import Path
import polars as pl
from pyiceberg.expressions import EqualTo
from obamasnow.parser.showdown_log_parser import ShowdownLogParser
from obamasnow.schemas.silver_layer import all_tables, SilverTable
from obamasnow.schemas.bronze_layer import replay_logs_table
from obamasnow.worker import LakehouseWorker


_WORKER_NAME = f"{Path(__file__).parent.name}-{Path(__file__).stem}"

def main():
    worker = LakehouseWorker(_WORKER_NAME)
    worker.logger.info(f"Buscando dados para ingestão da camada Silver..")
    table = worker.get_table(replay_logs_table.lh_name)
    df_replay_logs = table.scan(
        row_filter=EqualTo('gen','4')
    ).to_polars().unique()
    
    worker.logger.info(f"Preparando logs para o parser..")
    batch_logs = []
    for row in df_replay_logs.iter_rows(named=True):
        battle_id = row['replay_id']
        raw_log = row['raw_log']
        replay_date = row['replay_timestamp']
        
        # Formata como o parser espera (Lista de Listas de str)
        log_rows = [line.split('|') for line in raw_log.splitlines()]
        batch_logs.append((log_rows, battle_id, replay_date))
    
    worker.logger.info(f"Iniciando o parser..")
    parser = ShowdownLogParser()
    accumulated = parser.parse_batch(batch_logs)
    
    #converte 
    silver_dfs = {
        f'{SilverTable.namespace}.{table}': pl.DataFrame(data, strict=False)
        for table, data in accumulated.items()
    }
    
    #ingeri validando catalogo
    worker.logger.info('Iniciando ingestão dos dados..')
    for table, data in silver_dfs.items():
        arrow_batch = data.to_arrow()
        worker.ingest_pyarrow_data(table, arrow_batch)
        worker.logger.info(f'Inserido: {table}')
        
if __name__ == '__main__':
    main()