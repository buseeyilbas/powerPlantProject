# Filename: 14_1_load_geojson_states_as_layers.py
# Purpose: Build one memory point layer per state for QGIS pie charts.
#          Fields = 5 main energy groups + "Others", with supervisor-approved colors.

import os
import json
from qgis.core import (
    QgsVectorLayer, QgsProject, QgsFeature,
    QgsGeometry, QgsPointXY, QgsField
)
from PyQt5.QtCore import QVariant

GEOJSON_FOLDER = r"C:/Users/jo73vure/Desktop/powerPlantProject/data/geojson/by_state_three_checks"

PRIMARY_TYPES = {  # keep these five as distinct fields/slices
    "2495": "Photovoltaics",
    "2497": "Onshore Wind",
    "2498": "Hydropower",
    "2493": "Biogas",
    "2496": "Battery",
}
GROUP_ORDER = ["Photovoltaics", "Onshore Wind", "Hydropower", "Biogas", "Battery", "Others"]

# Fixed color palette (use these in QGIS Pie Chart renderer)
GROUP_COLORS = {
    "Photovoltaics": "yellow",
    "Battery": "purple",
    "Onshore Wind": "lightskyblue",
    "Hydropower": "darkblue",
    "Biogas": "darkgreen",
    "Others": "gray",
}

def map_code_to_group(code: str) -> str:
    """Return one of the 5 main groups, otherwise 'Others'."""
    if code in PRIMARY_TYPES:
        return PRIMARY_TYPES[code]
    return "Others"

def parse_kw(value):
    try:
        return float(str(value).replace(",", "."))
    except Exception:
        return 0.0

# -------- Pass 1: compute all state totals (sum of all groups) ----------------
state_totals = {}

for fname in os.listdir(GEOJSON_FOLDER):
    if not fname.endswith(".geojson"):
        continue

    fpath = os.path.join(GEOJSON_FOLDER, fname)
    state = fname.replace(".geojson", "")

    with open(fpath, "r", encoding="utf-8") as f:
        data = json.load(f)

    total = 0.0
    for feat in data.get("features", []):
        props = feat.get("properties", {})
        kw = parse_kw(props.get("Bruttoleistung", 0))
        total += kw

    state_totals[state] = total

# global min / max
max_total = max(state_totals.values()) if state_totals else 0.0
min_total = min(state_totals.values()) if state_totals else 0.0
print(f"🌍 Max total={max_total:.0f}, Min total={min_total:.0f}")

# -------- Pass 2: build layers with grouped fields ----------------------------
MIN_SIZE_MM = 10.0
MAX_SIZE_MM = 20.0

def scale_size(value, vmin, vmax, smin, smax):
    if vmax == vmin:
        return (smin + smax) / 2
    return smin + ((value - vmin) / (vmax - vmin)) * (smax - smin)

