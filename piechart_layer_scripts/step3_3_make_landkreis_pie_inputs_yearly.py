# Filename: step3_3_make_landkreis_pie_inputs_yearly.py
# Purpose : Nationwide county (Landkreis) pie INPUTS split by YEAR BINS,
#           then split into STATES using strict "3-checks" (polygon + Bundesland + AGS).
# Output  : <BASE>/<year-bin>/<state-slug>/de_<state-slug>_landkreis_pies_<bin>.geojson
#           plus <BASE>/<year-bin>/landkreis_pie_style_meta_<bin>.json (per-bin min/max)

from pathlib import Path
import os, re, unicodedata, json
import geopandas as gpd
import pandas as pd
from shapely.geometry import Point, shape, MultiPolygon, Polygon

# ---------- PATHS ----------
INPUT_DIR  = Path(r"C:\Users\jo73vure\Desktop\powerPlantProject\data\geojson\by_landkreis")
BASE_DIR   = Path(r"C:\Users\jo73vure\Desktop\powerPlantProject\data\geojson\pieCharts\nationwide_landkreis_pies_yearly")
POLYGON_STATES_PATH = Path(r"C:\Users\jo73vure\Desktop\powerPlantProject\data\polygon_states.json")  # GeoJSON with properties.name

# ---------- YEAR BINS (same as before) ----------
YEAR_BINS = [
    ("pre_1990",  "≤1990 — Pre-EEG (pre-support era)",      None, 1990),
    ("1991_1999", "1991–1999 — Post-reunification",          1991, 1999),
    ("2000_2003", "2000–2003 — EEG launch & early ramp-up",  2000, 2003),
    ("2004_2011", "2004–2011 — EEG expansion phase",         2004, 2011),
    ("2012_2016", "2012–2016 — EEG 2012 reform period",      2012, 2016),
    ("2017_2020", "2017–2020 — Auction transition",          2017, 2020),
    ("2021_2025", "2021–2025 — Recent years",                2021, 2025),
]
BIN_LABEL = {s: lbl for (s, lbl, *_ ) in YEAR_BINS}
BIN_ORDER = [s for (s, *_ ) in YEAR_BINS]
INCLUDE_UNKNOWN = False  # keep False as you said bins are already correct

# ---------- ENERGY (5 + Others) ----------
ENERGY_CODE_TO_LABEL = {
    "2403": "Tiefe Geothermie", "2405": "Klärgas", "2406": "Druckentspannung",
    "2493": "Biogas", "2495": "Photovoltaik", "2496": "Stromspeicher (Battery Storage)",
    "2497": "Windenergie Onshore", "2498": "Wasserkraft",
}
PRIORITY_FIELDNAMES = {
    "Photovoltaik": "pv_kw",
    "Windenergie Onshore": "wind_kw",
    "Wasserkraft": "hydro_kw",
    "Stromspeicher (Battery Storage)": "battery_kw",
    "Biogas": "biogas_kw",
}
OTHERS_FIELD = "others_kw"

# ---------- 3-checks mappings (as in step15) ----------
BUNDESLAND_CODE_TO_NAME = {
    "1400": "brandenburg","1401": "berlin","1402": "baden_wuerttemberg","1403": "bayern",
    "1404": "bremen","1405": "hessen","1406": "hamburg","1407": "mecklenburg_vorpommern",
    "1408": "niedersachsen","1409": "nordrhein_westfalen","1410": "rheinland_pfalz",
    "1411": "schleswig_holstein","1412": "saarland","1413": "sachsen","1414": "sachsen_anhalt",
    "1415": "thueringen",
}
GS_PREFIX_TO_NAME = {
    "01": "schleswig_holstein","02": "hamburg","03": "niedersachsen","04": "bremen",
    "05": "nordrhein_westfalen","06": "hessen","07": "rheinland_pfalz","08": "baden_wuerttemberg",
    "09": "bayern","10": "saarland","11": "berlin","12": "brandenburg","13": "mecklenburg_vorpommern",
    "14": "sachsen","15": "sachsen_anhalt","16": "thueringen",
}
# normalized name -> folder slug
NORM_TO_SLUG = {
    "badenwuerttemberg": "baden-wuerttemberg",
    "bayern": "bayern",
    "berlin": "berlin",
    "brandenburg": "brandenburg",
    "bremen": "bremen",
    "hamburg": "hamburg",
    "hessen": "hessen",
    "mecklenburgvorpommern": "mecklenburg-vorpommern",
    "niedersachsen": "niedersachsen",
    "nordrheinwestfalen": "nordrhein-westfalen",
    "rheinlandpfalz": "rheinland-pfalz",
    "saarland": "saarland",
    "sachsen": "sachsen",
    "sachsenanhalt": "sachsen-anhalt",
    "schleswigholstein": "schleswig-holstein",
    "thueringen": "thueringen",
}

