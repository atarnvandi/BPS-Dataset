"""
Raw JSON storage untuk BPS data pipeline.

Menyimpan response mentah dari BPS API ke filesystem sebelum transformasi.
Tujuan: preservasi data asli agar bisa di-reprocess jika mapping berubah.

Struktur output:
  data/raw/{variable_key}/{domain_code}/{domain}_{var_id}_{timestamp}.json

Setiap file disimpan dengan metadata wrapper:
  {
    "fetch_metadata": {
      "domain": "7301",
      "variable_key": "pdrb_perkapita",
      "var_id": 108,
      "fetched_at": "2026-08-23T14:00:00+08:00",
      "pipeline_version": "1.0.0"
    },
    "raw_response": { ... }  ← response asli dari BPS API
  }
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config.settings import RAW_DATA_DIR

logger = logging.getLogger("bps_pipeline")

PIPELINE_VERSION = "1.0.0"


class RawJsonStorage:
    """Simpan raw JSON response ke filesystem."""

    def __init__(self, base_dir: Path | None = None):
        """
        Args:
            base_dir: Base directory untuk raw data.
                      Default: config.settings.RAW_DATA_DIR
        """
        self.base_dir = base_dir or RAW_DATA_DIR

    def save(
        self,
        domain: str,
        variable_key: str,
        var_id: int,
        year: int | str,
        data: dict[str, Any],
        timestamp: datetime | None = None,
    ) -> Path:
        """
        Simpan raw response ke file JSON.

        Args:
            domain: Kode wilayah BPS (e.g. "7301")
            variable_key: Key variabel (e.g. "pdrb_perkapita")
            var_id: ID variabel BPS
            year: Tahun data untuk penamaan file
            data: Raw response dict dari BPS API
            timestamp: Waktu fetch. Default: now()

        Returns:
            Path ke file yang disimpan
        """
        if timestamp is None:
            timestamp = datetime.now(timezone.utc)

        # Buat directory structure
        output_dir = self.base_dir / variable_key / domain
        output_dir.mkdir(parents=True, exist_ok=True)

        # Filename stabil tanpa timestamp: {domain}_{var_id}_{year}.json
        filename = f"{domain}_{var_id}_{year}.json"
        filepath = output_dir / filename

        # Wrap dengan metadata
        wrapped = {
            "fetch_metadata": {
                "domain": domain,
                "variable_key": variable_key,
                "var_id": var_id,
                "fetched_at": timestamp.isoformat(),
                "pipeline_version": PIPELINE_VERSION,
            },
            "raw_response": data,
        }

        # Write JSON
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(wrapped, f, ensure_ascii=False, indent=2)

        logger.debug(f"Raw JSON saved: {filepath}")
        return filepath

    def get_output_dir(self, variable_key: str, domain: str) -> Path:
        """Return output directory path (tanpa create)."""
        return self.base_dir / variable_key / domain

    def is_exists(self, domain: str, variable_key: str, var_id: int, year: int | str) -> bool:
        """
        Cek apakah file raw JSON untuk domain & tahun ini sudah ada DAN memiliki data.
        Jika file ada tapi datanya kosong (belum tersedia di BPS saat itu),
        return False agar script men-download ulang di jadwal berikutnya.
        """
        filename = f"{domain}_{var_id}_{year}.json"
        filepath = self.get_output_dir(variable_key, domain) / filename
        
        if not filepath.exists():
            return False
            
        # Jika file ada, cek apakah isinya kosong
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
                datacontent = data.get("raw_response", {}).get("datacontent", {})
                if not datacontent:
                    return False  # Datanya kosong, anggap tidak ada agar di-fetch ulang
        except Exception:
            return False
            
        return True
