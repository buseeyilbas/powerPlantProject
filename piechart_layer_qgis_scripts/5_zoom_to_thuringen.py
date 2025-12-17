# Filename: zoom_to_thuringia.py
# Purpose : Zoom the map canvas to the state of Thüringen using existing admin layers if possible,
#           otherwise fall back to a WGS84 bounding box. All comments and the filename are in English.

from qgis.core import (
    QgsProject,
    QgsRectangle,
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsWkbTypes,
)
from qgis.PyQt.QtCore import QVariant
import unicodedata

def _normalize_txt(s: str) -> str:
    """Normalize text for reliable comparisons (strip accents, lowercase)."""
    if s is None:
        return ""
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    return s.lower().strip()

def zoom_to_thuringia():
    project = QgsProject.instance()
    canvas = iface.mapCanvas()
    target_crs = project.crs()

    # 1) Try to find Thüringen from any polygon admin layer
    thuringia_names = {"thuringen", "thueringen", "thuringia", "thüringen"}
    candidate_field_names = [
        "NAME_1", "NAME", "GEN", "LAN", "BUNDESLAND", "STATE", "NAME_DE", "NAME_EN"
    ]

    thuringia_extent = None

    for layer in project.mapLayers().values():
        # Only vector polygon layers
        if getattr(layer, "geometryType", None) and layer.geometryType() == QgsWkbTypes.PolygonGeometry:
            # Find a plausible name field on this layer
            layer_fields = {f.name(): f for f in layer.fields()}
            name_field = None
            for fn in candidate_field_names:
                if fn in layer_fields:
                    name_field = fn
                    break
            if name_field is None:
                # Try a heuristic: any string field that looks like a name field
                for f in layer.fields():
                    if f.type() == QVariant.String and f.name().lower() in {"name", "gen", "bez", "bezirk", "land"}:
                        name_field = f.name()
                        break

            if name_field is None:
                continue

            # Iterate features to find Thüringen
            found_geoms = []
            for feat in layer.getFeatures():
                val = _normalize_txt(feat[name_field]) if name_field in feat.fields().names() else ""
                if any(n in val for n in thuringia_names):
                    g = feat.geometry()
                    if g and not g.isEmpty():
                        found_geoms.append(g)

            if found_geoms:
                # Combine extents of all matching parts (multi-polygons, dissolved borders, etc.)
                e = found_geoms[0].boundingBox()
                for g in found_geoms[1:]:
                    e.combineExtentWith(g.boundingBox())
                thuringia_extent = e
                # We found it; no need to scan more layers
                break

    # 2) Transform and zoom (or use a WGS84 fallback bbox)
    if thuringia_extent is not None:
        src_crs = layer.crs()  # CRS of the layer where we found Thüringen
        if src_crs != target_crs:
            xform = QgsCoordinateTransform(src_crs, target_crs, project)
            thuringia_extent = xform.transformBoundingBox(thuringia_extent)
        canvas.setExtent(thuringia_extent)
        canvas.refresh()
        print("🔍 Zoomed to Thüringen (from layer geometry).")
        return

    # 3) Fallback: use a conservative WGS84 bbox around Thüringen
    # (approximate: lon 9.9–12.7, lat 50.1–51.7)
    extent_wgs84 = QgsRectangle(9.9, 50.1, 12.7, 51.7)
    crs_wgs84 = QgsCoordinateReferenceSystem("EPSG:4326")
    if crs_wgs84 != target_crs:
        xform = QgsCoordinateTransform(crs_wgs84, target_crs, project)
        extent_proj = xform.transformBoundingBox(extent_wgs84)
    else:
        extent_proj = extent_wgs84

    canvas.setExtent(extent_proj)
    canvas.refresh()
    print("🔍 Zoomed to Thüringen (WGS84 fallback bbox).")

# Run it
zoom_to_thuringia()
