# Filename: step2_3_make_statewise_landkreis_pie_inputs_yearly.py
# Purpose :
#   Yearly LANDKREIS pie INPUT POINTS for all states,
#   using the SAME AGS-based centers as step2_1 (via step2_0 centers file).
#
#   ✔ No filename-based kreis_key
#   ✔ kreis_key = AGS5
#   ✔ All centers taken from de_landkreis_centers.geojson
#
#   Outputs:
#       1) OUT_DIR/<bin_slug>/de_landkreis_pies_<bin_slug>.geojson
#       2) OUT_DIR/<state_slug>/<bin_slug>/de_<state_slug>_landkreis_pies_<bin_slug>.geojson
#       3) OUT_DIR/_STATEWISE_size_meta.json
#       4) OUT_DIR/de_yearly_totals.json + de_yearly_totals_chart.geojson + de_energy_legend_points.geojson

from pathlib import Path
import os
import re
import json
import unicodedata

import geopandas as gpd
import pandas as pd
from shapely.geometry import Point, Polygon

# ------------------------------ PATHS ------------------------------

INPUT_ROOT = Path(
    r"C:\Users\jo73vure\Desktop\powerPlantProject\data\geojson\by_state_landkreis_yearly"
)

OUT_DIR = Path(
    r"C:\Users\jo73vure\Desktop\powerPlantProject\data\geojson\pieCharts\statewise_landkreis_pies_yearly"
)

CENTERS_PATH = Path(
    r"C:\Users\jo73vure\Desktop\powerPlantProject\data\geojson\pieCharts\landkreis_centers\de_landkreis_centers.geojson"
)

# ------------------------------ YEAR BINS ------------------------------
YEAR_BINS = [
    ("pre_1990", "≤1990", None, 1990),
    ("1991_1992", "1991–1992", 1991, 1992),
    ("1993_1994", "1993–1994", 1993, 1994),
    ("1995_1996", "1995–1996", 1995, 1996),
    ("1997_1998", "1997–1998", 1997, 1998),
    ("1999_2000", "1999–2000", 1999, 2000),
    ("2001_2002", "2001–2002", 2001, 2002),
    ("2003_2004", "2003–2004", 2003, 2004),
    ("2005_2006", "2005–2006", 2005, 2006),
    ("2007_2008", "2007–2008", 2007, 2008),
    ("2009_2010", "2009–2010", 2009, 2010),
    ("2011_2012", "2011–2012", 2011, 2012),
    ("2013_2014", "2013–2014", 2013, 2014),
    ("2015_2016", "2015–2016", 2015, 2016),
    ("2017_2018", "2017–2018", 2017, 2018),
    ("2019_2020", "2019–2020", 2019, 2020),
    ("2021_2022", "2021–2022", 2021, 2022),
    ("2023_2024", "2023–2024", 2023, 2024),
    ("2025_2026", "2025–2026", 2025, 2026),
]
BIN_LABEL = {slug: lbl for slug, lbl, *_ in YEAR_BINS}

# ------------------------------ ENERGY ------------------------------
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

PRIORITY = {
    "Photovoltaik": "pv_kw",
    "Windenergie Onshore": "wind_kw",
    "Wasserkraft": "hydro_kw",
    "Stromspeicher (Battery Storage)": "battery_kw",
    "Biogas": "biogas_kw",
}
OTHERS = "others_kw"

PART_FIELDS = [
    "pv_kw",
    "wind_kw",
    "hydro_kw",
    "battery_kw",
    "biogas_kw",
    "others_kw",
]

R_MIN_M = 10000.0
R_MAX_M = 35000.0

# ------------------------------ HELPERS ------------------------------


def norm(s: str) -> str:
    if s is None:
        return ""
    s = unicodedata.normalize("NFKD", str(s))
    s = "".join(ch for ch in s if not unicodedata.combining(ch)).lower()
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")


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


def energy_norm(val, filename_hint="") -> str:
    if val is not None:
        s = str(val).strip()
        if s in ENERGY_CODE_TO_LABEL:
            return ENERGY_CODE_TO_LABEL[s]
        sn = norm(s)
        if "solar" in sn or "photovolta" in sn or sn == "pv":
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
    if "solar" in fn or "photovolta" in fn or "pv" in fn:
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


