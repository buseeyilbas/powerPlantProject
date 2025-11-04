"""
Build nationwide + per-state Landkreis pie INPUT POINTS with strict 3-check assignment.

Logic:
- Read raw plant points (by_landkreis/**/*.geojson).
- For each point, apply "triple consistency" like step15:
    polygon_state == Bundesland_code == AGS_prefix  (all must agree)
- Keep only consistent points.
- Aggregate to one point per Landkreis:
    pv_kw, wind_kw, hydro_kw, battery_kw, biogas_kw, others_kw, total_kw
    anchor = mean of consistent point coordinates
- Write nationwide points + meta (min/max).
- Also write per-state points under:
  ...\pieCharts\nationwide_landkreis_pies\<state-slug>\de_<state-slug>_landkreis_pies.geojson
"""

from pathlib import Path
import os, re, json, unicodedata
import geopandas as gpd
import pandas as pd
from shapely.geometry import Point, shape, MultiPolygon, Polygon

# -------- PATHS --------
INPUT_DIR  = r"C:\Users\jo73vure\Desktop\powerPlantProject\data\geojson\by_landkreis"
OUTPUT_DIR = r"C:\Users\jo73vure\Desktop\powerPlantProject\data\geojson\pieCharts\nationwide_landkreis_pies"
POLYGON_STATES_PATH = r"C:\Users\jo73vure\Desktop\powerPlantProject\data\polygon_states.json"  # properties.name

# -------- ENERGY MAPS --------
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

# --- Bundesland code (1400..1415) -> canonical name (normalized) like step15 ---
BUNDESLAND_CODE_TO_NAME = {
    "1400": "brandenburg",
    "1401": "berlin",
    "1402": "baden_wuerttemberg",
    "1403": "bayern",
    "1404": "bremen",
    "1405": "hessen",
    "1406": "hamburg",
    "1407": "mecklenburg_vorpommern",
    "1408": "niedersachsen",
    "1409": "nordrhein_westfalen",
    "1410": "rheinland_pfalz",
    "1411": "schleswig_holstein",
    "1412": "saarland",
    "1413": "sachsen",
    "1414": "sachsen_anhalt",
    "1415": "thueringen",
}

# --- AGS 2-digit prefix -> canonical name (normalized) like step15 ---
GS_PREFIX_TO_NAME = {
    "01": "schleswig_holstein",
    "02": "hamburg",
    "03": "niedersachsen",
    "04": "bremen",
    "05": "nordrhein_westfalen",
    "06": "hessen",
    "07": "rheinland_pfalz",
    "08": "baden_wuerttemberg",
    "09": "bayern",
    "10": "saarland",
    "11": "berlin",
    "12": "brandenburg",
    "13": "mecklenburg_vorpommern",
    "14": "sachsen",
    "15": "sachsen_anhalt",
    "16": "thueringen",
}

# normalized name -> folder slug (hyphenated)
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

def normalize_state_name(name: str) -> str:
    if not isinstance(name, str): return ""
    s = name.lower()
    s = (s.replace("ä","ae").replace("ö","oe").replace("ü","ue").replace("ß","ss"))
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

def load_state_polygons(geojson_path: str):
    data = json.loads(Path(geojson_path).read_text(encoding="utf-8"))
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
    # use 'covers' to include boundary points
    for norm_nm, mp in polygons.items():
        if mp.covers(point):
            return norm_nm
    return ""

def normalize_text(s: str) -> str:
    if s is None: return ""
    s = unicodedata.normalize("NFKD", str(s))
    s = "".join(ch for ch in s if not unicodedata.combining(ch)).lower()
    return re.sub(r"[^a-z0-9]+", " ", s).strip()

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

def parse_number(val):
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

def infer_kreis_name(row: pd.Series):
    for cand in ("Landkreis","landkreis","Kreis","kreis","kreis_name","county","County","NAME"):
        if cand in row and pd.notna(row[cand]):
            return str(row[cand]).strip()
    # fallback to code if nothing else
    for cand in ("Gemeindeschluessel","gemeindeschluessel","AGS","ags","ags_id"):
        if cand in row and pd.notna(row[cand]):
            s = re.sub(r"[^0-9]", "", str(row[cand]))
            if len(s) >= 5:
                return s[:5]
    return None

def first_power_column(cols):
    candidates = ["power_kw","Nettonennleistung","Bruttoleistung","Nennleistung","Leistung","installed_power_kw","kw","power"]
    for c in candidates:
        if c in cols: return c
    lc = {normalize_text(c): c for c in cols}
    for key in ["nettonennleistung","bruttoleistung","nennleistung","leistung","power","kw"]:
        for k, orig in lc.items():
            if key in k: return orig
    return None

