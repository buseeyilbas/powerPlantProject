# debug_compare_cumulative_power_3_inputs.py
# PURPOSE:
#   Scan THREE different input roots separately
#   and compare cumulative installed power per 2-year bin.
#
#   This is a PURE DEBUG script.
#   No pies, no styling, no geometry ops.
#
#   Output:
#     - per input: bin power + cumulative power
#     - final comparison table (consistency check)

from pathlib import Path
import geopandas as gpd
import pandas as pd
import re

# ============================================================
# INPUT ROOTS (EDIT IF NEEDED)
# ============================================================

INPUTS = {
    "1_state_yearly_3checks": Path(
        r"C:\Users\jo73vure\Desktop\powerPlantProject\data\geojson\by_state_yearly_4_checks"
    ),
    "2_state_landkreis_yearly": Path(
        r"C:\Users\jo73vure\Desktop\powerPlantProject\data\geojson\by_state_landkreis_yearly"
    ),
    "3_nationwide_landkreis_yearly": Path(
        r"C:\Users\jo73vure\Desktop\powerPlantProject\data\geojson\by_landkreis_yearly"
    ),
}

POWER_FIELDS = [
    "power_kw",
    "_power",
    "Bruttoleistung",
    "Nettonennleistung",
    "Nennleistung",
    "installed_power_kw",
]

YEAR_BINS = [
    ("pre_1990",  "≤1990", None, 1990),
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

BIN_ORDER = [b[0] for b in YEAR_BINS]

# ============================================================
# HELPERS
# ============================================================

def find_power_col(cols):
    for c in POWER_FIELDS:
        if c in cols:
            return c
    return None

def extract_year(val):
    if val is None:
        return None
    m = re.search(r"(19|20)\d{2}", str(val))
    return int(m.group(0)) if m else None

def year_to_bin(y):
    if y is None:
        return "unknown"
    for slug, _, start, end in YEAR_BINS:
        if (start is None or y >= start) and (end is None or y <= end):
            return slug
    return "unknown"


# ============================================================
# SCAN ONE INPUT ROOT
# ============================================================

def scan_root(root: Path) -> pd.DataFrame:
    rows = []
    files = list(root.rglob("*.geojson"))
    print(f"\n[SCAN] {root}")
    print(f"       files found: {len(files)}")

    for p in files:
        try:
            g = gpd.read_file(p)
        except Exception:
            continue
        if g.empty:
            continue

        pcol = find_power_col(g.columns)
        if not pcol:
            continue

        ycol = None
        for c in ["year", "Year", "YEAR", "Inbetriebnahmedatum", "commissioning_date"]:
            if c in g.columns:
                ycol = c
                break

        for _, r in g.iterrows():
            try:
                val = float(r.get(pcol))
            except Exception:
                continue
            if val <= 0:
                continue

            y = extract_year(r.get(ycol)) if ycol else None
            b = year_to_bin(y)

            if b == "unknown":
                continue

            rows.append({
                "bin": b,
                "power_kw": val,
            })

    df = pd.DataFrame(rows)
    if df.empty:
        return pd.DataFrame({"bin": BIN_ORDER, "bin_MW": 0.0, "cumulative_MW": 0.0})

    per_bin = (
        df.groupby("bin")["power_kw"]
        .sum()
        .reindex(BIN_ORDER, fill_value=0.0)
    )

    cum = per_bin.cumsum()

    return pd.DataFrame({
        "bin": BIN_ORDER,
        "bin_MW": per_bin.values / 1000.0,
        "cumulative_MW": cum.values / 1000.0,
    })

# ============================================================
# MAIN
# ============================================================

def main():
    results = {}

    for name, root in INPUTS.items():
        df = scan_root(root)
        results[name] = df
        print(f"\n--- {name} ---")
        print(df.to_string(index=False, float_format=lambda x: f"{x:12,.2f}"))

    # ---------------- COMPARISON ----------------
    print("\n================ CONSISTENCY CHECK ================\n")

    merged = results[list(results.keys())[0]][["bin"]].copy()
    for name, df in results.items():
        merged[name] = df["cumulative_MW"]

    print(merged.to_string(index=False, float_format=lambda x: f"{x:12,.2f}"))

    print("\n[INTERPRETATION]")
    print("- Same numbers  → inputs consistent")
    print("- Differences  → duplication / missing data / filtering mismatch")

    print("\n[DEBUG DONE]\n")


if __name__ == "__main__":
    main()
