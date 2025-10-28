"""
Aggregate plant points into county-level (Landkreis) totals for pie charts (one point per Landkreis).
- Input dir: GeoJSON point files under by_landkreis (all Germany)
- Output   : de_landkreis_pies.geojson (point per Landkreis with category sums)
             landkreis_pie_style_meta.json (min/max + field order)
Notes:
- Linear scaling will be applied later in geometry step.
- We DO NOT nudge county anchors; we keep them fixed at mean point coords.
"""

from pathlib import Path
import os, re, unicodedata, json
import geopandas as gpd
import pandas as pd
from shapely.geometry import Point

# -------- SETTINGS --------
INPUT_DIR  = r"C:\Users\jo73vure\Desktop\powerPlantProject\data\geojson\by_landkreis"
OUTPUT_DIR = r"C:\Users\jo73vure\Desktop\powerPlantProject\data\geojson\pieCharts"

ENERGY_FIELD = "energy_source_label"   # optional custom label field if present
STATE_FIELD  = None                    # unused here, we aggregate by Landkreis nationwide
# ------------------------------------

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

def normalize_text(s: str) -> str:
    if s is None: return ""
    s = unicodedata.normalize("NFKD", str(s))
    s = "".join(ch for ch in s if not unicodedata.combining(ch)).lower()
    return re.sub(r"[^a-z0-9]+", " ", s).strip()

def parse_number(val):
    """Parse values like '94.000', '1.234,56', '250' -> float."""
    if val is None: return None
    if isinstance(val, (int, float)): return float(val)
    s = str(val).strip().replace(" ", "")
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".")
    else:
        s = s.replace(",", ".")
    try:
        return float(s)
    except Exception:
        return None

def normalize_energy(val, filename_hint="") -> str:
    if val is not None:
        s = str(val).strip()
        if s in ENERGY_CODE_TO_LABEL: return ENERGY_CODE_TO_LABEL[s]
        sn = normalize_text(s)
        if "solar" in sn or "photovoltaik" in sn or sn == "pv": return "Photovoltaik"
        if "wind" in sn: return "Windenergie Onshore"
        if "wasser" in sn or "hydro" in sn: return "Wasserkraft"
        if "stromspeicher" in sn or "speicher" in sn or "battery" in sn: return "Stromspeicher (Battery Storage)"
        if "biogas" in sn or sn == "gas": return "Biogas"
    fn = normalize_text(filename_hint)
    if "solar" in fn or "photovoltaik" in fn or "pv" in fn: return "Photovoltaik"
    if "wind" in fn: return "Windenergie Onshore"
    if "wasser" in fn or "hydro" in fn: return "Wasserkraft"
    if "stromspeicher" in fn or "speicher" in fn or "battery" in fn: return "Stromspeicher (Battery Storage)"
    if "biogas" in fn: return "Biogas"
    return "Unknown"

def infer_kreis_from_row(row: pd.Series):
    # 1) direct name fields
    for cand in ("Landkreis","landkreis","Kreis","kreis","kreis_name","county","County"):
        if cand in row and pd.notna(row[cand]):
            return str(row[cand]).strip()
    # 2) build a 5-digit AGS Kreis code from Gemeindeschluessel if present (first 5 chars)
    kreis_code = None
    for cand in ("Gemeindeschluessel","gemeindeschluessel","AGS","ags","ags_id"):
        if cand in row and pd.notna(row[cand]):
            s = re.sub(r"[^0-9]", "", str(row[cand]))
            if len(s) >= 5:
                kreis_code = s[:5]
                break
    return kreis_code or None

def scan_geojsons(folder: str):
    for root, _, fnames in os.walk(folder):
        for fn in fnames:
            if Path(fn).suffix.lower() == ".geojson":
                yield Path(root) / fn

def first_power_column(cols):
    candidates = ["power_kw","Nettonennleistung","Bruttoleistung","Nennleistung","Leistung","installed_power_kw","kw","power"]
    for c in candidates:
        if c in cols: return c
    lc = {normalize_text(c): c for c in cols}
    for key in ["nettonennleistung","bruttoleistung","nennleistung","leistung","power","kw"]:
        for k, orig in lc.items():
            if key in k: return orig
    return None