DATE_CANDS = [
    "Inbetriebnahmedatum",
    "commissioning_date",
    "Baujahr",
    "year",
    "Year",
    "YEAR",
    "Inbetriebnahme",
]


def extract_year(row, filename=""):
    for col in DATE_CANDS:
        if col in row and pd.notna(row[col]):
            s = str(row[col]).strip()
            m = re.search(r"(19|20)\d{2}", s)
            if m:
                y = int(m.group(0))
                if 1900 <= y <= 2100:
                    return y
            try:
                dt = pd.to_datetime(s, errors="coerce")
                if pd.notna(dt):
                    return int(dt.year)
            except Exception:
                pass

    m = re.search(r"(19|20)\d{2}", filename)
    if m:
        y = int(m.group(0))
        if 1900 <= y <= 2100:
            return y
    return None


def year_to_bin(y):
    if y is None:
        return ("unknown", "Unknown / NA")
    for slug, lbl, start, end in YEAR_BINS:
        if (start is None or y >= start) and (end is None or y <= end):
            return (slug, lbl)
    return ("unknown", "Unknown / NA")


def scan_geojsons(folder: Path):
    for root, _, files in os.walk(folder):
        for fn in files:
            if fn.lower().endswith(".geojson"):
                yield Path(root) / fn


def load_centers():
    if not CENTERS_PATH.exists():
        raise RuntimeError(f"Centers file not found: {CENTERS_PATH}")
    g = gpd.read_file(CENTERS_PATH)
    if g.crs is None:
        g = g.set_crs("EPSG:4326", allow_override=True)

    centers = {}
    state_by_ags = {}
    for _, r in g.iterrows():
        ags = str(r.get("ags5", "")).strip()
        if not ags:
            continue
        centers[ags] = (float(r.geometry.x), float(r.geometry.y))
        state_by_ags[ags] = str(r.get("state_slug", "")).strip()
    print(f"[CENTERS] Loaded {len(centers)} centers from {CENTERS_PATH}")
    return centers, state_by_ags


# ------------------------------ MAIN ------------------------------


