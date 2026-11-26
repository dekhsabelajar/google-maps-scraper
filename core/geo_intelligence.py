"""
Geo-Intelligence & Spatial Market Analysis module:
- Extracts precise latitude/longitude from Google Maps URLs (zero API cost)
- Parses administrative regions (kecamatan, kota/kabupaten) from addresses
- Detects single-outlet SMEs vs multi-branch chains
- Computes kecamatan-level Whitespace & Demand-to-Supply opportunity scores
"""
import hashlib
import math
import re
from typing import Dict, Optional, Tuple
from urllib.parse import unquote, urlparse

import pandas as pd

# Exact pin coordinates in Google Maps place URLs: !3d<lat>!4d<lon>
_PIN_COORD_RE = re.compile(r"!3d(-?\d+\.\d+)!4d(-?\d+\.\d+)")
# Viewport center fallback: @<lat>,<lon>
_VIEWPORT_COORD_RE = re.compile(r"@(-?\d+\.\d+),(-?\d+\.\d+)")

# Administrative region patterns for Indonesian Google Maps addresses
_KECAMATAN_RE = re.compile(r"\b(?:Kec\.|Kecamatan)\s+([^,\d]+)", re.IGNORECASE)
_KOTA_KAB_RE = re.compile(r"\b(?:Kota|Kab\.|Kabupaten)\s+([^,\d]+)", re.IGNORECASE)

# Generic third-party/social domains excluded from multi-branch website matching
_GENERIC_DOMAINS = {
    "instagram.com",
    "www.instagram.com",
    "facebook.com",
    "www.facebook.com",
    "fb.com",
    "wa.me",
    "api.whatsapp.com",
    "whatsapp.com",
    "linktr.ee",
    "tiktok.com",
    "www.tiktok.com",
    "youtube.com",
    "www.youtube.com",
    "shopee.co.id",
    "tokopedia.com",
    "gofood.co.id",
    "grab.com",
    "bit.ly",
    "sites.google.com",
    "business.site",
}

_BRANCH_NOISE_RE = re.compile(
    r"\b(?:cabang|branch|outlet|unit|jogja|yogyakarta|sleman|bantul|klaten|magelang|"
    r"solo|surakarta|semarang|jakarta|bandung|surabaya|malang|bali|denpasar|"
    r"seturan|babarsari|gejayan|jakal|pogung|condongcatur|palagan|ugm|uny)\b",
    re.IGNORECASE,
)


_REGION_CENTROIDS: Dict[str, Tuple[float, float]] = {
    "yogyakarta": (-7.795580, 110.369490),
    "diy yogyakarta": (-7.795580, 110.369490),
    "sleman": (-7.732521, 110.355423),
    "bantul": (-7.889762, 110.328209),
    "kulon progo": (-7.826667, 110.164167),
    "gunungkidul": (-7.983333, 110.600000),
    "wonosari": (-7.966667, 110.600000),
    "klaten": (-7.705833, 110.606111),
    "magelang": (-7.479734, 110.217697),
    "solo": (-7.575489, 110.824327),
    "surakarta": (-7.575489, 110.824327),
    "semarang": (-6.966667, 110.416664),
    "salatiga": (-7.330523, 110.508423),
    "jakarta": (-6.208763, 106.845599),
    "jakarta selatan": (-6.261493, 106.810600),
    "jakarta pusat": (-6.186486, 106.834091),
    "jakarta barat": (-6.167431, 106.763725),
    "jakarta timur": (-6.225014, 106.900447),
    "jakarta utara": (-6.138414, 106.863956),
    "bogor": (-6.597147, 106.806039),
    "depok": (-6.402484, 106.794243),
    "tangerang": (-6.170180, 106.640324),
    "bekasi": (-6.238270, 106.975573),
    "bandung": (-6.917464, 107.619123),
    "surabaya": (-7.257472, 112.752088),
    "malang": (-7.966620, 112.632629),
    "bali": (-8.409518, 115.188919),
    "denpasar": (-8.670458, 115.212629),
    "medan": (3.595196, 98.672226),
    "makassar": (-5.147665, 119.432731),
}


def extract_coords_from_url(url: Optional[str]) -> Tuple[Optional[float], Optional[float]]:
    """
    Extract (latitude, longitude) from a Google Maps URL without external API calls.
    Prefers exact pin markers (!3d...!4d...) over viewport center (@lat,lon).
    """
    if not url or not isinstance(url, str):
        return None, None

    decoded_url = unquote(url)
    match = _PIN_COORD_RE.search(decoded_url) or _VIEWPORT_COORD_RE.search(decoded_url)
    if not match:
        return None, None

    try:
        lat = float(match.group(1))
        lon = float(match.group(2))
        if -90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0:
            return round(lat, 6), round(lon, 6)
    except ValueError:
        pass
    return None, None


