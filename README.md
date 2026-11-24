# Sistem Ekstraksi Kontak Bisnis Google Maps

Perangkat lunak otomatis untuk ekstraksi data kontak bisnis dari Google Maps berbasis kata kunci pencarian tertentu. Sistem dirancang menggunakan arsitektur pemrosesan dua tahap: pengambilan profil bisnis dari Google Maps menggunakan **Playwright**, diikuti oleh perayapan situs web bisnis asinkron berkecepatan tinggi menggunakan **httpx** dan **BeautifulSoup4** untuk mengekstrak alamat email bisnis.

---

## 1. Fitur Utama

- **Otomatisasi Google Maps Modern**: Menggunakan Playwright Chromium dengan selektor semantik aksesibilitas (`aria-label`, `data-item-id`, `role='feed'`, `role='article'`) yang tahan terhadap perubahan CSS class dinamis Google Maps.
- **Interaksi Manusiawi**: Pengguliran otomatis dinamis dengan jeda waktu acak (*humanized random delay* antara 1.5 hingga 4.0 detik).
- **Normalisasi Nomor Telepon Indonesia (FR-04)**: Mengubah awalan `08...`, kode area lokal seperti `(021)...`, `022...`, `031...` menjadi format internasional standar `+62...`.
- **Perayapan Email Asinkron Hemat Memori (FR-05)**: Merayapi beranda situs web bisnis dan maksimal 2 tautan internal kontak (`contact`, `kontak`, `about`, `tentang`, `hubungi`) dengan batas konkurensi hingga 15 pekerja asinkron.
- **Penyaringan False Positive Email (FR-06)**: Menyaring aset gambar (`.png`, `.jpg`, `.svg`), pustaka kode, tracker (`sentry.io`, `wixpress`), dan email dummy.
- **Blacklist Domain Sosial & Chat**: Otomatis melewati tautan WhatsApp (`wa.me`), Instagram, Facebook, Linktree, TikTok, dan Telegram, menandainya langsung sebagai `NO_WEBSITE`.
- **Akurasi Deduplikasi 100% (FR-07)**: Menghasilkan hash SHA-256 unik berdasarkan kombinasi nama bisnis dan nomor telepon/alamat fisik untuk mencegah duplikasi data (0% duplikat).
- **Ketahanan Kegagalan & Mode Resume (FR-08 & NFR-2)**: Data dari Google Maps langsung disimpan ke SQLite dengan status `PENDING`. Jika proses terputus, tahap perayapan email dapat dilanjutkan kapan saja menggunakan opsi `--resume`.
- **Ekspor Data Fleksibel**: Menyimpan hasil ekstraksi secara otomatis ke format CSV dan JSON pada direktori `exports/`.

---

## 2. Arsitektur Pemrosesan Dua Tahap

```
+--------------------------------------------------------------+
| Input Pengguna: Kata Kunci Pencarian & Target Batas Entitas  |
+------------------------------+-------------------------------+
                               |
                               v
+--------------------------------------------------------------+
| TAHAP 1: Ekstraksi Google Maps (core/maps_worker.py)         |
| • Playwright Chromium (1-2 instans terkendali)              |
| • Jeda acak (1.5 - 4.0s) & simulasi pengguliran manusiawi    |
| • Ekstraksi: Nama Usaha, Kategori, Alamat, Telepon, URL Web  |
| • Standardisasi Telepon (+62) & Hashing Deduplikasi          |
| • Simpan langsung ke database lokal (Status: PENDING)        |
+------------------------------+-------------------------------+
                               |
                               v
+--------------------------------------------------------------+
| TAHAP 2: Pengayaan Email Asinkron (core/email_enricher.py)   |
| • httpx AsyncClient (hingga 15 pekerja asinkron)             |
| • Filter domain media sosial (wa.me, IG, FB, Linktree)       |
| • Perayapan Beranda + maks 2 tautan internal kontak/tentang  |
| • Sanitasi Regex: buang ekstensi gambar dan tracker palsu    |
| • Perbarui database (Status: SUCCESS / NO_WEBSITE / FAILED)  |
+------------------------------+-------------------------------+
                               |
                               v
+--------------------------------------------------------------+
| HASIL AKHIR & EKSPOR DATA                                    |
| • Penyimpanan database lokal SQLite (data.db)                |
| • Ekspor otomatis ke CSV & JSON di folder exports/           |
+--------------------------------------------------------------+
```

