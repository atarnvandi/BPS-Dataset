"""
Mapping variabel BPS yang akan di-fetch.

Kode variabel (var_id) merujuk pada ID variabel di BPS Dynamic Data API.
Untuk menemukan kode variabel yang tepat, gunakan endpoint:
  https://webapi.bps.go.id/v1/api/list/model/var/domain/{domain}/key/{key}/

CATATAN: Kode variabel bisa berbeda antar level domain (nasional vs provinsi
vs kabupaten). Pastikan verifikasi melalui BPS API portal.

Setiap entry berisi:
- var_id : ID variabel di BPS API
- name   : Nama deskriptif variabel
- unit   : Satuan pengukuran
- notes  : Catatan tambahan untuk referensi
"""

BPS_VARIABLES: dict[str, dict] = {
    "pdrb_total": {
        "var_id": 79,
        "name": "PDRB Atas Dasar Harga Berlaku (Miliar Rupiah)",
    },
    "inflasi_mtom": {
        "var_id": 1,
        "name": "Inflasi Bulanan (M-to-M) (%)",
    },
    "tpt": {
        "var_id": 52,
        "name": "Tingkat Pengangguran Terbuka",
    },
    "garis_kemiskinan": {
        "var_id": 64,
        "name": "Garis Kemiskinan",
    },
}
