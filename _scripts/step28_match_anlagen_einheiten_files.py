# file: step28_match_anlagen_einheiten_files.py
"""
Step 28 - EEG-based power consistency check between Anlagen and Einheiten,
with chunked JSON output.

What this script does:
1) Scans all Einheiten*.json and aggregates per EEG ID (EegMaStRNummer):
     - sum_brutto_kw
     - unit_count
     - energy_types (set of Energietraeger codes)

2) Scans all Anlagen*.json and, for each Anlage:
     - uses its EegMaStRNummer to look up the aggregated Einheiten power
     - compares sum_bruttoleistung_kw vs InstallierteLeistung
     - writes a compact record via a chunked writer, with:
         * eeg_mastr_nummer
         * energy_type_codes
         * pair_key (from Anlagen filename, e.g. 'solar_7', 'stromspeicher_9')
         * einheiten_unit_count
         * installierte_leistung_kw
         * sum_bruttoleistung_kw
         * abs_power_diff_kw
         * status ('ok', 'power_mismatch', 'no_einheiten_for_eeg',
                   'no_power_field', 'no_power_and_no_units')
         * has_power_field (bool)
         * anlagen_file

3) Instead of one huge JSON file, records are split into multiple chunks:
     step28_records_part_001.json
     step28_records_part_002.json
     ...

4) A small summary file is written:
     step28_main_summary.json

Run:
    py step28_match_anlagen_einheiten_files.py
"""

from pathlib import Path
import json
from typing import List, Dict, Any, Tuple, Set


# Base directory where all JSON files live
BASE_DIR = Path(r"C:\Users\jo73vure\Desktop\powerPlantProject\data\json")

# Allowed absolute difference between Einheiten sum and InstallierteLeistung (in kW)
POWER_TOLERANCE_KW = 1.0

# Maximum number of records per chunk file
MAX_RECORDS_PER_CHUNK = 1_000_000


def _build_key_for_anlagen_file(name: str) -> str:
    """
    Build a normalized key from an Anlagen file name by:
    - Removing 'Anlagen' prefix if present
    - Removing '.json'
    - Removing leading 'Eeg' if present
    - Lowercasing

    Examples:
      'AnlagenSolar_7.json'        -> 'solar_7'
      'AnlagenEegSolar_7.json'     -> 'solar_7'
      'AnlagenEegGeothermieX.json' -> 'geothermiex'
    """
    base = name
    if base.startswith("Anlagen"):
        base = base[len("Anlagen"):]
    if base.lower().endswith(".json"):
        base = base[:-5]
    if base.startswith("Eeg"):
        base = base[3:]
    return base.lower()


def _to_float(value: Any):
    """
    Safely convert MaStR numeric strings like '2720.000' to float.
    Returns None if conversion is not possible.
    """
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    text = text.replace(",", ".")
    try:
        return float(text)
    except ValueError:
        return None


def load_einheiten_eeg_stats(base_dir: Path) -> Tuple[Dict[str, Dict[str, Any]], Dict[str, int]]:
    """
    Scan all Einheiten*.json files and aggregate per EEG MaStR number:
      - sum_brutto_kw: sum of Bruttoleistung across all units with this EEG
      - unit_count: number of Einheiten entries with this EEG
      - energy_types: set of Energietraeger codes (as strings)

    Returns:
      eeg_stats: dict[eeg_id] -> {sum_brutto_kw, unit_count, energy_types}
      meta: {"total_units": int, "total_eeg_ids": int, "einheiten_files": int}
    """
    eeg_stats: Dict[str, Dict[str, Any]] = {}
    total_units = 0
    einheiten_files = 0

    for path in base_dir.glob("Einheiten*.json"):
        einheiten_files += 1
        with path.open(encoding="utf-8") as f:
            try:
                einheiten = json.load(f)
            except json.JSONDecodeError as exc:
                print(f"[WARN] Could not parse {path.name}: {exc}")
                continue

        if not isinstance(einheiten, list):
            print(f"[WARN] Unexpected JSON structure in {path.name} (expected list).")
            continue

        for e in einheiten:
            if not isinstance(e, dict):
                continue
            eeg_id = e.get("EegMaStRNummer")
            if not eeg_id:
                continue

            total_units += 1

            brutto_kw = _to_float(e.get("Bruttoleistung"))
            energy_type = e.get("Energietraeger")

            stats = eeg_stats.get(eeg_id)
            if stats is None:
                stats = {
                    "sum_brutto_kw": 0.0,
                    "unit_count": 0,
                    "energy_types": set(),  # type: ignore
                }
                eeg_stats[eeg_id] = stats

            if brutto_kw is not None:
                stats["sum_brutto_kw"] += brutto_kw
            stats["unit_count"] += 1
            if energy_type is not None:
                stats["energy_types"].add(str(energy_type))

    meta = {
        "total_units": total_units,
        "total_eeg_ids": len(eeg_stats),
        "einheiten_files": einheiten_files,
    }
    return eeg_stats, meta


