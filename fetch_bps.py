#!/usr/bin/env python3
"""
BPS Data Pipeline — Fetch Script (Staging Layer)

Mengambil data statistik ekonomi regional dari BPS Web API
untuk 24 kabupaten/kota di Sulawesi Selatan, menyimpan raw JSON
response sebagai staging layer sebelum transformasi dan loading.

Usage:
    python fetch_bps.py                     # fetch semua variabel & wilayah
    python fetch_bps.py --dry-run           # validasi config tanpa request
    python fetch_bps.py --variable tpt      # fetch 1 variabel saja
    python fetch_bps.py --domain 7371       # fetch 1 wilayah saja
    python fetch_bps.py --variable tpt --domain 7371  # kombinasi

Exit codes:
    0 = semua request berhasil
    1 = ada request yang gagal (partial success)
    2 = error fatal (config/setup)
"""

import argparse
import math
import sys
import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from config import (
    BPS_VARIABLES,
    DEFAULT_YEARS,
    DELAY_BETWEEN_REQUESTS,
    SULSEL_REGIONS,
)
from config.settings import BPS_API_KEY
from src.api_client import BPSApiClient
from src.logger_setup import setup_logger
from src.raw_storage import RawJsonStorage
from src.transformer import transform_raw_to_csv


@dataclass
class FailedRequest:
    """Detail satu request yang gagal."""

    variable_key: str
    domain: str
    domain_name: str
    error: str


