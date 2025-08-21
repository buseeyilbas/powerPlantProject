import os
from qgis.core import QgsProject, QgsVectorFileWriter

# 📂 Output directory
OUTPUT_DIR = r"C:\Users\jo73vure\Desktop\powerPlantProject\qgis_map_files\piechart_landkreis_statewise"
os.makedirs(OUTPUT_DIR, exist_ok=True)

project = QgsProject.instance()
layers = project.mapLayers().values()


for layer in layers:
    name = layer.name()
    if not name.startswith("landkreis_pie_"):
        continue

    # GeoPackage path
    gpkg_path = os.path.join(OUTPUT_DIR, f"{name}.gpkg")

    # Export features as GeoPackage
    options = QgsVectorFileWriter.SaveVectorOptions()
    options.driverName = "GPKG"
    options.layerName = name
    options.actionOnExistingFile = QgsVectorFileWriter.CreateOrOverwriteFile

    error = QgsVectorFileWriter.writeAsVectorFormatV2(
        layer,
        gpkg_path,
        project.transformContext(),
        options
    )
    if error[0] == QgsVectorFileWriter.NoError:
        print(f"✅ Saved {name} → {gpkg_path}")
    else:
        print(f"❌ Error saving {name}: {error}")

    # Export style (QML) alongside GeoPackage
    qml_path = os.path.join(OUTPUT_DIR, f"{name}.qml")
    ok, err = layer.saveNamedStyle(qml_path)
    if ok:
        print(f"🎨 Style saved {name} → {qml_path}")
    else:
        print(f"⚠️ Could not save style for {name}: {err}")