class ChunkedRecordWriter:
    """
    Helper class to write records into multiple JSON files in chunks.

    Each chunk is a JSON array:
      [ {record1}, {record2}, ... ]
    """

    def __init__(
        self,
        base_dir: Path,
        base_name: str = "step26_records_part",
        max_records_per_chunk: int = MAX_RECORDS_PER_CHUNK,
    ):
        self.base_dir = base_dir
        self.base_name = base_name
        self.max_records_per_chunk = max_records_per_chunk
        self.current_part = 1
        self.buffer: List[Dict[str, Any]] = []
        self.files: List[str] = []

    def _current_filename(self) -> str:
        return f"{self.base_name}_{self.current_part:03d}.json"

    def _flush(self):
        if not self.buffer:
            return
        filename = self._current_filename()
        path = self.base_dir / filename
        with path.open("w", encoding="utf-8") as f:
            json.dump(self.buffer, f, ensure_ascii=False, indent=2)
        print(f"[INFO] Wrote chunk {filename} with {len(self.buffer)} records.")
        self.files.append(filename)
        self.buffer = []
        self.current_part += 1

    def write_record(self, record: Dict[str, Any]):
        self.buffer.append(record)
        if len(self.buffer) >= self.max_records_per_chunk:
            self._flush()

    def close(self) -> List[str]:
        # Flush remaining records
        self._flush()
        return self.files


