"""
Mapping kode wilayah BPS untuk 24 kabupaten/kota di Provinsi Sulawesi Selatan.

Kode wilayah mengikuti standar BPS:
- 2 digit pertama = kode provinsi (73 = Sulawesi Selatan)
- 2 digit terakhir = kode kabupaten/kota
- Kode 71-79 = kota (municipality)
- Kode 01-26 = kabupaten (regency)

Referensi: https://sig.bps.go.id/bridging-kode/index
"""

# Kode provinsi Sulawesi Selatan
PROVINCE_CODE = "7300"

# 24 Kabupaten/Kota di Sulawesi Selatan
# Format: {"kode_bps": "nama_wilayah"}
SULSEL_REGIONS: dict[str, str] = {
    # --- Kabupaten ---
    "7301": "Kab. Kepulauan Selayar",
    "7302": "Kab. Bulukumba",
    "7303": "Kab. Bantaeng",
    "7304": "Kab. Jeneponto",
    "7305": "Kab. Takalar",
    "7306": "Kab. Gowa",
    "7307": "Kab. Sinjai",
    "7308": "Kab. Bone",
    "7309": "Kab. Maros",
    "7310": "Kab. Pangkajene dan Kepulauan",
    "7311": "Kab. Barru",
    "7312": "Kab. Soppeng",
    "7313": "Kab. Wajo",
    "7314": "Kab. Sidenreng Rappang",
    "7315": "Kab. Pinrang",
    "7316": "Kab. Enrekang",
    "7317": "Kab. Luwu",
    "7318": "Kab. Tana Toraja",
    "7322": "Kab. Luwu Utara",
    "7325": "Kab. Luwu Timur",
    "7326": "Kab. Toraja Utara",
    # --- Kota ---
    "7371": "Kota Makassar",
    "7372": "Kota Parepare",
    "7373": "Kota Palopo",
}