def scan_geojsons(folder: str):
    for root, _, files in os.walk(folder):
        for fn in files:
            if Path(fn).suffix.lower() == ".geojson":
                yield Path(root) / fn

def main():
    in_dir = Path(INPUT_DIR)
    out_dir = Path(OUTPUT_DIR)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Load state polygons once (for the polygon leg of the 3-checks)
    polygons = load_state_polygons(POLYGON_STATES_PATH)

    paths = list(scan_geojsons(str(in_dir)))
    if not paths:
        raise RuntimeError("No .geojson files found in INPUT_DIR.")

    rows = []
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

            # energy + power
            if "energy_source_label" in g.columns:
                g["energy_norm"] = g["energy_source_label"].apply(lambda v: normalize_energy(v, p.name))
            elif "Energietraeger" in g.columns:
                g["energy_norm"] = g["Energietraeger"].apply(lambda v: normalize_energy(v, p.name))
            else:
                g["energy_norm"] = normalize_energy(None, p.name)

            power_col = first_power_column(g.columns)
            if power_col is None:
                print(f"[WARN] No power field in {p.name}; skipped.")
                continue
            g["_power"] = g[power_col].apply(parse_number)

            # kreis + codes
            g["kreis_name"] = g.apply(infer_kreis_name, axis=1)
            g["bl_norm"] = g.get("Bundesland", pd.Series([None]*len(g))).apply(bl_code_to_norm_name)
            g["gs_norm"] = g.get("Gemeindeschluessel", pd.Series([None]*len(g))).apply(gs_prefix_to_norm_name)

            # polygon state
            pts = g.geometry.apply(lambda geom: Point(geom.x, geom.y))
            g["poly_norm"] = [polygon_state_of_point(pt, polygons) for pt in pts]

            # keep strictly consistent
            sel = g[
                (g["_power"].notna()) & (g["_power"] > 0) &
                (g["kreis_name"].notna()) &
                (g["poly_norm"] != "") & (g["bl_norm"] != "") & (g["gs_norm"] != "") &
                (g["poly_norm"] == g["bl_norm"]) & (g["bl_norm"] == g["gs_norm"])
            ].copy()
            if sel.empty:
                continue

            # state slug from normalized name
            sel["state_slug"] = sel["poly_norm"].apply(lambda n: NORM_TO_SLUG.get(n, ""))

            rows.append(sel[["kreis_name","state_slug","energy_norm","_power","geometry"]])
        except Exception as e:
            print(f"[WARN] Skipped {p.name}: {e}")

    if not rows:
        raise RuntimeError("No consistent points after 3-checks. Verify inputs and polygon_states.json.")

    plants = pd.concat(rows, ignore_index=True)

    # aggregate per Landkreis
    out_recs = []
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
        totals["state_slug"] = grp["state_slug"].dropna().mode().iloc[0] if grp["state_slug"].notna().any() else ""
        # anchor = mean
        ax = float(grp.geometry.x.mean()); ay = float(grp.geometry.y.mean())
        totals["_x"] = ax; totals["_y"] = ay
        out_recs.append(totals)

    agg = pd.DataFrame(out_recs)
    agg["geometry"] = [Point(xy) for xy in zip(agg["_x"], agg["_y"])]
    gdf = gpd.GeoDataFrame(agg.drop(columns=["_x","_y"]), geometry="geometry", crs="EPSG:4326")

    # meta for nationwide scaling
    vmin = float(gdf["total_kw"].min()) if len(gdf) else 0.0
    vmax = float(gdf["total_kw"].max()) if len(gdf) else 1.0

    # write nationwide
    out_dir.mkdir(parents=True, exist_ok=True)
    nationwide_pts = Path(OUTPUT_DIR) / "de_landkreis_pies.geojson"
    gdf.to_file(nationwide_pts, driver="GeoJSON")
    meta = {
        "min_total_kw": vmin,
        "max_total_kw": vmax,
        "priority_fields": list(PRIORITY_FIELDNAMES.values()),
        "others_field": OTHERS_FIELD,
        "name_field": "kreis_name"
    }
    (Path(OUTPUT_DIR) / "landkreis_pie_style_meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"[OK] nationwide points -> {nationwide_pts}")

    # write per-state folders/files
    for slug, sub in gdf[gdf["state_slug"] != ""].groupby("state_slug"):
        tgt_dir = Path(OUTPUT_DIR) / slug
        tgt_dir.mkdir(parents=True, exist_ok=True)
        sub.to_file(tgt_dir / f"de_{slug}_landkreis_pies.geojson", driver="GeoJSON")
        print(f"[OK] per-state points -> {slug}\\de_{slug}_landkreis_pies.geojson")

if __name__ == "__main__":
    main()
