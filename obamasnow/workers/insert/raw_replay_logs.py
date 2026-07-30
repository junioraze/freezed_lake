import asyncio
import aiohttp
import time
import copy
import os
from pathlib import Path
import polars as pl
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from obamasnow.worker import LakehouseWorker

_GEN = "gen4ou"
_RANGE = int(os.getenv('RANGE'))
_URL_USER = "https://replay.pokemonshowdown.com/?format={}"
_TIMEOUT = 10
_WORKER_NAME = f"{Path(__file__).parent.name}-{Path(__file__).stem}"
_NAME_SPACE = os.getenv("NAME_SPACE")
_TABLE_NAME = os.getenv("TABLE_NAME")
_LH_TABLE = f"{_NAME_SPACE}.{_TABLE_NAME}"

def get_browser():
    opt = Options()
    opt.add_argument("--headless=new")
    opt.add_argument("--no-sandbox")
    opt.add_argument("--disable-dev-shm-usage")
    opt.add_argument("--disable-gpu")
    return webdriver.Chrome(options=opt)

def extract_replays_list(browser, logger):
    report = []
    first = True
    page_n = 1
    url = _URL_USER.format(_GEN)
    browser.get(url)
    
    while True:
        
        if _RANGE > 0 and _RANGE < len(report):
            report = report[:_RANGE]
            break
        
        if len(report) % 100 == 0:
            logger.info(f"{len(report)} uri's coletadas.")
        
        try:
            elem_present = EC.presence_of_element_located((By.CLASS_NAME, "blocklink"))
            WebDriverWait(browser, _TIMEOUT).until(elem_present)
            replays = browser.find_elements(By.TAG_NAME, "a")
            replays = [replay.get_attribute("href").replace("?p2", "") for replay in replays]
            replays = [replay for replay in replays if _GEN in replay or 'smogtours' in replay]
            replays = [replay for replay in replays if "?format" not in replay]
            report.extend(replays)
            plink = len(browser.find_elements(By.CLASS_NAME, "pagelink"))
            if plink > 0:
                if plink == 1 and not(first):
                    break
                if plink == 1 and first:
                    first = False
                page_n += 1
                url_n = f'{url}&page={page_n}'
                browser.get(url_n)
                time.sleep(1) #horroroso mas showdown e instantaneo
            else:
                break
        except TimeoutException:
            print("Timeout, page not loaded.")
    return copy.copy(report)

def collect_replay_urls(logger) -> list[str]:
    """Acessao showdown e busca a lista que sera enviada para o async."""
    browser = get_browser()
    try:
        return extract_replays_list(browser,logger)
    finally:
        browser.quit()

def parse_log_lines(data: str) -> tuple:
    """Função CPU-bound para parsear o log."""
    lines = data.splitlines()
    ts_str = next((l.split('|')[-1] for l in lines if l.startswith('|t:|')), None)
    gen = next((l.split('|')[-1] for l in lines if l.startswith('|gen|')), 'unknown')
    tier = next((l.split('|')[-1] for l in lines if l.startswith('|tier|')), 'unknown')
    return ts_str, gen, tier

async def fetch_replay_data(session: aiohttp.ClientSession, url: str) -> dict:
    """Baixa o log e parseia de forma síncrona dentro da task."""
    replay_id = url.split('-')[-1]
    log_url = f'{url}.log'
    
    try:
        async with session.get(log_url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
            if resp.status == 200:
                data = await resp.text()
            else:
                data = ""
    except Exception:
        data = ""
    
    # Parse (CPU-bound) 
    ts_str, gen, tier = parse_log_lines(data)
    
    return {
        "replay_id": replay_id,
        "gen": gen,
        "tier": tier,
        "ts_str": ts_str or "0",
        "raw_log": data
    }

async def fetch_all_replays(
    urls: list[str], 
    max_concurrent: int = 50, 
    log_every: int = 100,
    logger = None
) -> list[dict]:
    """
    Baixa todos os logs com paralelismo controlado e logs de progresso.
    """
    total = len(urls)
    if logger:
        logger.info(f"Iniciando download assíncrono de {total} replays (concorrência: {max_concurrent})")
    
    connector = aiohttp.TCPConnector(limit=max_concurrent, limit_per_host=10)
    timeout = aiohttp.ClientTimeout(total=60)
    results = []
    
    # Contadores de progresso
    success_count = 0
    fail_count = 0
    start_time = time.time()
    
    async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def fetch_with_limit(url: str):
            async with semaphore:
                return await fetch_replay_data(session, url)
        
        # Cria as tarefas
        tasks = [fetch_with_limit(url) for url in urls]
        
        # Itera conforme as tarefas são concluídas (as_completed)
        for coro in asyncio.as_completed(tasks):
            try:
                result = await coro
                if result and isinstance(result, dict):
                    results.append(result)
                    success_count += 1
                else:
                    fail_count += 1
            except Exception as e:
                fail_count += 1
                if logger:
                    logger.debug(f"Erro em requisição: {e}")
            
            completed = success_count + fail_count
            
            # Log de progresso a cada N itens OU no final
            if completed % log_every == 0 or completed == total:
                elapsed = time.time() - start_time
                rate = completed / elapsed if elapsed > 0 else 0
                eta = (total - completed) / rate if rate > 0 else 0
                
                if logger:
                    logger.info(
                        f"Progresso: {completed}/{total} completadas. "
                        f"Sucessos: {success_count}, Falhas: {fail_count}. "
                        f"Taxa: {rate:.1f} req/s. ETA: {eta:.1f}s"
                    )
    
    if logger:
        logger.info(
            f"Download concluído. Total: {completed}, "
            f"Sucessos: {success_count}, Falhas: {fail_count}. "
            f"Tempo total: {elapsed:.1f}s"
        )
    
    return results

def main():
    worker = LakehouseWorker(_WORKER_NAME)
    worker.logger.info(f"Iniciando scraping dos {_RANGE} replays.")
    
    # FASE 1: Coleta de URLs (síncrono)
    urls = collect_replay_urls(worker.logger)
    worker.logger.info(f"Coletadas {len(urls)} URLs")
    
    if not urls:
        worker.logger.warning("Nenhuma URL coletada. Encerrando.")
        return
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        raw_data = loop.run_until_complete(
            fetch_all_replays(
                urls, 
                max_concurrent=50, 
                log_every=100,
                logger=worker.logger
            )
        )
    finally:
        loop.close()
    
    worker.logger.info(f"Baixados {len(raw_data)} logs com sucesso")
    
    if raw_data:
        df = pl.DataFrame(raw_data)
        df = df.with_columns([
            pl.col("ts_str")
                .cast(pl.Int64, strict=False)
                .mul(1000)
                .cast(pl.Datetime(time_unit='ms'))
                .alias("replay_timestamp"),
            pl.lit(datetime.now()).alias("ingestion_timestamp")
        ]).drop('ts_str')
        
        arrow_batch = df.to_arrow()
        worker.ingest_pyarrow_data(_LH_TABLE, arrow_batch)
        worker.logger.info(f"Inseridos {len(arrow_batch)} registros em {_LH_TABLE}")
    else:
        worker.logger.warning("Nenhum dado para inserir.")

if __name__ == '__main__':
    main()