# Filename: step3_1_make_landkreis_pie_inputs.py
# Purpose:
#   Build NATIONWIDE Landkreis pie INPUT POINTS
#   using authoritative centers from step0_for2and3_make_landkreis_centers.py
#
# Logic (aligned with step2_1):
#   - Read raw plant points from by_state_landkreis/*/*.geojson
#   - Normalize energy + power
#   - Aggregate per Landkreis (kreis_key = AGS5)
#   - Geometry = authoritative center from step0 (NO recompute)
#   - Output:
#       - nationwide GeoJSON
#       - nationwide style meta (global min/max)
#       - per-state subfiles (same geometry, filtered)

from pathlib import Path
import os, re, json, unicodedata
import geopandas as gpd
import pandas as pd
from shapely.geometry import Point

# ---------------- PATHS ----------------

INPUT_ROOT = Path(
    r"C:\Users\jo73vure\Desktop\powerPlantProject\data\geojson\by_state_landkreis"
)

CENTERS_PATH = Path(
    r"C:\Users\jo73vure\Desktop\powerPlantProject\data\geojson\pieCharts\landkreis_centers\de_landkreis_centers.geojson"
)

OUTPUT_DIR = Path(
    r"C:\Users\jo73vure\Desktop\powerPlantProject\data\geojson\pieCharts\nationwide_landkreis_pies"
)

# ---------------- ENERGY MAPS ----------------

ENERGY_CODE_TO_LABEL = {
    "2403": "Tiefe Geothermie",
    "2405": "Klärgas",
    "2406": "Druckentspannung",
    "2493": "Biogas",
    "2495": "Photovoltaik",
    "2496": "Stromspeicher (Battery Storage)",
    "2497": "Windenergie Onshore",
    "2498": "Wasserkraft",
}

PRIORITY_FIELDNAMES = {
    "Photovoltaik": "pv_kw",
    "Windenergie Onshore": "wind_kw",
    "Wasserkraft": "hydro_kw",
    "Stromspeicher (Battery Storage)": "battery_kw",
    "Biogas": "biogas_kw",
}
OTHERS_FIELD = "others_kw"

# ---------------- HELPERS ----------------

def normalize_text(s: str) -> str:
    if s is None:
        return ""
    s = unicodedata.normalize("NFKD", str(s))
    s = "".join(ch for ch in s if not unicodedata.combining(ch)).lower()
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def normalize_energy(val, filename_hint="") -> str:
    if val is not None:
        s = str(val).strip()
        if s in ENERGY_CODE_TO_LABEL:
            return ENERGY_CODE_TO_LABEL[s]
        sn = normalize_text(s)
        if "solar" in sn or "photovoltaik" in sn or sn == "pv":
            return "Photovoltaik"
        if "wind" in sn:
            return "Windenergie Onshore"
        if "wasser" in sn or "hydro" in sn:
            return "Wasserkraft"
        if "stromspeicher" in sn or "speicher" in sn or "battery" in sn:
            return "Stromspeicher (Battery Storage)"
        if "biogas" in sn:
            return "Biogas"

    fn = normalize_text(filename_hint)
    if "solar" in fn or "photovoltaik" in fn or "pv" in fn:
        return "Photovoltaik"
    if "wind" in fn:
        return "Windenergie Onshore"
    if "wasser" in fn or "hydro" in fn:
        return "Wasserkraft"
    if "stromspeicher" in fn or "speicher" in fn or "battery" in fn:
        return "Stromspeicher (Battery Storage)"
    if "biogas" in fn:
        return "Biogas"

    return "Unknown"


def parse_number(val):
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return float(val)
    s = str(val).strip().replace(" ", "")
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".")
    else:
        s = s.replace(",", ".")
    try:
        return float(s)
    except Exception:
        return None


def extract_ags5(row: pd.Series):
    for cand in (
        "Gemeindeschluessel", "gemeindeschluessel",
        "AGS", "ags", "ags_id", "kreisschluessel", "rs"
    ):
        if cand in row and pd.notna(row[cand]):
            digits = re.sub(r"[^0-9]", "", str(row[cand]))
            if len(digits) >= 5:
                return digits[:5]
    return None


def first_power_column(cols):
    candidates = [
        "power_kw", "Nettonennleistung", "Bruttoleistung",
        "Nennleistung", "Leistung", "installed_power_kw",
        "kw", "power"
    ]
    for c in candidates:
        if c in cols:
            return c
    norm_cols = {normalize_text(c): c for c in cols}
    for key in ["nettonennleistung", "bruttoleistung", "nennleistung", "leistung", "power", "kw"]:
        for nk, orig in norm_cols.items():
            if key in nk:
                return orig
    return None


