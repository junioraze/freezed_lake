import copy
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from dotenv import load_dotenv; load_dotenv()
import time
import os
import requests

##config
_from_txt = False #just for test

#showdown
GEN = os.getenv("GEN","gen4ou")
RANGE = os.getenv("RANGE",30)
URL_USER = "https://replay.pokemonshowdown.com/?format={}"
TIMEOUT = os.getenv("TIMEOUT",10)

#polaris
POLARIS_ENDPOINT = os.getenv("POLARIS_ENDPOINT", "http://polaris:8181")
POLARIS_PASS = os.getenv("POLARIS_USER", "")
POLARIS_PASS = os.getenv("POLARIS_PASS", "")
POLARIS_REALM = os.getenv("POLARIS_REALM")

CATALOG_BUCKET = os.getenv("CATALOG_BUCKET")

#minio
MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "http://minio:9000")
MINIO_USER = os.getenv("MINIO_USER", "")
MINIO_PASS = os.getenv("MINIO_PASS", "")

#dead
def _execute_log(url):
    text = requests.get(url).text
    dir = "logs/"
    filename = url.split('/')[-1]
    with open(dir + filename, "w", encoding="utf-8") as file:
        file.write(text)
    print(f'persisted file... {url}')
    
def get_replay_dimensions(url):
    replay_id = url.split('-')[-1]
    data = requests.get(f'{url}.log').text
    row = [replay_id]
    time_catcher = '|t:|'
    gen_catcher = '|gen|'
    tier_catcher = '|tier|'
    end_catcher = '|rule|'
    extract = lambda x:str(x).split('|')[-1]
    
    for r in data.splitlines():
        if r.startswith(time_catcher):
            row.append(extract(r))
        if r.startswith(gen_catcher):
            row.append(extract(r))
        if r.startswith(tier_catcher):
            row.append(extract(r))
        if r.startswith(end_catcher):
            break
        
    row.append(data)
    return row        

def get_replays_list(browser):
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

if __name__ == "__main__":

    browser = webdriver.Chrome()
    if _from_txt:
        with open('replays.txt','r') as file:
            replays = [replay.replace('\n','') for replay in file.readlines()]        
    else:
        replays = get_replays_list(browser)
        browser.quit()
        
    for r in replays:
        print(get_replay_dimensions(r))




