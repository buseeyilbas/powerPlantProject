# Build county (Landkreis) totals per state from by_state_landkreis/*/*.geojson
# DEDUPE: one pie per Landkreis. Key is derived from filename BASE (energy tag stripped),
# with AGS5 appended if available. This prevents "multiple pies per Landkreis" explosions.

from pathlib import Path
import os, re, unicodedata, json, collections
import geopandas as gpd
import pandas as pd
from shapely.geometry import Point

INPUT_ROOT = Path(r"C:\Users\jo73vure\Desktop\powerPlantProject\data\geojson\by_state_landkreis")
OUTPUT_DIR = Path(r"C:\Users\jo73vure\Desktop\powerPlantProject\data\geojson\pieCharts\statewise_landkreis_pies")

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

STATE_SLUG_TO_OFFICIAL = {
    "baden-wuerttemberg": "Baden-Württemberg", "baden-württemberg": "Baden-Württemberg",
    "bayern": "Bayern", "berlin": "Berlin", "brandenburg": "Brandenburg", "bremen": "Bremen",
    "hamburg": "Hamburg", "hessen": "Hessen", "mecklenburg-vorpommern": "Mecklenburg-Vorpommern",
    "niedersachsen": "Niedersachsen", "nordrhein-westfalen": "Nordrhein-Westfalen",
    "rheinland-pfalz": "Rheinland-Pfalz", "saarland": "Saarland",
    "sachsen": "Sachsen", "sachsen-anhalt": "Sachsen-Anhalt",
    "schleswig-holstein": "Schleswig-Holstein",
    "thueringen": "Thüringen", "thüringen": "Thüringen", "thuringen": "Thüringen",
}

NAME_FIELDS = ("Landkreis","landkreis","Kreis","kreis","kreis_name","Landkreisname","landkreisname")

ENERGY_TOKENS = {
    "pv","photovoltaik","solar","wind","wasser","hydro","biogas","stromspeicher","speicher","battery","others"
}

def normalize_text(s: str) -> str:
    if s is None: return ""
    s = unicodedata.normalize("NFKD", str(s))
    s = "".join(ch for ch in s if not unicodedata.combining(ch)).lower()
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")

def kreis_base_from_stem(stem: str) -> str:
    """Strip energy tokens and numeric tails from file stem to get a stable Landkreis base."""
    s = normalize_text(stem)
    parts = [p for p in s.split("-") if p and p not in ENERGY_TOKENS and not p.isdigit()]
    # drop common "einheiten/anlagen" noise
    parts = [p for p in parts if p not in {"einheiten","anlagen","eeg","kwk"}]
    return "-".join(parts) or s

def clean_kreis_label(name: str) -> str:
    if not name: return ""
    s = str(name).strip()
    low = s.lower()
    for rep in ["kreisfreie stadt","landkreis","stadtkreis","kreis"]:
        low = low.replace(rep, " ")
    low = re.sub(r"-?kreis\b", " ", low)
    low = re.sub(r"\s+", " ", low).strip()
    return " ".join(w.capitalize() for w in low.split())

def extract_ags5(row: pd.Series):
    for cand in ("Gemeindeschluessel","gemeindeschluessel","AGS","ags","ags_id","kreisschluessel","rs"):
        if cand in row and pd.notna(row[cand]):
            digits = re.sub(r"[^0-9]", "", str(row[cand]))
            if len(digits) >= 5:
                return digits[:5]
    return None

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
    if "wind" in fn: return "Windenergie Onshore"
    if "wasser" in fn or "hydro" in fn: return "Wasserkraft"
    if "stromspeicher" in fn or "speicher" in fn or "battery" in fn: return "Stromspeicher (Battery Storage)"
    if "biogas" in fn: return "Biogas"
    return "Unknown"

def scan_geojsons(folder: Path):
    for root, _, files in os.walk(folder):
        for fn in files:
            if fn.lower().endswith(".geojson"):
                yield Path(root) / fn

def first_power_column(cols):
    prefs = ["power_kw","Nettonennleistung","Bruttoleistung","Nennleistung","Leistung",
             "installed_power_kw","kw","power"]
    for c in prefs:
        if c in cols: return c
    lc = {normalize_text(c): c for c in cols}
    for key in ["nettonennleistung","bruttoleistung","nennleistung","leistung","power","kw"]:
        for k, orig in lc.items():
            if key in k: return orig
    return None

