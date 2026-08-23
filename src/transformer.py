import csv
import json
import logging
from pathlib import Path
from typing import Any

from config.regions import SULSEL_REGIONS
from config.settings import RAW_DATA_DIR
from config.variables import BPS_VARIABLES

logger = logging.getLogger("bps_pipeline")


def transform_raw_to_csv(output_csv: Path | str = "data/clean/bps_sulsel.csv"):
    """
    Membaca semua raw JSON BPS dan merangkumnya menjadi satu file CSV yang bersih.
    """
    output_path = Path(output_csv)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Kumpulkan data dari raw/
    raw_dir = Path(RAW_DATA_DIR)
    if not raw_dir.exists():
        logger.warning(f"Direktori {raw_dir} tidak ditemukan.")
        return

    csv_rows = []
    
    # Iterasi semua file json di data/raw/*/*/*.json
    for json_file in raw_dir.rglob("*.json"):
        if "_errors" in str(json_file):
            continue
            
        try:
            with open(json_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                
            meta = data.get("fetch_metadata", {})
            raw = data.get("raw_response", {})
            
            domain_code = meta.get("domain")
            domain_name = SULSEL_REGIONS.get(domain_code, "Unknown")
            var_key = meta.get("variable_key")
            var_name = BPS_VARIABLES.get(var_key, {}).get("name", var_key)
            
            # Ambil tahun dari nama file (contoh: 7371_52_2025.json -> 2025)
            # Berjaga-jaga jika 'year' tidak ada di metadata JSON lama
            year = meta.get("year")
            if not year:
                year = json_file.stem.split("_")[-1]
            
            datacontent = raw.get("datacontent", {})
            if not datacontent:
                continue
                
            # Logika ekstraksi nilai
            # Jika hanya ada 1 data (seperti TPT, Kemiskinan, Inflasi)
            if len(datacontent) == 1:
                val = list(datacontent.values())[0]
            else:
                # Jika ada banyak data dimensi (seperti PDRB yg punya banyak sektor),
                # kita ambil angka terbesarnya sebagai "Total" PDRB sementara, 
                # karena Total selalu merupakan akumulasi seluruh sektor.
                val = max(datacontent.values())
                
            csv_rows.append({
                "domain_code": domain_code,
                "domain_name": domain_name,
                "year": year,
                "variable": var_key,
                "variable_name": var_name,
                "value": val
            })
            
        except Exception as e:
            logger.error(f"Gagal memparse file {json_file.name}: {e}")
            
    if not csv_rows:
        logger.warning("Tidak ada data valid yang bisa ditransformasi.")
        return
        
    # Urutkan berdasarkan wilayah, variabel, dan tahun
    csv_rows.sort(key=lambda x: (x["domain_code"], x["variable"], str(x["year"])))
    
    # Tulis ke CSV
    headers = ["domain_code", "domain_name", "year", "variable", "variable_name", "value"]
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        writer.writerows(csv_rows)
        
    logger.info(f"✅ Transformasi selesai. {len(csv_rows)} baris data disimpan ke {output_path}")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    transform_raw_to_csv()