---

## 3. Struktur Direktori

```text
google-maps-scraper/
├── config/
│   ├── __init__.py
│   └── settings.py          # Konfigurasi jeda waktu, konkurensi, blacklist domain, proksi
├── core/
│   ├── __init__.py
│   ├── maps_worker.py       # Logika otomatisasi Playwright untuk Google Maps (Tahap 1)
│   ├── email_enricher.py    # Perayapan situs web asinkron & regex email (Tahap 2)
│   └── normalizer.py        # Normalisasi nomor telepon (+62), email regex, & dedup hash
├── storage/
│   ├── __init__.py
│   ├── database.py          # Model database SQLAlchemy, deduplikasi 0%, checkpoint
│   └── exporter.py          # Ekspor hasil ekstraksi ke CSV dan JSON
├── exports/                 # Direktori penyimpanan berkas keluaran CSV dan JSON
├── tests/                   # Test suite unit & benchmark PRD
│   ├── test_normalizer.py
│   ├── test_database.py
│   ├── test_email_enricher.py
│   └── test_prd_metrics.py
├── main.py                  # Titik masuk antarmuka baris perintah (CLI)
├── requirements.txt         # Daftar pustaka Python
├── pyproject.toml           # Konfigurasi paket & build tool
└── README.md
```

---

## 4. Skema Data

Data disimpan ke dalam database lokal dengan struktur berikut:

| Nama Kolom | Tipe Data | Keterangan | Wajib |
|---|---|---|---|
| `id` | UUID / String | Identitas unik rekaman data. | Ya |
| `search_keyword` | String | Kata kunci pencarian yang menghasilkan entitas ini. | Ya |
| `business_name` | String | Nama resmi usaha dari Google Maps. | Ya |
| `category` | String | Kategori usaha. | Tidak |
| `address` | Text | Alamat fisik lengkap bisnis. | Tidak |
| `phone_number` | String | Nomor telepon ternormalisasi format internasional (`+62...`). | Tidak |
| `website_url` | String | Tautan situs web resmi bisnis. | Tidak |
| `extracted_emails` | JSON / Text | Daftar alamat email unik yang ditemukan dari situs web. | Tidak |
| `enrichment_status` | Enum | Status proses Tahap 2: `PENDING`, `SUCCESS`, `NO_WEBSITE`, `FAILED`. | Ya |
| `scraped_at` | Timestamp | Waktu pencatatan data dalam format ISO 8601. | Ya |
| `dedup_hash` | String | Hash unik pencegah duplikasi baris data. | Ya |

---

## 5. Instalasi

### Prasyarat
- Python 3.11 atau lebih baru.
- Koneksi internet aktif.

### Langkah Pemasangan

1. **Clone Repositori**:
   ```bash
   git clone https://github.com/dekhsabelajar/google-maps-scraper.git
   cd google-maps-scraper
   ```

2. **Pasang Dependensi**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Pasang Browser Playwright Chromium**:
   ```bash
   playwright install chromium
   ```

---

## 6. Panduan Penggunaan CLI (`main.py`)

### A. Ekstraksi Standar (Tahap 1 + Tahap 2)
Mengekstrak bisnis dan mencari alamat email dari situs web masing-masing:
```bash
python main.py -k "cafe jakarta selatan" --limit 50
```

### B. Multi Kata Kunci
```bash
python main.py -k "digital agency jakarta" -k "software house bandung" --limit 30
```

### C. Mode Tampilan Browser (Headed Mode)
Menampilkan jendela peramban Chromium saat proses berjalan:
```bash
python main.py -k "restoran surabaya" --limit 20 --no-headless
```

### D. Menggunakan Proksi (HTTP / SOCKS5)
```bash
python main.py -k "klinik gigi yogyakarta" --proxy "http://user:pass@proxy-server:8080"
```

### E. Hanya Menjalankan Ekstraksi Google Maps (Lewati Tahap 2)
```bash
python main.py -k "bengkel mobil semarang" --limit 100 --skip-enrich
```