def process_anlagen_with_eeg(
    base_dir: Path,
    eeg_stats: Dict[str, Dict[str, Any]],
    writer: ChunkedRecordWriter,
) -> Dict[str, int]:
    """
    Scan all Anlagen*.json files and, for each Anlage:
      - use its EegMaStRNummer to look up aggregated Einheiten power
      - compare sum_bruttoleistung_kw vs InstallierteLeistung
      - write a compact record via the given writer

    Returns:
      summary: dict with global counters
    """
    total_anlagen = 0
    anlagen_with_power_field = 0
    anlagen_without_power_field = 0
    anlagen_with_eeg_id = 0
    anlagen_without_eeg_id = 0
    ok_power_count = 0
    power_mismatch_count = 0
    no_einheiten_for_eeg_count = 0
    no_power_and_no_units_count = 0

    for path in base_dir.glob("Anlagen*.json"):
        pair_key = _build_key_for_anlagen_file(path.name)

        with path.open(encoding="utf-8") as f:
            try:
                anlagen = json.load(f)
            except json.JSONDecodeError as exc:
                print(f"[WARN] Could not parse {path.name}: {exc}")
                continue

        if not isinstance(anlagen, list):
            print(f"[WARN] Unexpected JSON structure in {path.name} (expected list).")
            continue

        for a in anlagen:
            if not isinstance(a, dict):
                continue

            total_anlagen += 1

            eeg_id = a.get("EegMaStRNummer")
            if eeg_id:
                anlagen_with_eeg_id += 1
            else:
                anlagen_without_eeg_id += 1

            installed_kw = _to_float(a.get("InstallierteLeistung"))
            has_power_field = installed_kw is not None
            if has_power_field:
                anlagen_with_power_field += 1
            else:
                anlagen_without_power_field += 1

            stats = eeg_stats.get(eeg_id) if eeg_id else None
            if stats:
                sum_brutto = stats.get("sum_brutto_kw", 0.0)
                energy_types = stats.get("energy_types", set())
                unit_count = stats.get("unit_count", 0)
            else:
                sum_brutto = None
                energy_types = set()
                unit_count = 0

            # Determine status and difference
            abs_diff = None
            status: str

            if not has_power_field and sum_brutto is None:
                status = "no_power_and_no_units"
                no_power_and_no_units_count += 1
            elif not has_power_field and sum_brutto is not None:
                status = "no_power_field"
            elif has_power_field and sum_brutto is None:
                status = "no_einheiten_for_eeg"
                no_einheiten_for_eeg_count += 1
            else:
                # both present
                diff = sum_brutto - installed_kw  # type: ignore
                abs_diff = abs(diff)
                if abs_diff <= POWER_TOLERANCE_KW:
                    status = "ok"
                    ok_power_count += 1
                else:
                    status = "power_mismatch"
                    power_mismatch_count += 1

            record = {
                "pair_key": pair_key,
                "anlagen_file": path.name,
                "eeg_mastr_nummer": eeg_id,
                "energy_type_codes": sorted(list(energy_types)),
                "einheiten_unit_count": unit_count,
                "installierte_leistung_kw": installed_kw,
                "sum_bruttoleistung_kw": sum_brutto,
                "abs_power_diff_kw": abs_diff,
                "status": status,
                "has_power_field": has_power_field,
            }
            writer.write_record(record)

    summary = {
        "total_anlagen": total_anlagen,
        "anlagen_with_eeg_id": anlagen_with_eeg_id,
        "anlagen_without_eeg_id": anlagen_without_eeg_id,
        "anlagen_with_power_field": anlagen_with_power_field,
        "anlagen_without_power_field": anlagen_without_power_field,
        "ok_power_count": ok_power_count,
        "power_mismatch_count": power_mismatch_count,
        "no_einheiten_for_eeg_count": no_einheiten_for_eeg_count,
        "no_power_and_no_units_count": no_power_and_no_units_count,
    }

    return summary


def main():
    print(f"[INFO] JSON base directory: {BASE_DIR}")
    if not BASE_DIR.exists():
        print("[ERROR] Base directory does not exist. Please check BASE_DIR.")
        return

    # 1) Aggregate Einheiten by EEG MaStR number
    print("[INFO] Loading Einheiten EEG statistics...")
    eeg_stats, einheiten_meta = load_einheiten_eeg_stats(BASE_DIR)
    print(
        f"[INFO] Einheiten stats: {einheiten_meta['total_units']} units, "
        f"{einheiten_meta['total_eeg_ids']} distinct EEG IDs, "
        f"{einheiten_meta['einheiten_files']} Einheiten files."
    )

    # 2) Process all Anlagen using EEG-based power lookup, with chunked writer
    print("[INFO] Processing Anlagen with EEG-based power check (chunked output)...")
    writer = ChunkedRecordWriter(BASE_DIR)
    anlagen_summary = process_anlagen_with_eeg(BASE_DIR, eeg_stats, writer)
    record_files = writer.close()

    print("[INFO] Anlagen summary:")
    print(json.dumps(anlagen_summary, indent=2))
    print(f"[INFO] Number of chunk files: {len(record_files)}")

    # 3) Write small main summary file
    summary_path = BASE_DIR / "step26_main_summary.json"
    summary_data = {
        "base_dir": str(BASE_DIR),
        "power_tolerance_kw": POWER_TOLERANCE_KW,
        "einheiten_summary": einheiten_meta,
        "anlagen_summary": anlagen_summary,
        "record_files": record_files,
        "max_records_per_chunk": MAX_RECORDS_PER_CHUNK,
    }

    with summary_path.open("w", encoding="utf-8") as f:
        json.dump(summary_data, f, ensure_ascii=False, indent=2)

    print(f"[INFO] Main summary written to: {summary_path}")


if __name__ == "__main__":
    main()
