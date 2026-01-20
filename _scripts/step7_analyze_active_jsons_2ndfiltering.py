
# Filename: step7_analyze_active_jsons_2ndfiltering.py

# Purpose:
#   After filtering JSONs to active units (EinheitBetriebsstatus == "35"),
#   generate a detailed second-stage analysis:
#     - Report each JSON file one-by-one (counts, size in GB/MB, field coverage, power stats)
#     - Compute min/max (and totals) by State, Landkreis, Energy Type
#     - Print everything to terminal and also write output documents (MD/JSON/CSV)
#
# Notes:
#   - Supervisor will provide upper/lower limits: set them in USER_LIMITS.

from __future__ import annotations

import csv
import json
import math
import os
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional, Tuple


# =========================
# === USER CONFIG (EDIT) ===
# =========================

INPUT_FOLDER = r"C:\Users\jo73vure\Desktop\powerPlantProject\data\active_json"
OUTPUT_FOLDER = r"C:\Users\jo73vure\Desktop\powerPlantProject\exports\step7_analysis_2ndfiltering"

# Supervisor will provide these limits. Keep None to disable.
USER_LIMITS = {
    # Installed power limits in kW (applied after parsing power_kw)
    "power_kw_min": None,   # e.g. 0.1
    "power_kw_max": None,   # e.g. 50000

    # Optional: commissioning date limits (ISO "YYYY-MM-DD" preferred).
    # If your data uses different date formats, adapt parse_date().
    "commissioning_date_min": None,  # e.g. "1990-01-01"
    "commissioning_date_max": None,  # e.g. "2025-12-31"
}

# Candidate field keys (add your exact keys here if different)
CANDIDATE_KEYS = {
    "state": ["Bundesland", "BundeslandId", "BundeslandSchluessel", "BundeslandCode"],
    "landkreis": ["Landkreis", "LandkreisId", "LandkreisSchluessel", "Kreis", "KreisId"],
    "energy": [
        "Energietraeger", "EnergietraegerId", "EnergietraegerSchluessel",
        "EnergietraegerBezeichnung", "EnergietraegerLabel"
    ],
    # Installed power fields (often in kW in MaStR exports, but not guaranteed)
    "power": ["Bruttoleistung", "Nettonennleistung", "InstallierteLeistung", "Nennleistung", "Leistung"],
    "commissioning_date": ["Inbetriebnahmedatum", "InbetriebnahmeDatum", "Inbetriebnahme", "CommissioningDate"],
}

# If power looks like it's in W, convert to kW above this threshold
WATT_TO_KW_THRESHOLD = 1_000_000  # if parsed power > 1e6, assume W


# ======================
# === DATA STRUCTURES ===
# ======================

@dataclass
class EntryRef:
    file_name: str
    index_in_file: int
    power_kw: Optional[float]
    state: str
    landkreis: str
    energy: str
    commissioning_date: str

    def to_compact_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        # Keep report readable
        if d["power_kw"] is not None:
            d["power_kw"] = round(d["power_kw"], 6)
        return d


@dataclass
class GroupStats:
    group_key: str
    count: int
    total_power_kw: float
    avg_power_kw: float
    min_power_kw: Optional[float]
    max_power_kw: Optional[float]
    min_ref: Optional[EntryRef]
    max_ref: Optional[EntryRef]


# ======================
# === HELPERS / PARSE ===
# ======================