### F. Melanjutkan Pengayaan Email yang Tertunda (`--resume`)
Jika koneksi internet terputus saat perayapan email, lanjutkan langsung tanpa mengulang ekstraksi Google Maps dari awal:
```bash
python main.py --resume
```

---

## 7. Pengujian (Testing)

Proyek ini dilengkapi rangkaian pengujian unit dan evaluasi kepatuhan metrik PRD:

Jalankan seluruh test suite menggunakan `pytest`:
```bash
pytest tests/ -v
```

Hasil uji mencakup:
- `test_normalizer.py`: Normalisasi nomor telepon (+62), filter blacklist domain, sanitasi email regex.
- `test_database.py`: Operasi CRUD, penolakan baris ganda (deduplikasi 0%), transisi status & resume.
- `test_email_enricher.py`: Parsing tautan internal halaman kontak dan tentang.
- `test_prd_metrics.py`: Verifikasi 3 Metrik Keberhasilan Utama PRD (Kelengkapan >= 90%, Duplikasi 0%, Stabilitas >= 100 entitas).

---

## 8. Dashboard Interaktif Streamlit

Aplikasi dasbor interaktif berbasis **Streamlit** disediakan untuk menganalisis data kontak dan ulasan bisnis dari 7 niche Micro-SaaS secara visual, statistik, dan inspeksi manual per file.

### Menjalankan Dashboard:
```bash
streamlit run app.py
```

### Fitur Utama Dashboard:
1. **Ringkasan Eksekutif & Matriks Prioritas**:
   - Kartu KPI tingkat tinggi (Total Niche, Total Entitas, Rata-rata Review Tertinggi, Ulasan Maksimal, Rekomendasi Utama Tier 1).
   - Matriks perbandingan 7 niche lengkap dengan tingkat saturasi software dari dokumen riset.
   - Grafik interaktif Altair: Rata-rata Ulasan per Niche, Ulasan Maksimum, Matriks Peluang (Saturasi vs Volume), dan Sebaran Sampel Geografis (DIY, Magelang, Klaten).
2. **Analisis Komparatif 7 Niche**:
   - Analisis mendalam profil petahana, kisaran harga, titik masalah operasional (*pain points*), dan spesifikasi solusi MVP Micro-SaaS per niche.
3. **Eksplorasi Data Manual (7 File & Master Data)**:
   - Pemilih file untuk memeriksa dataset master (127 entitas) atau masing-masing dari ke-7 file CSV niche secara mandiri.
   - Filter teks pencarian multi-kolom (Nama Bisnis, Kategori, Alamat).
   - Filter rentang rating, jumlah ulasan minimum, wilayah geografis, dan kelengkapan kontak (telepon, website, email).
   - Tombol unduh langsung berkas CSV aktif.
4. **Integrasi Presentasi Google Slides**:
   - Tautan langsung dan ringkasan 10 slide presentasi eksekutif.

---

## 9. Dataset Riset Pasar B2B Micro-SaaS (7 Niche)

Data scraping empiris di wilayah DI Yogyakarta, Magelang, dan Klaten tersimpan pada folder `exports/`:
- `niche_1_kost_eksklusif.csv`: 19 entitas, avg review 60.9 (top: Kost M - 314 reviews)
- `niche_2_gym_kebugaran.csv`: 18 entitas, avg review 164.8 (top: WGYM - 634 reviews)
- `niche_3_rental_kendaraan_kamera.csv`: 18 entitas, avg review 239.7 (top: JOGJAKAMERA - 1,445 reviews)
- `niche_4_barbershop_salon.csv`: 18 entitas, avg review 297.0 (top: BarberKing Klaten - 1,393 reviews)
- `niche_5_percetakan_digital.csv`: 18 entitas, avg review 633.7 (top: Mangrove Printing - 2,792 reviews)
- `niche_6_car_wash.csv`: 18 entitas, avg review 201.7 (top: DK Car Wash - 1,779 reviews)
- `niche_7_pet_shop_vet.csv`: 18 entitas, avg review 422.7 (top: Klinik Hewan Jogja - 2,236 reviews)
- `master_7_niches_summary.csv`: Ringkasan benchmark komparatif seluruh niche.
- `all_7_niches_contacts.csv`: Seluruh 127 baris kontak entitas bisnis gabungan.

---

## 10. Lisensi

Didistribusikan di bawah lisensi MIT.
