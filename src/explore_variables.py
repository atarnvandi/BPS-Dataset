"""
Script untuk menjelajahi dan mengekspor semua variabel BPS yang tersedia
di seluruh 24 kabupaten/kota Sulawesi Selatan ke dalam file CSV.

Output: config/variable_catalog.csv
Kolom:
  - domain_code: Kode wilayah BPS (e.g. 7301)
  - domain_name: Nama wilayah
  - var_id: ID variabel di BPS API
  - label: Nama lengkap variabel
  - unit: Satuan pengukuran (Persen, Rupiah, Miliar, dll)
  - subject: Topik/kategori variabel
  - variable_key: DIISI MANUAL — nama kunci untuk pipeline (e.g. tpt, pdrb_total)
  - selected: DIISI MANUAL — Y/N, apakah variabel ini mau di-fetch

Cara pakai:
  1. Jalankan script ini: PYTHONPATH=. python3 src/explore_variables.py
  2. Buka config/variable_catalog.csv di GitHub atau text editor
  3. Untuk setiap variabel yang ingin di-fetch:
     - Isi kolom 'variable_key' dengan nama kunci (contoh: tpt, pdrb_total, ipm, dll)
     - Ubah kolom 'selected' dari 'N' ke 'Y'
  4. Jalankan: PYTHONPATH=. python3 src/apply_selection.py
"""

import csv
import logging
import os
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

from config.regions import SULSEL_REGIONS
from config.settings import BPS_BASE_URL

logging.basicConfig(level=logging.INFO, format="%(levelname)s - %(message)s")
logger = logging.getLogger("explorer")

load_dotenv()
BPS_API_KEY = os.getenv("BPS_API_KEY")

OUTPUT_FILE = Path("config/variable_catalog.csv")
HEADERS = ["domain_code", "domain_name", "var_id", "label", "unit", "subject", "variable_key", "selected"]


def fetch_json(params: dict) -> dict | None:
    try:
        resp = requests.get(BPS_BASE_URL, params=params, timeout=30)
        data = resp.json()
        if isinstance(data, dict) and data.get("status") == "OK":
            return data
    except Exception as e:
        logger.warning(f"Request error: {e}")
    return None


def fetch_all_variables_for_domain(domain_code: str) -> list[dict]:
    """Mengambil SEMUA variabel yang terdaftar di domain tertentu."""
    all_vars = []
    page = 1

    while True:
        params = {
            "model": "var",
            "domain": domain_code,
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
            total_pages = meta.get("pages", 1)
            if page >= total_pages:
                break
        else:
            break

        page += 1
        time.sleep(0.3)

    return all_vars


def load_existing_catalog() -> dict:
    """
    Baca katalog yang sudah ada untuk mempertahankan pilihan user
    (variable_key dan selected) yang sudah diisi sebelumnya.
    Return: dict dengan key (domain_code, var_id) -> {variable_key, selected}
    """
    existing = {}
    if not OUTPUT_FILE.exists():
        return existing

    with open(OUTPUT_FILE, "r", encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            key = (row["domain_code"], row["var_id"])
            existing[key] = {
                "variable_key": row.get("variable_key", ""),
                "selected": row.get("selected", "N"),
            }
    logger.info(f"📖 Memuat {len(existing)} entri dari katalog yang sudah ada...")
    return existing


def main():
    if not BPS_API_KEY:
        logger.error("BPS_API_KEY tidak ditemukan di .env!")
        exit(1)

    logger.info("=" * 60)
    logger.info("BPS Variable Explorer")
    logger.info(f"Menjelajahi variabel untuk {len(SULSEL_REGIONS)} kabupaten/kota...")
    logger.info("=" * 60)

    # Muat pilihan user yang sudah ada (agar tidak hilang saat di-refresh)
    existing_selections = load_existing_catalog()

    all_rows = []
    total_vars = 0

    for domain_code, domain_name in SULSEL_REGIONS.items():
        logger.info(f"📡 {domain_code} ({domain_name})...")
        variables = fetch_all_variables_for_domain(domain_code)
        logger.info(f"   └ {len(variables)} variabel ditemukan")
        total_vars += len(variables)

        for v in variables:
            var_id = str(v.get("var_id", ""))
            label = v.get("title", "")
            unit = v.get("unit", "")
            subject = v.get("subj", "")

            # Pertahankan pilihan user sebelumnya jika ada
            key = (domain_code, var_id)
            prev = existing_selections.get(key, {})

            all_rows.append({
                "domain_code": domain_code,
                "domain_name": domain_name,
                "var_id": var_id,
                "label": label,
                "unit": unit,
                "subject": subject,
                "variable_key": prev.get("variable_key", ""),
                "selected": prev.get("selected", "N"),
            })

        time.sleep(1)  # Jeda sopan ke BPS

    # Tulis ke CSV
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=HEADERS)
        writer.writeheader()
        writer.writerows(all_rows)

    logger.info("")
    logger.info("=" * 60)
    logger.info(f"✅ Selesai! {total_vars} variabel dari {len(SULSEL_REGIONS)} wilayah")
    logger.info(f"📄 Disimpan ke: {OUTPUT_FILE}")
    logger.info("")
    logger.info("Langkah selanjutnya:")
    logger.info("  1. Buka config/variable_catalog.csv")
    logger.info("  2. Isi kolom 'variable_key' dan ubah 'selected' ke 'Y'")
    logger.info("  3. Jalankan: PYTHONPATH=. python3 src/apply_selection.py")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