def main():
    print("\n[step2_3] Building yearly Landkreis pie INPUTS (AGS-based).")
    if not INPUT_ROOT.exists():
        raise RuntimeError(f"INPUT_ROOT not found: {INPUT_ROOT}")

    centers, state_by_ags = load_centers()
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    all_rows = []

    dirs = [d.name for d in INPUT_ROOT.iterdir() if d.is_dir()]
    print(f"[INFO] Found {len(dirs)} state directories: {dirs}")

    for state_dir in sorted(INPUT_ROOT.iterdir()):
        if not state_dir.is_dir():
            continue

        print(f"\n---- STATE DIR: {state_dir.name} ----")

        for p in scan_geojsons(state_dir):
            try:
                g = gpd.read_file(p)
            except Exception as e:
                print(f"  [WARN] skipped {p.name}: {e}")
                continue

            if g.empty or "geometry" not in g.columns:
                continue

            g = g[g.geometry.notnull()]
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
                    lambda v: energy_norm(v, filename)
                )
            elif "Energietraeger" in g.columns:
                g["energy_norm"] = g["Energietraeger"].apply(
                    lambda v: energy_norm(v, filename)
                )
            else:
                g["energy_norm"] = energy_norm(None, filename)

            # power
            power_col = None
            for c in [
                "power_kw",
                "Nettonennleistung",
                "Bruttoleistung",
                "Nennleistung",
                "installed_power_kw",
                "Leistung",
                "kw",
                "power",
            ]:
                if c in g.columns:
                    power_col = c
                    break
            if not power_col:
                continue

            g["_power"] = g[power_col].apply(parse_number)
            g = g[(g["_power"] > 0) & pd.notna(g["_power"])]
            if g.empty:
                continue

            # year bins
            years = [extract_year(r, filename) for _, r in g.iterrows()]
            bins = [year_to_bin(y) for y in years]
            g["year_bin_slug"] = [b[0] for b in bins]
            g["year_bin_label"] = [b[1] for b in bins]

            # row-wise
            for _, r in g.iterrows():
                yslug = r["year_bin_slug"]
                ylbl = r["year_bin_label"]
                if yslug == "unknown":
                    continue

                ags5 = extract_ags5(r)
                if not ags5:
                    continue
                if ags5 not in centers:
                    continue

                state_slug = state_by_ags.get(ags5, "")
                if not state_slug:
                    continue

                cx, cy = centers[ags5]

                all_rows.append(
                    {
                        "state_slug": state_slug,
                        "kreis_key": ags5,
                        "energy_norm": r["energy_norm"],
                        "_power": float(r["_power"]),
                        "year_bin_slug": yslug,
                        "year_bin_label": ylbl,
                        "_x": cx,
                        "_y": cy,
                    }
                )

    if not all_rows:
        print("[FATAL] No usable yearly rows.")
        return

    df = pd.DataFrame(all_rows)
    df = df[df["year_bin_slug"] != "unknown"]
    if df.empty:
        print("[FATAL] All rows mapped to unknown year bin.")
        return

    # ---------------- AGGREGATE (state, kreis, bin) ----------------
    by_bin = {}
    for (state_slug, kreis_key, bin_slug), grp in df.groupby(
        ["state_slug", "kreis_key", "year_bin_slug"]
    ):
        label = grp["year_bin_label"].iloc[0]

        totals = {f: 0.0 for f in PRIORITY.values()}
        others = 0.0

        for _, r in grp.iterrows():
            cat = r["energy_norm"]
            pkw = float(r["_power"])
            if cat in PRIORITY:
                totals[PRIORITY[cat]] += pkw
            else:
                others += pkw

        totals[OTHERS] = others
        totals["total_kw"] = sum(totals.values())
        totals["state_slug"] = state_slug
        totals["kreis_key"] = kreis_key
        totals["year_bin_slug"] = bin_slug
        totals["year_bin_label"] = label

        any_row = grp.iloc[0]
        totals["_x"] = float(any_row["_x"])
        totals["_y"] = float(any_row["_y"])

        by_bin.setdefault(bin_slug, []).append(totals)

    # ---------------- STATEWISE GLOBAL MIN/MAX (ALL YEARS) ----------------
    state_stats = {}
    for bin_slug, rows in by_bin.items():
        for t in rows:
            st = t.get("state_slug")
            if not st:
                continue
            val = float(t.get("total_kw", 0.0) or 0.0)
            kreis = t.get("kreis_key", "")
            yslug = t.get("year_bin_slug", "")

            if st not in state_stats:
                state_stats[st] = {
                    "min_total_kw": val,
                    "max_total_kw": val,
                    "min_kreis_key": kreis,
                    "max_kreis_key": kreis,
                    "min_year_bin": yslug,
                    "max_year_bin": yslug,
                }
            else:
                if val < state_stats[st]["min_total_kw"]:
                    state_stats[st]["min_total_kw"] = val
                    state_stats[st]["min_kreis_key"] = kreis
                    state_stats[st]["min_year_bin"] = yslug
                if val > state_stats[st]["max_total_kw"]:
                    state_stats[st]["max_total_kw"] = val
                    state_stats[st]["max_kreis_key"] = kreis
                    state_stats[st]["max_year_bin"] = yslug

    print("\n[STATEWISE-GLOBAL-SIZE] All years (ca. 1900–2026)")
    for st in sorted(state_stats.keys()):
        info = state_stats[st]
        print(
            f"  {st:15s}  vmin={info['min_total_kw']:12,.1f} kW"
            f"  (kreis={info['min_kreis_key']}, bin={info['min_year_bin']})"
        )
        print(
            f"                 vmax={info['max_total_kw']:12,.1f} kW"
            f"  (kreis={info['max_kreis_key']}, bin={info['max_year_bin']})"
        )
        print(
            f"                 radii → min={R_MIN_M:,.1f} m, max={R_MAX_M:,.1f} m"
        )

    state_meta_path = OUT_DIR / "_STATEWISE_size_meta.json"
    state_meta_path.write_text(json.dumps(state_stats, indent=2), encoding="utf-8")

    for st, info in state_stats.items():
        st_dir = OUT_DIR / st
        st_dir.mkdir(parents=True, exist_ok=True)
        vmin = float(info["min_total_kw"])
        vmax = float(info["max_total_kw"])
        (st_dir / "_STATE_META.json").write_text(
            json.dumps([vmin, vmax], indent=2), encoding="utf-8"
        )

    # ---------------- GERMANY-WIDE BIN ENERGY + CUMULATIVE TOTALS ----------------
    all_bins_energy = {}
    yearly_totals = []
    cumulative = {f: 0.0 for f in PART_FIELDS}

    for slug, lbl, *_ in YEAR_BINS:
        rows = by_bin.get(slug, [])
        if not rows:
            continue

        bin_energy = {f: 0.0 for f in PART_FIELDS}
        for r in rows:
            for f in PART_FIELDS:
                bin_energy[f] += float(r.get(f, 0.0) or 0.0)
        all_bins_energy[slug] = bin_energy

        for f in PART_FIELDS:
            cumulative[f] += bin_energy[f]

        total_kw = sum(cumulative.values())
        yearly_totals.append(
            {
                "year_bin_slug": slug,
                "year_bin_label": lbl,
                "total_kw": total_kw,
            }
        )

    # ---------------- WRITE GERMANY-WIDE PER-BIN INPUT FILES (FOR STEP2_4) ----------------
    for bin_slug, rows in by_bin.items():
        bin_dir = OUT_DIR / bin_slug
        bin_dir.mkdir(parents=True, exist_ok=True)

        gdf_all = gpd.GeoDataFrame(
            rows,
            geometry=[Point(t["_x"], t["_y"]) for t in rows],
            crs="EPSG:4326",
        )
        gdf_all = gdf_all.drop(columns=["_x", "_y"])
        out_all = bin_dir / f"de_landkreis_pies_{bin_slug}.geojson"
        gdf_all.to_file(out_all, driver="GeoJSON")
        print(f"[GLOBAL INPUT] wrote {out_all} (features={len(gdf_all)})")

    # ---------------- WRITE PER-BIN PER-STATE INPUT FILES + META ----------------
    by_state_bin = {}
    for bin_slug, rows in by_bin.items():
        for t in rows:
            st = t["state_slug"]
            by_state_bin.setdefault((st, bin_slug), []).append(t)

    for (state_slug, bin_slug), rows in sorted(by_state_bin.items()):
        lbl = BIN_LABEL.get(bin_slug, bin_slug)

        bin_dir = OUT_DIR / state_slug / bin_slug
        bin_dir.mkdir(parents=True, exist_ok=True)

        gdf = gpd.GeoDataFrame(
            rows,
            geometry=[Point(t["_x"], t["_y"]) for t in rows],
            crs="EPSG:4326",
        )
        gdf = gdf.drop(columns=["_x", "_y"])

        outp = bin_dir / f"de_{state_slug}_landkreis_pies_{bin_slug}.geojson"
        gdf.to_file(outp, driver="GeoJSON")

        vmin = float(gdf["total_kw"].min())
        vmax = float(gdf["total_kw"].max())

        print(f"\n[STATE-BIN] {state_slug:15s} / {lbl} (slug: {bin_slug})")
        print(f"  bin vmin = {vmin:12,.1f} kW")
        print(f"  bin vmax = {vmax:12,.1f} kW")
        print(
            f"  example radii (if scaled locally) → [{R_MIN_M:,.1f} m, {R_MAX_M:,.1f} m]"
        )

        meta = {
            "state_slug": state_slug,
            "year_bin": lbl,
            "year_bin_slug": bin_slug,
            "min_total_kw": vmin,
            "max_total_kw": vmax,
            "priority_fields": list(PRIORITY.values()),
            "others_field": OTHERS,
            "name_field": "kreis_key",
        }
        (bin_dir / f"landkreis_pie_style_meta_{bin_slug}.json").write_text(
            json.dumps(meta, indent=2), encoding="utf-8"
        )

    # ---------------- SAVE YEARLY TOTALS JSON ----------------
    (OUT_DIR / "de_yearly_totals.json").write_text(
        json.dumps(yearly_totals, indent=2), encoding="utf-8"
    )

    # ---------------- ROW CHART GEOMETRIES ----------------
    CHART_BASE_LON = -2.2
    CHART_BASE_LAT = 47.5
    MAX_BAR_WIDTH = 6.8
    BAR_HEIGHT = 0.15
    BAR_GAP = 0.05

    YEAR_LABEL_LON = CHART_BASE_LON - 0.8
    VALUE_LABEL_LON = 5.1

    chart_feats = []
    vals = [yt["total_kw"] for yt in yearly_totals]
    max_total = float(max(vals)) if vals else 1.0

    STACK_ORDER = ["hydro_kw", "biogas_kw", "pv_kw", "wind_kw", "others_kw", "battery_kw"]

    for idx, info in enumerate(reversed(yearly_totals)):
        slug = info["year_bin_slug"]
        label = info["year_bin_label"]
        total = float(info["total_kw"])

        y0 = CHART_BASE_LAT + idx * (BAR_HEIGHT + BAR_GAP)
        y1 = y0 + BAR_HEIGHT
        yc = 0.5 * (y0 + y1)
        x_base = CHART_BASE_LON

        for key in STACK_ORDER:
            seg_val = float(all_bins_energy.get(slug, {}).get(key, 0.0))
            if seg_val <= 0:
                continue

            seg_ratio = seg_val / max_total
            seg_w = seg_ratio * MAX_BAR_WIDTH
            x1 = x_base + seg_w

            poly = Polygon(
                [(x_base, y0), (x1, y0), (x1, y1), (x_base, y1), (x_base, y0)]
            )
            chart_feats.append(
                {
                    "year_bin_slug": slug,
                    "year_bin_label": label,
                    "energy_type": key,
                    "energy_kw": seg_val,
                    "total_kw": total,
                    "label_anchor": 0,
                    "value_anchor": 0,
                    "geometry": poly,
                }
            )
            x_base = x1

        chart_feats.append(
            {
                "year_bin_slug": slug,
                "year_bin_label": label,
                "energy_type": "others_kw",
                "energy_kw": 0.0,
                "total_kw": total,
                "label_anchor": 1,
                "value_anchor": 0,
                "geometry": Point(YEAR_LABEL_LON, yc),
            }
        )

        chart_feats.append(
            {
                "year_bin_slug": slug,
                "year_bin_label": label,
                "energy_type": "others_kw",
                "energy_kw": 0.0,
                "total_kw": total,
                "label_anchor": 0,
                "value_anchor": 1,
                "geometry": Point(VALUE_LABEL_LON, yc),
            }
        )

    title_point = Point(
        CHART_BASE_LON + MAX_BAR_WIDTH / 2.0,
        CHART_BASE_LAT + (len(yearly_totals) + 1) * (BAR_HEIGHT + BAR_GAP),
    )
    chart_feats.append(
        {
            "year_bin_slug": "title",
            "year_bin_label": "Cumulative Installed Power (MW)",
            "energy_type": "others_kw",
            "energy_kw": 0.0,
            "total_kw": 0.0,
            "label_anchor": 0,
            "value_anchor": 0,
            "geometry": title_point,
        }
    )

    g_chart = gpd.GeoDataFrame(chart_feats, geometry="geometry", crs="EPSG:4326")
    g_chart.to_file(OUT_DIR / "de_yearly_totals_chart.geojson", driver="GeoJSON")

    # ---------------- ENERGY LEGEND ----------------
    LEG_BASE_LON = -2.2
    LEG_TOP_LAT = 54.9
    LEG_STEP = -0.2

    legend_list = [
        ("pv_kw", "Photovoltaics"),
        ("wind_kw", "Onshore Wind Energy"),
        ("hydro_kw", "Hydropower"),
        ("biogas_kw", "Biogas"),
        ("battery_kw", "Battery"),
        ("others_kw", "Others"),
    ]

    legend_feats = []
    for idx, (etype, lbl) in enumerate(legend_list):
        y = LEG_TOP_LAT + idx * LEG_STEP
        legend_feats.append(
            {
                "energy_type": etype,
                "legend_label": lbl,
                "geometry": Point(LEG_BASE_LON, y),
            }
        )

    g_leg = gpd.GeoDataFrame(legend_feats, geometry="geometry", crs="EPSG:4326")
    g_leg.to_file(OUT_DIR / "de_energy_legend_points.geojson", driver="GeoJSON")

    print("[DONE] step2_3 complete.")


if __name__ == "__main__":
    main()