@dataclass
class PipelineStats:
    """Statistik keseluruhan pipeline run."""

    total: int = 0
    success: int = 0
    failed: int = 0
    failed_details: list[FailedRequest] = field(default_factory=list)
    start_time: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def elapsed_seconds(self) -> float:
        return (datetime.now(timezone.utc) - self.start_time).total_seconds()


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Fetch data statistik BPS untuk Sulawesi Selatan",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python fetch_bps.py                          # fetch semua
  python fetch_bps.py --dry-run                # validasi config
  python fetch_bps.py --variable pdrb_perkapita
  python fetch_bps.py --domain 7371
  python fetch_bps.py --variable tpt --domain 7371
        """,
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validasi config dan tampilkan rencana fetch tanpa kirim request",
    )
    parser.add_argument(
        "--variable",
        type=str,
        choices=list(BPS_VARIABLES.keys()),
        help="Fetch hanya variabel tertentu",
    )
    parser.add_argument(
        "--domain",
        type=str,
        help="Fetch hanya wilayah tertentu (kode BPS, e.g. 7371)",
    )
    return parser.parse_args()


def validate_config(logger) -> bool:
    """Validasi konfigurasi sebelum fetch."""
    is_valid = True

    if not BPS_API_KEY:
        logger.error("❌ BPS_API_KEY belum di-set! Set via .env atau environment.")
        is_valid = False

    if not SULSEL_REGIONS:
        logger.error("❌ SULSEL_REGIONS kosong!")
        is_valid = False

    if not BPS_VARIABLES:
        logger.error("❌ BPS_VARIABLES kosong!")
        is_valid = False

    return is_valid


def chunk_years(years: list[int], max_per_chunk: int = 1) -> list[list[int]]:
    """
    Split list tahun menjadi chunks.

    BPS API di level kabupaten/kota hanya menerima 1 tahun per request
    untuk parameter 'th'. Default max_per_chunk=1 untuk kompatibilitas
    maksimal.

    Contoh: [2021,2022,2023] → [[2021],[2022],[2023]]
    """
    return [years[i:i + max_per_chunk] for i in range(0, len(years), max_per_chunk)]


def print_plan(
    variables: dict,
    regions: dict,
    year_chunks: list[list[int]],
    logger,
    dry_run: bool = False,
):
    """Tampilkan rencana fetch."""
    total = len(variables) * len(regions) * len(year_chunks)
    mode = "DRY RUN" if dry_run else "LIVE"

    logger.info("=" * 60)
    logger.info(f"BPS Data Fetch Pipeline — {mode}")
    logger.info("=" * 60)
    logger.info(f"Variabel   : {len(variables)}")
    for key, var in variables.items():
        logger.info(f"  - {key} (var_id={var['var_id']}): {var['name']}")
    logger.info(f"Wilayah    : {len(regions)} kabupaten/kota")
    logger.info(f"Tahun      : {DEFAULT_YEARS[0]}-{DEFAULT_YEARS[-1]} ({len(year_chunks)} requests per variabel/wilayah)")
    logger.info(f"Total req  : {total}")
    logger.info("=" * 60)


def print_summary(stats: PipelineStats, logger):
    """Tampilkan summary hasil fetch."""
    elapsed = stats.elapsed_seconds
    minutes = int(elapsed // 60)
    seconds = int(elapsed % 60)

    logger.info("")
    logger.info("=" * 60)
    logger.info("FETCH SUMMARY")
    logger.info("=" * 60)
    logger.info(f"✅ Berhasil : {stats.success}/{stats.total}")
    logger.info(f"❌ Gagal    : {stats.failed}/{stats.total}")
    logger.info(f"⏱️  Durasi   : {minutes}m {seconds}s")

    if stats.failed_details:
        logger.info("")
        logger.info("Detail request gagal:")
        for fail in stats.failed_details:
            logger.info(
                f"  - {fail.variable_key} / {fail.domain} "
                f"({fail.domain_name}): {fail.error}"
            )

    logger.info("=" * 60)


def run_fetch(
    variables: dict,
    regions: dict,
    dry_run: bool = False,
) -> PipelineStats:
    """
    Main fetch loop.

    Args:
        variables: Dict variabel yang akan di-fetch
        regions: Dict wilayah yang akan di-fetch
        dry_run: Jika True, hanya tampilkan rencana tanpa request

    Returns:
        PipelineStats dengan statistik hasil
    """
    logger = setup_logger()
    stats = PipelineStats()

    # BPS API kabupaten: 1 tahun per request
    year_chunks = chunk_years(DEFAULT_YEARS)
    stats.total = len(variables) * len(regions) * len(year_chunks)

    # Tampilkan rencana
    print_plan(variables, regions, year_chunks, logger, dry_run)

    if dry_run:
        logger.info("🏁 Dry run selesai. Tidak ada request yang dikirim.")
        return stats

    # Validasi config
    if not validate_config(logger):
        logger.error("❌ Config validation gagal. Abort.")
        sys.exit(2)

    # Inisialisasi components
    storage = RawJsonStorage()
    counter = 0

    with BPSApiClient() as client:
        # Load dynamic mapping jika ada
        domain_vars_map = {}
        map_path = Path("config/domain_vars.json")
        if map_path.exists():
            import json
            with open(map_path, "r", encoding="utf-8") as f:
                domain_vars_map = json.load(f)
                
        for var_key, var_info in variables.items():
            default_var_id = var_info["var_id"]
            var_name = var_info["name"]

            logger.info("")
            logger.info(f"📊 Fetching variabel: {var_name}")
            logger.info("-" * 40)

            var_success = 0
            var_fail = 0

            for domain_code, domain_name in regions.items():
                # Tentukan var_id (Dinamis dari map, atau fallback statis)
                var_id = domain_vars_map.get(domain_code, {}).get(var_key, default_var_id)
                
                for yr_chunk in year_chunks:
                    counter += 1
                    yr_label = f"{yr_chunk[0]}-{yr_chunk[-1]}" if len(yr_chunk) > 1 else str(yr_chunk[0])
                    label = f"[{counter}/{stats.total}]"

                    logger.info(
                        f"{label} {var_key} → {domain_code} ({domain_name}) [{yr_label}]...",
                    )

                    if storage.is_exists(domain_code, var_key, var_id, yr_label):
                        logger.info(f"{label} ⏭️ SKIPPED: {var_key} → {domain_code} [{yr_label}] (Sudah ada)")
                        var_success += 1
                        stats.success += 1
                        continue

                    # Fetch dari BPS API — max 2 tahun per request
                    result = client.fetch_data(
                        domain=domain_code,
                        var_id=var_id,
                        years=yr_chunk,
                    )

                    if result.success:
                        # Simpan raw JSON
                        fetch_time = datetime.now(timezone.utc)
                        saved_path = storage.save(
                            domain=domain_code,
                            variable_key=var_key,
                            var_id=var_id,
                            year=yr_label,
                            data=result.data,
                            timestamp=fetch_time,
                        )
                        retry_note = (
                            f" (retry {result.attempts})" if result.attempts > 1 else ""
                        )
                        logger.info(
                            f"{label} ✅ OK{retry_note} → {saved_path.name}"
                        )
                        stats.success += 1
                        var_success += 1

                    else:
                        logger.warning(
                            f"{label} ❌ GAGAL: {result.error_msg}"
                        )
                        stats.failed += 1
                        var_fail += 1
                        stats.failed_details.append(
                            FailedRequest(
                                variable_key=var_key,
                                domain=domain_code,
                                domain_name=domain_name,
                                error=f"[{yr_label}] {result.error_msg or 'Unknown error'}",
                            )
                        )

                        # Tetap simpan response jika ada (untuk debugging)
                        if result.data:
                            fetch_time = datetime.now(timezone.utc)
                            error_storage = RawJsonStorage()
                            error_storage.save(
                                domain=domain_code,
                                variable_key=f"_errors/{var_key}",
                                var_id=var_id,
                                data=result.data,
                                timestamp=fetch_time,
                            )

                    # Delay antar request
                    if counter < stats.total:
                        time.sleep(DELAY_BETWEEN_REQUESTS)

            # Summary per variabel
            logger.info(
                f"  ↳ {var_name}: {var_success} berhasil, {var_fail} gagal"
            )

    return stats


def update_readme_dashboard(stats: PipelineStats):
    """Update README.md dengan baris log baru di bawah FETCH_LOG_START."""
    readme_path = Path("README.md")
    if not readme_path.exists():
        return
        
    content = readme_path.read_text(encoding="utf-8")
    
    # Format baris baru
    # Runner GitHub Actions memakai UTC, jadi zona waktu harus eksplisit.
    date_str = datetime.now(ZoneInfo("Asia/Jakarta")).strftime("%Y-%m-%d %H:%M:%S WIB")
    minutes = int(stats.elapsed_seconds // 60)
    seconds = int(stats.elapsed_seconds % 60)
    duration_str = f"{minutes}m {seconds}s"
    
    # Hitung jumlah skip (berhasil tapi tidak lewat HTTP)
    total_skip = stats.success  # Asumsi sukses yang durasinya sangat cepat adalah skip
    # (Untuk perbaikan ke depannya, stats bisa di-extend dengan field 'skipped')
    
    new_row = f"| {date_str} | {stats.success} | {stats.failed} | - | {duration_str} |\n"
    
    # Sisipkan tepat di bawah baris pemisah tabel (| --- |) setelah marker START.
    # Marker harus berada di luar tabel, kalau tidak GitHub tidak me-render tabelnya.
    marker = "<!-- FETCH_LOG_START -->"
    start = content.find(marker)
    if start == -1:
        return
    sep = content.find("| ---", start)
    if sep == -1:
        return
    insert_at = content.index("\n", sep) + 1
    content = content[:insert_at] + new_row + content[insert_at:]
    readme_path.write_text(content, encoding="utf-8")

def main():
    """Entry point."""
    args = parse_args()

    # Filter variabel dan region berdasarkan CLI args
    variables = BPS_VARIABLES
    regions = SULSEL_REGIONS

    if args.variable:
        if args.variable not in BPS_VARIABLES:
            print(f"Error: variabel '{args.variable}' tidak ditemukan.")
            print(f"Pilihan: {', '.join(BPS_VARIABLES.keys())}")
            sys.exit(2)
        variables = {args.variable: BPS_VARIABLES[args.variable]}

    if args.domain:
        if args.domain not in SULSEL_REGIONS:
            print(f"Error: domain '{args.domain}' tidak ditemukan.")
            print(f"Pilihan: {', '.join(SULSEL_REGIONS.keys())}")
            sys.exit(2)
        regions = {args.domain: SULSEL_REGIONS[args.domain]}

    # Run pipeline
    stats = run_fetch(
        variables=variables,
        regions=regions,
        dry_run=args.dry_run,
    )

    # Tampilkan summary
    logger = setup_logger()
    if not args.dry_run:
        print_summary(stats, logger)
        
        # Eksekusi Transformasi CSV
        try:
            logger.info("🔄 Menjalankan transformasi data mentah ke CSV...")
            transform_raw_to_csv()
        except Exception as e:
            logger.error(f"❌ Gagal melakukan transformasi: {e}")
            
        try:
            update_readme_dashboard(stats)
            logger.info("✅ Dashboard README.md diupdate.")
        except Exception as e:
            logger.error(f"❌ Gagal update README: {e}")

    # Exit code
    # Sengaja tidak sys.exit(1) jika ada yang gagal, agar Git Scraping 
    # tetap lanjut menge-commit data-data yang berhasil didownload.
    sys.exit(0)


if __name__ == "__main__":
    main()
