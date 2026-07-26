import copy
import time
import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
import requests
import polars as pl
from datetime import datetime
from lakehouse_worker import LakehouseWorker, logger
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from dotenv import load_dotenv; load_dotenv()

#showdown
GEN = os.getenv("GEN","gen4ou")
RANGE = int(os.getenv("RANGE",30))
URL_USER = "https://replay.pokemonshowdown.com/?format={}"
TIMEOUT = os.getenv("TIMEOUT",10)

#target
LAKEHOUSE_TABLE = os.getenv("LAKEHOUSE_TABLE")

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
    url = URL_USER.format(GEN)
    browser.get(url)
    while True:
        if RANGE > 0 and RANGE < len(report): #hardcode condition to limit replays range
            report = report[:RANGE]
            break
        try:
            
            elem_present = EC.presence_of_element_located((By.CLASS_NAME, "blocklink"))
            WebDriverWait(browser, TIMEOUT).until(elem_present)
            replays = browser.find_elements(By.TAG_NAME, "a")
            replays = [replay.get_attribute("href").replace("?p2", "") for replay in replays]
            replays = [replay for replay in replays if GEN in replay or 'smogtours' in replay]
            replays = [replay for replay in replays if "?format" not in replay]
            report.extend(replays)
            print(replays)
            plink = len(browser.find_elements(By.CLASS_NAME, "pagelink"))
            print(f'plink value: {plink}')
            print(f'replays: {len(report)}')
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
    logger.info(f"Iniciando extração dos dados")
    browser = webdriver.Chrome()
    replays = extract_replays_list(browser)
    browser.quit()
    raw_data = [extract_replay_data_dimensions(r) for r in replays]
    
    logger.info(f"Montando batch de importação")
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
    
    logger.info(f"Inserindo em {LAKEHOUSE_TABLE}")
    worker = LakehouseWorker()
    table = worker.get_table(LAKEHOUSE_TABLE)
    table_schema = table.schema().as_arrow()
    schema_field_order = [field.name for field in table_schema]
    #forçando schema
    arrow_batch = arrow_batch.select(schema_field_order)
    table.append(arrow_batch.cast(table_schema))
    logger.info(f"Dados importados em {LAKEHOUSE_TABLE}")
    

if __name__ == "__main__":
    main()




