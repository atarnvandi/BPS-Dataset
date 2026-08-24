"""
Script untuk membaca pilihan user dari variable_catalog.csv
dan memperbarui config/domain_vars.json secara otomatis.

Cara pakai:
  Setelah mengedit config/variable_catalog.csv (isi variable_key & ubah selected=Y):
  PYTHONPATH=. python3 src/apply_selection.py
"""

import csv
import json
import logging
from collections import defaultdict
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s - %(message)s")
logger = logging.getLogger("apply_selection")

CATALOG_FILE = Path("config/variable_catalog.csv")
OUTPUT_FILE = Path("config/domain_vars.json")


def main():
    if not CATALOG_FILE.exists():
        logger.error(f"File katalog tidak ditemukan: {CATALOG_FILE}")
        logger.error("Jalankan dulu: PYTHONPATH=. python3 src/explore_variables.py")
        exit(1)

    logger.info(f"Membaca pilihan dari {CATALOG_FILE}...")

    # Baca seluruh katalog, ambil yang selected=Y dan punya variable_key
    selected_rows = []
    skipped_no_key = 0
    skipped_not_selected = 0

    with open(CATALOG_FILE, "r", encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            if row.get("selected", "N").strip().upper() != "Y":
                skipped_not_selected += 1
                continue
            if not row.get("variable_key", "").strip():
                logger.warning(
                    f"  ⚠️  {row['domain_code']} var_id={row['var_id']} ({row['label'][:40]}) "
                    f"sudah selected=Y tapi variable_key kosong — dilewati!"
                )
                skipped_no_key += 1
                continue

            selected_rows.append(row)

    logger.info(f"  └ {len(selected_rows)} variabel terpilih")
    logger.info(f"  └ {skipped_not_selected} belum dipilih (selected=N)")
    if skipped_no_key:
        logger.warning(f"  └ {skipped_no_key} ada selected=Y tapi variable_key kosong (dilewati)")

    if not selected_rows:
        logger.error("Tidak ada variabel yang dipilih! Pastikan ada baris dengan selected=Y dan variable_key terisi.")
        exit(1)

    # Kelompokkan menjadi struktur domain_vars.json
    # Format: { "7301": {"tpt": 52, "pdrb_total": 196, ...}, ... }
    domain_map: dict[str, dict[str, int]] = defaultdict(dict)

    for row in selected_rows:
        domain_code = row["domain_code"]
        var_key = row["variable_key"].strip()
        var_id = int(row["var_id"])

        if var_key in domain_map[domain_code]:
            existing = domain_map[domain_code][var_key]
            logger.warning(
                f"  ⚠️  Duplikat: {domain_code} '{var_key}' sudah ada (var_id={existing}), "
                f"ditimpa dengan var_id={var_id}"
            )

        domain_map[domain_code][var_key] = var_id

    # Simpan ke domain_vars.json
    # Sort by domain_code agar rapi
    sorted_map = dict(sorted(domain_map.items()))

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(sorted_map, f, ensure_ascii=False, indent=2)

    logger.info("")
    logger.info("=" * 60)
    logger.info(f"✅ Selesai! config/domain_vars.json diperbarui.")
    logger.info(f"   {len(sorted_map)} wilayah, {len(selected_rows)} total pilihan variabel.")
    logger.info("")

    # Ringkasan variable_key yang akan di-fetch
    all_keys = set()
    for v in domain_map.values():
        all_keys.update(v.keys())

    logger.info(f"Variabel yang akan di-fetch ({len(all_keys)}):")
    for k in sorted(all_keys):
        count = sum(1 for d in domain_map.values() if k in d)
        logger.info(f"  - {k:<25} ({count} wilayah)")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