def main():
    in_dir = Path(INPUT_DIR)
    out_dir = Path(OUTPUT_DIR); out_dir.mkdir(parents=True, exist_ok=True)

    paths = list(scan_geojsons(str(in_dir)))
    print(f"Found {len(paths)} GeoJSON files under: {in_dir}")
    if not paths:
        raise RuntimeError("No .geojson files found in INPUT_DIR.")

    frames = []
    for p in paths:
        try:
            g = gpd.read_file(p)
            if g.empty or "geometry" not in g.columns:
                continue
            g = g[~g.geometry.is_empty & g.geometry.notnull()].copy()
            g = g[g.geometry.geom_type.isin(["Point","MultiPoint"])]
            if g.empty:
                continue
            try:
                if "MultiPoint" in g.geometry.geom_type.unique():
                    g = g.explode(index_parts=False).reset_index(drop=True)
            except TypeError:
                g = g.explode().reset_index(drop=True)

            # kreis name/code
            g["kreis_name"] = g.apply(infer_kreis_from_row, axis=1)

            # energy
            if ENERGY_FIELD in g.columns:
                g["energy_norm"] = g[ENERGY_FIELD].apply(lambda v: normalize_energy(v, p.name))
            elif "Energietraeger" in g.columns:
                g["energy_norm"] = g["Energietraeger"].apply(lambda v: normalize_energy(v, p.name))
            else:
                g["energy_norm"] = normalize_energy(None, p.name)

            # power
            power_col = first_power_column(g.columns)
            if power_col is None:
                print(f"[WARN] No power field found in {p.name}; skipped.")
                continue
            g["_power"] = g[power_col].apply(parse_number)

            g = g[(pd.notna(g["kreis_name"])) & (pd.notna(g["_power"])) & (g["_power"] > 0)]
            if g.empty:
                print(f"[WARN] No positive power rows after parsing in {p.name}; skipped.")
                continue

            frames.append(g[["kreis_name","energy_norm","_power","geometry"]])
        except Exception as e:
            print(f"[WARN] Skipped {p}: {e}")

    if not frames:
        raise RuntimeError("No usable point features found across GeoJSON files.")

    plants = pd.concat(frames, ignore_index=True)

    # aggregate per Landkreis
    rows = []
    for kreis, grp in plants.groupby("kreis_name"):
        totals = {f: 0.0 for f in PRIORITY_FIELDNAMES.values()}
        others = 0.0
        for _, r in grp.iterrows():
            cat = r["energy_norm"]; pkw = float(r["_power"])
            if cat in PRIORITY_FIELDNAMES:
                totals[PRIORITY_FIELDNAMES[cat]] += pkw
            else:
                others += pkw
        totals[OTHERS_FIELD] = others
        totals["total_kw"] = sum(totals.values())
        totals["kreis_name"] = str(kreis)
        # anchor: fixed mean of points (no nudge)
        ax = float(grp.geometry.x.mean()); ay = float(grp.geometry.y.mean())
        totals["_x"] = ax; totals["_y"] = ay
        rows.append(totals)

    agg = pd.DataFrame(rows)
    agg["geometry"] = [Point(xy) for xy in zip(agg["_x"], agg["_y"])]

    gdf = gpd.GeoDataFrame(agg.drop(columns=["_x","_y"]), geometry="geometry", crs="EPSG:4326")
    vmin = float(gdf["total_kw"].min()) if len(gdf) else 0.0
    vmax = float(gdf["total_kw"].max()) if len(gdf) else 1.0

    out_pts = out_dir / "de_landkreis_pies.geojson"
    gdf.to_file(out_pts, driver="GeoJSON")

    meta = {
        "min_total_kw": vmin,
        "max_total_kw": vmax,
        "priority_fields": list(PRIORITY_FIELDNAMES.values()),
        "others_field": OTHERS_FIELD,
        "name_field": "kreis_name"
    }
    (out_dir / "landkreis_pie_style_meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(f"Created: {out_pts}")
    print(f"Saved:   {out_dir / 'landkreis_pie_style_meta.json'}")

if __name__ == "__main__":
    main()