for fname in os.listdir(GEOJSON_FOLDER):
    if not fname.endswith(".geojson"):
        continue

    fpath = os.path.join(GEOJSON_FOLDER, fname)
    state = fname.replace(".geojson", "")

    with open(fpath, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Grouped power sums (5 main + Others)
    power_by_group = {g: 0.0 for g in GROUP_ORDER}
    coords = []

    for feat in data.get("features", []):
        props = feat.get("properties", {})
        geom = feat.get("geometry", {})
        coord = geom.get("coordinates")
        if coord:
            coords.append(coord)

        code = str(props.get("Energietraeger", "")).strip()
        group = map_code_to_group(code)
        power_by_group[group] += parse_kw(props.get("Bruttoleistung", 0))

    if not coords:
        print(f"❌ No coordinates in {state}")
        continue

    avg_x = sum(c[0] for c in coords) / len(coords)
    avg_y = sum(c[1] for c in coords) / len(coords)
    centroid = QgsGeometry.fromPointXY(QgsPointXY(avg_x, avg_y))

    total_power = state_totals.get(state, 0.0)

    # --- compute scaled size once (constant per state) ---
    size_mm = scale_size(total_power, min_total, max_total, MIN_SIZE_MM, MAX_SIZE_MM)

    # ✅ Build memory layer with grouped fields (order matters for pie renderer)
    layer = QgsVectorLayer("Point?crs=EPSG:4326", f"state_pie_{state}", "memory")
    provider = layer.dataProvider()

    # one field per GROUP_ORDER + meta fields
    provider.addAttributes([QgsField(g, QVariant.Double) for g in GROUP_ORDER])
    provider.addAttributes([
        QgsField("StateTotalPower", QVariant.Double),
        QgsField("DE_MaxTotalPower", QVariant.Double),
        QgsField("DE_MinTotalPower", QVariant.Double),
        QgsField("DiagramSizeMM", QVariant.Double)
    ])
    layer.updateFields()

    feat = QgsFeature()
    feat.setGeometry(centroid)
    feat.setAttributes(
        [power_by_group[g] for g in GROUP_ORDER] +
        [total_power, max_total, min_total, size_mm]
    )
    provider.addFeature(feat)
    layer.updateExtents()

    QgsProject.instance().addMapLayer(layer)
    print(f"🎨 {state}: Total={total_power:.0f}, Size={size_mm:.1f} mm (constant)")

# Tip (QGIS side):
# - Use 'Pie Chart' renderer on each 'state_pie_*' layer.
# - Set the slices to fields in GROUP_ORDER (same order), and assign GROUP_COLORS.
# - Set size = data-defined using 'DiagramSizeMM' (map units: millimeters).





####
### Filename: 14_1_load_geojson_states_as_layers.py
### Purpose: Build one file-backed point layer per state (for QGIS pie charts).
###          Writes layers into a single GeoPackage safely on QGIS 3.10:
###          - Write all layers first (no loading while writing)
###          - First layer: CreateOrOverwriteFile, others: CreateOrOverwriteLayer
###          - Then load all saved layers into a group.
##
##import os, json, re
##from qgis.core import (
##    QgsProject, QgsFeature, QgsGeometry, QgsPointXY, QgsField,
##    QgsVectorLayer, QgsVectorFileWriter, QgsCoordinateTransformContext
##)
##from PyQt5.QtCore import QVariant
##
### --- Input & output -----------------------------------------------------------
##GEOJSON_FOLDER = r"C:/Users/jo73vure/Desktop/powerPlantProject/data/geojson/by_state_three_checks"
##OUTPUT_GPKG    = r"C:/Users/jo73vure/Desktop/powerPlantProject/data/derived/state_pies.gpkg"
##GROUP_NAME     = "state_pie_layers (file)"
##
### --- Grouping (5 main + Others) ----------------------------------------------
##PRIMARY_TYPES = {"2495":"Photovoltaics","2497":"Onshore Wind","2498":"Hydropower","2493":"Biogas","2496":"Battery"}
##GROUP_ORDER   = ["Photovoltaics","Onshore Wind","Hydropower","Biogas","Battery","Others"]
##
##def map_code_to_group(code: str) -> str:
##    return PRIMARY_TYPES.get(code, "Others")
##
##def parse_kw(v):
##    try: return float(str(v).replace(",", "."))
##    except: return 0.0
##
### --- Clean up any layers already pointing to this GPKG (avoid file locks) -----
##proj = QgsProject.instance()
##for lyr in list(proj.mapLayers().values()):
##    try:
##        if lyr and OUTPUT_GPKG.lower() in lyr.source().lower():
##            proj.removeMapLayer(lyr.id())
##    except Exception:
##        pass
##
### --- Compute totals for size scaling ------------------------------------------
##state_totals = {}
##for fname in os.listdir(GEOJSON_FOLDER):
##    if fname.endswith(".geojson"):
##        with open(os.path.join(GEOJSON_FOLDER, fname), "r", encoding="utf-8") as f:
##            data = json.load(f)
##        total = sum(parse_kw(ft.get("properties",{}).get("Bruttoleistung",0)) for ft in data.get("features",[]))
##        state_totals[fname.replace(".geojson","")] = total
##
##max_total = max(state_totals.values()) if state_totals else 0.0
##min_total = min(state_totals.values()) if state_totals else 0.0
##print(f"🌍 Max total={max_total:.0f}, Min total={min_total:.0f}")
##
##MIN_SIZE_MM, MAX_SIZE_MM = 10.0, 20.0
##def scale_size(v, vmin, vmax, smin, smax):
##    if vmax == vmin: return (smin+smax)/2
##    return smin + ((v-vmin)/(vmax-vmin))*(smax-smin)
##
### --- Ensure output folder exists ----------------------------------------------
##os.makedirs(os.path.dirname(OUTPUT_GPKG), exist_ok=True)
##
### --- PASS A: WRITE all layers to GPKG (do not load yet) -----------------------
##ctx  = QgsProject.instance().transformContext()
##file_exists = os.path.exists(OUTPUT_GPKG)
##saved_layer_names = []
##
##for fname in sorted(os.listdir(GEOJSON_FOLDER)):
##    if not fname.endswith(".geojson"): 
##        continue
##    fpath = os.path.join(GEOJSON_FOLDER, fname)
##    state = fname.replace(".geojson","")
##    safe_state = re.sub(r"[^A-Za-z0-9_]+","_", state)  # gpkg layer name safe
##    layer_name = f"state_pie_{safe_state}"
##
##    with open(fpath, "r", encoding="utf-8") as f:
##        data = json.load(f)
##
##    power = {g:0.0 for g in GROUP_ORDER}
##    coords = []
##    for ft in data.get("features",[]):
##        pr = ft.get("properties",{})
##        gm = ft.get("geometry",{}) or {}
##        c  = gm.get("coordinates")
##        if c: coords.append(c)
##        power[map_code_to_group(str(pr.get("Energietraeger","")).strip())] += parse_kw(pr.get("Bruttoleistung",0))
##
##    if not coords:
##        print(f"❌ No coordinates in {state}")
##        continue
##
##    avg_x = sum(c[0] for c in coords)/len(coords)
##    avg_y = sum(c[1] for c in coords)/len(coords)
##    centroid = QgsGeometry.fromPointXY(QgsPointXY(avg_x, avg_y))
##    total_power = state_totals.get(state, 0.0)
##    size_mm = scale_size(total_power, min_total, max_total, MIN_SIZE_MM, MAX_SIZE_MM)
##
##    # build a tiny memory layer just to feed the writer
##    mem = QgsVectorLayer("Point?crs=EPSG:4326", "tmp", "memory")
##    prv = mem.dataProvider()
##    prv.addAttributes([QgsField(g, QVariant.Double) for g in GROUP_ORDER])
##    prv.addAttributes([
##        QgsField("StateTotalPower", QVariant.Double),
##        QgsField("DE_MaxTotalPower", QVariant.Double),
##        QgsField("DE_MinTotalPower", QVariant.Double),
##        QgsField("DiagramSizeMM", QVariant.Double),
##        QgsField("State", QVariant.String),
##    ])
##    mem.updateFields()
##
##    feat = QgsFeature(mem.fields())
##    feat.setGeometry(centroid)
##    feat.setAttributes([power[g] for g in GROUP_ORDER] + [total_power, max_total, min_total, size_mm, state])
##    prv.addFeature(feat)
##    mem.updateExtents()
##
##    # writer options: first layer -> overwrite FILE, others -> overwrite LAYER
##    opts = QgsVectorFileWriter.SaveVectorOptions()
##    opts.driverName = "GPKG"
##    opts.layerName  = layer_name
##    if not file_exists:
##        opts.actionOnExistingFile = QgsVectorFileWriter.CreateOrOverwriteFile
##        file_exists = True
##    else:
##        opts.actionOnExistingFile = QgsVectorFileWriter.CreateOrOverwriteLayer
##
##    err, msg = QgsVectorFileWriter.writeAsVectorFormatV2(mem, OUTPUT_GPKG, ctx, opts)
##    if err != QgsVectorFileWriter.NoError:
##        raise RuntimeError(f"Failed to save layer {state}: {msg}")
##
##    saved_layer_names.append(layer_name)
##    print(f"📦 Saved: {layer_name}")
##
### --- PASS B: LOAD the saved layers into a group -------------------------------
##root = QgsProject.instance().layerTreeRoot()
##old = root.findGroup(GROUP_NAME)
##if old: root.removeChildNode(old)
##group = root.addGroup(GROUP_NAME)
##
##for lname in saved_layer_names:
##    uri = f"{OUTPUT_GPKG}|layername={lname}"
##    lyr = QgsVectorLayer(uri, lname, "ogr")
##    if not lyr.isValid():
##        print(f"⚠️ Could not load {lname} from GeoPackage.")
##        continue
##    QgsProject.instance().addMapLayer(lyr, False)
##    group.addLayer(lyr)
##
##print(f"✅ Done. Loaded {len(saved_layer_names)} file-backed layers into '{GROUP_NAME}'.")
### Styling tip:
### - Use 'Pie Chart' renderer, slices = GROUP_ORDER fields, size = DiagramSizeMM (mm).
##