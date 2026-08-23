import json
import logging
import os
import time

import requests
from dotenv import load_dotenv

from config.regions import SULSEL_REGIONS
from config.settings import BPS_BASE_URL

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s - %(message)s")
logger = logging.getLogger("var_mapper")

# Muat API Key dari .env (bukan .env.example)
load_dotenv()
BPS_API_KEY = os.getenv("BPS_API_KEY")

if not BPS_API_KEY:
    logger.error("BPS_API_KEY tidak ditemukan di .env! Harap masukkan API key yang baru.")
    exit(1)

OUTPUT_FILE = "config/domain_vars.json"

def fetch_json(params: dict) -> dict | None:
    try:
        resp = requests.get(BPS_BASE_URL, params=params, timeout=30)
        data = resp.json()
        if isinstance(data, dict) and data.get("status") == "OK":
            return data
    except Exception as e:
        logger.error(f"Request error: {e}")
    return None

def fetch_all_variables(domain: str) -> list[dict]:
    """Mengambil seluruh variabel yang ada di suatu domain"""
    all_vars = []
    page = 1
    while True:
        params = {
            "model": "var",
            "domain": domain,
            "lang": "ind",
            "page": str(page),
            "key": BPS_API_KEY,
        }
        data = fetch_json(params)
        if not data:
            break
            
        items = data.get("data", [])
        if len(items) >= 2 and isinstance(items[1], list):
            all_vars.extend(items[1])
            
        if len(items) >= 1 and isinstance(items[0], dict):
            meta = items[0]
            if page >= meta.get("pages", 1):
                break
        else:
            break
            
        page += 1
        time.sleep(0.5)
        
    return all_vars

def main():
    logger.info("Memulai pemetaan ID Variabel per Kabupaten...")
    
    mapping = {}
    
    for domain_code, domain_name in SULSEL_REGIONS.items():
        logger.info(f"🔍 Mencari variabel untuk {domain_code} ({domain_name})...")
        variables = fetch_all_variables(domain_code)
        
        # Default fallback (kasus terburuk pakai ID statis)
        domain_map = {
            "tpt": 52,
            "pdrb_total": 79,
            "inflasi_mtom": 1,
            "garis_kemiskinan": 64
        }
        
        # Pencarian TPT
        for v in variables:
            title = v.get("title", "").lower()
            var_id = v.get("var_id")
            
            # TPT
            if "tingkat pengangguran terbuka" in title:
                domain_map["tpt"] = var_id
            
            # PDRB Harga Berlaku
            elif "produk domestik regional bruto" in title and "harga berlaku" in title and "lapangan usaha" in title:
                domain_map["pdrb_total"] = var_id
                
            # Inflasi M-to-M
            elif "inflasi" in title and ("bulanan" in title or "m-to-m" in title):
                domain_map["inflasi_mtom"] = var_id
                
            # Garis Kemiskinan
            elif "garis kemiskinan" in title and "per kapita" not in title:
                domain_map["garis_kemiskinan"] = var_id

        mapping[domain_code] = domain_map
        logger.info(f"   => Ditemukan: TPT={domain_map['tpt']}, PDRB={domain_map['pdrb_total']}, Inflasi={domain_map['inflasi_mtom']}, GK={domain_map['garis_kemiskinan']}")
        
        # Simpan perlahan agar progress terlihat
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            json.dump(mapping, f, ensure_ascii=False, indent=2)
            
        time.sleep(1) # Jeda sopan ke API BPS
        
    logger.info(f"✅ Selesai! Pemetaan disimpan ke {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
