import copy
from pathlib import Path
import time
import requests
import polars as pl
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from obamasnow.worker import LakehouseWorker
from dotenv import load_dotenv

load_dotenv()

_GEN = "gen4ou"
_RANGE = 30
_URL_USER = "https://replay.pokemonshowdown.com/?format={}"
_TIMEOUT = 10
_WORKER_NAME = f"{Path(__file__).parent.name}-{Path(__file__).stem}"
_NAME_SPACE = "raw"
_TABLE_NAME = "replay_logs"
_LH_TABLE = f"{_NAME_SPACE}.{_TABLE_NAME}"

def get_browser():
    opt = Options()
    # sem interface gráfica 
    opt.add_argument(argument="--headless=new") 
    
    # Evita problemas de permissão e memória compartilhada no container Linux
    opt.add_argument(argument="--no-sandbox")
    opt.add_argument(argument="--disable-dev-shm-usage")
    opt.add_argument(argument="--disable-gpu")

    # Inicializa o navegador apontando para os drivers do sistema
    return webdriver.Chrome(options=opt)
    

def extract_replay_data_dimensions(url):
    replay_id = url.split('-')[-1]
    data = requests.get(f'{url}.log').text
    lines = data.splitlines()
    ts_str = next((l.split('|')[-1] for l in lines if l.startswith('|t:|')), None)
    gen = next((l.split('|')[-1] for l in lines if l.startswith('|gen|')), 'unknown')
    tier = next((l.split('|')[-1] for l in lines if l.startswith('|tier|')), 'unknown')
    return {
        "replay_id": replay_id,
        "gen": gen,
        "tier": tier,
        "ts_str": ts_str or "0",
        "raw_log": data
    }

def extract_replays_list(browser):
    report = []
    first = True
    page_n = 1
    url = _URL_USER.format(_GEN)
    browser.get(url)
    while True:
        if _RANGE > 0 and _RANGE < len(report): #hardcode condition to limit replays range
            report = report[:_RANGE]
            break
        try:
            
            elem_present = EC.presence_of_element_located((By.CLASS_NAME, "blocklink"))
            WebDriverWait(browser, _TIMEOUT).until(elem_present)
            replays = browser.find_elements(By.TAG_NAME, "a")
            replays = [replay.get_attribute("href").replace("?p2", "") for replay in replays]
            replays = [replay for replay in replays if _GEN in replay or 'smogtours' in replay]
            replays = [replay for replay in replays if "?format" not in replay]
            report.extend(replays)
            plink = len(browser.find_elements(By.CLASS_NAME, "pagelink"))
            #recursive operation in while for drop lists
            if plink > 0:
                if plink == 1 and not(first):
                    break
                if plink == 1 and first:
                    first = False

                page_n += 1
                url_n = f'{url}&page={page_n}'
                browser.get(url_n)
                time.sleep(1)
            else:
                break
        except TimeoutException:
            print("Timeout, page not loaded.")
            
    return copy.copy(report)

def main():
    worker = LakehouseWorker(_WORKER_NAME)
    worker.logger.info("Iniciando scrapping dos replays")
    browser = get_browser()
    try:
        replays = extract_replays_list(browser)
    finally:
        browser.quit()
    raw_data = [extract_replay_data_dimensions(r) for r in replays]
    
    worker.logger.info(f"Montando batch de importação files:{len(raw_data)}")
    df = pl.DataFrame(raw_data)
    df = df.with_columns([
        pl.col("ts_str")
            .cast(pl.Int64, strict=False)
            .mul(1000)
            .cast(pl.Datetime(time_unit='ms'))
            .alias("replay_timestamp"),
        pl.lit(datetime.now())
            .alias("ingestion_timestamp")
    ]).drop('ts_str')
    arrow_batch = df.to_arrow()
    
    worker.logger.info("Validando catálogo e inserindo dados.")
    worker.ingest_pyarrow_data(_LH_TABLE, arrow_batch)
    worker.logger.info(f"Inseridos {len(arrow_batch)} registros em {_LH_TABLE}")
    
if __name__ == '__main__':
    main()