# make_state_pie_inputs.py
# Build a state-level pie input layer (one point per Bundesland) from GeoJSONs.
# Uses 'Bundesland' numeric codes for state names; city-states are fixed anchors.

import os, re, unicodedata, math, json
from pathlib import Path
import geopandas as gpd
import pandas as pd
from shapely.geometry import Point

# -------- SETTINGS --------
INPUT_DIR  = r"C:\Users\jo73vure\Desktop\powerPlantProject\data\geojson\by_state_three_checks"
OUTPUT_DIR = r"C:\Users\jo73vure\Desktop\powerPlantProject\data\geojson\pieCharts\state_pies"

ENERGY_FIELD = "energy_source_label"   # preferred energy label field if present
STATE_FIELD  = None                    # set if explicit (e.g., "BundeslandName")

# Separation parameters (approx. kilometers)
MIN_SEPARATION_KM = 50.0
MAX_SEP_ITER = 80

# City-states fixed at known anchors (lon, lat)
LOCKED_STATES = {"Berlin", "Hamburg", "Bremen", "Niedersachsen"}
FIXED_ANCHORS = {
    "Berlin":  (13.404954, 52.520008),
    "Hamburg": ( 9.993682, 53.551086),
    "Bremen":  ( 8.801694, 53.079296),
    "Niedersachsen": ( 9.732010, 52.636878)
}
# --------------------------

# Bundesland code -> official name
BUNDESLAND_CODES = {
    "1400": "Brandenburg",
    "1401": "Berlin",
    "1402": "Baden-Württemberg",
    "1403": "Bayern",
    "1404": "Bremen",
    "1405": "Hessen",
    "1406": "Hamburg",
    "1407": "Mecklenburg-Vorpommern",
    "1408": "Niedersachsen",
    "1409": "Nordrhein-Westfalen",
    "1410": "Rheinland-Pfalz",
    "1411": "Schleswig-Holstein",
    "1412": "Saarland",
    "1413": "Sachsen",
    "1414": "Sachsen-Anhalt",
    "1415": "Thüringen",
}

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

STATE_PREFIXES = {
    "01":"Schleswig-Holstein","02":"Hamburg","03":"Niedersachsen","04":"Bremen","05":"Nordrhein-Westfalen",
    "06":"Hessen","07":"Rheinland-Pfalz","08":"Baden-Württemberg","09":"Bayern","10":"Saarland","11":"Berlin",
    "12":"Brandenburg","13":"Mecklenburg-Vorpommern","14":"Sachsen","15":"Sachsen-Anhalt","16":"Thüringen"
}
CITY_STATES = {"Berlin","Hamburg","Bremen"}

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

def map_bundesland_code(val) -> str:
    """Return state name from 'Bundesland' code if possible."""
    if val is None: return None
    s = str(val).strip()
    # Some files may have integer like 1406 -> cast to string
    if s.isdigit():
        return BUNDESLAND_CODES.get(s)
    # Occasionally stored with decimals like '1406.0'
    s2 = s.split(".")[0] if s.replace(".", "", 1).isdigit() else s
    return BUNDESLAND_CODES.get(s2)

def infer_state_from_row(row: pd.Series):
    # 1) explicit name field
    if STATE_FIELD and STATE_FIELD in row and pd.notna(row[STATE_FIELD]):
        return str(row[STATE_FIELD]).strip()

    # 2) Bundesland numeric code
    for cand in ("Bundesland", "bundesland", "BUNDESLAND"):
        if cand in row and pd.notna(row[cand]):
            mapped = map_bundesland_code(row[cand])
            if mapped:
                return mapped

    # 3) already-textual state-like fields
    for cand in ("state","State","STATE","BundeslandName"):
        if cand in row and pd.notna(row[cand]):
            val = str(row[cand]).strip()
            if not val.isdigit():
                return val

    # 4) city-state hint in other fields
    for cand in ("Landkreis","Gemeinde","Ort"):
        if cand in row and pd.notna(row[cand]):
            v = str(row[cand]).strip()
            if v in CITY_STATES: return v

    # 5) fallback via municipality code prefix (AGS)
    for cand in ("Gemeindeschluessel","gemeindeschluessel","AGS","ags","ags_id"):
        if cand in row and pd.notna(row[cand]):
            s = str(row[cand]).strip()
            if len(s) >= 2 and s[:2].isdigit():
                st = STATE_PREFIXES.get(s[:2])
                if st: return st
    return None

def infer_state_from_path(p: Path):
    # Keep as a last resort (not needed if Bundesland codes exist)
    for seg in p.parts:
        slug = normalize_text(seg).replace(" ", "-")
        # (we intentionally don't rely on slugs anymore)
        if slug in ["berlin","hamburg","bremen","bayern","baden-wuerttemberg","baden-württemberg",
                    "niedersachsen","hessen","saarland","brandenburg","mecklenburg-vorpommern",
                    "sachsen","sachsen-anhalt","rheinland-pfalz","schleswig-holstein","thueringen","thuringen","thüringen"]:
            # map common slugs to proper names
            for k, v in BUNDESLAND_CODES.items():
                if normalize_text(v).replace(" ", "-") == slug:
                    return v
            if slug in ("thueringen","thuringen","thüringen"):
                return "Thüringen"
    return None

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

