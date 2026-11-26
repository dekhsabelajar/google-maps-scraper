"""
Executive Dashboard: B2B Micro-SaaS Market Intelligence
Minimalist, high-clarity dashboard with live fast Google Maps scraping
(keyword search + multi-location tags) and pre-loaded 7-niche validation data.
"""

import asyncio
import queue
import sys
import time
import traceback
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Coroutine, List, TypeVar

import altair as alt
import pandas as pd
import pydeck as pdk
import streamlit as st

from core.geo_intelligence import build_whitespace_summary, enrich_geo_and_scale_df
from core.maps_worker import MapsWorker
from storage.database import DatabaseManager


# --- PAGE CONFIGURATION (must be first Streamlit command) ---
st.set_page_config(
    page_title="B2B Micro-SaaS Market Intelligence",
    page_icon=None,
    layout="wide",
    initial_sidebar_state="collapsed",
)


@st.cache_resource
def ensure_playwright_installed():
    """Ensure Playwright Chromium binary is downloaded in cloud container environments."""
    try:
        import subprocess
        subprocess.run(
            [sys.executable, "-m", "playwright", "install", "chromium"],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        pass


T = TypeVar("T")


def run_async(coro_factory: Callable[[], Coroutine[Any, Any, T]]) -> T:
    """Run an async coroutine on a dedicated ProactorEventLoop on Windows."""
    def _runner() -> T:
        if sys.platform == "win32":
            loop = asyncio.ProactorEventLoop()
            asyncio.set_event_loop(loop)
            try:
                return loop.run_until_complete(coro_factory())
            finally:
                loop.close()
        return asyncio.run(coro_factory())

    with ThreadPoolExecutor(max_workers=1) as executor:
        return executor.submit(_runner).result()

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
        margin-bottom: 20px;
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

DEFAULT_KEYWORDS = [
    "Cafe",
    "Coffee Shop",
    "Kost",
    "Kost Eksklusif",
    "Gym & Fitness",
    "Barbershop",
    "Salon Kecantikan",
    "Laundry",
    "Restoran",
    "Warung Makan",
    "Bakery & Pastry",
    "Catering",
    "Hotel & Penginapan",
    "Villa & Resort",
    "Coworking Space",
    "Klinik Gigi",
    "Klinik Kecantikan",
    "Apotek",
    "Pet Shop & Grooming",
    "Dokter Hewan",
    "Bengkel Mobil",
    "Bengkel Motor",
    "Car Wash & Detailing",
    "Toko Sparepart",
    "Rental Mobil",
    "Rental Motor",
    "Rental Kamera",
    "Percetakan Digital",
    "Studio Foto",
    "Wedding Organizer",
    "Event Organizer",
    "Bimbingan Belajar",
    "Kursus Bahasa",
    "Toko Bangunan",
    "Jasa Desain Interior",
    "Kontraktor",
    "Toko Elektronik",
    "Toko Komputer & Laptop",
    "Service HP",
    "Toko Furniture",
    "Florist / Toko Bunga",
    "Travel Agent",
    "Ekspedisi & Logistik",
]

DEFAULT_LOCATIONS = [
    # DIY & Jawa Tengah
    "Yogyakarta",
    "Sleman",
    "Bantul",
    "Kulon Progo",
    "Gunungkidul",
    "Wonosari",
    "Klaten",
    "Magelang",
    "Solo",
    "Surakarta",
    "Sukoharjo",
    "Karanganyar",
    "Boyolali",
    "Sragen",
    "Wonogiri",
    "Semarang",
    "Salatiga",
    "Ungaran",
    "Purwokerto",
    "Banyumas",
    "Cilacap",
    "Purbalingga",
    "Kebumen",
    "Purworejo",
    "Wonosobo",
    "Temanggung",
    "Pekalongan",
    "Tegal",
    "Kudus",
    "Jepara",
    "Pati",
    # Jabodetabek & Jawa Barat
    "Jakarta",
    "Jakarta Selatan",
    "Jakarta Pusat",
    "Jakarta Barat",
    "Jakarta Timur",
    "Jakarta Utara",
    "Bogor",
    "Depok",
    "Tangerang",
    "Tangerang Selatan",
    "Bekasi",
    "Bandung",
    "Cimahi",
    "Cirebon",
    "Tasikmalaya",
    "Garut",
    "Sukabumi",
    "Karawang",
    "Purwakarta",
    # Jawa Timur
    "Surabaya",
    "Malang",
    "Batu",
    "Sidoarjo",
    "Gresik",
    "Kediri",
    "Jember",
    "Banyuwangi",
    "Madiun",
    "Blitar",
    "Mojokerto",
    "Pasuruan",
    # Bali & Nusa Tenggara
    "Bali",
    "Denpasar",
    "Badung",
    "Canggu",
    "Ubud",
    "Gianyar",
    "Lombok",
    "Mataram",
    # Sumatra, Kalimantan, Sulawesi
    "Medan",
    "Palembang",
    "Padang",
    "Pekanbaru",
    "Batam",
    "Bandar Lampung",
    "Balikpapan",
    "Samarinda",
    "Banjarmasin",
    "Pontianak",
    "Makassar",
    "Manado",
]

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


@st.cache_data
def load_reviews_data() -> pd.DataFrame:
    path = EXPORTS_DIR / "scraped_business_reviews.csv"
    if path.exists():
        df = pd.read_csv(path)
        if "rating" in df.columns:
            df["rating"] = pd.to_numeric(df["rating"], errors="coerce")
        return df
    return pd.DataFrame()


def build_live_summary(df: pd.DataFrame) -> pd.DataFrame:
    """Build summary metrics grouped by niche (if multi-keyword) or by region (if single keyword)."""
    if df.empty:
        return pd.DataFrame()

    unique_niches = df["niche"].nunique() if "niche" in df.columns else 1
    group_col = "niche" if unique_niches > 1 else "region"

    rows = []
    for idx, (group_name, grp) in enumerate(df.groupby(group_col, sort=False), start=1):
        has_web = grp["website_url"].notna() & (grp["website_url"].astype(str).str.strip() != "")
        has_phone = grp["phone_number"].notna() & (grp["phone_number"].astype(str).str.strip() != "")
        web_pct = float(has_web.mean() * 100) if len(grp) else 0.0
        no_web_pct = 100.0 - web_pct

        if no_web_pct >= 65:
            tier = "Tier 1 (Peluang Tinggi)"
        elif no_web_pct >= 40:
            tier = "Tier 2 (Potensial)"
        else:
            tier = "Tier 3 (Digital Matang)"

        rows.append({
            "niche_id": idx,
            "niche_name": group_name,
            "total_sample_scraped": int(len(grp)),
            "avg_reviews": float(grp["reviews_count"].mean()) if len(grp) else 0.0,
            "max_reviews": int(grp["reviews_count"].max()) if len(grp) else 0,
            "avg_rating": float(grp["rating"].dropna().mean()) if grp["rating"].notna().any() else 0.0,
            "with_website_count": int(has_web.sum()),
            "without_website_count": int((~has_web).sum()),
            "with_phone_pct": float(has_phone.mean() * 100) if len(grp) else 0.0,
            "saturation_pct": round(web_pct, 1),
            "no_website_pct": round(no_web_pct, 1),
            "opportunity_tier": tier,
        })

    return pd.DataFrame(rows)


def normalize_scraped_df(items: List[dict]) -> pd.DataFrame:
    if not items:
        return pd.DataFrame()
    df = pd.DataFrame(items)
    if "rating" in df.columns:
        df["rating"] = pd.to_numeric(df["rating"], errors="coerce")
    if "reviews_count" in df.columns:
        df["reviews_count"] = pd.to_numeric(df["reviews_count"], errors="coerce").fillna(0).astype(int)
    else:
        df["reviews_count"] = 0
    if "region" not in df.columns:
        df["region"] = "Lainnya"
    if "niche" not in df.columns:
        df["niche"] = df.get("search_keyword", "Lainnya")
    return enrich_geo_and_scale_df(df)


# --- HEADER ---
st.markdown(
    """
    <div class="top-bar">
        <div class="top-title">B2B Micro-SaaS Market Intelligence</div>
        <div class="top-subtitle">Fast Google Maps Market Scraper & Analisis Validasi Bisnis Multi-Wilayah</div>
    </div>
    """,
    unsafe_allow_html=True,
)

# --- SEARCH BAR & MULTI-LOCATION TAGS ---
with st.container(border=True):
    s_col1, s_col2, s_col3, s_col4 = st.columns([2.5, 2.5, 1.2, 1.3], vertical_alignment="bottom")

    with s_col1:
        selected_keywords = st.multiselect(
            "Kata Kunci / Niche (Maks. 10)",
            options=DEFAULT_KEYWORDS,
            default=[],
            max_selections=10,
            placeholder="Pilih hingga 10 kata kunci/niche...",
            key="search_kw_select",
        )

    with s_col2:
        selected_locations = st.multiselect(
            "Tag Lokasi / Kota",
            options=DEFAULT_LOCATIONS,
            default=[],
            placeholder="Pilih satu atau beberapa kota/daerah...",
            key="location_tags_select",
        )

    with s_col3:
        scrape_all = st.checkbox(
            "Tanpa Batas (Semua)",
            value=True,
            help="Scrape semua hasil yang tersedia di Google Maps sampai akhir daftar.",
            key="scrape_all_cb",
        )
        if scrape_all:
            limit_per_loc = 0
        else:
            limit_per_loc = st.number_input(
                "Target / Lokasi",
                min_value=10,
                max_value=500,
                value=100,
                step=10,
                key="limit_per_loc_input",
            )

    with s_col4:
        run_scrape_btn = st.button(
            "Mulai Scrape",
            type="primary",
            use_container_width=True,
        )

    opt_col1, opt_col2, opt_col3 = st.columns([2.0, 2.0, 1.5], vertical_alignment="bottom")
    with opt_col1:
        custom_kw_raw = st.text_input(
            "Tambah Kata Kunci Kustom (pisahkan koma, maks. total 10)",
            placeholder="Contoh: coffee shop, coworking space, bakery",
            key="custom_kw_input",
        )
    with opt_col2:
        custom_loc_raw = st.text_input(
            "Tambah Tag Lokasi Kustom (opsional, pisahkan koma)",
            placeholder="Contoh: Bantul, Wonosari, Salatiga",
            key="custom_loc_input",
        )
    with opt_col3:
        fetch_details = st.checkbox(
            "Ambil No. HP & Website (Detail Paralel)",
            value=True,
            help="Mengunjungi halaman detail tiap bisnis secara paralel (5 tab) untuk mengambil No. HP & Website yang tidak tampil di list.",
            key="fetch_details_cb",
        )

# Merge preset + custom keywords (max 10)
all_keywords: List[str] = list(selected_keywords)
if custom_kw_raw.strip():
    for part in custom_kw_raw.split(","):
        kw_item = part.strip()
        if kw_item and kw_item not in all_keywords:
            all_keywords.append(kw_item)

if len(all_keywords) > 10:
    st.warning("Maksimal 10 kata kunci per sesi. Hanya 10 kata kunci pertama yang akan diproses.")
    all_keywords = all_keywords[:10]

# Merge preset + custom location tags while preserving order
all_location_tags: List[str] = list(selected_locations)
if custom_loc_raw.strip():
    for part in custom_loc_raw.split(","):
        loc_clean = part.strip()
        if loc_clean and loc_clean not in all_location_tags:
            all_location_tags.append(loc_clean)

# Handle Scrape Execution
if run_scrape_btn:
    if not all_keywords:
        st.warning("Pilih atau masukkan minimal satu kata kunci pencarian (contoh: `Cafe`).")
    elif not all_location_tags:
        st.warning("Pilih atau tambahkan minimal satu tag lokasi (contoh: `Yogyakarta`, `Klaten`, `Magelang`).")
    else:
        ensure_playwright_installed()
        t_start = time.perf_counter()
        kw_preview = ", ".join(all_keywords[:3]) + (f" (+{len(all_keywords) - 3} lainnya)" if len(all_keywords) > 3 else "")
        status_box = st.status(
            f"Menjalankan Fast Scraper untuk **{len(all_keywords)} kata kunci** ({kw_preview}) di **{len(all_location_tags)} lokasi**...",
            expanded=True,
        )
        progress_bar = st.progress(0.0)

        db = DatabaseManager()
        worker = MapsWorker(db_manager=db, headless=True)

        progress_queue: queue.Queue = queue.Queue()
        loc_logs: List[str] = []

        def on_task_start(kw_name: str, loc_name: str, idx: int, total: int):
            progress_queue.put(("start", kw_name, loc_name, idx, total))

        def on_task_done(kw_name: str, loc_name: str, items: List[dict]):
            progress_queue.put(("done", kw_name, loc_name, len(items)))

        def _worker_task():
            if sys.platform == "win32":
                loop = asyncio.ProactorEventLoop()
                asyncio.set_event_loop(loop)
                try:
                    return loop.run_until_complete(
                        worker.search_batch(
                            keywords=all_keywords,
                            locations=all_location_tags,
                            limit_per_location=int(limit_per_loc),
                            on_task_start=on_task_start,
                            on_task_done=on_task_done,
                            fetch_details=fetch_details,
                        )
                    )
                finally:
                    loop.close()
            return asyncio.run(
                worker.search_batch(
                    keywords=all_keywords,
                    locations=all_location_tags,
                    limit_per_location=int(limit_per_loc),
                    on_task_start=on_task_start,
                    on_task_done=on_task_done,
                    fetch_details=fetch_details,
                )
            )

        try:
            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(_worker_task)
                while not future.done():
                    while not progress_queue.empty():
                        evt = progress_queue.get_nowait()
                        if evt[0] == "start":
                            _, kw_name, loc_name, idx, total = evt
                            progress_bar.progress(
                                (idx - 1) / max(total, 1),
                                text=f"Scraping '{kw_name} {loc_name}' ({idx}/{total})...",
                            )
                        elif evt[0] == "done":
                            _, kw_name, loc_name, count = evt
                            loc_logs.append(f"- **{kw_name}** ({loc_name}): {count} entitas")
                    time.sleep(0.2)

                combined_items = future.result()
                while not progress_queue.empty():
                    evt = progress_queue.get_nowait()
                    if evt[0] == "done":
                        _, kw_name, loc_name, count = evt
                        loc_logs.append(f"- **{kw_name}** ({loc_name}): {count} entitas")

            elapsed = time.perf_counter() - t_start
            progress_bar.progress(1.0, text="Selesai!")

            live_df = normalize_scraped_df(combined_items)
            if not live_df.empty:
                EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                safe_kw = "".join(c if c.isalnum() else "_" for c in all_keywords[0])
                out_filename = f"live_{safe_kw}_{len(all_keywords)}kw_{ts}.csv"
                live_df.to_csv(EXPORTS_DIR / out_filename, index=False, encoding="utf-8-sig")

                st.session_state["live_df"] = live_df
                st.session_state["live_meta"] = {
                    "keywords": all_keywords,
                    "keyword": kw_preview,
                    "locations": all_location_tags,
                    "elapsed": elapsed,
                    "filename": out_filename,
                }
                st.session_state["view_mode"] = "Hasil Scrape Terbaru"
                status_box.update(
                    label=f"Selesai dalam {elapsed:.1f} detik — {len(live_df)} entitas unik terkumpul!",
                    state="complete",
                )
                for line in loc_logs:
                    status_box.write(line)
            else:
                status_box.update(label="Tidak ada entitas yang berhasil diambil.", state="error")
        except Exception as err:
            status_box.update(label=f"Terjadi kesalahan saat scraping: {type(err).__name__}: {err}", state="error")
            status_box.code(traceback.format_exc())

# ==============================================================================
# RENDER REPORT ONLY WHEN LIVE DATA EXISTS
# ==============================================================================
has_live_data = "live_df" in st.session_state and not st.session_state["live_df"].empty

if not has_live_data:
    st.info("Masukkan kata kunci dan pilih tag lokasi di atas, lalu klik **Mulai Scrape** untuk melihat laporan analisis pasar.")
else:
    is_live_mode = True
    live_df = st.session_state["live_df"]
    live_meta = st.session_state["live_meta"]
    summary_df = build_live_summary(live_df)

    total_entities = int(len(live_df))
    locs_label = ", ".join(live_meta["locations"])
    kw_label = live_meta["keyword"]

    # KPI 2: Digital Opportunity (No Website)
    has_web_mask = live_df["website_url"].notna() & (live_df["website_url"].astype(str).str.strip() != "")
    no_web_count = int((~has_web_mask).sum())
    no_web_pct = (no_web_count / max(total_entities, 1)) * 100

    # KPI 3: Highest Avg Reviews region/niche
    top_avg_row = summary_df.loc[summary_df["avg_reviews"].idxmax()] if not summary_df.empty else None
    avg_name = top_avg_row["niche_name"] if top_avg_row is not None else "-"
    avg_val = f"{top_avg_row['avg_reviews']:.1f}" if top_avg_row is not None else "0.0"

    # KPI 4: Most reviewed business
    max_idx = live_df["reviews_count"].idxmax() if not live_df.empty else None
    max_rev_num = f"{int(live_df.loc[max_idx, 'reviews_count']):,}" if max_idx is not None else "0"
    max_rev_biz = str(live_df.loc[max_idx, "business_name"]) if max_idx is not None else "-"

    kpi_cards = [
        ("Total Entitas Tervalidasi", f"{total_entities:,}", f"{kw_label} • {locs_label} ({live_meta['elapsed']:.1f}s)"),
        ("Peluang Digital (Tanpa Web)", f"{no_web_pct:.0f}%", f"{no_web_count:,} dari {total_entities:,} bisnis belum punya web"),
        ("Rata-rata Ulasan Tertinggi", avg_val, avg_name),
        ("Ulasan Bisnis Terbanyak", max_rev_num, max_rev_biz),
    ]

    # --- 4 CLEAN KPI TILES ---
    col1, col2, col3, col4 = st.columns(4)
    for col, (label, number, desc) in zip([col1, col2, col3, col4], kpi_cards):
        with col:
            st.markdown(
                f"""
                <div class="kpi-card">
                    <div class="kpi-label">{label}</div>
                    <div class="kpi-number">{number}</div>
                    <div class="kpi-desc">{desc}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    st.write("")

    # --- TABS NAVIGATION ---
    tab_overview, tab_geo, tab_explorer = st.tabs([
        "Ringkasan & Visualisasi",
        "Analisis Spasial & Peta Pasar",
        "Eksplorasi Data Gabungan",
    ])

    # ==============================================================================
    # TAB 1: RINGKASAN & VISUALISASI
    # ==============================================================================
    with tab_overview:
        if not summary_df.empty:
            is_multi_niche_live = st.session_state["live_df"]["niche"].nunique() > 1
            col_dim_name = "Niche Bisnis" if is_multi_niche_live else "Wilayah / Lokasi"
            tbl = summary_df[[
                "niche_id", "niche_name", "total_sample_scraped",
                "avg_reviews", "max_reviews", "avg_rating", "saturation_pct", "opportunity_tier"
            ]].copy()
            tbl.columns = [
                "ID", col_dim_name, "Jumlah Entitas",
                "Rata-rata Review", "Review Maksimal", "Rating", "Adopsi Website (%)", "Status Peluang"
            ]
            st.dataframe(
                tbl,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "ID": st.column_config.NumberColumn(width="small"),
                    col_dim_name: st.column_config.TextColumn(width="medium"),
                    "Jumlah Entitas": st.column_config.NumberColumn(format="%d"),
                    "Rata-rata Review": st.column_config.NumberColumn(format="%.1f"),
                    "Review Maksimal": st.column_config.NumberColumn(format="%d"),
                    "Rating": st.column_config.NumberColumn(format="%.2f ★"),
                    "Adopsi Website (%)": st.column_config.ProgressColumn(min_value=0, max_value=100, format="%.0f%%"),
                    "Status Peluang": st.column_config.TextColumn(width="medium"),
                },
            )

            st.write("")

            chart_col1, chart_col2 = st.columns(2)
            dim_label = "Niche" if is_multi_niche_live else "Wilayah"

            with chart_col1:
                st.caption(f"Jumlah Entitas Bisnis Tervalidasi per {dim_label}")
                chart_count = (
                    alt.Chart(summary_df)
                    .mark_bar(cornerRadiusEnd=4, color="#2563eb")
                    .encode(
                        x=alt.X("total_sample_scraped:Q", title="Jumlah Entitas"),
                        y=alt.Y("niche_name:N", sort="-x", title=""),
                        tooltip=[
                            alt.Tooltip("niche_name:N", title=dim_label),
                            alt.Tooltip("total_sample_scraped:Q", title="Total Entitas"),
                        ],
                    )
                    .properties(height=280)
                )
                st.altair_chart(chart_count, use_container_width=True)

            with chart_col2:
                st.caption(f"Rata-rata Ulasan per {dim_label} (Tingkat Aktivitas Pasar)")
                chart_rev = (
                    alt.Chart(summary_df)
                    .mark_bar(cornerRadiusEnd=4, color="#0f766e")
                    .encode(
                        x=alt.X("avg_reviews:Q", title="Rata-rata Ulasan"),
                        y=alt.Y("niche_name:N", sort="-x", title=""),
                        tooltip=[
                            alt.Tooltip("niche_name:N", title=dim_label),
                            alt.Tooltip("avg_reviews:Q", format=".1f", title="Rata-rata Ulasan"),
                            alt.Tooltip("max_reviews:Q", title="Ulasan Terbanyak"),
                        ],
                    )
                    .properties(height=280)
                )
                st.altair_chart(chart_rev, use_container_width=True)

            chart_col3, chart_col4 = st.columns(2)

            with chart_col3:
                if is_multi_niche_live:
                    st.caption("Sebaran Wilayah per Niche")
                    geo_counts = live_df.groupby(["niche", "region"]).size().reset_index(name="Jumlah")
                    chart_geo = (
                        alt.Chart(geo_counts)
                        .mark_bar()
                        .encode(
                            x=alt.X("Jumlah:Q", title="Jumlah Bisnis"),
                            y=alt.Y("niche:N", title=""),
                            color=alt.Color("region:N", title="Wilayah"),
                            tooltip=["niche:N", "region:N", "Jumlah:Q"],
                        )
                        .properties(height=280)
                    )
                    st.altair_chart(chart_geo, use_container_width=True)
                else:
                    st.caption("Kesiapan Digital per Wilayah: Punya Website vs Tanpa Website")
                    web_df = summary_df.melt(
                        id_vars=["niche_name"],
                        value_vars=["with_website_count", "without_website_count"],
                        var_name="Status Website",
                        value_name="Jumlah",
                    )
                    web_df["Status Website"] = web_df["Status Website"].replace({
                        "with_website_count": "Memiliki Website",
                        "without_website_count": "Belum Ada Website",
                    })
                    chart_geo = (
                        alt.Chart(web_df)
                        .mark_bar()
                        .encode(
                            x=alt.X("Jumlah:Q", title="Jumlah Bisnis"),
                            y=alt.Y("niche_name:N", title=""),
                            color=alt.Color("Status Website:N", scale=alt.Scale(range=["#1e3a8a", "#94a3b8"])),
                            tooltip=["niche_name:N", "Status Website:N", "Jumlah:Q"],
                        )
                        .properties(height=280)
                    )
                    st.altair_chart(chart_geo, use_container_width=True)

            with chart_col4:
                st.caption(f"Tingkat Adopsi Website per {dim_label} (%)")
                chart_sat = (
                    alt.Chart(summary_df)
                    .mark_bar(cornerRadiusEnd=4)
                    .encode(
                        x=alt.X("saturation_pct:Q", title="Persentase (%)", scale=alt.Scale(domain=[0, 100])),
                        y=alt.Y("niche_name:N", sort="x", title=""),
                        color=alt.Color(
                            "saturation_pct:Q",
                            title="Persentase (%)",
                            scale=alt.Scale(scheme="redyellowgreen", reverse=True),
                            legend=None,
                        ),
                        tooltip=[
                            alt.Tooltip("niche_name:N", title=dim_label),
                            alt.Tooltip("saturation_pct:Q", title="Persentase (%)"),
                            alt.Tooltip("opportunity_tier:N", title="Status Peluang"),
                        ],
                    )
                    .properties(height=280)
                )
                st.altair_chart(chart_sat, use_container_width=True)

    # ==============================================================================
    # TAB 2: DATA EXPLORER
    # ==============================================================================
    with tab_explorer:
        df_active = live_df
        file_to_load = live_meta["filename"]
        col_sel, col_btn = st.columns([3, 1])
        with col_sel:
            st.caption(
                f"Dataset gabungan hasil scrape: **{live_meta['keyword']}** "
                f"({', '.join(live_meta['locations'])})"
            )
        with col_btn:
            csv_data = df_active.to_csv(index=False).encode("utf-8")
            st.download_button(
                label=f"Unduh {file_to_load}",
                data=csv_data,
                file_name=file_to_load,
                mime="text/csv",
                use_container_width=True,
            )

        if "niche" in df_active.columns and df_active["niche"].nunique() > 1:
            col_s0, col_s1, col_s2, col_s3, col_s4 = st.columns([1.2, 1.3, 1.1, 0.9, 1.0])
            with col_s0:
                niche_opts = ["Semua Niche"] + sorted(list(df_active["niche"].dropna().unique()))
                selected_live_niche = st.selectbox("Niche:", options=niche_opts, label_visibility="collapsed")
        else:
            selected_live_niche = "Semua Niche"
            col_s1, col_s2, col_s3, col_s4 = st.columns(4)

        with col_s1:
            q = st.text_input("Cari Bisnis / Alamat:", placeholder="Ketik kata kunci...", label_visibility="collapsed")
        with col_s2:
            reg_opts = ["Semua Wilayah"] + sorted(list(df_active["region"].dropna().unique()))
            selected_reg = st.selectbox("Wilayah:", options=reg_opts, label_visibility="collapsed")
        with col_s3:
            min_rev = st.number_input("Min. Review:", min_value=0, value=0, step=25, label_visibility="collapsed")
        with col_s4:
            has_phone_only = st.checkbox("Hanya yang ada No. HP", value=False)

        filtered = df_active.copy()
        if selected_live_niche != "Semua Niche" and "niche" in filtered.columns:
            filtered = filtered[filtered["niche"] == selected_live_niche]
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

        pct_phone = (filtered["phone_number"].notna() & (filtered["phone_number"] != "")).mean() * 100 if len(filtered) > 0 else 0
        pct_web = (filtered["website_url"].notna() & (filtered["website_url"] != "")).mean() * 100 if len(filtered) > 0 else 0

        st.caption(
            f"Menampilkan **{len(filtered)}** dari total **{len(df_active)}** entitas | "
            f"Kelengkapan Telepon: **{pct_phone:.1f}%** | Kelengkapan Website: **{pct_web:.1f}%**"
        )

        show_cols = [
            c for c in ["niche", "business_name", "business_scale", "category", "rating", "reviews_count", "phone_number", "website_url", "google_url", "kecamatan", "region", "address"]
            if c in filtered.columns
        ]
        st.dataframe(
            filtered[show_cols],
            use_container_width=True,
            hide_index=True,
            column_config={
                "niche": st.column_config.TextColumn("Niche / Kata Kunci", width="small"),
                "business_name": st.column_config.TextColumn("Nama Usaha", width="medium"),
                "business_scale": st.column_config.TextColumn("Skala Usaha", width="small"),
                "category": st.column_config.TextColumn("Kategori", width="small"),
                "rating": st.column_config.NumberColumn("Rating", format="%.1f ★", width="small"),
                "reviews_count": st.column_config.NumberColumn("Ulasan", format="%d", width="small"),
                "phone_number": st.column_config.TextColumn("Telepon (+62)", width="medium"),
                "website_url": st.column_config.LinkColumn("Website", width="medium"),
                "google_url": st.column_config.LinkColumn("Link GMaps", display_text="Buka Maps", width="small"),
                "kecamatan": st.column_config.TextColumn("Kecamatan", width="small"),
                "region": st.column_config.TextColumn("Wilayah", width="small"),
                "address": st.column_config.TextColumn("Alamat Lengkap", width="large"),
            },
        )

    # ==============================================================================
    # TAB 3 (Rendered into tab_geo): GEO-INTELLIGENCE & SPATIAL ANALYSIS
    # ==============================================================================
    with tab_geo:
        geo_df = enrich_geo_and_scale_df(live_df)
        ws_df = build_whitespace_summary(geo_df)

        coord_mask = geo_df["latitude"].notna() & geo_df["longitude"].notna()
        mapped_count = int(coord_mask.sum())
        exact_gps_count = int((coord_mask & (geo_df.get("coord_source", "") == "Presisi GPS")).sum())
        kec_count = int(geo_df.loc[geo_df["kecamatan"] != "Tidak Diketahui", "kecamatan"].nunique())
        umkm_pct = float((geo_df["business_scale"] == "UMKM Tunggal").mean() * 100) if len(geo_df) else 0.0
        chain_count = int((geo_df["business_scale"] == "Jaringan / Multi-Cabang").sum())

        top_ws_kec = ws_df.iloc[0]["kecamatan"] if not ws_df.empty else "-"
        top_ws_score = f"{ws_df.iloc[0]['whitespace_score']:.1f}/100" if not ws_df.empty else "-"

        geo_kpis = [
            ("Kecamatan Teridentifikasi", f"{kec_count}", "Wilayah administratif terdeteksi"),
            ("Whitespace Teratas", top_ws_kec, f"Skor Peluang: {top_ws_score}"),
            ("Proporsi UMKM Tunggal", f"{umkm_pct:.1f}%", f"{chain_count} Entitas Multi-Cabang"),
            ("Koordinat Terpetakan", f"{mapped_count} / {len(geo_df)}", f"{exact_gps_count} Presisi GPS"),
        ]
        gc1, gc2, gc3, gc4 = st.columns(4)
        for col, (label, number, desc) in zip([gc1, gc2, gc3, gc4], geo_kpis):
            with col:
                st.markdown(
                    f"""
                    <div class="kpi-card">
                        <div class="kpi-label">{label}</div>
                        <div class="kpi-number">{number}</div>
                        <div class="kpi-desc">{desc}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

        st.write("")
        st.markdown("#### Peta Sebaran & Kepadatan Pasar")

        # Map Controls
        mc1, mc2, mc3, mc4 = st.columns([1.6, 1.0, 1.0, 1.0])
        with mc1:
            map_mode = st.radio(
                "Mode Peta",
                options=["Titik Bisnis (Scatter)", "Kepadatan Area (Hexagon)"],
                horizontal=True,
                key="geo_map_mode",
            )
        with mc2:
            region_filter_opts = ["Semua Wilayah (Auto-Fit)"] + sorted(
                [r for r in geo_df["region"].dropna().unique() if str(r).strip()]
            )
            sel_geo_region = st.selectbox("Fokus Kota / Wilayah", options=region_filter_opts, key="geo_region_filter")
        with mc3:
            niche_filter_opts = ["Semua Niche"] + sorted(list(geo_df["niche"].dropna().unique()))
            sel_geo_niche = st.selectbox("Filter Niche", options=niche_filter_opts, key="geo_niche_filter")
        with mc4:
            scale_filter_opts = ["Semua Skala", "UMKM Tunggal", "Jaringan / Multi-Cabang"]
            sel_geo_scale = st.selectbox("Filter Skala Usaha", options=scale_filter_opts, key="geo_scale_filter")

        map_df = geo_df[coord_mask].copy()
        if sel_geo_region != "Semua Wilayah (Auto-Fit)":
            map_df = map_df[map_df["region"] == sel_geo_region]
        if sel_geo_niche != "Semua Niche":
            map_df = map_df[map_df["niche"] == sel_geo_niche]
        if sel_geo_scale != "Semua Skala":
            map_df = map_df[map_df["business_scale"] == sel_geo_scale]

        if not map_df.empty:
            map_df["latitude"] = pd.to_numeric(map_df["latitude"], errors="coerce")
            map_df["longitude"] = pd.to_numeric(map_df["longitude"], errors="coerce")
            map_df = map_df.dropna(subset=["latitude", "longitude"]).copy()

            is_hexagon = "Hexagon" in map_mode

            if len(map_df) == 1:
                view_state = pdk.ViewState(
                    latitude=float(map_df["latitude"].iloc[0]),
                    longitude=float(map_df["longitude"].iloc[0]),
                    zoom=13.5,
                    pitch=40 if is_hexagon else 0,
                )
            else:
                view_state = pdk.data_utils.compute_view(
                    map_df[["longitude", "latitude"]],
                    view_proportion=0.75,
                )
                view_state.zoom = min(14.0, max(5.0, float(view_state.zoom)))
                view_state.pitch = 40 if is_hexagon else 0

            if is_hexagon:
                hex_df = map_df[["longitude", "latitude"]].astype(float).reset_index(drop=True)
                layer = pdk.Layer(
                    "HexagonLayer",
                    data=hex_df,
                    get_position=["longitude", "latitude"],
                    radius=450,
                    elevation_scale=12,
                    elevation_range=[0, 1200],
                    pickable=True,
                    extruded=True,
                    coverage=0.85,
                )
                tooltip = {"text": "Kepadatan Area\nJumlah Entitas: {elevationValue}"}
            else:
                def _point_color(row):
                    if row.get("business_scale") == "Jaringan / Multi-Cabang":
                        return [217, 119, 6, 200]
                    has_w = bool(str(row.get("website_url") or "").strip())
                    return [37, 99, 235, 190] if has_w else [22, 163, 74, 210]

                scatter_df = map_df.copy()
                scatter_df["color"] = scatter_df.apply(_point_color, axis=1)
                scatter_df["radius"] = scatter_df["reviews_count"].apply(lambda r: min(240, max(60, 50 + int(r) * 0.35)))
                scatter_df["rating_str"] = scatter_df["rating"].apply(lambda x: f"{x:.1f}" if pd.notna(x) else "-")

                layer = pdk.Layer(
                    "ScatterplotLayer",
                    data=scatter_df,
                    get_position=["longitude", "latitude"],
                    get_fill_color="color",
                    get_radius="radius",
                    pickable=True,
                    stroked=True,
                    get_line_color=[255, 255, 255, 180],
                    line_width_min_pixels=1,
                )
                tooltip = {
                    "html": (
                        "<b>{business_name}</b><br/>"
                        "Skala: {business_scale}<br/>"
                        "Kecamatan: {kecamatan}<br/>"
                        "Rating: {rating_str} ★ ({reviews_count} ulasan)"
                    ),
                    "style": {"backgroundColor": "#0f172a", "color": "white", "fontSize": "12px"},
                }

            deck_key = f"pydeck_{map_mode}_{sel_geo_region}_{sel_geo_niche}_{sel_geo_scale}_{len(map_df)}"
            st.pydeck_chart(
                pdk.Deck(
                    layers=[layer],
                    initial_view_state=view_state,
                    tooltip=tooltip,
                    map_style=pdk.map_styles.CARTO_ROAD,
                ),
                use_container_width=True,
                height=420,
                key=deck_key,
            )
            if is_hexagon:
                st.caption("Semakin tinggi & terang kolom heksagon, semakin tinggi konsentrasi kompetitor pada area radius 450m.")
            else:
                st.caption("Keterangan warna: Hijau = UMKM Tanpa Website (Peluang Digital) | Biru = UMKM Memiliki Website | Oranye = Jaringan / Multi-Cabang")
        else:
            st.info("Belum ada titik koordinat yang sesuai filter atau lokasi belum dikenali.")

        st.divider()

        # Section 2: Full-width Whitespace Table
        st.markdown("#### Indeks Whitespace & Demand-to-Supply per Kecamatan")
        st.caption("Kecamatan dengan skor tertinggi menandakan permintaan pasar tinggi (banyak ulasan) namun kepadatan kompetitor masih rendah.")
        if not ws_df.empty:
            st.dataframe(
                ws_df,
                use_container_width=True,
                hide_index=True,
                height=320,
                column_config={
                    "kecamatan": st.column_config.TextColumn("Kecamatan", width="medium"),
                    "niche": st.column_config.TextColumn("Niche", width="small"),
                    "jumlah_kompetitor": st.column_config.NumberColumn("Kompetitor", format="%d"),
                    "total_ulasan": st.column_config.NumberColumn("Total Ulasan", format="%d"),
                    "rata_rata_ulasan": st.column_config.NumberColumn("Avg Ulasan", format="%.1f"),
                    "rata_rata_rating": st.column_config.NumberColumn("Avg Rating", format="%.2f ★"),
                    "tanpa_website_pct": st.column_config.NumberColumn("Tanpa Web", format="%.0f%%"),
                    "umkm_tunggal_pct": st.column_config.NumberColumn("UMKM Tunggal", format="%.0f%%"),
                    "whitespace_score": st.column_config.ProgressColumn("Skor Whitespace", min_value=0, max_value=100, format="%.1f"),
                    "status_pasar": st.column_config.TextColumn("Status Pasar", width="medium"),
                },
            )
        else:
            st.info("Nama kecamatan belum terdeteksi pada alamat hasil scrape. Aktifkan 'Ambil No. HP & Website (Detail Paralel)' agar alamat lengkap terambil.")

        st.divider()

        # Section 3: Balanced 2-column Business Scale Breakdown
        st.markdown("#### Analisis Skala Usaha: UMKM Tunggal vs Jaringan Multi-Cabang")
        scale_left, scale_right = st.columns([1.0, 1.5], gap="large")

        with scale_left:
            st.caption("Proporsi Skala Usaha")
            scale_counts = geo_df["business_scale"].value_counts().reset_index()
            scale_counts.columns = ["Skala", "Jumlah"]
            chart_scale = (
                alt.Chart(scale_counts)
                .mark_bar(cornerRadiusEnd=4)
                .encode(
                    x=alt.X("Jumlah:Q", title="Jumlah Entitas"),
                    y=alt.Y("Skala:N", sort="-x", title=""),
                    color=alt.Color(
                        "Skala:N",
                        scale=alt.Scale(domain=["UMKM Tunggal", "Jaringan / Multi-Cabang"], range=["#2563eb", "#d97706"]),
                        legend=None,
                    ),
                    tooltip=["Skala:N", "Jumlah:Q"],
                )
                .properties(height=240)
            )
            st.altair_chart(chart_scale, use_container_width=True)

        with scale_right:
            chains_df = geo_df[geo_df["business_scale"] == "Jaringan / Multi-Cabang"][
                [c for c in ["business_name", "branch_count", "kecamatan", "website_url"] if c in geo_df.columns]
            ].drop_duplicates(subset=["business_name"])
            if not chains_df.empty:
                st.caption("Entitas Terdeteksi Multi-Cabang / Jaringan")
                st.dataframe(
                    chains_df.head(15),
                    use_container_width=True,
                    hide_index=True,
                    height=240,
                    column_config={
                        "business_name": st.column_config.TextColumn("Nama Brand / Cabang"),
                        "branch_count": st.column_config.NumberColumn("Estimasi Cabang", format="%d"),
                        "kecamatan": st.column_config.TextColumn("Kecamatan"),
                        "website_url": st.column_config.LinkColumn("Website"),
                    },
                )
            else:
                st.caption("Top UMKM Tunggal Tanpa Website (Prioritas Prospek Digital)")
                no_web_mask = geo_df["website_url"].isna() | (geo_df["website_url"].astype(str).str.strip() == "")
                top_umkm = (
                    geo_df[no_web_mask]
                    .sort_values(by="reviews_count", ascending=False)
                    [[c for c in ["business_name", "kecamatan", "reviews_count", "phone_number"] if c in geo_df.columns]]
                    .head(15)
                )
                st.dataframe(
                    top_umkm,
                    use_container_width=True,
                    hide_index=True,
                    height=240,
                    column_config={
                        "business_name": st.column_config.TextColumn("Nama Usaha"),
                        "kecamatan": st.column_config.TextColumn("Kecamatan"),
                        "reviews_count": st.column_config.NumberColumn("Ulasan", format="%d"),
                        "phone_number": st.column_config.TextColumn("Telepon (+62)"),
                    },
                )

# Footer
st.markdown(
    """
    <div style="margin-top: 32px; padding-top: 16px; border-top: 1px solid #f1f5f9; text-align: center; color: #94a3b8; font-size: 11px;">
        Google Maps Scraper & Micro-SaaS Market Intelligence
    </div>
    """,
    unsafe_allow_html=True,
)
