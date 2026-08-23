"""
Settings umum untuk BPS data pipeline.

Semua konfigurasi yang mengatur perilaku fetcher: URL, timeout, retry,
output directory, dll. Environment-specific values dibaca dari .env file.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env file jika ada
load_dotenv()

# ─── Paths ────────────────────────────────────────────────────────────────────
# Base directory = root project (parent dari folder config/)
BASE_DIR = Path(__file__).resolve().parent.parent

RAW_DATA_DIR = BASE_DIR / "data" / "raw"
LOG_DIR = BASE_DIR / "logs"

# ─── BPS API ──────────────────────────────────────────────────────────────────
BPS_BASE_URL = "https://webapi.bps.go.id/v1/api/list"
BPS_API_KEY = os.getenv("BPS_API_KEY", "")

# ─── Data Range ───────────────────────────────────────────────────────────────
# Tahun yang akan di-fetch (bisa dioverride via CLI args)
DEFAULT_YEARS = list(range(2021, 2026))  # 2021, 2022, 2023, 2024, 2025

# Mapping dari kalender tahun (int) ke BPS period ID ('th' parameter)
# BPS API mewajibkan th=121 untuk 2021, 122 untuk 2022, dst (berdasarkan model=th)
YEAR_TO_TH_ID = {
    2021: 121,
    2022: 122,
    2023: 123,
    2024: 124,
    2025: 125,
}

# ─── Retry & Rate Limiting ────────────────────────────────────────────────────
MAX_RETRIES = 5                    # Jumlah maksimum retry per request
BACKOFF_BASE = 2                   # Base untuk exponential backoff (detik)
REQUEST_TIMEOUT = 30               # Timeout per HTTP request (detik)
DELAY_BETWEEN_REQUESTS = 1.0       # Delay antar request untuk hindari rate-limit (detik)

# ─── Validation ───────────────────────────────────────────────────────────────
if not BPS_API_KEY:
    import warnings
    warnings.warn(
        "BPS_API_KEY belum di-set! Pastikan ada di .env atau environment variable. "
        "Fetch akan gagal tanpa API key yang valid.",
        UserWarning,
        stacklevel=2,
    )
