"""
HTTP client untuk BPS Web API dengan retry logic dan exponential backoff.

Endpoint yang digunakan: Dynamic Data
  https://webapi.bps.go.id/v1/api/list

Parameter utama:
  model=data, domain, var, th (period), key

Response format:
  {
    "status": "OK",
    "data-availability": "available",
    "var": [...],
    "datacontent": { ... }
  }
"""

import logging
import time
from dataclasses import dataclass
from typing import Any

import requests

from config.settings import (
    BACKOFF_BASE,
    BPS_API_KEY,
    BPS_BASE_URL,
    MAX_RETRIES,
    REQUEST_TIMEOUT,
    YEAR_TO_TH_ID,
)

logger = logging.getLogger("bps_pipeline")


@dataclass
class FetchResult:
    """Hasil dari satu API call."""

    success: bool
    data: dict[str, Any] | None
    error_msg: str | None
    attempts: int


class BPSApiClient:
    """
    HTTP client untuk BPS Web API.

    Menangani:
    - Konstruksi URL parameter sesuai format BPS API
    - Retry dengan exponential backoff untuk error transient
    - Logging detail per-request
    """

    def __init__(self, api_key: str | None = None):
        """
        Args:
            api_key: BPS API key. Jika None, baca dari config/settings.
        """
        self.api_key = api_key or BPS_API_KEY
        self.base_url = BPS_BASE_URL
        self.session = requests.Session()
        self.session.headers.update({
            "Accept": "application/json",
            "User-Agent": "BPS-DataPipeline/1.0",
        })

    def fetch_data(
        self,
        domain: str,
        var_id: int,
        years: list[int] | None = None,
    ) -> FetchResult:
        """
        Fetch data dari BPS Dynamic Data API.

        Args:
            domain: Kode wilayah BPS (e.g. "7301")
            var_id: ID variabel BPS (e.g. 108)
            years:  List tahun data. BPS API mewajibkan parameter 'th'.
                    Format: range "2021:2025" atau multiple "2021;2022;2023"

        Returns:
            FetchResult dengan success status, raw data, dan error info.
        """
        # Bangun parameter URL sesuai format BPS API
        params = {
            "model": "data",
            "lang": "ind",
            "domain": domain,
            "var": str(var_id),
            "key": self.api_key,
        }

        # BPS API mewajibkan parameter 'th' (period)
        # Parameter th tidak bisa diisi tahun langsung, melainkan harus menggunakan period ID
        if years:
            th_ids = [str(YEAR_TO_TH_ID.get(y, y)) for y in years]
            if len(th_ids) == 1:
                params["th"] = th_ids[0]
            else:
                params["th"] = f"{th_ids[0]}:{th_ids[-1]}"

        return self._request_with_retry(params)

    def _request_with_retry(self, params: dict) -> FetchResult:
        """
        Kirim HTTP request dengan retry logic.

        Retry strategy:
        - Exponential backoff: delay = BACKOFF_BASE ^ attempt
        - Retry pada: timeout, connection error, HTTP 429/500/502/503/504
        - Tidak retry pada: HTTP 400/401/403/404 (client error permanen)
        """
        last_error = None

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                response = self.session.get(
                    self.base_url,
                    params=params,
                    timeout=REQUEST_TIMEOUT,
                )

                # --- HTTP Error Handling ---
                if response.status_code == 429:
                    # Rate limited — wajib retry
                    wait = BACKOFF_BASE ** attempt
                    logger.warning(
                        f"Rate limited (429). Retry {attempt}/{MAX_RETRIES} "
                        f"in {wait}s"
                    )
                    time.sleep(wait)
                    continue

                if response.status_code in (500, 502, 503, 504):
                    # Server error — retry
                    wait = BACKOFF_BASE ** attempt
                    logger.warning(
                        f"Server error ({response.status_code}). "
                        f"Retry {attempt}/{MAX_RETRIES} in {wait}s"
                    )
                    time.sleep(wait)
                    continue

                if response.status_code >= 400:
                    # Client error (400, 401, 403, 404) — tidak retry
                    return FetchResult(
                        success=False,
                        data=None,
                        error_msg=f"HTTP {response.status_code}: {response.text[:200]}",
                        attempts=attempt,
                    )

                # --- Parse Response ---
                data = response.json()

                if not isinstance(data, dict):
                    return FetchResult(
                        success=False,
                        data=None,
                        error_msg=f"Unexpected response type: {type(data).__name__}",
                        attempts=attempt,
                    )

                # BPS API mengembalikan status di body JSON
                status = data.get("status", "")
                availability = data.get("data-availability", "")

                if status != "OK":
                    return FetchResult(
                        success=False,
                        data=data,  # tetap simpan untuk debugging
                        error_msg=f"API status: {status}",
                        attempts=attempt,
                    )

                if availability == "not-available":
                    return FetchResult(
                        success=False,
                        data=data,
                        error_msg="data-availability: not-available",
                        attempts=attempt,
                    )

                # Sukses
                return FetchResult(
                    success=True,
                    data=data,
                    error_msg=None,
                    attempts=attempt,
                )

            except requests.exceptions.Timeout:
                last_error = "Request timeout"
                wait = BACKOFF_BASE ** attempt
                logger.warning(
                    f"Timeout. Retry {attempt}/{MAX_RETRIES} in {wait}s"
                )
                time.sleep(wait)

            except requests.exceptions.ConnectionError:
                last_error = "Connection error"
                wait = BACKOFF_BASE ** attempt
                logger.warning(
                    f"Connection error. Retry {attempt}/{MAX_RETRIES} in {wait}s"
                )
                time.sleep(wait)

            except requests.exceptions.RequestException as e:
                last_error = f"Request error: {e}"
                wait = BACKOFF_BASE ** attempt
                logger.warning(
                    f"Request error: {e}. Retry {attempt}/{MAX_RETRIES} in {wait}s"
                )
                time.sleep(wait)

            except ValueError as e:
                # JSON decode error
                return FetchResult(
                    success=False,
                    data=None,
                    error_msg=f"JSON decode error: {e}",
                    attempts=attempt,
                )

        # Semua retry habis
        return FetchResult(
            success=False,
            data=None,
            error_msg=f"Max retries ({MAX_RETRIES}) exceeded. Last error: {last_error}",
            attempts=MAX_RETRIES,
        )

    def close(self):
        """Close HTTP session."""
        self.session.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
