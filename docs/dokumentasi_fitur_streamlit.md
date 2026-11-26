# Dokumentasi Fitur Aplikasi Streamlit: B2B Micro-SaaS Market Intelligence

Dokumen ini merangkum seluruh arsitektur, alur kerja, dan fitur yang tersedia pada aplikasi web Streamlit ([app.py](file:///c:/Users/LENOVO/Desktop/Project-DekhsaBelajar/google-maps-scraper/app.py)) dalam proyek **Google Maps Scraper & Market Intelligence**.

---

## 1. Gambaran Umum Aplikasi

Aplikasi ini merupakan dashboard intelijen pasar (*market intelligence*) berbasis web yang menggabungkan **live scraping Google Maps berkecepatan tinggi**, **analisis peluang digital**, **pemetaan spasial (Geo-Intelligence)**, serta **eksplorasi dan ekspor data prospek B2B** dalam satu antarmuka.

Alur pemrosesan data secara garis besar:
1. **Input Pencarian:** Pengguna memilih kombinasi kata kunci/niche dan tag kota/wilayah pada antarmuka Streamlit.
2. **Stage 1 Scraping ([maps_worker.py](file:///c:/Users/LENOVO/Desktop/Project-DekhsaBelajar/google-maps-scraper/core/maps_worker.py)):** Browser headless Playwright Chromium menggulir daftar hasil Google Maps (`div[role="feed"]`), mem-parsing HTML kartu bisnis menggunakan BeautifulSoup, dan (opsional) mengunjungi halaman detail bisnis untuk mengambil nomor telepon, website, dan alamat lengkap.
3. **Normalisasi & Penyimpanan ([normalizer.py](file:///c:/Users/LENOVO/Desktop/Project-DekhsaBelajar/google-maps-scraper/core/normalizer.py), [database.py](file:///c:/Users/LENOVO/Desktop/Project-DekhsaBelajar/google-maps-scraper/storage/database.py)):** Nomor telepon distandardisasi ke format `+62`, URL dibersihkan, entitas dideduplikasi menggunakan hash SHA-256 (`dedup_hash`), lalu disimpan ke SQLite lokal (`data.db`) dan diekspor ke berkas CSV di folder `exports/`.
4. **Geo-Intelligence ([geo_intelligence.py](file:///c:/Users/LENOVO/Desktop/Project-DekhsaBelajar/google-maps-scraper/core/geo_intelligence.py)):** Koordinat (`latitude`, `longitude`) diekstrak langsung dari URL Google Maps tanpa API berbayar, alamat diurai menjadi `kecamatan` dan `kota_kabupaten`, serta skala usaha diklasifikasikan (*UMKM Tunggal* vs *Jaringan / Multi-Cabang*).
5. **Visualisasi & Eksplorasi:** Hasil langsung dirender menjadi KPI, tabel agregat, grafik Altair, peta interaktif PyDeck, dan tabel data yang dapat diunduh sebagai CSV.

---

## 2. Panel Kontrol Live Scraping

Terletak di bagian atas halaman, panel ini memungkinkan pengguna menjalankan ekstraksi data langsung dari browser:

* **Kata Kunci / Niche (Maks. 10):**
  * Tersedia **43 pilihan preset** niche bisnis populer (`Cafe`, `Coffee Shop`, `Kost`, `Kost Eksklusif`, `Gym & Fitness`, `Barbershop`, `Salon Kecantikan`, `Laundry`, `Restoran`, `Pet Shop & Grooming`, `Rental Mobil/Motor/Kamera`, `Percetakan Digital`, dll.).
  * Dilengkapi input **Tambah Kata Kunci Kustom** (pisahkan dengan koma) untuk mencari industri di luar daftar preset (total gabungan tetap dibatasi maks. 10 kata kunci per sesi).
* **Tag Lokasi / Kota:**
  * Tersedia **70+ pilihan kota/kabupaten** di Indonesia (mencakup DIY, Jawa Tengah, Jabodetabek, Jawa Barat, Jawa Timur, Bali, Lombok, Sumatra, Kalimantan, dan Sulawesi).
  * Dilengkapi input **Tambah Tag Lokasi Kustom** (pisahkan dengan koma).
* **Target Jumlah Hasil:**
  * Checkbox **Tanpa Batas (Semua)** (aktif secara default): menggulir daftar Google Maps hingga akhir daftar (`max_scrolls=120`).
  * Jika tidak dicentang, muncul input angka **Target / Lokasi** (`10` hingga `500`, kelipatan `10`, default `100`).
* **Opsi Pengambilan Detail (`Ambil No. HP & Website (Detail Paralel)`):**
  * Jika aktif, worker mengunjungi halaman profil tiap bisnis untuk mengambil nomor telepon, URL website, dan alamat lengkap yang sering tidak tampil di tampilan ringkasan daftar.
  * Dioptimalkan untuk container cloud (RAM 1 GB): menjalankan 1 lokasi per giliran dengan pool maksimal 3 tab paralel di Linux/cloud (2 lokasi × 6 tab di Windows), mendaur ulang tab setiap 30 tempat, serta memblokir gambar, font, CSS, dan *tile* peta berat.
* **Indikator Progres Real-Time:**
  * Menampilkan `st.status` dan `st.progress` yang diperbarui secara langsung per kombinasi kata kunci dan lokasi, serta log ringkas jumlah entitas yang berhasil diambil.

---

## 3. Ringkasan KPI Utama (4 Kartu Metrik)

Setelah data tersedia di sesi (`st.session_state["live_df"]`), aplikasi menampilkan 4 kartu metrik eksekutif di atas tab:

1. **Total Entitas Tervalidasi:** Jumlah total entitas unik setelah deduplikasi, beserta ringkasan kata kunci, lokasi, dan durasi scraping.
2. **Peluang Digital (Tanpa Web):** Persentase dan jumlah bisnis yang belum memiliki website (target prospek utama untuk solusi digital/Micro-SaaS).
3. **Rata-rata Ulasan Tertinggi:** Nama niche atau wilayah dengan rata-rata volume ulasan pelanggan tertinggi.
4. **Ulasan Bisnis Terbanyak:** Nama bisnis dan jumlah ulasan tertinggi yang ditemukan dalam sesi tersebut.

---

## 4. Fitur per Tab di Streamlit

### Tab 1: Ringkasan & Visualisasi
Menyajikan evaluasi komparatif antar niche (jika >1 kata kunci) atau antar wilayah (jika 1 kata kunci):

* **Tabel Ringkasan Agregat:** Menampilkan kolom `ID`, `Niche Bisnis / Wilayah / Lokasi`, `Jumlah Entitas`, `Rata-rata Review`, `Review Maksimal`, `Rating (★)`, `Adopsi Website (%)` (visual *progress bar* 0–100%), dan `Status Peluang` otomatis:
  * `Tier 1 (Peluang Tinggi)`: ≥ 65% bisnis belum memiliki website.
  * `Tier 2 (Potensial)`: 40% – 64.9% belum memiliki website.
  * `Tier 3 (Digital Matang)`: < 40% belum memiliki website.
* **4 Grafik Analitik Interaktif (Altair):**
  1. **Jumlah Entitas Bisnis Tervalidasi:** Grafik batang horizontal volume entitas.
  2. **Rata-rata Ulasan (Tingkat Aktivitas Pasar):** Grafik batang horizontal rata-rata ulasan per entitas beserta tooltip ulasan maksimal.
  3. **Sebaran Wilayah / Kesiapan Digital:**
     * *Mode multi-niche:* Grafik batang bertumpuk sebaran wilayah per niche.
     * *Mode 1 niche:* Grafik perbandingan jumlah bisnis yang **Memiliki Website** vs **Belum Ada Website** per wilayah.
  4. **Tingkat Adopsi Website (%):** Grafik batang horizontal dengan gradasi warna (`redyellowgreen` terbalik) untuk membedakan pasar yang masih minim adopsi digital vs pasar yang sudah matang.

---

### Tab 2: Analisis Spasial & Peta Pasar (Geo-Intelligence)
Memanfaatkan koordinat geografis dan struktur alamat untuk analisis kepadatan pasar:

* **4 KPI Spasial:**
  1. `Kecamatan Teridentifikasi`
  2. `Whitespace Teratas` (kecamatan dengan skor peluang tertinggi)
  3. `Proporsi UMKM Tunggal` (vs jumlah entitas multi-cabang)
  4. `Koordinat Terpetakan` (termasuk rincian jumlah koordinat `Presisi GPS` vs fallback `Estimasi Wilayah`)
* **Peta Interaktif PyDeck (`CARTO_ROAD`):**
  * **Mode 1 — Titik Bisnis (`ScatterplotLayer`):** Menampilkan posisi tiap bisnis dengan ukuran titik proporsional terhadap jumlah ulasan dan kode warna:
    * **Hijau:** UMKM Tanpa Website (peluang digital tinggi).
    * **Biru:** UMKM Memiliki Website.
    * **Oranye:** Jaringan / Multi-Cabang.
    * Dilengkapi *tooltip* nama usaha, skala, kecamatan, rating, dan jumlah ulasan.
  * **Mode 2 — Kepadatan Area (`HexagonLayer`):** Peta heksagon 3D (radius 450m) untuk melihat titik konsentrasi kompetitor tertinggi.
  * **Kontrol Peta:** Kamera otomatis menyesuaikan batas koordinat data (*auto-fit* via `pdk.data_utils.compute_view`) dengan filter **Fokus Kota / Wilayah**, **Filter Niche**, dan **Filter Skala Usaha**.
* **Tabel Indeks *Whitespace* & *Demand-to-Supply* per Kecamatan:**
  * Mengagregasi data per kecamatan (dan niche jika multi-niche) untuk menghitung `whitespace_score` (0–100) dari kombinasi volume rata-rata ulasan, rendahnya kepadatan kompetitor, dan tingginya persentase bisnis tanpa website.
  * Kategori pasar otomatis: `Peluang Tinggi (Whitespace)` (≥60), `Potensial` (≥42), dan `Kompetitif / Padat` (<42).
* **Analisis Skala Usaha:**
  * Grafik batang perbandingan **UMKM Tunggal** vs **Jaringan / Multi-Cabang** (dideteksi dari kesamaan domain website kustom di luar domain sosial/generik dan kemiripan nama brand yang telah dinormalisasi).
  * Tabel pendamping yang menampilkan daftar **Entitas Terdeteksi Multi-Cabang / Jaringan** atau **Top UMKM Tunggal Tanpa Website** jika tidak ada jaringan yang terdeteksi.

---

### Tab 3: Eksplorasi Data Gabungan
Antarmuka inspeksi data mentah dan ekspor berkas:

* **Unduh CSV:** Tombol **Unduh `live_<keyword>_<N>kw_<timestamp>.csv`** untuk mengunduh seluruh dataset gabungan hasil sesi scraping.
* **Filter Multi-Kriteria:**
  * Dropdown **Niche** (muncul jika multi-niche)
  * Pencarian kata kunci bebas (mencocokkan *Nama Usaha*, *Alamat*, atau *Kategori*)
  * Dropdown **Wilayah**
  * Input **Min. Review**
  * Checkbox **Hanya yang ada No. HP**
* **Metrik Kelengkapan Real-Time:** Menampilkan jumlah baris terfilter beserta persentase `Kelengkapan Telepon` dan `Kelengkapan Website`.
* **Tabel Data Lengkap:** Menampilkan kolom `Niche / Kata Kunci`, `Nama Usaha`, `Skala Usaha`, `Kategori`, `Rating`, `Ulasan`, `Telepon (+62)`, `Website` (tautan klik), `Link GMaps` (`Buka Maps`), `Kecamatan`, `Wilayah`, dan `Alamat Lengkap`.

---

## 5. Konfigurasi Pendukung Deployment

* **[requirements.txt](file:///c:/Users/LENOVO/Desktop/Project-DekhsaBelajar/google-maps-scraper/requirements.txt):** Dependensi Python (`streamlit`, `playwright`, `beautifulsoup4`, `pandas`, `altair`, `pydeck`, `SQLAlchemy`, `pydantic-settings`, dll.).
* **[packages.txt](file:///c:/Users/LENOVO/Desktop/Project-DekhsaBelajar/google-maps-scraper/packages.txt):** Daftar pustaka sistem Debian (`libglib2.0-0`, `libnss3`, `libnspr4`, `libatk1.0-0`, `libgbm1`, dll.) yang dibutuhkan Chromium headless pada container Linux / Streamlit Community Cloud.
* **[.streamlit/config.toml](file:///c:/Users/LENOVO/Desktop/Project-DekhsaBelajar/google-maps-scraper/.streamlit/config.toml):** Pengaturan tema warna korporat dan mode server `headless = true`.