def _estimate_coords_from_region(
    name: str,
    kota_kab: str,
    region: str,
    address: str,
) -> Tuple[Optional[float], Optional[float]]:
    """Deterministic regional centroid fallback with small jitter when exact pin coords are absent."""
    haystack = f"{kota_kab} {region} {address}".lower()
    base = None
    for key, coords in _REGION_CENTROIDS.items():
        if key in haystack:
            base = coords
            break
    if base is None:
        return None, None

    digest = hashlib.md5(f"{name}|{address}".encode("utf-8")).hexdigest()
    # Deterministic offset within ~1.5km radius so markers/hexagons distribute cleanly
    lat_off = ((int(digest[:4], 16) / 65535.0) - 0.5) * 0.025
    lon_off = ((int(digest[4:8], 16) / 65535.0) - 0.5) * 0.025
    return round(base[0] + lat_off, 6), round(base[1] + lon_off, 6)


def extract_admin_region(
    address: Optional[str],
    fallback_region: Optional[str] = None,
) -> Tuple[str, str]:
    """
    Parse (kecamatan, kota_kabupaten) from an address string.
    Returns 'Tidak Diketahui' when a level cannot be reliably determined.
    """
    addr = str(address or "").strip()
    kecamatan = "Tidak Diketahui"
    kota_kab = str(fallback_region or "").strip() or "Tidak Diketahui"

    if addr:
        m_kec = _KECAMATAN_RE.search(addr)
        if m_kec:
            kecamatan = re.sub(r"\s+", " ", m_kec.group(1)).strip(" .-")

        m_kota = _KOTA_KAB_RE.search(addr)
        if m_kota:
            kota_kab = re.sub(r"\s+", " ", m_kota.group(1)).strip(" .-")

    return kecamatan or "Tidak Diketahui", kota_kab or "Tidak Diketahui"


def _extract_custom_domain(website_url: Optional[str]) -> str:
    """Return normalized domain if custom business website; empty string for social/generic links."""
    if not website_url or not isinstance(website_url, str):
        return ""
    raw = website_url.strip()
    if not raw:
        return ""
    if not raw.startswith(("http://", "https://")):
        raw = f"https://{raw}"
    try:
        host = (urlparse(raw).hostname or "").lower().removeprefix("www.")
    except Exception:
        return ""
    if not host or host in _GENERIC_DOMAINS or f"www.{host}" in _GENERIC_DOMAINS:
        return ""
    return host


def _normalize_brand_key(name: Optional[str]) -> str:
    """Strip branch/city modifiers from a business name to detect multi-branch brands."""
    if not name or not isinstance(name, str):
        return ""
    cleaned = re.sub(r"\([^)]*\)|\[[^\]]*\]", " ", name.lower())
    cleaned = _BRANCH_NOISE_RE.sub(" ", cleaned)
    cleaned = re.sub(r"[^a-z0-9\s]", " ", cleaned)
    cleaned = re.sub(r"\b\d+\b", " ", cleaned)
    tokens = [t for t in cleaned.split() if len(t) > 1]
    return " ".join(tokens)


def enrich_geo_and_scale_df(df: pd.DataFrame) -> pd.DataFrame:
    """
    Ensure spatial columns (latitude, longitude, kecamatan, kota_kabupaten) and
    business scale classification (business_scale, branch_count) exist on the DataFrame.
    """
    if df.empty:
        return df

    out = df.copy()

    # 1. Coordinates
    if "latitude" not in out.columns:
        out["latitude"] = None
    if "longitude" not in out.columns:
        out["longitude"] = None

    if "google_url" in out.columns:
        missing_coord = out["latitude"].isna() | out["longitude"].isna()
        if missing_coord.any():
            coords = out.loc[missing_coord, "google_url"].apply(extract_coords_from_url)
            out.loc[missing_coord, "latitude"] = [c[0] for c in coords]
            out.loc[missing_coord, "longitude"] = [c[1] for c in coords]

    out["latitude"] = pd.to_numeric(out["latitude"], errors="coerce")
    out["longitude"] = pd.to_numeric(out["longitude"], errors="coerce")

    # 2. Administrative regions (kecamatan, kota_kabupaten)
    need_kec = "kecamatan" not in out.columns or out["kecamatan"].isna().all()
    need_kota = "kota_kabupaten" not in out.columns or out["kota_kabupaten"].isna().all()
    if need_kec or need_kota:
        regions = out.apply(
            lambda r: extract_admin_region(r.get("address"), r.get("region")),
            axis=1,
        )
        if need_kec:
            out["kecamatan"] = [reg[0] for reg in regions]
        if need_kota:
            out["kota_kabupaten"] = [reg[1] for reg in regions]
    else:
        out["kecamatan"] = out["kecamatan"].fillna("Tidak Diketahui").replace("", "Tidak Diketahui")
        out["kota_kabupaten"] = out["kota_kabupaten"].fillna("Tidak Diketahui").replace("", "Tidak Diketahui")

    # Fallback regional centroid for rows still missing coordinates
    still_missing = out["latitude"].isna() | out["longitude"].isna()
    out["coord_source"] = "Presisi GPS"
    if still_missing.any():
        out.loc[still_missing, "coord_source"] = "Estimasi Wilayah"
        est = out.loc[still_missing].apply(
            lambda r: _estimate_coords_from_region(
                str(r.get("business_name") or ""),
                str(r.get("kota_kabupaten") or ""),
                str(r.get("region") or ""),
                str(r.get("address") or ""),
            ),
            axis=1,
        )
        out.loc[still_missing, "latitude"] = [e[0] for e in est]
        out.loc[still_missing, "longitude"] = [e[1] for e in est]
        out["latitude"] = pd.to_numeric(out["latitude"], errors="coerce")
        out["longitude"] = pd.to_numeric(out["longitude"], errors="coerce")

    # 3. Multi-branch / chain detection
    domains = out["website_url"].apply(_extract_custom_domain) if "website_url" in out.columns else pd.Series([""] * len(out), index=out.index)
    brand_keys = out["business_name"].apply(_normalize_brand_key) if "business_name" in out.columns else pd.Series([""] * len(out), index=out.index)

    domain_counts: Dict[str, int] = domains[domains != ""].value_counts().to_dict()
    # Require >= 2 meaningful words for name-based chain matching to avoid false positives on generic 1-word names
    valid_brand_mask = brand_keys.apply(lambda k: len(k.split()) >= 2)
    brand_counts: Dict[str, int] = brand_keys[valid_brand_mask].value_counts().to_dict()

    branch_counts = []
    scales = []
    for idx in out.index:
        dom = domains.loc[idx]
        bkey = brand_keys.loc[idx]
        c_dom = domain_counts.get(dom, 0) if dom else 0
        c_brand = brand_counts.get(bkey, 0) if len(bkey.split()) >= 2 else 0
        count = max(1, c_dom, c_brand)
        branch_counts.append(count)
        scales.append("Jaringan / Multi-Cabang" if count >= 2 else "UMKM Tunggal")

    out["branch_count"] = branch_counts
    out["business_scale"] = scales
    return out


