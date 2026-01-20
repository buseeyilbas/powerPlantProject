# Filename: 2_style_landkreisPieChart.py
# Purpose : Load & style per-state Landkreis pie layers based ONLY on folder names
#           (NO spatial clipping, NO intersects with GADM). QGIS 3.10-safe.
#
# Expected layout:
#   BASE_DIR/
#     <state-slug>/
#       de_<state-slug>_landkreis_pie.geojson
#       (fallback pattern: de_*_landkreis_pie*.geojson)

from qgis.core import (
    QgsProject, QgsVectorLayer, QgsLayerTreeGroup,
    QgsCategorizedSymbolRenderer, QgsRendererCategory, QgsFillSymbol
)
from qgis.PyQt.QtGui import QColor
from pathlib import Path

# ---- SETTINGS ---------------------------------------------------------------
GROUP_NAME = "landkreis_pies"  # main group in the Layer Panel

BASE_DIR = Path(
    r"C:\Users\jo73vure\Desktop\powerPlantProject\data\geojson\pieCharts\nationwide_landkreis_pies"
)

PALETTE = {
    "pv_kw":      QColor(255,255,0,255),
    "battery_kw": QColor(148,87,235,255),
    "wind_kw":    QColor(173,216,230,255),
    "hydro_kw":   QColor(0,0,255,255),
    "biogas_kw":  QColor(0,190,0,255),
    "others_kw":  QColor(158,158,158,255),
}

# Optional pretty names for slugs (fallback = slug itself)
SLUG_TO_PRETTY = {
    "baden-wuerttemberg": "Baden-Württemberg",
    "bayern": "Bayern",
    "berlin": "Berlin",
    "brandenburg": "Brandenburg",
    "bremen": "Bremen",
    "hamburg": "Hamburg",
    "hessen": "Hessen",
    "mecklenburg-vorpommern": "Mecklenburg-Vorpommern",
    "niedersachsen": "Niedersachsen",
    "nordrhein-westfalen": "Nordrhein-Westfalen",
    "rheinland-pfalz": "Rheinland-Pfalz",
    "saarland": "Saarland",
    "sachsen": "Sachsen",
    "sachsen-anhalt": "Sachsen-Anhalt",
    "schleswig-holstein": "Schleswig-Holstein",
    "thueringen": "Thüringen",
}

# -----------------------------------------------------------------------------
proj = QgsProject.instance()
root = proj.layerTreeRoot()

def ensure_group(parent, name: str):
    grp = parent.findGroup(name)
    if grp is None:
        grp = parent.addGroup(name)
    return grp

def style_energy_type(lyr: QgsVectorLayer):
    cats = []
    for key, color in PALETTE.items():
        sym = QgsFillSymbol.createSimple({
            "color": f"{color.red()},{color.green()},{color.blue()},255",
            "outline_style": "no",
            "outline_color": "0,0,0,0",
            "outline_width": "0"
        })
        cats.append(QgsRendererCategory(key, sym, key))
    lyr.setRenderer(QgsCategorizedSymbolRenderer("energy_type", cats))
    lyr.triggerRepaint()

def load_state_layer(state_dir: Path, group: QgsLayerTreeGroup):
    """
    Load the state's pie layer by file name convention INSIDE this directory.
    Never clips by geometry; the directory decides the target state.
    """
    slug = state_dir.name
    # Prefer exact canonical filename:
    candidate = state_dir / f"de_{slug}_landkreis_pie.geojson"
    if not candidate.exists():
        # Fallback to any matching pattern in the folder
        matches = sorted(state_dir.glob("de_*_landkreis_pie*.geojson"))
        if not matches:
            print(f"[SKIP] No pie geojson in: {state_dir}")
            return
        candidate = matches[0]

    vl = QgsVectorLayer(str(candidate), SLUG_TO_PRETTY.get(slug, slug), "ogr")
    if not vl.isValid():
        print(f"[WARN] Invalid layer: {candidate}")
        return

    proj.addMapLayer(vl, False)
    group.addLayer(vl)
    style_energy_type(vl)
    print(f"[OK] Loaded: {slug} -> {candidate.name}")

def main():
    if not BASE_DIR.exists():
        raise Exception(f"[ERROR] BASE_DIR not found: {BASE_DIR}")

    # Create/clean main group
    g_main = ensure_group(root, GROUP_NAME)
    for ch in list(g_main.children()):
        g_main.removeChildNode(ch)

    # Iterate state folders ONLY (no top-level ALL)
    state_dirs = [p for p in BASE_DIR.iterdir() if p.is_dir()]
    if not state_dirs:
        raise Exception(f"[ERROR] No state folders under: {BASE_DIR}")

    # Load each state's pies from its own folder and attach directly under main group
    for st_dir in sorted(state_dirs, key=lambda p: p.name):
        load_state_layer(st_dir, g_main)

    print("✅ Folder-based state assignment complete (no spatial clipping).")

main()
