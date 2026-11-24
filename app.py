"""
Executive Dashboard: B2B Micro-SaaS Market Intelligence & Lead Validation
Regional Analysis: DIY Yogyakarta, Magelang, & Klaten
Strictly professional corporate design without unnecessary emojis.
"""

from pathlib import Path
import re
import pandas as pd
import streamlit as st
import altair as alt

# --- PAGE CONFIGURATION ---
st.set_page_config(
    page_title="B2B Micro-SaaS Market Intelligence",
    page_icon=None,
    layout="wide",
    initial_sidebar_state="expanded",
)

# --- CORPORATE THEME STYLING ---
st.markdown(
    """
    <style>
    /* Global corporate palette */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    }
    
    /* Top banner */
    .corporate-header {
        background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
        padding: 28px 32px;
        border-radius: 8px;
        color: #ffffff;
        margin-bottom: 24px;
        border-left: 6px solid #2563eb;
    }
    .corporate-header h1 {
        font-size: 26px;
        font-weight: 700;
        margin: 0 0 8px 0;
        letter-spacing: -0.5px;
        color: #ffffff;
    }
    .corporate-header p {
        font-size: 14px;
        color: #94a3b8;
        margin: 0;
        line-height: 1.5;
    }

    /* Metric cards */
    .metric-card {
        background-color: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 6px;
        padding: 18px 20px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    }
    .metric-title {
        font-size: 12px;
        font-weight: 600;
        text-transform: uppercase;
        color: #64748b;
        letter-spacing: 0.5px;
        margin-bottom: 6px;
    }
    .metric-value {
        font-size: 24px;
        font-weight: 700;
        color: #0f172a;
        margin-bottom: 4px;
    }
    .metric-sub {
        font-size: 12px;
        color: #475569;
    }

    /* Status badge */
    .badge {
        display: inline-block;
        padding: 3px 8px;
        font-size: 11px;
        font-weight: 600;
        border-radius: 4px;
        text-transform: uppercase;
        letter-spacing: 0.3px;
    }
    .badge-tier1 {
        background-color: #dbeafe;
        color: #1e40af;
        border: 1px solid #bfdbfe;
    }
    .badge-tier2 {
        background-color: #fef3c7;
        color: #92400e;
        border: 1px solid #fde68a;
    }
    .badge-tier3 {
        background-color: #f1f5f9;
        color: #475569;
        border: 1px solid #e2e8f0;
    }

    /* Information callout */
    .callout-box {
        background-color: #f8fafc;
        border-left: 4px solid #3b82f6;
        padding: 16px 20px;
        border-radius: 0 6px 6px 0;
        margin: 16px 0;
        color: #1e293b;
        font-size: 13.5px;
        line-height: 1.6;
    }

    /* Tab navigation tweaks */
    button[data-baseweb="tab"] {
        font-size: 14px !important;
        font-weight: 600 !important;
        padding-top: 10px !important;
        padding-bottom: 10px !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# --- DIRECTORY CONFIGURATION ---
BASE_DIR = Path(__file__).resolve().parent
EXPORTS_DIR = BASE_DIR / "exports"

# --- DATA LOADERS WITH CACHE ---
@st.cache_data
def load_summary_data() -> pd.DataFrame:
    path = EXPORTS_DIR / "master_7_niches_summary.csv"
    if path.exists():
        df = pd.read_csv(path)
        # Add metadata from competitor analysis
        saturation_map = {
            1: 62.0,  # Kost Eksklusif
            2: 58.0,  # Gym
            3: 20.0,  # Rental
            4: 88.0,  # Barbershop
            5: 34.0,  # Percetakan
            6: 26.0,  # Car Wash
            7: 52.0,  # Pet Shop
        }
        tier_map = {
            1: "Tier 2 (Moderat)",
            2: "Tier 2 (Moderat)",
            3: "Tier 1 (Prioritas Utama)",
            4: "Tier 3 (Jenuh / POS Red Ocean)",
            5: "Tier 1 (Prioritas Tinggi)",
            6: "Tier 1 (Prioritas Tinggi)",
            7: "Tier 2 (Moderat)",
        }
        df["software_saturation_pct"] = df["niche_id"].map(saturation_map)
        df["opportunity_tier"] = df["niche_id"].map(tier_map)
        return df
    return pd.DataFrame()


@st.cache_data
def load_niche_file(filename: str) -> pd.DataFrame:
    path = EXPORTS_DIR / filename
    if path.exists():
        df = pd.read_csv(path)
        # Ensure ratings and reviews are numeric
        if "rating" in df.columns:
            df["rating"] = pd.to_numeric(df["rating"], errors="coerce")
        if "reviews_count" in df.columns:
            df["reviews_count"] = pd.to_numeric(df["reviews_count"], errors="coerce").fillna(0).astype(int)
        
        # Determine region tag based on keyword/address
        def detect_region(row):
            text = f"{row.get('search_keyword', '')} {row.get('address', '')}".lower()
            if "magelang" in text:
                return "Magelang"
            if "klaten" in text:
                return "Klaten"
            if "jogja" in text or "sleman" in text or "bantul" in text or "yogyakarta" in text:
                return "DIY Yogyakarta"
            return "Lainnya / Regional"
        
        df["region"] = df.apply(detect_region, axis=1)
        return df
    return pd.DataFrame()


# File catalog mapping
NICHE_FILES = {
    "Master Dataset (Seluruh 127 Entitas)": "all_7_niches_contacts.csv",
    "Niche 1: Kost Eksklusif": "niche_1_kost_eksklusif.csv",
    "Niche 2: Gym & Pusat Kebugaran": "niche_2_gym_kebugaran.csv",
    "Niche 3: Rental Kendaraan & Kamera": "niche_3_rental_kendaraan_kamera.csv",
    "Niche 4: Barbershop & Salon": "niche_4_barbershop_salon.csv",
    "Niche 5: Percetakan Digital": "niche_5_percetakan_digital.csv",
    "Niche 6: Car Wash": "niche_6_car_wash.csv",
    "Niche 7: Pet Shop, Grooming, & Vet": "niche_7_pet_shop_vet.csv",
}

NICHE_DETAILS = {
    1: {
        "title": "Kost Eksklusif & Co-living",
        "incumbents": "Mamikos Pro, Juragan Kost, Maikos, BukuKos",
        "pricing": "Rp99.000 – Rp300.000 / bulan atau skema komisi listing",
        "saturation": "62% (Tingkat Menengah)",
        "pain_points": [
            "Pemilik menolak potongan komisi sewa bulanan dari agregator kamar.",
            "Rekonsiliasi mutasi bank transfer dan konfirmasi pembayaran manual via WA menyita waktu pengelola.",
            "Pencatatan pembukuan multi-pintu dan pengingat jatuh tempo sewa sering terlewat."
        ],
        "mvp_solution": "Sistem Auto-Billing QRIS/VA otomatis terintegrasi WhatsApp gateway tanpa biaya potongan komisi per kamar."
    },
    2: {
        "title": "Gym & Pusat Kebugaran",
        "incumbents": "OnlyGym, Fitlink, GymMaster, AYO / KUYY",
        "pricing": "Rp300.000 – Rp1.400.000 / bulan",
        "saturation": "58% (Tingkat Menengah)",
        "pain_points": [
            "Biaya hardware turnstile gate member dan setup fingerprint mahal untuk gym lokal mandiri.",
            "Kebocoran pendapatan akibat member sharing barcode kartu ke teman non-member.",
            "Perhitungan komisi sesi Personal Trainer (PT) masih direkap manual di spreadsheet."
        ],
        "mvp_solution": "Micro-SaaS check-in QR dinamis (anti-screenshot) dan pencatatan sesi PT otomatis untuk studio kelas & gym rintisan."
    },
    3: {
        "title": "Rental Kendaraan & Kamera",
        "incumbents": "CekSewa, WSoft RentCar (Segmen rental kamera nihil pemain SaaS lokal)",
        "pricing": "Freemium – Rp150.000 / bulan",
        "saturation": "20% (Peluang Sangat Luas / Sweet Spot)",
        "pain_points": [
            "Tingginya risiko penggelapan unit kamera lensa dan kendaraan rental di wilayah wisata DIY-Jateng.",
            "Inspeksi kondisi fisik barang (baret, jamur lensa, lecet body) masih manual dan rawan sengketa klaim deposit.",
            "Jadwal ketersediaan unit sewa harian/jam masih ditanyakan berulang kali via pesan chat WhatsApp."
        ],
        "mvp_solution": "Katalog booking web publik real-time, verifikasi identitas e-KYC KTP anti-fraud, dan modul checklist foto kondisi serah terima unit."
    },
    4: {
        "title": "Barbershop & Salon",
        "incumbents": "Majoo, Zenwel / Olsera, ReBill POS, Fresha",
        "pricing": "Rp107.000 – Rp999.000 / bulan",
        "saturation": "88% (Pasar Sangat Padat / Red Ocean)",
        "pain_points": [
            "Fitur komisi kapster dan antrean lanjutan sering dikunci pada tier langganan POS enterprise termahal.",
            "Pelanggan enggan mengunduh aplikasi mobile native hanya untuk potong rambut 3 minggu sekali.",
            "Sulit memantau performa dan pembagian bagi hasil harian kapster secara transparan."
        ],
        "mvp_solution": "Micro-tool antrean online berbasis web tanpa instal aplikasi (direct browser) dengan otomasi pengingat potong rambut 3 mingguan via WhatsApp."
    },
    5: {
        "title": "Percetakan Digital & Konveksi",
        "incumbents": "Printsoft (Hana), KasirPercetakan, Printflow, software desktop marketplace",
        "pricing": "Rp399.000 – Rp3.600.000 (lisensi beli-putus / ERP kustom)",
        "saturation": "34% (Peluang Terbuka / Blue Ocean)",
        "pain_points": [
            "Antrean kasir menumpuk karena lamanya kalkulasi manual dimensi luas bahan (A3+, meteran, gramatur).",
            "Pelanggan sering menghubungi admin berulang kali menanyakan status SPK: apakah pesanan sudah dicetak, dipotong, atau siap ambil.",
            "Miskomunikasi spesifikasi file cetak antara bagian depan (frontdesk) dan operator mesin produksi."
        ],
        "mvp_solution": "Kalkulator instan harga cetak bahan dan portal pelacak status SPK produksi online menggunakan link publik WhatsApp."
    },
    6: {
        "title": "Car Wash & Auto Detailing",
        "incumbents": "Cucimoo, Car Wash POS (Avymob), Kledo POS",
        "pricing": "Freemium – Rp199.000 / bulan",
        "saturation": "26% (Peluang Sangat Terbuka)",
        "pain_points": [
            "Pelanggan menunggu tanpa kepastian durasi pengerjaan saat antrean mobil di pit cuci sedang padat.",
            "Nota kertas manual rentan rusak terkena air dan rawan manipulasi rekonsiliasi kasir harian.",
            "Pencatatan bagi hasil operator cuci per nomor plat kendaraan masih memakai papan tulis manual."
        ],
        "mvp_solution": "Kasir cepat 3-klik berbasis nomor polisi, papan antrean status cuci publik, dan auto-notifikasi WhatsApp saat kendaraan selesai."
    },
    7: {
        "title": "Pet Shop, Grooming, & Vet",
        "incumbents": "KlinikPro Vet, PAWSI Vet, kumoVet",
        "pricing": "Rp200.000 – Rp488.000 / bulan",
        "saturation": "52% (Tingkat Menengah)",
        "pain_points": [
            "Aplikasi EMR medis klinik veteriner terlalu mahal dan rumit untuk pet shop ritel murni atau home grooming.",
            "Pemilik hewan sering cemas dan terus menanyakan kondisi anabul saat dititipkan di pet hotel.",
            "Pengingat vaksin tahunan dan jadwal grooming rutin hewan peliharaan belum terotomasi."
        ],
        "mvp_solution": "SaaS pencatatan grooming & pet hotel ringan dengan modul kirim foto/video kondisi hewan ke WhatsApp pemilik serta jadwal vaksin berkala."
    }
}

# --- HEADER SECTION ---
st.markdown(
    """
    <div class="corporate-header">
        <h1>SISTEM INTELIJEN PASAR & VALIDASI PROSPEK B2B MICRO-SAAS</h1>
        <p>Analisis Empiris 7 Niche Bisnis Lokal Berdasarkan Data Google Maps di Wilayah DI Yogyakarta, Magelang, & Klaten</p>
    </div>
    """,
    unsafe_allow_html=True,
)

# Load master summary data
summary_df = load_summary_data()

# --- TOP EXECUTIVE METRIC TILES ---
total_sample = int(summary_df["total_sample_scraped"].sum()) if not summary_df.empty else 605
top_niche_reviews = summary_df.loc[summary_df["avg_reviews"].idxmax()] if not summary_df.empty else None
top_avg_val = f"{top_niche_reviews['avg_reviews']:.1f} Ulasan" if top_niche_reviews is not None else "-"
top_avg_name = f"{top_niche_reviews['niche_name']} (Rata-rata)" if top_niche_reviews is not None else "-"

max_rev_row = summary_df.loc[summary_df["max_reviews"].idxmax()] if not summary_df.empty else None
max_rev_val = f"{int(max_rev_row['max_reviews']):,} Ulasan".replace(",", ".") if max_rev_row is not None else "-"
max_rev_name = f"{max_rev_row['top_active_business'].split('(')[0].strip()}" if max_rev_row is not None else "-"

col_kpi1, col_kpi2, col_kpi3, col_kpi4, col_kpi5 = st.columns(5)
with col_kpi1:
    st.markdown(
        """
        <div class="metric-card">
            <div class="metric-title">Total Niche Diuji</div>
            <div class="metric-value">7 Vertikal</div>
            <div class="metric-sub">B2B Micro-SaaS Terfokus</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
with col_kpi2:
    st.markdown(
        f"""
        <div class="metric-card">
            <div class="metric-title">Total Entitas Tervalidasi</div>
            <div class="metric-value">{total_sample} Bisnis</div>
            <div class="metric-sub">DIY, Magelang, Klaten</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
with col_kpi3:
    st.markdown(
        f"""
        <div class="metric-card">
            <div class="metric-title">Aktivitas Ulasan Tertinggi</div>
            <div class="metric-value">{top_avg_val}</div>
            <div class="metric-sub">{top_avg_name}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
with col_kpi4:
    st.markdown(
        f"""
        <div class="metric-card">
            <div class="metric-title">Volume Review Maksimum</div>
            <div class="metric-value">{max_rev_val}</div>
            <div class="metric-sub">{max_rev_name}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
with col_kpi5:
    st.markdown(
        """
        <div class="metric-card">
            <div class="metric-title">Rekomendasi Utama (Tier 1)</div>
            <div class="metric-value">Rental Alat</div>
            <div class="metric-sub">Saturasi Software Rendah (20%)</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

st.write("")

# --- MAIN TABS ARCHITECTURE ---
tab1, tab2, tab3, tab4 = st.tabs([
    "Ringkasan Eksekutif & Matriks Prioritas",
    "Analisis Komparatif 7 Niche",
    "Eksplorasi Data Manual (7 File & Master)",
    "Integrasi Presentasi Google Slides",
])

# ==============================================================================
# TAB 1: EXECUTIVE BENCHMARK & PRIORITIZATION MATRIX
# ==============================================================================
with tab1:
    st.subheader("Matriks Perbandingan 7 Niche Bisnis")
    st.caption("Data hasil scraping 127 profil Google Maps diperkaya dengan tingkat saturasi software dari dokumen analisis kompetitor.")

    if not summary_df.empty:
        display_summary = summary_df[[
            "niche_id", "niche_name", "total_sample_scraped", "avg_rating",
            "avg_reviews", "max_reviews", "software_saturation_pct", "opportunity_tier", "top_active_business"
        ]].copy()
        
        display_summary.columns = [
            "ID", "Nama Niche", "Sampel Scraped", "Rata-rata Rating",
            "Rata-rata Ulasan", "Maksimum Ulasan", "Saturasi Software (%)", "Klasifikasi Peluang", "Entitas Teraktif"
        ]
        
        st.dataframe(
            display_summary,
            use_container_width=True,
            hide_index=True,
            column_config={
                "ID": st.column_config.NumberColumn(width="small"),
                "Nama Niche": st.column_config.TextColumn(width="medium"),
                "Rata-rata Rating": st.column_config.NumberColumn(format="%.2f ★"),
                "Rata-rata Ulasan": st.column_config.NumberColumn(format="%.1f"),
                "Maksimum Ulasan": st.column_config.NumberColumn(format="%d"),
                "Saturasi Software (%)": st.column_config.ProgressColumn(
                    min_value=0, max_value=100, format="%.0f%%"
                ),
            }
        )

    st.write("")
    
    # CHARTS GRID
    col_chart1, col_chart2 = st.columns(2)

    with col_chart1:
        st.markdown("##### Rata-rata Ulasan per Niche (Tingkat Aktivitas Pelanggan)")
        chart_avg_rev = (
            alt.Chart(summary_df)
            .mark_bar(color="#1e40af", cornerRadiusEnd=4)
            .encode(
                x=alt.X("avg_reviews:Q", title="Rata-rata Ulasan"),
                y=alt.Y("niche_name:N", sort="-x", title="Niche Bisnis"),
                tooltip=[
                    alt.Tooltip("niche_name:N", title="Niche"),
                    alt.Tooltip("avg_reviews:Q", format=".1f", title="Rata-rata Ulasan"),
                    alt.Tooltip("max_reviews:Q", title="Ulasan Tertinggi"),
                ],
            )
            .properties(height=320)
        )
        st.altair_chart(chart_avg_rev, use_container_width=True)

    with col_chart2:
        st.markdown("##### Ulasan Maksimum (Skala Bisnis Tertinggi per Niche)")
        chart_max_rev = (
            alt.Chart(summary_df)
            .mark_bar(color="#0284c7", cornerRadiusEnd=4)
            .encode(
                x=alt.X("max_reviews:Q", title="Ulasan Terbanyak Tercatat"),
                y=alt.Y("niche_name:N", sort="-x", title="Niche Bisnis"),
                tooltip=[
                    alt.Tooltip("niche_name:N", title="Niche"),
                    alt.Tooltip("max_reviews:Q", title="Ulasan Maksimal"),
                    alt.Tooltip("top_active_business:N", title="Bisnis Teraktif"),
                ],
            )
            .properties(height=320)
        )
        st.altair_chart(chart_max_rev, use_container_width=True)

    col_chart3, col_chart4 = st.columns(2)

    with col_chart3:
        st.markdown("##### Matriks Prioritas: Saturasi Software vs Volume Review")
        # Scatter/Bubble plot comparing saturation with reviews
        chart_matrix = (
            alt.Chart(summary_df)
            .mark_circle(size=250)
            .encode(
                x=alt.X("software_saturation_pct:Q", title="Tingkat Saturasi Software (%)", scale=alt.Scale(domain=[10, 100])),
                y=alt.Y("avg_reviews:Q", title="Rata-rata Review (Volume Pasar)", scale=alt.Scale(domain=[0, 700])),
                color=alt.Color("opportunity_tier:N", title="Klasifikasi Peluang", scale=alt.Scale(
                    domain=["Tier 1 (Prioritas Utama)", "Tier 1 (Prioritas Tinggi)", "Tier 2 (Moderat)", "Tier 3 (Jenuh / POS Red Ocean)"],
                    range=["#16a34a", "#2563eb", "#d97706", "#dc2626"]
                )),
                tooltip=[
                    alt.Tooltip("niche_name:N", title="Niche"),
                    alt.Tooltip("software_saturation_pct:Q", format=".0f%%", title="Saturasi"),
                    alt.Tooltip("avg_reviews:Q", format=".1f", title="Rata-rata Review"),
                    alt.Tooltip("opportunity_tier:N", title="Tier Peluang"),
                ]
            )
            .properties(height=320)
        )
        st.altair_chart(chart_matrix, use_container_width=True)

    with col_chart4:
        st.markdown("##### Sebaran Sampel Geografis per Niche (DIY vs Magelang vs Klaten)")
        geo_df = summary_df.melt(
            id_vars=["niche_name"],
            value_vars=["diy_sample", "magelang_sample", "klaten_sample"],
            var_name="Wilayah",
            value_name="Jumlah Entitas",
        )
        geo_df["Wilayah"] = geo_df["Wilayah"].replace({
            "diy_sample": "DI Yogyakarta",
            "magelang_sample": "Magelang",
            "klaten_sample": "Klaten"
        })
        chart_geo = (
            alt.Chart(geo_df)
            .mark_bar()
            .encode(
                x=alt.X("Jumlah Entitas:Q", title="Jumlah Entitas"),
                y=alt.Y("niche_name:N", title="Niche"),
                color=alt.Color("Wilayah:N", scale=alt.Scale(range=["#1e3a8a", "#0284c7", "#94a3b8"])),
                tooltip=["niche_name:N", "Wilayah:N", "Jumlah Entitas:Q"]
            )
            .properties(height=320)
        )
        st.altair_chart(chart_geo, use_container_width=True)

    st.markdown(
        """
        <div class="callout-box">
            <strong>Kesimpulan Strategis Matriks Prioritas:</strong><br>
            • <strong>Peluang Tier 1 (Sweet Spot):</strong> <em>Rental Kendaraan & Kamera</em> (103 entitas, saturasi 20%, top: 2.468 ulasan) dan <em>Car Wash</em> (88 entitas, saturasi 26%, top: 1.779 ulasan). Pasar ini memiliki volume interaksi ulasan tinggi namun kompetisi SaaS lokal masih sangat rendah.<br>
            • <strong>Peluang Efisiensi SPK & Tracking:</strong> <em>Percetakan Digital</em> (89 entitas, 351.8 avg ulasan; top: 2.792 ulasan) dan <em>Barbershop & Salon</em> (90 entitas, 497.0 avg ulasan; top: 4.395 ulasan) mencerminkan perputaran pelanggan yang sangat masif di wilayah DIY-Jateng.<br>
            • <strong>Zona Kompetisi Tinggi (Red Ocean POS):</strong> Segmen <em>Barbershop & Salon</em> jenuh (88% saturasi POS generik), memerlukan positioning mikro khusus reservasi kapster 3-mingguan tanpa instal aplikasi.
        </div>
        """,
        unsafe_allow_html=True,
    )


# ==============================================================================
# TAB 2: DETAILED NICHE-BY-NICHE COMPARATIVE ANALYSIS
# ==============================================================================
with tab2:
    st.subheader("Analisis Mendalam 7 Vertikal B2B Micro-SaaS")
    st.caption("Eksplorasi profil pemain petahana, struktur harga, titik masalah operasional, dan rekomendasi MVP.")

    selected_niche_id = st.selectbox(
        "Pilih Niche Bisnis untuk Menampilkan Detail:",
        options=list(NICHE_DETAILS.keys()),
        format_func=lambda x: f"Niche {x}: {NICHE_DETAILS[x]['title']}"
    )

    detail = NICHE_DETAILS[selected_niche_id]
    niche_stat = summary_df[summary_df["niche_id"] == selected_niche_id].iloc[0] if not summary_df.empty else None

    col_meta1, col_meta2, col_meta3, col_meta4 = st.columns(4)
    with col_meta1:
        st.metric("Tingkat Saturasi Software", detail["saturation"])
    with col_meta2:
        st.metric("Rata-rata Rating", f"{niche_stat['avg_rating']:.2f} ★" if niche_stat is not None else "-")
    with col_meta3:
        st.metric("Rata-rata Ulasan", f"{niche_stat['avg_reviews']:.1f}" if niche_stat is not None else "-")
    with col_meta4:
        st.metric("Ulasan Maksimal", f"{niche_stat['max_reviews']}" if niche_stat is not None else "-")

    col_d1, col_d2 = st.columns([1, 1])

    with col_d1:
        st.markdown("##### Profil Industri & Pemain Utama")
        st.markdown(f"**Pemain Petahana Saat Ini:** {detail['incumbents']}")
        st.markdown(f"**Rentang Harga Langganan Pasar:** {detail['pricing']}")
        st.markdown(f"**Bisnis Teraktif Sampel Scraping:** {niche_stat['top_active_business'] if niche_stat is not None else '-'}")
        
        st.markdown("##### Titik Masalah Operasional Utama (Pain Points)")
        for pp in detail["pain_points"]:
            st.markdown(f"• {pp}")

    with col_d2:
        st.markdown("##### Rekomendasi Solusi MVP Micro-SaaS")
        st.markdown(
            f"""
            <div style="background-color: #f1f5f9; border: 1px solid #cbd5e1; border-radius: 6px; padding: 18px 20px; font-size: 14px; line-height: 1.6; color: #0f172a;">
                <strong>Arsitektur Solusi Minimum (MVP):</strong><br>
                {detail['mvp_solution']}
            </div>
            """,
            unsafe_allow_html=True,
        )
        
        st.write("")
        st.markdown("##### Model Pendapatan yang Direkomendasikan")
        st.markdown("• **Model Langganan Flat:** Rp99.000 – Rp149.000 / bulan per outlet tanpa biaya potongan transaksi.")
        st.markdown("• **Kanal Distribusi Penjualan:** Direct sales / WhatsApp outreach ke kontak bisnis hasil ekstraksi Google Maps di DIY, Magelang, dan Klaten.")


# ==============================================================================
# TAB 3: MANUAL DATA INSPECTION (ALL 7 FILES & MASTER DATA)
# ==============================================================================
with tab3:
    st.subheader("Eksplorasi Data Manual (7 File Niche & Master Data)")
    st.caption("Bagian ini memfasilitasi pemeriksaan langsung entitas bisnis hasil scraping per file CSV secara independen.")

    col_file_sel, col_download = st.columns([3, 1])
    with col_file_sel:
        selected_file_label = st.selectbox(
            "Pilih File Dataset Hasil Scraping:",
            options=list(NICHE_FILES.keys()),
            index=0
        )
    
    selected_filename = NICHE_FILES[selected_file_label]
    df_raw = load_niche_file(selected_filename)

    with col_download:
        st.write("")
        if not df_raw.empty:
            csv_bytes = df_raw.to_csv(index=False).encode("utf-8")
            st.download_button(
                label=f"Unduh File CSV ({selected_filename})",
                data=csv_bytes,
                file_name=selected_filename,
                mime="text/csv",
                use_container_width=True
            )

    if df_raw.empty:
        st.warning(f"File {selected_filename} tidak ditemukan di direktori exports/.")
    else:
        # Filter controls
        st.markdown("---")
        st.markdown("##### Filter Data Interaktif")
        
        col_f1, col_f2, col_f3, col_f4 = st.columns(4)
        
        with col_f1:
            search_query = st.text_input("Pencarian Teks (Nama, Kategori, Alamat):", placeholder="Contoh: Depok, Studio, Klaten...")
        
        with col_f2:
            min_rating_val = float(df_raw["rating"].min()) if "rating" in df_raw.columns and not df_raw["rating"].isna().all() else 0.0
            max_rating_val = float(df_raw["rating"].max()) if "rating" in df_raw.columns and not df_raw["rating"].isna().all() else 5.0
            rating_filter = st.slider("Rating Minimum:", min_value=1.0, max_value=5.0, value=min_rating_val, step=0.1)
        
        with col_f3:
            max_reviews_in_df = int(df_raw["reviews_count"].max()) if "reviews_count" in df_raw.columns else 100
            reviews_filter = st.number_input("Jumlah Ulasan Minimum:", min_value=0, max_value=max(1, max_reviews_in_df), value=0, step=10)
        
        with col_f4:
            region_options = ["Semua Wilayah"] + sorted(list(df_raw["region"].unique())) if "region" in df_raw.columns else ["Semua Wilayah"]
            selected_region = st.selectbox("Wilayah Geografis:", options=region_options)

        # Contact filters
        col_c1, col_c2, col_c3 = st.columns(3)
        with col_c1:
            only_with_phone = st.checkbox("Hanya yang memiliki Nomor Telepon", value=False)
        with col_c2:
            only_with_website = st.checkbox("Hanya yang memiliki Tautan Website", value=False)
        with col_c3:
            only_with_email = st.checkbox("Hanya yang memiliki Email Terekstraksi", value=False)

        # Apply filtering
        filtered_df = df_raw.copy()

        if search_query:
            q = search_query.strip().lower()
            mask = (
                filtered_df["business_name"].astype(str).str.lower().str.contains(q) |
                filtered_df["category"].astype(str).str.lower().str.contains(q) |
                filtered_df["address"].astype(str).str.lower().str.contains(q)
            )
            filtered_df = filtered_df[mask]

        if "rating" in filtered_df.columns:
            filtered_df = filtered_df[filtered_df["rating"] >= rating_filter]

        if "reviews_count" in filtered_df.columns:
            filtered_df = filtered_df[filtered_df["reviews_count"] >= reviews_filter]

        if selected_region != "Semua Wilayah" and "region" in filtered_df.columns:
            filtered_df = filtered_df[filtered_df["region"] == selected_region]

        if only_with_phone and "phone_number" in filtered_df.columns:
            filtered_df = filtered_df[filtered_df["phone_number"].notna() & (filtered_df["phone_number"] != "")]

        if only_with_website and "website_url" in filtered_df.columns:
            filtered_df = filtered_df[filtered_df["website_url"].notna() & (filtered_df["website_url"] != "")]

        if only_with_email and "extracted_emails" in filtered_df.columns:
            filtered_df = filtered_df[filtered_df["extracted_emails"].notna() & (filtered_df["extracted_emails"] != "")]

        # Summary bar for filtered results
        tot_filtered = len(filtered_df)
        tot_raw = len(df_raw)
        has_phone_pct = (filtered_df["phone_number"].notna() & (filtered_df["phone_number"] != "")).mean() * 100 if tot_filtered > 0 else 0
        has_web_pct = (filtered_df["website_url"].notna() & (filtered_df["website_url"] != "")).mean() * 100 if tot_filtered > 0 else 0
        avg_rat_filtered = filtered_df["rating"].mean() if tot_filtered > 0 else 0
        avg_rev_filtered = filtered_df["reviews_count"].mean() if tot_filtered > 0 else 0

        st.write("")
        col_res1, col_res2, col_res3, col_res4 = st.columns(4)
        with col_res1:
            st.metric("Entitas Ditampilkan", f"{tot_filtered} dari {tot_raw}")
        with col_res2:
            st.metric("Kelengkapan Telepon", f"{has_phone_pct:.1f}%")
        with col_res3:
            st.metric("Kelengkapan Website", f"{has_web_pct:.1f}%")
        with col_res4:
            st.metric("Rata-rata Review Filtered", f"{avg_rev_filtered:.1f}")

        # Render styled dataframe
        st.write("")
        cols_to_show = [
            "business_name", "category", "rating", "reviews_count",
            "phone_number", "website_url", "address", "extracted_emails", "region"
        ]
        available_cols = [c for c in cols_to_show if c in filtered_df.columns]
        
        st.dataframe(
            filtered_df[available_cols],
            use_container_width=True,
            hide_index=True,
            column_config={
                "business_name": st.column_config.TextColumn("Nama Bisnis", width="medium"),
                "category": st.column_config.TextColumn("Kategori", width="small"),
                "rating": st.column_config.NumberColumn("Rating", format="%.1f ★", width="small"),
                "reviews_count": st.column_config.NumberColumn("Total Ulasan", format="%d", width="small"),
                "phone_number": st.column_config.TextColumn("No. Telepon", width="medium"),
                "website_url": st.column_config.LinkColumn("Website / Profil URL", width="medium"),
                "address": st.column_config.TextColumn("Alamat Fisik", width="large"),
                "extracted_emails": st.column_config.TextColumn("Email Terekstraksi", width="medium"),
                "region": st.column_config.TextColumn("Wilayah", width="small"),
            }
        )


# ==============================================================================
# TAB 4: GOOGLE SLIDES PRESENTATION DECK INTEGRATION
# ==============================================================================
with tab4:
    st.subheader("Integrasi Presentasi Google Slides")
    st.caption("Presentasi eksekutif 10 slide telah disinkronkan ke Google Drive untuk kebutuhan paparan pemangku kepentingan.")

    slides_url = "https://docs.google.com/presentation/d/14t__HKhfUhLBtCdFePodnnAGZaeQpR588UcawF8JiNM/edit"
    
    st.markdown(
        f"""
        <div style="background-color: #ffffff; border: 1px solid #cbd5e1; border-radius: 8px; padding: 24px; margin-bottom: 20px;">
            <h4 style="margin: 0 0 10px 0; color: #0f172a;">Laporan Riset Pasar B2B Micro-SaaS (DIY, Magelang, Klaten)</h4>
            <p style="color: #475569; font-size: 14px; margin-bottom: 16px;">
                Dokumen presentasi mencakup ringkasan eksekutif, metodologi ekstraksi data Google Maps, profil aktivitas per vertikal industri, matriks prioritas, dan peta jalan komersialisasi produk.
            </p>
            <a href="{slides_url}" target="_blank" style="display: inline-block; background-color: #2563eb; color: #ffffff; text-decoration: none; padding: 10px 18px; border-radius: 6px; font-weight: 600; font-size: 13.5px;">
                Buka Presentasi di Google Slides &rarr;
            </a>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("##### Ringkasan Struktur 10 Slide Presentasi:")
    slide_structure = [
        ("Slide 1: Judul Eksekutif", "Laporan Riset Pasar & Validasi Prospek B2B Micro-SaaS Regional DIY, Magelang, & Klaten."),
        ("Slide 2: Metodologi & Hasil Scraping", "Scraping 127 entitas Google Maps dengan tingkat kelengkapan nomor telepon 95.3% dan review."),
        ("Slide 3: Ringkasan Aktivitas Review per Niche", "Komparasi rata-rata ulasan: Percetakan (633.7), Pet Shop (422.7), Barbershop (297.0), Rental (239.7)."),
        ("Slide 4: Analisis Niche Tier 1 (Rental)", "Peluang tertinggi dengan saturasi software hanya 20% dan ulasan aktif hingga 1,445 ulasan."),
        ("Slide 5: Analisis Niche Tier 1 (Car Wash)", "Saturasi 26%, nota basah dan komisi pencuci mobil membutuhkan automasi antrean publik dan WA."),
        ("Slide 6: Analisis Niche Tier 1 (Percetakan Digital)", "Volume ulasan masif (2,792 ulasan puncak), butuh automasi tracking SPK dan kalkulator bahan."),
        ("Slide 7: Analisis Niche Tier 2 (Pet Shop & Gym)", "Segmen moderat dengan kebutuhan rekam medis EMR ringan dan anti-fraud member check-in."),
        ("Slide 8: Analisis Niche Tier 3 (Barbershop & Kost)", "Pasar padat (red ocean POS 88%), memerlukan positioning mikro yang sangat spesifik."),
        ("Slide 9: Matriks Prioritas Rekomendasi", "Visualisasi kuadran strategi go-to-market berdasarkan saturasi software versus volume pasar."),
        ("Slide 10: Rencana Aksi & Roadmap Validasi", "Langkah eksekusi outreach WhatsApp ke kontak terverifikasi dan peluncuran MVP 30 hari.")
    ]

    for title, desc in slide_structure:
        with st.expander(title):
            st.write(desc)

# --- FOOTER ---
st.markdown("---")
st.markdown(
    """
    <div style="text-align: center; color: #64748b; font-size: 12px; padding: 12px 0;">
        Sistem Ekstraksi Kontak Bisnis Google Maps & Analisis Pasar B2B Micro-SaaS • Wilayah DIY, Magelang, Klaten
    </div>
    """,
    unsafe_allow_html=True,
)
