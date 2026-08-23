"""
Logger setup untuk BPS data pipeline.

Konfigurasi dual-handler logging:
- Console (INFO): output ringkas ke terminal
- File (DEBUG): log detail ke file untuk troubleshooting

Log file disimpan di: logs/fetch_{timestamp}.log
"""

import logging
import sys
from datetime import datetime
from pathlib import Path

from config.settings import LOG_DIR


def setup_logger(name: str = "bps_pipeline") -> logging.Logger:
    """
    Setup dan return logger dengan console + file handler.

    Args:
        name: Nama logger (default: "bps_pipeline")

    Returns:
        logging.Logger: Logger yang sudah dikonfigurasi
    """
    logger = logging.getLogger(name)

    # Hindari duplicate handler jika dipanggil berulang
    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG)

    # ─── Format ───────────────────────────────────────────────────────────
    console_format = logging.Formatter(
        fmt="[%(asctime)s] %(levelname)-7s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    file_format = logging.Formatter(
        fmt="[%(asctime)s] %(levelname)-7s %(name)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # ─── Console Handler (INFO) ──────────────────────────────────────────
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(console_format)
    logger.addHandler(console_handler)

    # ─── File Handler (DEBUG) ────────────────────────────────────────────
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = LOG_DIR / f"fetch_{timestamp}.log"

    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(file_format)
    logger.addHandler(file_handler)

    logger.debug(f"Log file: {log_file}")

    return logger