def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def read_json(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def bytes_to_gb_mb(num_bytes: int) -> Tuple[float, float]:
    gb = num_bytes / (1024 ** 3)
    mb = num_bytes / (1024 ** 2)
    return gb, mb


def safe_str(x: Any) -> str:
    if x is None:
        return ""
    return str(x).strip()


def pick_first(entry: Dict[str, Any], keys: List[str]) -> str:
    for k in keys:
        if k in entry and entry[k] not in (None, ""):
            return safe_str(entry[k])
    return ""


def parse_float_maybe(x: Any) -> Optional[float]:
    if x is None:
        return None
    if isinstance(x, (int, float)):
        if math.isnan(float(x)):
            return None
        return float(x)
    s = safe_str(x)
    if not s:
        return None
    # Accept comma decimals (German exports sometimes)
    s = s.replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def parse_power_kw(entry: Dict[str, Any]) -> Optional[float]:
    raw = None
    for k in CANDIDATE_KEYS["power"]:
        if k in entry and entry[k] not in (None, ""):
            raw = entry[k]
            break
    val = parse_float_maybe(raw)
    if val is None:
        return None

    # Heuristic: if extremely large, treat as W and convert to kW
    if val > WATT_TO_KW_THRESHOLD:
        return val / 1000.0
    return val


def parse_date(entry: Dict[str, Any]) -> str:
    # Keep as string for now; user may have multiple formats in dataset.
    # If needed later, implement robust parsing and normalization.
    return pick_first(entry, CANDIDATE_KEYS["commissioning_date"])


def passes_limits(power_kw: Optional[float], commissioning_date: str) -> Tuple[bool, List[str]]:
    reasons: List[str] = []

    pmin = USER_LIMITS.get("power_kw_min")
    pmax = USER_LIMITS.get("power_kw_max")
    dmin = USER_LIMITS.get("commissioning_date_min")
    dmax = USER_LIMITS.get("commissioning_date_max")

    if power_kw is not None:
        if pmin is not None and power_kw < float(pmin):
            reasons.append(f"power_kw < {pmin}")
        if pmax is not None and power_kw > float(pmax):
            reasons.append(f"power_kw > {pmax}")
    else:
        # If you want to drop entries without power, uncomment next line
        # reasons.append("missing power_kw")
        pass

    # Date limits are string-based, expecting ISO YYYY-MM-DD for correct comparisons
    if commissioning_date:
        if dmin is not None and commissioning_date < str(dmin):
            reasons.append(f"date < {dmin}")
        if dmax is not None and commissioning_date > str(dmax):
            reasons.append(f"date > {dmax}")
    else:
        # If you want to drop entries without date, uncomment next line
        # reasons.append("missing commissioning_date")
        pass

    return (len(reasons) == 0), reasons


def normalize_label(x: str, fallback: str = "UNKNOWN") -> str:
    s = safe_str(x)
    return s if s else fallback


# =================
# === AGGREGATE ===
# =================

def update_group(
    groups: Dict[str, GroupStats],
    group_key: str,
    ref: EntryRef,
) -> None:
    key = normalize_label(group_key)

    if key not in groups:
        groups[key] = GroupStats(
            group_key=key,
            count=0,
            total_power_kw=0.0,
            avg_power_kw=0.0,
            min_power_kw=None,
            max_power_kw=None,
            min_ref=None,
            max_ref=None,
        )

    g = groups[key]
    g.count += 1

    if ref.power_kw is not None:
        g.total_power_kw += ref.power_kw

        if g.min_power_kw is None or ref.power_kw < g.min_power_kw:
            g.min_power_kw = ref.power_kw
            g.min_ref = ref

        if g.max_power_kw is None or ref.power_kw > g.max_power_kw:
            g.max_power_kw = ref.power_kw
            g.max_ref = ref

    # avg computed later (needs final count of entries with power)


def finalize_group_avgs(groups: Dict[str, GroupStats], power_counts: Dict[str, int]) -> None:
    for k, g in groups.items():
        pcount = power_counts.get(k, 0)
        if pcount > 0:
            g.avg_power_kw = g.total_power_kw / pcount
        else:
            g.avg_power_kw = 0.0


def group_to_rows(groups: Dict[str, GroupStats]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for k, g in sorted(groups.items(), key=lambda kv: (-kv[1].total_power_kw, kv[0])):
        rows.append({
            "group_key": g.group_key,
            "count": g.count,
            "total_power_kw": round(g.total_power_kw, 6),
            "avg_power_kw": round(g.avg_power_kw, 6),
            "min_power_kw": None if g.min_power_kw is None else round(g.min_power_kw, 6),
            "max_power_kw": None if g.max_power_kw is None else round(g.max_power_kw, 6),
            "min_ref_file": "" if g.min_ref is None else g.min_ref.file_name,
            "min_ref_index": "" if g.min_ref is None else g.min_ref.index_in_file,
            "max_ref_file": "" if g.max_ref is None else g.max_ref.file_name,
            "max_ref_index": "" if g.max_ref is None else g.max_ref.index_in_file,
        })
    return rows


def write_csv(path: str, rows: List[Dict[str, Any]]) -> None:
    if not rows:
        return
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


# ======================
# === MAIN ANALYSIS  ===
# ======================

def analyze() -> None:
    ensure_dir(OUTPUT_FOLDER)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_folder = os.path.join(OUTPUT_FOLDER, f"run_{timestamp}")
    ensure_dir(run_folder)

    json_files = [fn for fn in os.listdir(INPUT_FOLDER) if fn.lower().endswith(".json")]
    json_files.sort()

    if not json_files:
        print(f"❌ No JSON files found in: {INPUT_FOLDER}")
        return

    # Global aggregations
    by_state: Dict[str, GroupStats] = {}
    by_landkreis: Dict[str, GroupStats] = {}
    by_energy: Dict[str, GroupStats] = {}

    power_count_state: Dict[str, int] = {}
    power_count_landkreis: Dict[str, int] = {}
    power_count_energy: Dict[str, int] = {}

    global_missing = {
        "state_missing": 0,
        "landkreis_missing": 0,
        "energy_missing": 0,
        "power_missing": 0,
        "commissioning_date_missing": 0,
    }

    per_file_rows: List[Dict[str, Any]] = []
    dropped_total = 0
    kept_total = 0

    print("\n==============================")
    print("STEP 7 - SECOND FILTERING / ANALYSIS")
    print("==============================")
    print(f"Input folder : {INPUT_FOLDER}")
    print(f"Output folder: {run_folder}")
    print(f"Files found  : {len(json_files)}")

    print("\n=== Active limits ===")
    for k, v in USER_LIMITS.items():
        print(f"- {k}: {v}")

    for file_i, file_name in enumerate(json_files, start=1):
        path = os.path.join(INPUT_FOLDER, file_name)
        size_bytes = os.path.getsize(path)
        size_gb, size_mb = bytes_to_gb_mb(size_bytes)

        try:
            data = read_json(path)
        except json.JSONDecodeError:
            print(f"\n[{file_i}/{len(json_files)}] ⚠️ Invalid JSON skipped: {file_name}")
            continue

        if not isinstance(data, list):
            print(f"\n[{file_i}/{len(json_files)}] ⚠️ Not a list JSON skipped: {file_name}")
            continue

        total_entries = len(data)
        kept_entries = 0
        dropped_entries = 0

        power_values: List[float] = []
        missing_state = 0
        missing_landkreis = 0
        missing_energy = 0
        missing_power = 0
        missing_date = 0

        print(f"\n[{file_i}/{len(json_files)}] 📄 {file_name}")
        print(f"- entries: {total_entries}")
        print(f"- size   : {size_gb:.6f} GB ({size_mb:.2f} MB)")

        for idx, entry in enumerate(data):
            if not isinstance(entry, dict):
                dropped_entries += 1
                continue

            state = normalize_label(pick_first(entry, CANDIDATE_KEYS["state"]))
            landkreis = normalize_label(pick_first(entry, CANDIDATE_KEYS["landkreis"]))
            energy = normalize_label(pick_first(entry, CANDIDATE_KEYS["energy"]))
            power_kw = parse_power_kw(entry)
            commissioning_date = normalize_label(parse_date(entry), fallback="")

            if state == "UNKNOWN":
                missing_state += 1
            if landkreis == "UNKNOWN":
                missing_landkreis += 1
            if energy == "UNKNOWN":
                missing_energy += 1
            if power_kw is None:
                missing_power += 1
            if commissioning_date == "":
                missing_date += 1

            ok, _reasons = passes_limits(power_kw, commissioning_date)
            if not ok:
                dropped_entries += 1
                continue

            kept_entries += 1
            if power_kw is not None:
                power_values.append(power_kw)

            ref = EntryRef(
                file_name=file_name,
                index_in_file=idx,
                power_kw=power_kw,
                state=state,
                landkreis=landkreis,
                energy=energy,
                commissioning_date=commissioning_date,
            )

            update_group(by_state, state, ref)
            update_group(by_landkreis, landkreis, ref)
            update_group(by_energy, energy, ref)

            if power_kw is not None:
                power_count_state[state] = power_count_state.get(state, 0) + 1
                power_count_landkreis[landkreis] = power_count_landkreis.get(landkreis, 0) + 1
                power_count_energy[energy] = power_count_energy.get(energy, 0) + 1

        kept_total += kept_entries
        dropped_total += dropped_entries

        # file stats
        if power_values:
            p_min = min(power_values)
            p_max = max(power_values)
            p_avg = sum(power_values) / len(power_values)
            p_sum = sum(power_values)
        else:
            p_min = p_max = p_avg = None
            p_sum = 0.0

        global_missing["state_missing"] += missing_state
        global_missing["landkreis_missing"] += missing_landkreis
        global_missing["energy_missing"] += missing_energy
        global_missing["power_missing"] += missing_power
        global_missing["commissioning_date_missing"] += missing_date

        print(f"- kept (after limits): {kept_entries}")
        print(f"- dropped (after limits / invalid entries): {dropped_entries}")
        print("- power_kw stats (only parsed values):")
        if p_min is None:
            print("  - no power values found")
        else:
            print(f"  - min: {p_min:.6f} kW")
            print(f"  - max: {p_max:.6f} kW")
            print(f"  - avg: {p_avg:.6f} kW")
            print(f"  - sum: {p_sum:.6f} kW")
        print("- missing fields (raw entries):")
        print(f"  - state missing     : {missing_state}")
        print(f"  - landkreis missing : {missing_landkreis}")
        print(f"  - energy missing    : {missing_energy}")
        print(f"  - power missing     : {missing_power}")
        print(f"  - date missing      : {missing_date}")

        per_file_rows.append({
            "file_name": file_name,
            "entries_total": total_entries,
            "entries_kept": kept_entries,
            "entries_dropped": dropped_entries,
            "file_size_gb": round(size_gb, 9),
            "file_size_mb": round(size_mb, 3),
            "power_values_count": len(power_values),
            "power_kw_min": None if p_min is None else round(p_min, 6),
            "power_kw_max": None if p_max is None else round(p_max, 6),
            "power_kw_avg": None if p_avg is None else round(p_avg, 6),
            "power_kw_sum": round(p_sum, 6),
            "missing_state": missing_state,
            "missing_landkreis": missing_landkreis,
            "missing_energy": missing_energy,
            "missing_power": missing_power,
            "missing_date": missing_date,
        })

    finalize_group_avgs(by_state, power_count_state)
    finalize_group_avgs(by_landkreis, power_count_landkreis)
    finalize_group_avgs(by_energy, power_count_energy)

    # Write outputs
    per_file_csv = os.path.join(run_folder, "per_file.csv")
    by_state_csv = os.path.join(run_folder, "by_state.csv")
    by_landkreis_csv = os.path.join(run_folder, "by_landkreis.csv")
    by_energy_csv = os.path.join(run_folder, "by_energy_type.csv")
    summary_json = os.path.join(run_folder, "summary.json")
    report_md = os.path.join(run_folder, "report.md")

    write_csv(per_file_csv, per_file_rows)
    write_csv(by_state_csv, group_to_rows(by_state))
    write_csv(by_landkreis_csv, group_to_rows(by_landkreis))
    write_csv(by_energy_csv, group_to_rows(by_energy))

    summary = {
        "input_folder": INPUT_FOLDER,
        "output_folder": run_folder,
        "files_seen": len(json_files),
        "entries_kept_total": kept_total,
        "entries_dropped_total": dropped_total,
        "global_missing_counts": global_missing,
        "limits_used": USER_LIMITS,
        "top10_states_by_total_power_kw": group_to_rows(by_state)[:10],
        "top10_landkreise_by_total_power_kw": group_to_rows(by_landkreis)[:10],
        "top10_energy_types_by_total_power_kw": group_to_rows(by_energy)[:10],
    }

    with open(summary_json, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    # Markdown report
    def md_line(s: str = "") -> str:
        return s + "\n"

    md = ""
    md += md_line("# Step 7 - Second filtering / analysis report")
    md += md_line(f"- Generated: {datetime.now().isoformat(timespec='seconds')}")
    md += md_line(f"- Input: `{INPUT_FOLDER}`")
    md += md_line(f"- Output: `{run_folder}`")
    md += md_line(f"- Files: **{len(json_files)}**")
    md += md_line(f"- Entries kept total: **{kept_total}**")
    md += md_line(f"- Entries dropped total: **{dropped_total}**")
    md += md_line("")
    md += md_line("## Limits used")
    for k, v in USER_LIMITS.items():
        md += md_line(f"- `{k}`: `{v}`")
    md += md_line("")
    md += md_line("## Global missing counts (raw entries)")
    for k, v in global_missing.items():
        md += md_line(f"- `{k}`: **{v}**")
    md += md_line("")
    md += md_line("## Output files")
    md += md_line(f"- `per_file.csv`")
    md += md_line(f"- `by_state.csv`")
    md += md_line(f"- `by_landkreis.csv`")
    md += md_line(f"- `by_energy_type.csv`")
    md += md_line(f"- `summary.json`")
    md += md_line("")
    md += md_line("## Top 10 by total_power_kw")
    md += md_line("### States")
    for row in summary["top10_states_by_total_power_kw"]:
        md += md_line(f"- {row['group_key']}: total={row['total_power_kw']} kW, count={row['count']}, "
                      f"min={row['min_power_kw']}, max={row['max_power_kw']}")
    md += md_line("### Landkreise")
    for row in summary["top10_landkreise_by_total_power_kw"]:
        md += md_line(f"- {row['group_key']}: total={row['total_power_kw']} kW, count={row['count']}, "
                      f"min={row['min_power_kw']}, max={row['max_power_kw']}")
    md += md_line("### Energy types")
    for row in summary["top10_energy_types_by_total_power_kw"]:
        md += md_line(f"- {row['group_key']}: total={row['total_power_kw']} kW, count={row['count']}, "
                      f"min={row['min_power_kw']}, max={row['max_power_kw']}")

    with open(report_md, "w", encoding="utf-8") as f:
        f.write(md)

    # Final terminal summary
    print("\n==============================")
    print("✅ DONE - Outputs written")
    print("==============================")
    print(f"- {report_md}")
    print(f"- {summary_json}")
    print(f"- {per_file_csv}")
    print(f"- {by_state_csv}")
    print(f"- {by_landkreis_csv}")
    print(f"- {by_energy_csv}")


if __name__ == "__main__":
    analyze()
