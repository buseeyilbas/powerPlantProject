# Filename: step2_1_make_statewise_landkreis_pie_inputs.py
# Purpose :
#   Build non-yearly LANDKREIS pie INPUT POINTS per state,
#   using the SINGLE AGS-based center set from step2_0.
#
#   Input:
#       - by_state_landkreis/*/*.geojson
#       - pieCharts/landkreis_centers/de_landkreis_centers.geojson
#
#   Output:
#       - pieCharts/statewise_landkreis_pies/de_<state_slug>_landkreis_pies.geojson
#       - pieCharts/statewise_landkreis_pies/<state_slug>_landkreis_pie_style_meta.json

from pathlib import Path
import os
import re
import unicodedata
import json
import collections

import geopandas as gpd
import pandas as pd
from shapely.geometry import Point

# ------------------------------ PATHS ------------------------------

INPUT_ROOT = Path(
    r"C:\Users\jo73vure\Desktop\powerPlantProject\data\geojson\by_state_landkreis"
)

OUTPUT_DIR = Path(
    r"C:\Users\jo73vure\Desktop\powerPlantProject\data\geojson\pieCharts\statewise_landkreis_pies"
)

CENTERS_PATH = Path(
    r"C:\Users\jo73vure\Desktop\powerPlantProject\data\geojson\pieCharts\landkreis_centers\de_landkreis_centers.geojson"
)

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

NAME_FIELDS = (
    "Landkreis",
    "landkreis",
    "Kreis",
    "kreis",
    "kreis_name",
    "Landkreisname",
    "landkreisname",
    "GEN",
)


# ------------------------------ HELPERS ------------------------------


def norm(s: str) -> str:
    if s is None:
        return ""
    s = unicodedata.normalize("NFKD", str(s))
    s = "".join(ch for ch in s if not unicodedata.combining(ch)).lower()
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")


def clean_kreis_label(name: str) -> str:
    if not name:
        return ""
    s = str(name).strip()
    low = s.lower()
    for rep in ["kreisfreie stadt", "landkreis", "stadtkreis", "kreis"]:
        low = low.replace(rep, " ")
    low = re.sub(r"-?kreis\b", " ", low)
    low = re.sub(r"\s+", " ", low).strip()
    return " ".join(w.capitalize() for w in low.split())


def extract_ags5(row: pd.Series):
    for cand in (
        "Gemeindeschluessel",
        "gemeindeschluessel",
        "AGS",
        "ags",
        "ags_id",
        "kreisschluessel",
        "rs",
    ):
        if cand in row and pd.notna(row[cand]):
            digits = re.sub(r"[^0-9]", "", str(row[cand]))
            if len(digits) >= 5:
                return digits[:5]
    return None


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


def normalize_energy(val, filename_hint="") -> str:
    if val is not None:
        s = str(val).strip()
        if s in ENERGY_CODE_TO_LABEL:
            return ENERGY_CODE_TO_LABEL[s]
        sn = norm(s)
        if "solar" in sn or "photovoltaik" in sn or sn == "pv":
            return "Photovoltaik"
        if "wind" in sn:
            return "Windenergie Onshore"
        if "wasser" in sn or "hydro" in sn:
            return "Wasserkraft"
        if "stromspeicher" in sn or "speicher" in sn or "battery" in sn:
            return "Stromspeicher (Battery Storage)"
        if "biogas" in sn or sn == "gas":
            return "Biogas"

    fn = norm(filename_hint)
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


def scan_geojsons(folder: Path):
    for root, _, files in os.walk(folder):
        for fn in files:
            if fn.lower().endswith(".geojson"):
                yield Path(root) / fn


def first_power_column(cols):
    prefs = [
        "power_kw",
        "Nettonennleistung",
        "Bruttoleistung",
        "Nennleistung",
        "Leistung",
        "installed_power_kw",
        "kw",
        "power",
    ]
    for c in prefs:
        if c in cols:
            return c
    lc = {norm(c): c for c in cols}
    for key in [
        "nettonennleistung",
        "bruttoleistung",
        "nennleistung",
        "leistung",
        "power",
        "kw",
    ]:
        for k, orig in lc.items():
            if key in k:
                return orig
    return None


def choose_label(labels):
    labels = [l for l in labels if l]
    if not labels:
        return ""
    cnt = collections.Counter(labels)
    top_n = cnt.most_common(1)[0][1]
    cands = [l for l, n in cnt.items() if n == top_n]
    return max(cands, key=len)


# ------------------------------ LOAD CENTERS ------------------------------


def load_centers():
    if not CENTERS_PATH.exists():
        raise RuntimeError(f"Centers file not found: {CENTERS_PATH}")

    g = gpd.read_file(CENTERS_PATH)
    if g.crs is None:
        g = g.set_crs("EPSG:4326", allow_override=True)

    centers_by_ags = {}
    state_by_ags = {}
    name_by_ags = {}

    for _, r in g.iterrows():
        ags = str(r.get("ags5", "")).strip()
        if not ags:
            continue
        centers_by_ags[ags] = (float(r.geometry.x), float(r.geometry.y))
        state_by_ags[ags] = str(r.get("state_slug", "")).strip()
        name_by_ags[ags] = str(r.get("kreis_name", ags)).strip()

    print(
        f"[CENTERS] Loaded {len(centers_by_ags)} Landkreis centers from {CENTERS_PATH}"
    )
    return centers_by_ags, state_by_ags, name_by_ags


