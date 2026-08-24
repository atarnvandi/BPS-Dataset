import csv
import logging
import os
from pathlib import Path
from typing import List, Dict, Any

import pymysql
from dotenv import load_dotenv

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s - %(message)s")
logger = logging.getLogger("db_loader")

def get_db_connection():
    """Membuat koneksi ke TiDB Serverless."""
    load_dotenv()
    
    host = os.getenv("TIDB_HOST")
    user = os.getenv("TIDB_USER")
    password = os.getenv("TIDB_PASSWORD")
    database = os.getenv("TIDB_DB_NAME")
    port = int(os.getenv("TIDB_PORT", 4000))
    
    if not all([host, user, password, database]):
        logger.error("Kredensial TiDB tidak lengkap di .env!")
        exit(1)
        
    logger.info(f"Mencoba terhubung ke TiDB: {host} (Database: {database})...")
    
    return pymysql.connect(
        host=host,
        port=port,
        user=user,
        password=password,
        database=database,
        ssl_verify_cert=True,
        ssl_verify_identity=True,
        autocommit=False
    )

def create_table_if_not_exists(cursor, table_name: str):
    """
    Membuat tabel secara dinamis jika belum ada.
    Primary Key adalah gabungan domain_code dan year agar tidak ada data ganda.
    """
    # Kolom disesuaikan dengan struktur CSV kita
    sql = f"""
    CREATE TABLE IF NOT EXISTS `{table_name}` (
        domain_code VARCHAR(10) NOT NULL,
        domain_name VARCHAR(100) NOT NULL,
        year INT NOT NULL,
        variable VARCHAR(50) NOT NULL,
        variable_name VARCHAR(255) NOT NULL,
        value FLOAT,
        PRIMARY KEY (domain_code, year)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
    """
    cursor.execute(sql)
    logger.info(f"Tabel `{table_name}` dicek/dibuat.")

def load_csv_to_db(cursor, csv_path: Path):
    """Membaca CSV dan meng-UPSERT datanya ke dalam tabel."""
    table_name = csv_path.stem  # Nama file menjadi nama tabel (misal: tpt, pdrb_total)
    
    # 1. Pastikan tabel ada
    create_table_if_not_exists(cursor, table_name)
    
    # 2. Baca CSV
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        
    if not rows:
        logger.warning(f"File {csv_path.name} kosong. Dilewati.")
        return 0
        
    # 3. Siapkan query UPSERT (Insert On Duplicate Key Update)
    # Ini memastikan jika data tahun & wilayah tersebut sudah ada, angkanya akan di-update, bukan ganda.
    sql = f"""
        INSERT INTO `{table_name}` 
        (domain_code, domain_name, year, variable, variable_name, value)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
        value = VALUES(value),
        domain_name = VALUES(domain_name),
        variable_name = VALUES(variable_name);
    """
    
    # 4. Eksekusi query
    # Konversi data ke format tuple untuk pymysql executemany
    values = []
    for r in rows:
        # Tangani nilai value yang mungkin kosong atau bukan angka
        try:
            val = float(r["value"])
        except ValueError:
            val = None
            
        values.append((
            r["domain_code"],
            r["domain_name"],
            int(r["year"]),
            r["variable"],
            r["variable_name"],
            val
        ))
        
    cursor.executemany(sql, values)
    return len(rows)

def main():
    clean_dir = Path("data/clean")
    if not clean_dir.exists():
        logger.error("Folder data/clean tidak ditemukan. Harap jalankan fetcher terlebih dahulu.")
        return

    csv_files = list(clean_dir.glob("*.csv"))
    if not csv_files:
        logger.error("Tidak ada file CSV ditemukan di data/clean.")
        return
        
    # Buat koneksi ke database
    try:
        conn = get_db_connection()
    except Exception as e:
        logger.error(f"Gagal terhubung ke Database: {e}")
        return
        
    logger.info("✅ Berhasil terhubung ke TiDB!")
    
    total_inserted = 0
    with conn.cursor() as cursor:
        for csv_path in csv_files:
            logger.info(f"Memproses {csv_path.name}...")
            try:
                count = load_csv_to_db(cursor, csv_path)
                logger.info(f"  └ Berhasil menyiapkan {count} baris data ke tabel `{csv_path.stem}`.")
                total_inserted += count
            except Exception as e:
                logger.error(f"  └ Gagal memproses {csv_path.name}: {e}")
                conn.rollback() # Batalkan transaksi jika ada yang gagal
                
        # Simpan perubahan (Commit)
        conn.commit()
        
    conn.close()
    logger.info(f"🎉 Selesai! Sebanyak {total_inserted} baris data telah berhasil di-UPSERT ke database.")

if __name__ == "__main__":
    main()