# ---------- helpers ----------
def normalize_text(s: str) -> str:
    if s is None: return ""
    s = unicodedata.normalize("NFKD", str(s))
    s = "".join(ch for ch in s if not unicodedata.combining(ch)).lower()
    return re.sub(r"[^a-z0-9]+", " ", s).strip()

def normalize_state_name(name: str) -> str:
    if not isinstance(name, str): return ""
    s = name.lower().replace("ä","ae").replace("ö","oe").replace("ü","ue").replace("ß","ss")
    for ch in [" ", "_", "-", "(", ")", "[", "]", "{", "}", ".", ",", "'"]:
        s = s.replace(ch, "")
    return s

def bl_code_to_norm_name(code) -> str:
    c = str(code).strip() if code is not None else ""
    nm = BUNDESLAND_CODE_TO_NAME.get(c)
    return normalize_state_name(nm) if nm else ""

def gs_prefix_to_norm_name(gs) -> str:
    s = re.sub(r"[^0-9]", "", str(gs)) if gs is not None else ""
    if len(s) < 2: return ""
    nm = GS_PREFIX_TO_NAME.get(s[:2])
    return normalize_state_name(nm) if nm else ""

def load_state_polygons(geojson_path: Path):
    data = json.loads(geojson_path.read_text(encoding="utf-8"))
    feats = data["features"] if isinstance(data, dict) and "features" in data else data
    out = {}
    for feat in feats:
        props = feat.get("properties", {}) or {}
        nm = props.get("name")
        if not nm: continue
        geom = shape(feat.get("geometry"))
        if isinstance(geom, Polygon):
            geom = MultiPolygon([geom])
        if not isinstance(geom, MultiPolygon):
            continue
        out[normalize_state_name(nm)] = geom
    return out

def polygon_state_of_point(point: Point, polygons: dict) -> str:
    for norm_nm, mp in polygons.items():
        if mp.covers(point):
            return norm_nm
    return ""

def parse_number(val):
    if val is None: return None
    if isinstance(val, (int, float)): return float(val)
    s = str(val).strip().replace(" ", "")
    if "," in s and "." in s: s = s.replace(".", "").replace(",", ".")
    else: s = s.replace(",", ".")
    try: return float(s)
    except Exception: return None

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
    if "wind"  in fn: return "Windenergie Onshore"
    if "wasser" in fn or "hydro" in fn: return "Wasserkraft"
    if "stromspeicher" in fn or "speicher" in fn or "battery" in fn: return "Stromspeicher (Battery Storage)"
    if "biogas" in fn: return "Biogas"
    return "Unknown"

def infer_kreis_from_row(row: pd.Series):
    for cand in ("Landkreis","landkreis","Kreis","kreis","kreis_name","county","County"):
        if cand in row and pd.notna(row[cand]):
            return str(row[cand]).strip()
    for cand in ("Gemeindeschluessel","gemeindeschluessel","AGS","ags","ags_id","rs"):
        if cand in row and pd.notna(row[cand]):
            s = re.sub(r"[^0-9]", "", str(row[cand]))
            if len(s) >= 5: return s[:5]
    return None