def build_whitespace_summary(df: pd.DataFrame) -> pd.DataFrame:
    """
    Aggregate market density and demand-to-supply opportunity by kecamatan (and niche if multi-niche).
    Higher whitespace_score indicates strong review demand with relatively low competitor saturation.
    """
    if df.empty or "kecamatan" not in df.columns:
        return pd.DataFrame()

    work = df[df["kecamatan"].astype(str).str.strip().ne("Tidak Diketahui")].copy()
    if work.empty:
        return pd.DataFrame()

    multi_niche = "niche" in work.columns and work["niche"].nunique() > 1
    group_cols = ["kecamatan", "niche"] if multi_niche else ["kecamatan"]

    rows = []
    for keys, grp in work.groupby(group_cols, sort=False):
        kec = keys[0] if multi_niche else keys
        niche_val = keys[1] if multi_niche else (grp["niche"].iloc[0] if "niche" in grp.columns else "-")

        comp_count = int(len(grp))
        avg_rev = float(grp["reviews_count"].mean()) if "reviews_count" in grp.columns and len(grp) else 0.0
        total_rev = int(grp["reviews_count"].sum()) if "reviews_count" in grp.columns else 0
        avg_rat = float(grp["rating"].dropna().mean()) if "rating" in grp.columns and grp["rating"].notna().any() else 0.0

        has_web = grp["website_url"].notna() & (grp["website_url"].astype(str).str.strip() != "")
        no_web_pct = float((~has_web).mean() * 100) if len(grp) else 0.0

        umkm_pct = float((grp["business_scale"] == "UMKM Tunggal").mean() * 100) if "business_scale" in grp.columns else 100.0

        # Demand factor (0..1), supply sparsity factor (0..1), digital gap factor (0..1)
        demand_factor = min(1.0, math.log1p(max(0.0, avg_rev)) / math.log1p(500.0))
        sparsity_factor = 1.0 / (1.0 + (comp_count / 6.0))
        digital_gap_factor = no_web_pct / 100.0

        raw_score = (0.45 * demand_factor + 0.35 * sparsity_factor + 0.20 * digital_gap_factor) * 100.0
        whitespace_score = round(min(100.0, max(0.0, raw_score)), 1)

        if whitespace_score >= 60.0:
            status = "Peluang Tinggi (Whitespace)"
        elif whitespace_score >= 42.0:
            status = "Potensial"
        else:
            status = "Kompetitif / Padat"

        rows.append({
            "kecamatan": kec,
            "niche": niche_val,
            "jumlah_kompetitor": comp_count,
            "total_ulasan": total_rev,
            "rata_rata_ulasan": round(avg_rev, 1),
            "rata_rata_rating": round(avg_rat, 2),
            "tanpa_website_pct": round(no_web_pct, 1),
            "umkm_tunggal_pct": round(umkm_pct, 1),
            "whitespace_score": whitespace_score,
            "status_pasar": status,
        })

    res = pd.DataFrame(rows)
    if not res.empty:
        res = res.sort_values(by=["whitespace_score", "rata_rata_ulasan"], ascending=[False, False]).reset_index(drop=True)
    return res