# ------------------------------ PROCESS STATELESS (AGS-BASED) ------------------------------


def main():
    print("\n[step2_1] Building statewise Landkreis pie INPUTS (non-yearly).")

    if not INPUT_ROOT.exists():
        raise RuntimeError(f"INPUT_ROOT not found: {INPUT_ROOT}")

    centers_by_ags, state_by_ags, name_by_ags = load_centers()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    rows = []

    # We process all state dirs, but the real "state_slug" comes from centers_by_ags.
    for state_dir in sorted(INPUT_ROOT.iterdir()):
        if not state_dir.is_dir():
            continue

        print(f"\n-- SCAN STATE DIR: {state_dir.name} --")
        for p in scan_geojsons(state_dir):
            try:
                g = gpd.read_file(p)
            except Exception as e:
                print(f"  [WARN] skipped {p.name}: {e}")
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

            filename = p.name

            # energy
            if "energy_source_label" in g.columns:
                g["energy_norm"] = g["energy_source_label"].apply(
                    lambda v: normalize_energy(v, filename)
                )
            elif "Energietraeger" in g.columns:
                g["energy_norm"] = g["Energietraeger"].apply(
                    lambda v: normalize_energy(v, filename)
                )
            else:
                g["energy_norm"] = normalize_energy(None, filename)

            # power
            power_col = first_power_column(g.columns)
            if not power_col:
                print(f"  [WARN] no power field in {p.name}; skipped.")
                continue

            g["_power"] = g[power_col].apply(parse_number)
            g = g[(pd.notna(g["_power"])) & (g["_power"] > 0)]
            if g.empty:
                continue

            # AGS and label
            for _, r in g.iterrows():
                ags5 = extract_ags5(r)
                if not ags5:
                    continue
                if ags5 not in centers_by_ags:
                    # AGS we do not have a center for → skip
                    continue

                center_state = state_by_ags.get(ags5, "")
                kreis_name = name_by_ags.get(ags5, ags5)

                # attribute-based label fallback if available
                for nm in NAME_FIELDS:
                    if nm in r and pd.notna(r[nm]):
                        kreis_name = clean_kreis_label(r[nm])
                        break

                rows.append(
                    {
                        "state_slug": center_state,
                        "kreis_key": ags5,
                        "kreis_name": kreis_name,
                        "energy_norm": r["energy_norm"],
                        "_power": float(r["_power"]),
                    }
                )

    if not rows:
        print("[FATAL] No usable rows. Nothing to write.")
        return

    df = pd.DataFrame(rows)

    # ---------------- AGGREGATE PER (STATE, KREIS) ----------------
    grouped = []
    for (state_slug, kreis_key), grp in df.groupby(
        ["state_slug", "kreis_key"], dropna=False
    ):
        totals = {f: 0.0 for f in PRIORITY_FIELDNAMES.values()}
        others = 0.0
        for _, r in grp.iterrows():
            cat = r["energy_norm"]
            pkw = float(r["_power"])
            if cat in PRIORITY_FIELDNAMES:
                totals[PRIORITY_FIELDNAMES[cat]] += pkw
            else:
                others += pkw

        totals[OTHERS_FIELD] = others
        totals["total_kw"] = sum(totals.values())
        totals["state_slug"] = state_slug
        totals["kreis_key"] = kreis_key
        totals["kreis_name"] = choose_label(grp["kreis_name"].tolist()) or kreis_key

        # use center from centers file
        cx, cy = centers_by_ags[kreis_key]
        totals["_x"] = cx
        totals["_y"] = cy
        grouped.append(totals)

    agg = pd.DataFrame(grouped)

    # ---------------- WRITE PER STATE ----------------
    for state_slug, grp in agg.groupby("state_slug"):
        gdf = gpd.GeoDataFrame(
            grp.drop(columns=["_x", "_y"]),
            geometry=[Point(xy) for xy in zip(grp["_x"], grp["_y"])],
            crs="EPSG:4326",
        )

        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        out_pts = OUTPUT_DIR / f"de_{state_slug}_landkreis_pies.geojson"
        gdf.to_file(out_pts, driver="GeoJSON")

        vmin = float(gdf["total_kw"].min()) if len(gdf) else 0.0
        vmax = float(gdf["total_kw"].max()) if len(gdf) else 1.0
        meta = {
            "min_total_kw": vmin,
            "max_total_kw": vmax,
            "priority_fields": list(PRIORITY_FIELDNAMES.values()),
            "others_field": OTHERS_FIELD,
            "name_field": "kreis_name",
        }
        (OUTPUT_DIR / f"{state_slug}_landkreis_pie_style_meta.json").write_text(
            json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(
            f"[OK] {state_slug}: wrote {out_pts.name} (unique_kreise={len(gdf)})"
        )


if __name__ == "__main__":
    main()