DATE_CANDIDATES = [
    "Inbetriebnahmedatum","inbetriebnahmedatum","Inbetriebnahme","commissioning_date",
    "CommissioningDate","Betriebsbeginn","Baujahr","year","Year","YEAR"
]
def extract_year(row: pd.Series, filename_hint="") -> int or None:
    for col in DATE_CANDIDATES:
        if col in row and pd.notna(row[col]):
            s = str(row[col]).strip()
            m = re.search(r"(19|20)\d{2}", s)
            if m:
                y = int(m.group(0))
                if 1900 <= y <= 2100: return y
            try:
                dt = pd.to_datetime(s, errors="coerce")
                if pd.notna(dt): return int(dt.year)
            except Exception:
                pass
    m = re.search(r"(19|20)\d{2}", filename_hint)
    if m:
        y = int(m.group(0))
        if 1900 <= y <= 2100: return y
    return None

def year_to_bin(y: int):
    if y is None: return ("unknown", "Unknown / NA")
    for slug, label, start, end in YEAR_BINS:
        if (start is None or y >= start) and (end is None or y <= end):
            return (slug, label)
    return ("unknown", "Unknown / NA")

def scan_geojsons(folder: Path):
    for root, _, fnames in os.walk(folder):
        for fn in fnames:
            if fn.lower().endswith(".geojson"):
                yield Path(root) / fn