def scan_geojsons(folder: Path):
    for root, _, files in os.walk(folder):
        for fn in files:
            if fn.lower().endswith(".geojson"):
                yield Path(root) / fn


# ---------------- MAIN ----------------

def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # --- load authoritative centers ---
    centers_gdf = gpd.read_file(CENTERS_PATH)
    centers_by_ags = {
        r["ags5"]: (r.geometry.x, r.geometry.y)
        for _, r in centers_gdf.iterrows()
    }
    state_by_ags = {
        r["ags5"]: r["state_slug"]
        for _, r in centers_gdf.iterrows()
    }
    name_by_ags = {
        r["ags5"]: r["kreis_name"]
        for _, r in centers_gdf.iterrows()
    }

    rows = []

    # --- read plant points ---
    for state_dir in INPUT_ROOT.iterdir():
        if not state_dir.is_dir():
            continue

        for p in scan_geojsons(state_dir):
            try:
                g = gpd.read_file(p)
            except Exception:
                continue

            if g.empty or "geometry" not in g.columns:
                continue

            g = g[g.geometry.notnull()].copy()
            g = g[g.geometry.geom_type.isin(["Point", "MultiPoint"])]
            if g.empty:
                continue

            try:
                if "MultiPoint" in g.geometry.geom_type.unique():
                    g = g.explode(index_parts=False).reset_index(drop=True)
            except Exception:
                g = g.explode().reset_index(drop=True)

            # energy
            if "energy_source_label" in g.columns:
                g["energy_norm"] = g["energy_source_label"].apply(
                    lambda v: normalize_energy(v, p.name)
                )
            elif "Energietraeger" in g.columns:
                g["energy_norm"] = g["Energietraeger"].apply(
                    lambda v: normalize_energy(v, p.name)
                )
            else:
                g["energy_norm"] = normalize_energy(None, p.name)

            power_col = first_power_column(g.columns)
            if power_col is None:
                continue

            g["_power"] = g[power_col].apply(parse_number)

            for _, r in g.iterrows():
                if r["_power"] is None or r["_power"] <= 0:
                    continue

                ags5 = extract_ags5(r)
                if not ags5 or ags5 not in centers_by_ags:
                    continue

                rows.append(
                    {
                        "kreis_key": ags5,
                        "state_slug": state_by_ags.get(ags5, ""),
                        "energy_norm": r["energy_norm"],
                        "_power": float(r["_power"]),
                    }
                )

    if not rows:
        raise RuntimeError("No valid plant points found.")

    df = pd.DataFrame(rows)

    # --- aggregate nationwide per Landkreis ---
    out_rows = []
    for kreis_key, grp in df.groupby("kreis_key"):
        totals = {f: 0.0 for f in PRIORITY_FIELDNAMES.values()}
        others = 0.0

        for _, r in grp.iterrows():
            cat = r["energy_norm"]
            pkw = r["_power"]
            if cat in PRIORITY_FIELDNAMES:
                totals[PRIORITY_FIELDNAMES[cat]] += pkw
            else:
                others += pkw

        totals[OTHERS_FIELD] = others
        totals["total_kw"] = sum(totals.values())

        cx, cy = centers_by_ags[kreis_key]

        out_rows.append(
            {
                "kreis_key": kreis_key,
                "kreis_name": name_by_ags.get(kreis_key, kreis_key),
                "state_slug": state_by_ags.get(kreis_key, ""),
                **totals,
                "geometry": Point(cx, cy),
            }
        )

    gdf = gpd.GeoDataFrame(out_rows, geometry="geometry", crs="EPSG:4326")

    # --- nationwide meta ---
    vmin = float(gdf["total_kw"].min()) if len(gdf) else 0.0
    vmax = float(gdf["total_kw"].max()) if len(gdf) else 1.0

    meta = {
        "min_total_kw": vmin,
        "max_total_kw": vmax,
        "priority_fields": list(PRIORITY_FIELDNAMES.values()),
        "others_field": OTHERS_FIELD,
        "name_field": "kreis_name",
    }

    # --- write nationwide ---
    nationwide_path = OUTPUT_DIR / "de_landkreis_pies.geojson"
    gdf.to_file(nationwide_path, driver="GeoJSON")

    (OUTPUT_DIR / "landkreis_pie_style_meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"[OK] nationwide pies -> {nationwide_path}")

    # --- write per-state subsets ---
    for slug, sub in gdf[gdf["state_slug"] != ""].groupby("state_slug"):
        tgt_dir = OUTPUT_DIR / slug
        tgt_dir.mkdir(parents=True, exist_ok=True)
        outp = tgt_dir / f"de_{slug}_landkreis_pies.geojson"
        sub.to_file(outp, driver="GeoJSON")
        print(f"[OK] per-state subset -> {outp}")


if __name__ == "__main__":
    main()
