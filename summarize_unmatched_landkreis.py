#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Stream-count Landkreis-like names from a huge _unmatched.geojson without loading it in memory.

- Supports:
  * GeoJSON FeatureCollection (streamed via ijson over features.item)
  * NDJSON (one JSON object per line)
  * Gzip files (.gz)

- Writes a CSV with counts, and prints a short summary.
- Keeps memory low by streaming; only the set of distinct names is stored.
"""

import argparse
import csv
import gzip
import io
import json
import os
import re
import sys
from collections import Counter
from typing import Any, Dict, Iterable, Optional, Tuple

import ijson  # pip install ijson

# Candidate property keys that might carry a Landkreis/district name (case-insensitive)
CANDIDATE_KEYS = [
    "Landkreis",
    "NAME_2",
    "kreis_NAME_2",
    "District",
    "district",
    "Kreis",
    "kreis",
    "KreisfreieStadt",
    "Kreisfreie_Stadt",
]

def normalize_name(s: str) -> str:
    """Trim + collapse whitespace; keep diacritics."""
    s = s.strip()
    s = re.sub(r"\s+", " ", s)
    return s

def open_maybe_gzip(path: str):
    """Open plain text or gzip transparently, in text mode (utf-8)."""
    if path.lower().endswith(".gz"):
        return io.TextIOWrapper(gzip.open(path, "rb"), encoding="utf-8", newline="")
    return open(path, "r", encoding="utf-8", newline="")

def extract_landkreis_name(props: Dict[str, Any]) -> Optional[str]:
    """Try to get a Landkreis-like name from properties using candidate keys."""
    if not isinstance(props, dict):
        return None
    lower_map = {k.lower(): k for k in props.keys()}
    # 1) Direct keys
    for key in CANDIDATE_KEYS:
        lk = key.lower()
        if lk in lower_map:
            raw = props.get(lower_map[lk])
            if isinstance(raw, str) and raw.strip():
                return normalize_name(raw)
    # 2) Light heuristic: any key containing 'kreis' or 'name_2'
    for k, v in props.items():
        if not isinstance(v, str):
            continue
        kl = str(k).lower()
        if ("kreis" in kl or "name_2" in kl) and v.strip():
            return normalize_name(v)
    return None

def iter_features_geojson_stream(fh) -> Iterable[Dict[str, Any]]:
    """
    Stream features from a big FeatureCollection using ijson.
    Assumes top-level structure: {"type":"FeatureCollection", "features":[ ... ]}
    """
    # ijson.items(..., 'features.item') yields each feature object
    for feat in ijson.items(fh, "features.item"):
        if isinstance(feat, dict):
            yield feat

def is_probably_ndjson(sample: str) -> bool:
    """
    Heuristic: if the file does not start with '{' or '[' but has lots of newlines,
    or it starts with '{' and has '"type":"Feature"' on the first line only, treat as NDJSON.
    """
    s = sample.lstrip()
    if not s:
        return False
    if s[0] == "[":
        return False  # array => not NDJSON
    if s[0] == "{":
        # could be FeatureCollection; we’ll assume NOT ndjson and let ijson parse
        return False
    # e.g., starts with '{' later in the line? fall back to NDJSON
    return True

def iter_features_ndjson_stream(fh) -> Iterable[Dict[str, Any]]:
    """
    Stream features when the file is NDJSON (one JSON per line).
    """
    for line in fh:
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
            if isinstance(obj, dict) and obj.get("type") == "Feature":
                yield obj
        except json.JSONDecodeError:
            continue

def main():
    ap = argparse.ArgumentParser(description="Stream list Landkreis names from a huge _unmatched.geojson (memory-safe).")
    ap.add_argument("--input", "-i", required=True, help="Path to _unmatched.geojson (or .geojson.gz)")
    ap.add_argument("--out-csv", "-o", required=True, help="Where to write the CSV of name,count")
    ap.add_argument("--progress-every", type=int, default=500000,
                    help="Print a progress line every N features (default 500,000)")
    args = ap.parse_args()

    if not os.path.isfile(args.input):
        print(f"❌ Not found: {args.input}", file=sys.stderr)
        sys.exit(1)

    counter: Counter[str] = Counter()
    total = 0
    hits = 0
    misses = 0

    # We need two passes of the file handle only to sniff; reopen afterwards.
    with open_maybe_gzip(args.input) as sniff_fh:
        sample = sniff_fh.read(2048)
    ndjson_mode = is_probably_ndjson(sample)

    with open_maybe_gzip(args.input) as fh:
        if ndjson_mode:
            feature_iter = iter_features_ndjson_stream(fh)
        else:
            feature_iter = iter_features_geojson_stream(fh)

        for feat in feature_iter:
            total += 1
            props = feat.get("properties") or {}
            name = extract_landkreis_name(props)
            if name:
                counter[name] += 1
                hits += 1
            else:
                misses += 1

            if args.progress_every and total % args.progress_every == 0:
                print(f"... processed {total:,} features (names found: {hits:,}, no-name: {misses:,})")

    # Ensure output dir exists
    os.makedirs(os.path.dirname(args.out_csv), exist_ok=True)
    with open(args.out_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["landkreis_name", "count"])
        for name, cnt in counter.most_common():
            w.writerow([name, cnt])

    print("\n—— Summary ——")
    print(f"Total unmatched features     : {total:,}")
    print(f"With detectable Landkreis    : {hits:,}")
    print(f"Without detectable Landkreis : {misses:,}")
    print(f"Distinct names               : {len(counter):,}")
    print(f"CSV written                  : {args.out_csv}")

if __name__ == "__main__":
    main()