def sep_one_step(points, min_km, locked_states):
    """Push points apart until every pair >= min_km. points: list of dicts with {'x','y','state'}."""
    changed = False
    for i in range(len(points)):
        for j in range(i+1, len(points)):
            pi, pj = points[i], points[j]
            lat = (pi['y'] + pj['y']) / 2.0
            km_lat = 111.32
            km_lon = 111.32 * math.cos(math.radians(lat))
            dx = (pj['x'] - pi['x']) * km_lon
            dy = (pj['y'] - pi['y']) * km_lat
            d = math.hypot(dx, dy)
            if d < 1e-6:
                ang = 2*math.pi * (i+1)/(len(points)+1)
                pj['x'] += (math.cos(ang)*0.05)/km_lon
                pj['y'] += (math.sin(ang)*0.05)/km_lat
                changed = True
                continue
            if d < min_km:
                push = (min_km - d)
                ux, uy = dx/d, dy/d
                i_locked = pi['state'] in locked_states
                j_locked = pj['state'] in locked_states
                if i_locked and j_locked:
                    continue
                elif i_locked and not j_locked:
                    pj['x'] += (ux * push) / km_lon
                    pj['y'] += (uy * push) / km_lat
                elif j_locked and not i_locked:
                    pi['x'] -= (ux * push) / km_lon
                    pi['y'] -= (uy * push) / km_lat
                else:
                    shift_lon = (ux * (push/2)) / km_lon
                    shift_lat = (uy * (push/2)) / km_lat
                    pi['x'] -= shift_lon; pi['y'] -= shift_lat
                    pj['x'] += shift_lon; pj['y'] += shift_lat
                changed = True
    return changed

def main():
    outdir = Path(OUTPUT_DIR); outdir.mkdir(parents=True, exist_ok=True)
    paths = list(scan_geojsons(INPUT_DIR))
    print(f"Found {len(paths)} GeoJSON files under: {INPUT_DIR}")
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

            # state (prefer Bundesland code if present)
            if "state_name" not in g.columns:
                g["state_name"] = None
            g["state_name"] = g.apply(lambda r: infer_state_from_row(r) or infer_state_from_path(p), axis=1)

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

            g = g[(pd.notna(g["state_name"])) & (pd.notna(g["_power"])) & (g["_power"] > 0)]
            if g.empty:
                print(f"[WARN] No positive power rows after parsing in {p.name}; skipped.")
                continue

            frames.append(g[["state_name","energy_norm","_power","geometry"]])
        except Exception as e:
            print(f"[WARN] Skipped {p}: {e}")

    if not frames:
        raise RuntimeError("No usable point features found across GeoJSON files.")

    plants = pd.concat(frames, ignore_index=True)

    # aggregate per state
    rows = []
    for state, grp in plants.groupby("state_name"):
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
        totals["state_name"] = state

        # anchor: fixed for city-states, else mean of points
        if state in FIXED_ANCHORS:
            ax, ay = FIXED_ANCHORS[state]
        else:
            ax = float(grp.geometry.x.mean())
            ay = float(grp.geometry.y.mean())
        totals["_x"] = ax; totals["_y"] = ay
        rows.append(totals)

    agg = pd.DataFrame(rows)

    # collision avoidance (locked states never move)
    pts = [{"x": float(x), "y": float(y), "state": s}
           for x, y, s in zip(agg["_x"], agg["_y"], agg["state_name"])]
    for _ in range(MAX_SEP_ITER):
        if not sep_one_step(pts, MIN_SEPARATION_KM, LOCKED_STATES):
            break
    agg["_x"] = [p["x"] for p in pts]; agg["_y"] = [p["y"] for p in pts]

    # write output points
    agg["geometry"] = [Point(xy) for xy in zip(agg["_x"], agg["_y"])]
    gdf = gpd.GeoDataFrame(agg.drop(columns=["_x","_y"]), geometry="geometry", crs="EPSG:4326")

    vmin = float(gdf["total_kw"].min()) if len(gdf) else 0.0
    vmax = float(gdf["total_kw"].max()) if len(gdf) else 1.0

    out_geojson = Path(OUTPUT_DIR) / "de_state_pies.geojson"
    gdf.to_file(out_geojson, driver="GeoJSON")

    meta = {
        "min_total_kw": vmin,
        "max_total_kw": vmax,
        "priority_fields": list(PRIORITY_FIELDNAMES.values()),
        "others_field": OTHERS_FIELD,
        "name_field": "state_name"
    }
    (Path(OUTPUT_DIR) / "state_pie_style_meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(f"Created: {out_geojson}")
    print(f"Saved:   {Path(OUTPUT_DIR) / 'state_pie_style_meta.json'}")

if __name__ == "__main__":
    main()
