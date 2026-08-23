#!/usr/bin/env python3
"""
Script discovery untuk mencari kode variabel BPS yang tersedia
di level kabupaten/kota Sulawesi Selatan.

Menggunakan endpoint:
- List Variable: model=var (list semua variabel untuk domain tertentu)
- List Subject:  model=subject (list semua subjek/kategori)

Kita cari variabel terkait:
  1. PDRB per kapita
  2. Inflasi / IHK
  3. Tingkat Pengangguran Terbuka (TPT)
  4. Garis Kemiskinan
"""

import json
import time
import requests
from config.settings import BPS_API_KEY, BPS_BASE_URL

API_KEY = BPS_API_KEY
BASE_URL = BPS_BASE_URL

# Domain test: Kota Makassar
TEST_DOMAIN = "7371"

# Keywords untuk cari variabel yang relevan
SEARCH_KEYWORDS = [
    "pdrb", "produk domestik", "per kapita",
    "inflasi", "ihk", "harga konsumen",
    "pengangguran", "tpt", "angkatan kerja",
    "kemiskinan", "garis kemiskinan", "miskin",
    "penduduk",
]


def fetch_json(params: dict) -> dict | None:
    """Fetch dari BPS API, return parsed JSON atau None."""
    try:
        resp = requests.get(BASE_URL, params=params, timeout=30)
        data = resp.json()
        if isinstance(data, dict):
            return data
        return None
    except Exception as e:
        print(f"  ⚠️  Error: {e}")
        return None


def list_subjects(domain: str) -> list:
    """List semua subject yang tersedia untuk domain."""
    all_subjects = []
    page = 1

    while True:
        params = {
            "model": "subject",
            "domain": domain,
            "lang": "ind",
            "page": str(page),
            "key": API_KEY,
        }
        data = fetch_json(params)
        if not data or data.get("status") != "OK":
            break

        items = data.get("data", [])
        if len(items) >= 2 and isinstance(items[1], list):
            all_subjects.extend(items[1])

        # Check pagination
        if len(items) >= 1 and isinstance(items[0], dict):
            meta = items[0]
            if page >= meta.get("pages", 1):
                break
        else:
            break

        page += 1
        time.sleep(0.5)

    return all_subjects


def list_variables(domain: str, subject_id: int | None = None) -> list:
    """List semua variable yang tersedia untuk domain (optionally filtered by subject)."""
    all_vars = []
    page = 1

    while True:
        params = {
            "model": "var",
            "domain": domain,
            "lang": "ind",
            "page": str(page),
            "key": API_KEY,
        }
        if subject_id is not None:
            params["subject"] = str(subject_id)

        data = fetch_json(params)
        if not data or data.get("status") != "OK":
            break

        items = data.get("data", [])
        if len(items) >= 2 and isinstance(items[1], list):
            all_vars.extend(items[1])

        # Check pagination
        if len(items) >= 1 and isinstance(items[0], dict):
            meta = items[0]
            if page >= meta.get("pages", 1):
                break
        else:
            break

        page += 1
        time.sleep(0.5)

    return all_vars


from config.settings import BPS_API_KEY, BPS_BASE_URL, YEAR_TO_TH_ID

def test_variable_has_data(domain: str, var_id: int, year: int = 2023) -> bool:
    """Cek apakah variabel punya data untuk domain & tahun tertentu."""
    # Gunakan mapping tahun -> period ID
    th_id = YEAR_TO_TH_ID.get(year, year)
    
    params = {
        "model": "data",
        "domain": domain,
        "var": str(var_id),
        "th": str(th_id),
        "lang": "ind",
        "key": API_KEY,
    }
    data = fetch_json(params)
    if not data:
        return False

    if data.get("status") != "OK":
        return False

    dc = data.get("datacontent")
    if dc and isinstance(dc, dict) and len(dc) > 0:
        return True

    return False


def main():
    print("=" * 70)
    print(f"BPS Variable Discovery — Domain: {TEST_DOMAIN} (Kota Makassar)")
    print("=" * 70)

    # Step 1: List semua subject
    print("\n📂 Step 1: Mengambil daftar Subject...")
    subjects = list_subjects(TEST_DOMAIN)
    print(f"   Ditemukan {len(subjects)} subjects")

    # Filter subjects yang relevan
    relevant_subjects = []
    for subj in subjects:
        title = subj.get("title", "").lower()
        for kw in SEARCH_KEYWORDS:
            if kw in title:
                relevant_subjects.append(subj)
                break

    print(f"\n📋 Subjects relevan ({len(relevant_subjects)}):")
    for s in relevant_subjects:
        print(f"   [{s.get('sub_id')}] {s.get('title')} (ntabel={s.get('ntabel')})")

    # Juga print semua subjects untuk referensi
    print(f"\n📋 Semua subjects ({len(subjects)}):")
    for s in subjects:
        print(f"   [{s.get('sub_id')}] {s.get('title')} (ntabel={s.get('ntabel')})")

    # Step 2: List variabel dari subject yang relevan
    print("\n" + "=" * 70)
    print("📊 Step 2: Mengambil daftar Variable per subject relevan...")
    print("=" * 70)

    all_relevant_vars = []

    for subj in relevant_subjects:
        sub_id = subj.get("sub_id")
        sub_title = subj.get("title")
        print(f"\n   --- Subject [{sub_id}] {sub_title} ---")

        variables = list_variables(TEST_DOMAIN, subject_id=sub_id)
        print(f"   Ditemukan {len(variables)} variables")

        for v in variables:
            var_id = v.get("var_id")
            title = v.get("title", "")
            unit = v.get("unit", "")
            print(f"   [{var_id}] {title} ({unit})")
            all_relevant_vars.append({
                "var_id": var_id,
                "title": title,
                "unit": unit,
                "subject": sub_title,
                "sub_id": sub_id,
            })

        time.sleep(1)

    # Step 3: Test data availability untuk variabel kandidat
    print("\n" + "=" * 70)
    print("🔍 Step 3: Testing data availability (tahun 2023)...")
    print("=" * 70)

    candidates = []
    for v in all_relevant_vars:
        var_id = v["var_id"]
        title = v["title"]

        has_data = test_variable_has_data(TEST_DOMAIN, var_id, year=2023)
        status = "✅ ADA DATA" if has_data else "❌ KOSONG"
        print(f"   [{var_id}] {title}: {status}")

        if has_data:
            candidates.append(v)

        time.sleep(0.5)

    # Summary
    print("\n" + "=" * 70)
    print("📝 HASIL DISCOVERY — Variabel dengan data tersedia")
    print("=" * 70)

    if candidates:
        for c in candidates:
            print(f"   var_id={c['var_id']:>6}  | {c['title']}")
            print(f"           unit={c['unit']}  | subject: {c['subject']}")
    else:
        print("   Tidak ditemukan variabel dengan data.")

    # Save results
    output = {
        "domain": TEST_DOMAIN,
        "all_subjects": subjects,
        "relevant_variables": all_relevant_vars,
        "candidates_with_data": candidates,
    }
    with open("discovery_results.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"\n💾 Hasil lengkap disimpan ke: discovery_results.json")


if __name__ == "__main__":
    main()