def main():
    BASE_DIR.mkdir(parents=True, exist_ok=True)
    polygons = load_state_polygons(POLYGON_STATES_PATH)

    paths = list(scan_geojsons(INPUT_DIR))
    if not paths: 
        raise RuntimeError(f"No .geojson under {INPUT_DIR}")

    frames = []
    for p in paths:
        try:
            g = gpd.read_file(p)
            if g.empty or "geometry" not in g.columns: continue
            g = g[~g.geometry.is_empty & g.geometry.notnull()].copy()
            g = g[g.geometry.geom_type.isin(["Point","MultiPoint"])]
            if g.empty: continue
            try:
                if "MultiPoint" in g.geometry.geom_type.unique():
                    g = g.explode(index_parts=False).reset_index(drop=True)
            except TypeError:
                g = g.explode().reset_index(drop=True)

            g["kreis_name"] = g.apply(infer_kreis_from_row, axis=1)

            # energy + power
            if "energy_source_label" in g.columns:
                g["energy_norm"] = g["energy_source_label"].apply(lambda v: normalize_energy(v, p.name))
            elif "Energietraeger" in g.columns:
                g["energy_norm"] = g["Energietraeger"].apply(lambda v: normalize_energy(v, p.name))
            else:
                g["energy_norm"] = normalize_energy(None, p.name)

            power_col = None
            for c in ["power_kw","Nettonennleistung","Bruttoleistung","Nennleistung","Leistung","installed_power_kw","kw","power"]:
                if c in g.columns: power_col = c; break
            if power_col is None:
                print(f"[WARN] No power col in {p.name}; skipped."); continue
            g["_power"] = g[power_col].apply(lambda v: parse_number(v))

            # year + bin
            years = [extract_year(r, p.name) for _, r in g.iterrows()]
            g["_year"] = years
            bins  = [year_to_bin(y) for y in g["_year"]]
            g["year_bin_slug"]  = [b[0] for b in bins]
            g["year_bin_label"] = [b[1] for b in bins]

            # ---- 3-checks ----
            g["bl_norm"] = g.get("Bundesland", pd.Series([None]*len(g))).apply(bl_code_to_norm_name)
            g["gs_norm"] = g.get("Gemeindeschluessel", pd.Series([None]*len(g))).apply(gs_prefix_to_norm_name)
            pts = g.geometry.apply(lambda geom: Point(geom.x, geom.y))
            g["poly_norm"] = [polygon_state_of_point(pt, polygons) for pt in pts]

            # Use only consistent points
            g = g[
                (pd.notna(g["kreis_name"])) &
                (pd.notna(g["_power"])) & (g["_power"] > 0) &
                ((g["year_bin_slug"] != "unknown") | INCLUDE_UNKNOWN) &
                (g["poly_norm"] != "") & (g["bl_norm"] != "") & (g["gs_norm"] != "") &
                (g["poly_norm"] == g["bl_norm"]) & (g["bl_norm"] == g["gs_norm"])
            ].copy()
            if g.empty: 
                continue

            # state slug for foldering
            g["state_slug"] = g["poly_norm"].apply(lambda n: NORM_TO_SLUG.get(n, ""))
            frames.append(g[["kreis_name","state_slug","energy_norm","_power","year_bin_slug","year_bin_label","geometry"]])
        except Exception as e:
            print(f"[WARN] Skipped {p.name}: {e}")

    if not frames:
        raise RuntimeError("No usable features after 3-checks.")

    df = pd.concat(frames, ignore_index=True)

    # Aggregate per (Landkreis, year_bin) — but we will write per state inside each bin folder
    by_bin = {}
    for (kreis, yslug), grp in df.groupby(["kreis_name","year_bin_slug"]):
        label = grp["year_bin_label"].iloc[0]
        totals = {f: 0.0 for f in PRIORITY_FIELDNAMES.values()}
        others = 0.0
        for _, r in grp.iterrows():
            cat = r["energy_norm"]; pkw = float(r["_power"])
            if cat in PRIORITY_FIELDNAMES: totals[PRIORITY_FIELDNAMES[cat]] += pkw
            else: others += pkw
        totals[OTHERS_FIELD] = others
        totals["total_kw"]   = sum(totals.values())
        totals["kreis_name"] = str(kreis)
        # anchor
        xs = grp.geometry.x.astype(float); ys = grp.geometry.y.astype(float)
        totals["_x"], totals["_y"] = xs.mean(), ys.mean()
        totals["year_bin_slug"]   = yslug
        totals["year_bin_label"]  = label
        # carry the dominant state slug of this Landkreis in this bin
        st = grp["state_slug"].dropna()
        totals["state_slug"] = (st.mode().iloc[0] if len(st) else "")
        by_bin.setdefault(yslug, []).append(totals)

    # Write per-bin, per-state points and per-bin meta (for consistent scaling within the bin)
    for slug, label, *_ in YEAR_BINS:
        rows = by_bin.get(slug, [])
        if not rows: 
            continue
        # to GeoDataFrame
        gdf = gpd.GeoDataFrame(rows,
               geometry=[Point(t["_x"], t["_y"]) for t in rows], crs="EPSG:4326").drop(columns=["_x","_y"])

        # per-bin min/max for scaling in step3_4
        vmin = float(gdf["total_kw"].min()); vmax = float(gdf["total_kw"].max())
        bin_dir = BASE_DIR / slug
        bin_dir.mkdir(parents=True, exist_ok=True)
        (bin_dir / f"landkreis_pie_style_meta_{slug}.json").write_text(
            json.dumps({
                "min_total_kw": vmin, "max_total_kw": vmax,
                "priority_fields": list(PRIORITY_FIELDNAMES.values()),
                "others_field": OTHERS_FIELD, "name_field": "kreis_name",
                "year_bin": BIN_LABEL[slug]
            }, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )

        # write per-state files under <bin>/<state-slug>/
        valid = gdf[gdf["state_slug"].notna() & (gdf["state_slug"] != "")]
        for st_slug, sub in valid.groupby("state_slug"):
            tgt = bin_dir / st_slug
            tgt.mkdir(parents=True, exist_ok=True)
            out_pts = tgt / f"de_{st_slug}_landkreis_pies_{slug}.geojson"
            sub.drop(columns=[], errors="ignore").to_file(out_pts, driver="GeoJSON")
            print(f"[OK] wrote {out_pts}")

    print("Done.")

if __name__ == "__main__":
    main()