def choose_label(labels):
    labels = [l for l in labels if l]
    if not labels: return ""
    cnt = collections.Counter(labels)
    top_n = cnt.most_common(1)[0][1]
    cands = [l for l, n in cnt.items() if n == top_n]
    return max(cands, key=len)

def process_state(state_dir: Path):
    slug = normalize_text(state_dir.name)
    state_name = STATE_SLUG_TO_OFFICIAL.get(slug, state_dir.name)

    paths = list(scan_geojsons(state_dir))
    if not paths:
        print(f"[WARN] no .geojson under: {state_dir}")
        return

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

            # file-level base + per-row AGS (mode later)
            base = kreis_base_from_stem(p.stem)
            g["kreis_base"] = base

            # candidate label from attributes
            labels = []
            for _, r in g.iterrows():
                lab = None
                for nm in NAME_FIELDS:
                    if nm in r and pd.notna(r[nm]):
                        lab = clean_kreis_label(r[nm]); break
                labels.append(lab)
            g["kreis_label"] = labels

            # energy + power
            if "energy_source_label" in g.columns:
                g["energy_norm"] = g["energy_source_label"].apply(lambda v: normalize_energy(v, p.name))
            elif "Energietraeger" in g.columns:
                g["energy_norm"] = g["Energietraeger"].apply(lambda v: normalize_energy(v, p.name))
            else:
                g["energy_norm"] = normalize_energy(None, p.name)

            power_col = first_power_column(g.columns)
            if not power_col:
                print(f"[WARN] no power field in {p.name}; skipped.")
                continue
            g["_power"] = g[power_col].apply(parse_number)
            g = g[(pd.notna(g["_power"])) & (g["_power"] > 0)]
            if g.empty: continue

            # AGS5 (mode across rows)
            ags = [extract_ags5(r) for _, r in g.iterrows()]
            ags = [a for a in ags if a]
            ags5 = collections.Counter(ags).most_common(1)[0][0] if ags else None
            g["ags5"] = ags5

            g["state_name"] = state_name
            frames.append(g[["state_name","kreis_base","ags5","kreis_label","energy_norm","_power","geometry"]])
        except Exception as e:
            print(f"[WARN] skipped {p}: {e}")

    if not frames:
        print(f"[WARN] no usable features for state {state_name}")
        return

    plants = pd.concat(frames, ignore_index=True)

    # aggregate per (base, ags5)
    rows = []
    for (base, ags5), grp in plants.groupby(["kreis_base","ags5"], dropna=False):
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
        totals["state_name"] = state_name
        # key and display name
        totals["kreis_key"] = f"{base}|{ags5}" if ags5 else base
        totals["kreis_name"] = choose_label(grp["kreis_label"].tolist()) or " ".join(w.capitalize() for w in base.split("-"))
        # anchor
        xs = grp.geometry.x.astype(float); ys = grp.geometry.y.astype(float)
        totals["_x"], totals["_y"] = xs.mean(), ys.mean()
        rows.append(totals)

    agg = pd.DataFrame(rows)
    agg["geometry"] = [Point(xy) for xy in zip(agg["_x"], agg["_y"])]
    gdf = gpd.GeoDataFrame(agg.drop(columns=["_x","_y"]), geometry="geometry", crs="EPSG:4326")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_pts = OUTPUT_DIR / f"de_{slug}_landkreis_pies.geojson"  # points (plural)
    gdf.to_file(out_pts, driver="GeoJSON")

    vmin = float(gdf["total_kw"].min()) if len(gdf) else 0.0
    vmax = float(gdf["total_kw"].max()) if len(gdf) else 1.0
    meta = {
        "min_total_kw": vmin,
        "max_total_kw": vmax,
        "priority_fields": list(PRIORITY_FIELDNAMES.values()),
        "others_field": OTHERS_FIELD,
        "name_field": "kreis_name"
    }
    (OUTPUT_DIR / f"{slug}_landkreis_pie_style_meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"[OK] {state_name}: wrote {out_pts.name} (unique kreise={len(gdf)})")

def main():
    if not INPUT_ROOT.exists():
        raise RuntimeError(f"INPUT_ROOT not found: {INPUT_ROOT}")
    for item in sorted(INPUT_ROOT.iterdir()):
        if item.is_dir():
            process_state(item)

if __name__ == "__main__":
    main()
