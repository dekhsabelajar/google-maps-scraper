"""
Executive Dashboard: B2B Micro-SaaS Market Intelligence
Minimalist, high-clarity dashboard analyzing 605 verified business entities
across DIY Yogyakarta, Magelang, and Klaten.
Strictly professional design with concise text and zero unnecessary emojis.
"""

from pathlib import Path
import pandas as pd
import streamlit as st
import altair as alt

# --- PAGE CONFIGURATION ---
st.set_page_config(
    page_title="B2B Micro-SaaS Market Intelligence",
    page_icon=None,
    layout="wide",
    initial_sidebar_state="collapsed",
)

# --- MINIMALIST CORPORATE CSS ---
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    }

    /* Clean subtle header */
    .top-bar {
        border-bottom: 1px solid #e2e8f0;
        padding-bottom: 16px;
        margin-bottom: 24px;
    }
    .top-title {
        font-size: 22px;
        font-weight: 700;
        color: #0f172a;
        margin: 0;
        letter-spacing: -0.4px;
    }
    .top-subtitle {
        font-size: 13px;
        color: #64748b;
        margin: 4px 0 0 0;
    }

    /* Metric cards */
    .kpi-card {
        background-color: #f8fafc;
        border: 1px solid #e2e8f0;
        border-radius: 8px;
        padding: 16px 20px;
    }
    .kpi-label {
        font-size: 11px;
        font-weight: 600;
        text-transform: uppercase;
        color: #64748b;
        letter-spacing: 0.5px;
        margin-bottom: 6px;
    }
    .kpi-number {
        font-size: 26px;
        font-weight: 700;
        color: #0f172a;
        letter-spacing: -0.5px;
    }
    .kpi-desc {
        font-size: 12px;
        color: #2563eb;
        margin-top: 4px;
        font-weight: 500;
    }

    /* Clean tabs */
    button[data-baseweb="tab"] {
        font-size: 13.5px !important;
        font-weight: 600 !important;
        padding: 8px 16px !important;
    }

    /* Card container */
    .section-card {
        background: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 8px;
        padding: 20px;
        margin-bottom: 20px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# --- DIRECTORY & DATA LOADERS ---
BASE_DIR = Path(__file__).resolve().parent
EXPORTS_DIR = BASE_DIR / "exports"


@st.cache_data
def load_summary_data() -> pd.DataFrame:
    path = EXPORTS_DIR / "master_7_niches_summary.csv"
    if path.exists():
        df = pd.read_csv(path)
        saturation_map = {1: 62.0, 2: 58.0, 3: 20.0, 4: 88.0, 5: 34.0, 6: 26.0, 7: 52.0}
        tier_map = {
            1: "Tier 2",
            2: "Tier 2",
            3: "Tier 1 (Peluang Utama)",
            4: "Tier 3 (Jenuh POS)",
            5: "Tier 1 (Peluang Tinggi)",
            6: "Tier 1 (Peluang Tinggi)",
            7: "Tier 2",
        }
        df["saturation_pct"] = df["niche_id"].map(saturation_map)
        df["opportunity_tier"] = df["niche_id"].map(tier_map)
        return df
    return pd.DataFrame()


@st.cache_data
def load_niche_data(filename: str) -> pd.DataFrame:
    path = EXPORTS_DIR / filename
    if path.exists():
        df = pd.read_csv(path)
        if "rating" in df.columns:
            df["rating"] = pd.to_numeric(df["rating"], errors="coerce")
        if "reviews_count" in df.columns:
            df["reviews_count"] = pd.to_numeric(df["reviews_count"], errors="coerce").fillna(0).astype(int)

        def get_region(row):
            txt = f"{row.get('search_keyword', '')} {row.get('address', '')}".lower()
            if "magelang" in txt:
                return "Magelang"
            if "klaten" in txt:
                return "Klaten"
            return "DIY Yogyakarta"

        df["region"] = df.apply(get_region, axis=1)
        return df
    return pd.DataFrame()


# Catalog of 7 niche CSV files
FILE_OPTIONS = {
    "Master Dataset (Semua 605 Entitas)": "all_7_niches_contacts.csv",
    "Niche 1: Kost Eksklusif": "niche_1_kost_eksklusif.csv",
    "Niche 2: Gym & Pusat Kebugaran": "niche_2_gym_kebugaran.csv",
    "Niche 3: Rental Kendaraan & Kamera": "niche_3_rental_kendaraan_kamera.csv",
    "Niche 4: Barbershop & Salon": "niche_4_barbershop_salon.csv",
    "Niche 5: Percetakan Digital": "niche_5_percetakan_digital.csv",
    "Niche 6: Car Wash & Detailing": "niche_6_car_wash.csv",
    "Niche 7: Pet Shop, Grooming, & Vet": "niche_7_pet_shop_vet.csv",
}

# --- HEADER ---
st.markdown(
    """
    <div class="top-bar">
        <div class="top-title">B2B Micro-SaaS Market Intelligence</div>
        <div class="top-subtitle">Analisis Validasi Empiris 605 Entitas Google Maps (DIY Yogyakarta, Magelang, & Klaten)</div>
    </div>
    """,
    unsafe_allow_html=True,
)

summary_df = load_summary_data()

# --- 4 CLEAN KPI TILES ---
total_entities = int(summary_df["total_sample_scraped"].sum()) if not summary_df.empty else 605
top_rev_row = summary_df.loc[summary_df["max_reviews"].idxmax()] if not summary_df.empty else None
top_avg_row = summary_df.loc[summary_df["avg_reviews"].idxmax()] if not summary_df.empty else None

col1, col2, col3, col4 = st.columns(4)
with col1:
    st.markdown(
        f"""
        <div class="kpi-card">
            <div class="kpi-label">Total Entitas Tervalidasi</div>
            <div class="kpi-number">{total_entities:,}</div>
            <div class="kpi-desc">7 Vertikal • DIY, Magelang, Klaten</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
with col2:
    st.markdown(
        """
        <div class="kpi-card">
            <div class="kpi-label">Peluang Terbesar (Tier 1)</div>
            <div class="kpi-number">Rental Alat</div>
            <div class="kpi-desc">103 Bisnis • Saturasi Software 20%</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
with col3:
    avg_name = top_avg_row["niche_name"] if top_avg_row is not None else "Barbershop & Salon"
    avg_val = f"{top_avg_row['avg_reviews']:.1f}" if top_avg_row is not None else "497.0"
    st.markdown(
        f"""
        <div class="kpi-card">
            <div class="kpi-label">Rata-rata Ulasan Tertinggi</div>
            <div class="kpi-number">{avg_val}</div>
            <div class="kpi-desc">{avg_name}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
with col4:
    max_rev_num = f"{int(top_rev_row['max_reviews']):,}" if top_rev_row is not None else "4,395"
    st.markdown(
        f"""
        <div class="kpi-card">
            <div class="kpi-label">Ulasan Bisnis Terbanyak</div>
            <div class="kpi-number">{max_rev_num}</div>
            <div class="kpi-desc">Daisy Beauty Salon Jogja</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

st.write("")

# --- TABS NAVIGATION ---
tab_overview, tab_explorer, tab_matrix, tab_slides = st.tabs([
    "Ringkasan & Visualisasi",
    "Eksplorasi Data Manual (7 File CSV)",
    "Peluang Solusi Micro-SaaS",
    "Presentasi Google Slides",
])

# ==============================================================================
# TAB 1: RINGKASAN & VISUALISASI
# ==============================================================================
with tab_overview:
    # Summary Table
    if not summary_df.empty:
        tbl = summary_df[[
            "niche_id", "niche_name", "total_sample_scraped",
            "avg_reviews", "max_reviews", "avg_rating", "saturation_pct", "opportunity_tier"
        ]].copy()
        tbl.columns = [
            "ID", "Niche Bisnis", "Jumlah Entitas",
            "Rata-rata Review", "Review Maksimal", "Rating", "Saturasi Software", "Status Peluang"
        ]
        st.dataframe(
            tbl,
            use_container_width=True,
            hide_index=True,
            column_config={
                "ID": st.column_config.NumberColumn(width="small"),
                "Niche Bisnis": st.column_config.TextColumn(width="medium"),
                "Jumlah Entitas": st.column_config.NumberColumn(format="%d"),
                "Rata-rata Review": st.column_config.NumberColumn(format="%.1f"),
                "Review Maksimal": st.column_config.NumberColumn(format="%d"),
                "Rating": st.column_config.NumberColumn(format="%.2f ★"),
                "Saturasi Software": st.column_config.ProgressColumn(min_value=0, max_value=100, format="%.0f%%"),
                "Status Peluang": st.column_config.TextColumn(width="medium"),
            }
        )

    st.write("")

    # Visualizations: 2 Columns
    chart_col1, chart_col2 = st.columns(2)

    with chart_col1:
        st.caption("Jumlah Entitas Bisnis Tervalidasi per Niche")
        chart_count = (
            alt.Chart(summary_df)
            .mark_bar(cornerRadiusEnd=4, color="#2563eb")
            .encode(
                x=alt.X("total_sample_scraped:Q", title="Jumlah Entitas"),
                y=alt.Y("niche_name:N", sort="-x", title=""),
                tooltip=[
                    alt.Tooltip("niche_name:N", title="Niche"),
                    alt.Tooltip("total_sample_scraped:Q", title="Total Entitas"),
                ],
            )
            .properties(height=280)
        )
        st.altair_chart(chart_count, use_container_width=True)

    with chart_col2:
        st.caption("Rata-rata Ulasan per Niche (Tingkat Aktivitas Pasar)")
        chart_rev = (
            alt.Chart(summary_df)
            .mark_bar(cornerRadiusEnd=4, color="#0f766e")
            .encode(
                x=alt.X("avg_reviews:Q", title="Rata-rata Ulasan"),
                y=alt.Y("niche_name:N", sort="-x", title=""),
                tooltip=[
                    alt.Tooltip("niche_name:N", title="Niche"),
                    alt.Tooltip("avg_reviews:Q", format=".1f", title="Rata-rata Ulasan"),
                    alt.Tooltip("max_reviews:Q", title="Ulasan Terbanyak"),
                ],
            )
            .properties(height=280)
        )
        st.altair_chart(chart_rev, use_container_width=True)

    chart_col3, chart_col4 = st.columns(2)

    with chart_col3:
        st.caption("Sebaran Wilayah: DIY vs Magelang vs Klaten")
        geo_df = summary_df.melt(
            id_vars=["niche_name"],
            value_vars=["diy_sample", "magelang_sample", "klaten_sample"],
            var_name="Wilayah",
            value_name="Jumlah",
        )
        geo_df["Wilayah"] = geo_df["Wilayah"].replace({
            "diy_sample": "DIY Yogyakarta",
            "magelang_sample": "Magelang",
            "klaten_sample": "Klaten"
        })
        chart_geo = (
            alt.Chart(geo_df)
            .mark_bar()
            .encode(
                x=alt.X("Jumlah:Q", title="Jumlah Bisnis"),
                y=alt.Y("niche_name:N", title=""),
                color=alt.Color("Wilayah:N", scale=alt.Scale(range=["#1e3a8a", "#0284c7", "#94a3b8"])),
                tooltip=["niche_name:N", "Wilayah:N", "Jumlah:Q"],
            )
            .properties(height=280)
        )
        st.altair_chart(chart_geo, use_container_width=True)

    with chart_col4:
        st.caption("Matriks Prioritas: Saturasi Kompetitor vs Volume Review")
        chart_matrix = (
            alt.Chart(summary_df)
            .mark_circle(size=260)
            .encode(
                x=alt.X("saturation_pct:Q", title="Tingkat Saturasi Software (%)", scale=alt.Scale(domain=[10, 100])),
                y=alt.Y("avg_reviews:Q", title="Rata-rata Review", scale=alt.Scale(domain=[0, 600])),
                color=alt.Color(
                    "opportunity_tier:N",
                    title="Peluang",
                    scale=alt.Scale(
                        domain=["Tier 1 (Peluang Utama)", "Tier 1 (Peluang Tinggi)", "Tier 2", "Tier 3 (Jenuh POS)"],
                        range=["#16a34a", "#2563eb", "#d97706", "#dc2626"],
                    ),
                ),
                tooltip=[
                    alt.Tooltip("niche_name:N", title="Niche"),
                    alt.Tooltip("saturation_pct:Q", format=".0f%%", title="Saturasi"),
                    alt.Tooltip("avg_reviews:Q", format=".1f", title="Rata-rata Review"),
                    alt.Tooltip("total_sample_scraped:Q", title="Jumlah Entitas"),
                ],
            )
            .properties(height=280)
        )
        st.altair_chart(chart_matrix, use_container_width=True)


# ==============================================================================
# TAB 2: MANUAL DATA EXPLORER (ALL 7 FILES)
# ==============================================================================
with tab_explorer:
    col_sel, col_btn = st.columns([3, 1])

    with col_sel:
        selected_label = st.selectbox(
            "Pilih File Dataset Hasil Scraping:",
            options=list(FILE_OPTIONS.keys()),
            index=0,
            label_visibility="collapsed",
        )

    file_to_load = FILE_OPTIONS[selected_label]
    df_active = load_niche_data(file_to_load)

    with col_btn:
        if not df_active.empty:
            csv_data = df_active.to_csv(index=False).encode("utf-8")
            st.download_button(
                label=f"Unduh {file_to_load}",
                data=csv_data,
                file_name=file_to_load,
                mime="text/csv",
                use_container_width=True,
            )

    if not df_active.empty:
        # Compact filter bar
        col_s1, col_s2, col_s3, col_s4 = st.columns(4)
        with col_s1:
            q = st.text_input("Cari Bisnis / Alamat:", placeholder="Ketik kata kunci...", label_visibility="collapsed")
        with col_s2:
            reg_opts = ["Semua Wilayah"] + sorted(list(df_active["region"].unique()))
            selected_reg = st.selectbox("Wilayah:", options=reg_opts, label_visibility="collapsed")
        with col_s3:
            min_rev = st.number_input("Min. Review:", min_value=0, value=0, step=25, label_visibility="collapsed")
        with col_s4:
            has_phone_only = st.checkbox("Hanya yang ada No. HP", value=False)

        # Filter execution
        filtered = df_active.copy()
        if q:
            term = q.strip().lower()
            filtered = filtered[
                filtered["business_name"].astype(str).str.lower().str.contains(term)
                | filtered["address"].astype(str).str.lower().str.contains(term)
                | filtered["category"].astype(str).str.lower().str.contains(term)
            ]
        if selected_reg != "Semua Wilayah":
            filtered = filtered[filtered["region"] == selected_reg]
        if min_rev > 0 and "reviews_count" in filtered.columns:
            filtered = filtered[filtered["reviews_count"] >= min_rev]
        if has_phone_only and "phone_number" in filtered.columns:
            filtered = filtered[filtered["phone_number"].notna() & (filtered["phone_number"] != "")]

        # Quick stats line
        pct_phone = (filtered["phone_number"].notna() & (filtered["phone_number"] != "")).mean() * 100 if len(filtered) > 0 else 0
        pct_web = (filtered["website_url"].notna() & (filtered["website_url"] != "")).mean() * 100 if len(filtered) > 0 else 0
        
        st.caption(f"Menampilkan **{len(filtered)}** dari total **{len(df_active)}** entitas | Kelengkapan Telepon: **{pct_phone:.1f}%** | Kelengkapan Website: **{pct_web:.1f}%**")

        # Table display
        show_cols = [
            c for c in ["business_name", "category", "rating", "reviews_count", "phone_number", "website_url", "region", "address"]
            if c in filtered.columns
        ]
        st.dataframe(
            filtered[show_cols],
            use_container_width=True,
            hide_index=True,
            column_config={
                "business_name": st.column_config.TextColumn("Nama Usaha", width="medium"),
                "category": st.column_config.TextColumn("Kategori", width="small"),
                "rating": st.column_config.NumberColumn("Rating", format="%.1f ★", width="small"),
                "reviews_count": st.column_config.NumberColumn("Ulasan", format="%d", width="small"),
                "phone_number": st.column_config.TextColumn("Telepon (+62)", width="medium"),
                "website_url": st.column_config.LinkColumn("Website", width="medium"),
                "region": st.column_config.TextColumn("Wilayah", width="small"),
                "address": st.column_config.TextColumn("Alamat Lengkap", width="large"),
            },
        )
    else:
        st.info(f"File {file_to_load} belum tersedia di folder exports.")


# ==============================================================================
# TAB 3: CONCISE OPPORTUNITY & MVP RECOMMENDATIONS
# ==============================================================================
with tab_matrix:
    st.caption("Pemetaan Ringkas Masalah Operasional & Rekomendasi Solusi Micro-SaaS per Niche")

    solutions = [
        {
            "tier": "Tier 1",
            "niche": "Rental Kendaraan & Kamera",
            "stat": "103 Entitas • 20% Saturasi",
            "problem": "Rawan penggelapan alat/unit, sengketa lecet fisik, dan pengecekan ketersediaan manual via WA.",
            "mvp": "Web booking real-time + verifikasi e-KYC KTP anti-fraud + form foto kondisi serah terima unit."
        },
        {
            "tier": "Tier 1",
            "niche": "Car Wash & Detailing",
            "stat": "88 Entitas • 26% Saturasi",
            "problem": "Pelanggan menunggu tanpa kepastian durasi, nota kertas basah, dan komisi pencuci direkap manual.",
            "mvp": "Kasir 3-klik berbasis plat nomor, papan antrean status cuci publik, dan auto-notifikasi WA selesai cuci."
        },
        {
            "tier": "Tier 1",
            "niche": "Percetakan Digital",
            "stat": "89 Entitas • 34% Saturasi",
            "problem": "Antrean kasir lambat karena hitung manual meteran bahan, serta admin lelah membalas 'kapan cetakan selesai'.",
            "mvp": "Kalkulator instan harga cetak luas/bahan + link publik pelacak status pesanan SPK online."
        },
        {
            "tier": "Tier 2",
            "niche": "Pet Shop, Grooming, & Vet",
            "stat": "69 Entitas • 52% Saturasi",
            "problem": "SaaS klinik veteriner terlalu mahal bagi grooming ritel, dan pemilik cemas saat hewan dititipkan.",
            "mvp": "SaaS pencatatan grooming/hotel ringan dengan kirim foto progres anabul ke WA + pengingat vaksin berkala."
        },
        {
            "tier": "Tier 2",
            "niche": "Gym & Studio Kebugaran",
            "stat": "80 Entitas • 58% Saturasi",
            "problem": "Turnstile gate mahal bagi gym mandiri, rawan titip kartu member, dan komisi Personal Trainer manual.",
            "mvp": "Absensi member berbasis QR dinamis resepsionis (anti-screenshot) + pencatatan sesi PT otomatis."
        },
        {
            "tier": "Tier 2",
            "niche": "Kost Eksklusif",
            "stat": "86 Entitas • 62% Saturasi",
            "problem": "Pemilik menolak komisi agregator kamar, serta rekonsiliasi transfer bank manual sering menyita waktu.",
            "mvp": "Sistem penagihan otomatis QRIS/VA via WhatsApp tanpa biaya potongan komisi per kamar."
        },
        {
            "tier": "Tier 3",
            "niche": "Barbershop & Salon",
            "stat": "90 Entitas • 88% Saturasi",
            "problem": "Sangat padat oleh POS kasir generik (Moka, Majoo, Fresha), namun minim retensi kunjungan ulang.",
            "mvp": "Micro-tool antrean kapster via web browser + reminder otomatis potong rambut setiap 3 minggu."
        },
    ]

    for item in solutions:
        with st.expander(f"[{item['tier']}] {item['niche']} — {item['stat']}"):
            col_p, col_s = st.columns(2)
            with col_p:
                st.markdown(f"**Titik Masalah:**\n{item['problem']}")
            with col_s:
                st.markdown(f"**Rekomendasi MVP:**\n{item['mvp']}")


# ==============================================================================
# TAB 4: GOOGLE SLIDES INTEGRATION
# ==============================================================================
with tab_slides:
    slides_link = "https://docs.google.com/presentation/d/14t__HKhfUhLBtCdFePodnnAGZaeQpR588UcawF8JiNM/edit"
    
    st.markdown(
        f"""
        <div style="background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 20px; margin-bottom: 16px;">
            <div style="font-size: 16px; font-weight: 700; color: #0f172a; margin-bottom: 6px;">
                Laporan Presentasi Eksekutif Google Slides (10 Slide)
            </div>
            <div style="font-size: 13px; color: #475569; margin-bottom: 14px;">
                Dokumen paparan lengkap mencakup ringkasan eksekutif, metodologi ekstraksi 605 entitas, lanskap kompetisi, dan peta jalan komersialisasi.
            </div>
            <a href="{slides_link}" target="_blank" style="display: inline-block; background-color: #2563eb; color: #ffffff; text-decoration: none; padding: 8px 16px; border-radius: 6px; font-weight: 600; font-size: 13px;">
                Buka Presentasi Google Slides &rarr;
            </a>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.caption("Rangkuman Topik 10 Slide:")
    topics = [
        "Slide 1: Judul & Lingkup Wilayah DIY, Magelang, Klaten",
        "Slide 2: Metodologi & Validasi 605 Entitas Google Maps",
        "Slide 3: Komparasi Volume Ulasan & Aktivitas Pelanggan",
        "Slide 4: Deep-Dive Tier 1: Rental Kendaraan & Kamera (Saturasi 20%)",
        "Slide 5: Deep-Dive Tier 1: Car Wash & Detailing (Saturasi 26%)",
        "Slide 6: Deep-Dive Tier 1: Percetakan Digital & SPK Tracking (Saturasi 34%)",
        "Slide 7: Deep-Dive Tier 2: Pet Shop, Vet, & Gym Studio",
        "Slide 8: Deep-Dive Tier 3: Barbershop & Kost Eksklusif (Pasar Padat POS)",
        "Slide 9: Matriks Prioritas Eksekusi Go-To-Market",
        "Slide 10: Rencana Aksi Outreach WhatsApp 30 Hari",
    ]
    for top in topics:
        st.markdown(f"• {top}")

# Footer
st.markdown(
    """
    <div style="margin-top: 32px; padding-top: 16px; border-top: 1px solid #f1f5f9; text-align: center; color: #94a3b8; font-size: 11px;">
        Google Maps Scraper & Micro-SaaS Market Intelligence • DIY, Magelang, Klaten
    </div>
    """,
    unsafe_allow_html=True,
)
