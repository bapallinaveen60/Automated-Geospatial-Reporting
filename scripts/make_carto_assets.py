"""Generate the standard map-plate layout template (.qpt) and layer styles (.qml).

The outputs in src/geovision/carto/{templates,styles} are committed. Re-run this after
changing the layout here, or open the .qpt in QGIS Desktop (Project > Layout Manager >
"Create from template") to fine-tune it by hand.

Run with QGIS's Python (Windows):
    "C:\\Program Files\\QGIS 3.44.15\\bin\\python-qgis-ltr.bat" scripts\\make_carto_assets.py
or inside the renderer image:
    docker run --rm -v "%cd%:/repo" -w /repo --entrypoint xvfb-run geovision-qgis:latest \
        -a python3 scripts/make_carto_assets.py
"""

import os
import sys
import tempfile
from pathlib import Path

if sys.platform.startswith("linux"):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from qgis.core import (  # noqa: E402
    Qgis,
    QgsApplication,
    QgsColorRampShader,
    QgsFillSymbol,
    QgsLayoutItemLabel,
    QgsLayoutItemLegend,
    QgsLayoutItemMap,
    QgsLayoutItemPage,
    QgsLayoutItemPicture,
    QgsLayoutItemScaleBar,
    QgsLayoutMeasurement,
    QgsLayoutPoint,
    QgsLayoutSize,
    QgsLegendStyle,
    QgsLineSymbol,
    QgsPrintLayout,
    QgsProject,
    QgsRasterLayer,
    QgsRasterShader,
    QgsReadWriteContext,
    QgsScaleBarSettings,
    QgsSingleBandPseudoColorRenderer,
    QgsSingleSymbolRenderer,
    QgsTextFormat,
    QgsUnitTypes,
    QgsVectorLayer,
)
from qgis.PyQt.QtGui import QColor, QFont  # noqa: E402

CARTO = Path(__file__).resolve().parent.parent / "src" / "geovision" / "carto"
TEMPLATES = CARTO / "templates"
STYLES = CARTO / "styles"

FONT = "Noto Sans"
INK = QColor("#1d2939")
MUTED = QColor("#667085")
MM = QgsUnitTypes.LayoutMillimeters


def _text(size: float, bold: bool = False, color: QColor = INK) -> QgsTextFormat:
    fmt = QgsTextFormat()
    font = QFont(FONT)
    font.setBold(bold)
    fmt.setFont(font)
    fmt.setSize(size)
    fmt.setSizeUnit(Qgis.RenderUnit.Points)
    fmt.setColor(color)
    return fmt


def _label(layout, item_id, text, x, y, w, h, fmt) -> QgsLayoutItemLabel:
    label = QgsLayoutItemLabel(layout)
    label.setId(item_id)
    label.setText(text)
    label.setTextFormat(fmt)
    label.attemptMove(QgsLayoutPoint(x, y, MM))
    label.attemptResize(QgsLayoutSize(w, h, MM))
    layout.addLayoutItem(label)
    return label


def build_a4_landscape(project: QgsProject) -> QgsPrintLayout:
    """A4 landscape: map on the left, legend / scale / notes panel on the right."""
    layout = QgsPrintLayout(project)
    layout.initializeDefaults()
    layout.setName("plate_a4_landscape")
    layout.pageCollection().page(0).setPageSize("A4", QgsLayoutItemPage.Landscape)

    _label(layout, "Title", "Plate title", 10, 7, 277, 9, _text(16, bold=True))
    _label(layout, "Subtitle", "Project · Site", 10, 16, 277, 6, _text(9, color=MUTED))

    m = QgsLayoutItemMap(layout)
    m.setId("MainMap")
    m.attemptMove(QgsLayoutPoint(10, 24, MM))
    m.attemptResize(QgsLayoutSize(205, 176, MM))
    m.setFrameEnabled(True)
    m.setFrameStrokeWidth(QgsLayoutMeasurement(0.3, MM))
    layout.addLayoutItem(m)

    north = QgsLayoutItemPicture(layout)
    north.setId("NorthArrow")
    north.setPicturePath(":/images/north_arrows/layout_default_north_arrow.svg")
    north.setLinkedMap(m)
    north.setNorthMode(QgsLayoutItemPicture.GridNorth)
    north.attemptMove(QgsLayoutPoint(200, 27, MM))
    north.attemptResize(QgsLayoutSize(12, 16, MM))
    layout.addLayoutItem(north)

    legend = QgsLayoutItemLegend(layout)
    legend.setId("Legend")
    legend.setTitle("Legend")
    legend.setLinkedMap(m)
    legend.setAutoUpdateModel(True)
    legend.setResizeToContents(True)
    legend.rstyle(QgsLegendStyle.Title).setTextFormat(_text(10, bold=True))
    legend.rstyle(QgsLegendStyle.Group).setTextFormat(_text(8, bold=True))
    legend.rstyle(QgsLegendStyle.Subgroup).setTextFormat(_text(8, bold=True))
    legend.rstyle(QgsLegendStyle.SymbolLabel).setTextFormat(_text(8))
    legend.setSymbolWidth(7)
    legend.setSymbolHeight(4)
    legend.attemptMove(QgsLayoutPoint(221, 24, MM))
    layout.addLayoutItem(legend)

    bar = QgsLayoutItemScaleBar(layout)
    bar.setId("ScaleBar")
    bar.setStyle("Single Box")
    bar.setLinkedMap(m)
    bar.applyDefaultSize()
    bar.setUnits(Qgis.DistanceUnit.Meters)
    bar.setUnitLabel("m")
    bar.setNumberOfSegments(2)
    bar.setNumberOfSegmentsLeft(0)
    bar.setSegmentSizeMode(QgsScaleBarSettings.SegmentSizeFitWidth)
    bar.setMinimumBarWidth(35)
    bar.setMaximumBarWidth(60)
    bar.setTextFormat(_text(7))
    bar.attemptMove(QgsLayoutPoint(221, 150, MM))
    layout.addLayoutItem(bar)

    _label(layout, "Notes", "Sources and notes", 221, 165, 66, 30, _text(6.5, color=MUTED))
    _label(
        layout,
        "Footer",
        "Footer",
        10,
        202,
        277,
        5,
        _text(6.5, color=MUTED),
    )
    return layout


def _save_vector_style(name: str, geom: str, renderer) -> None:
    layer = QgsVectorLayer(f"{geom}?crs=EPSG:4326", name, "memory")
    layer.setRenderer(renderer)
    msg, ok = layer.saveNamedStyle(str(STYLES / f"{name}.qml"))
    if not ok:
        raise RuntimeError(f"Failed to save style {name}: {msg}")


def _fill(**props) -> QgsSingleSymbolRenderer:
    return QgsSingleSymbolRenderer(QgsFillSymbol.createSimple(props))


def make_styles() -> None:
    STYLES.mkdir(parents=True, exist_ok=True)
    _save_vector_style(
        "aoi",
        "Polygon",
        _fill(color="0,0,0,0", style="no", outline_color="#d92d20", outline_width="0.8"),
    )
    _save_vector_style(
        "buffer",
        "Polygon",
        _fill(
            color="0,0,0,0",
            style="no",
            outline_color="#475467",
            outline_width="0.4",
            outline_style="dash",
        ),
    )
    _save_vector_style(
        "protected_areas",
        "Polygon",
        _fill(color="22,163,74,60", outline_color="#15803d", outline_width="0.4"),
    )
    _save_vector_style(
        "wetlands_water",
        "Polygon",
        _fill(color="37,99,235,90", outline_color="#1d4ed8", outline_width="0.3"),
    )
    _save_vector_style(
        "forest",
        "Polygon",
        _fill(color="101,163,13,70", outline_color="#4d7c0f", outline_width="0.3"),
    )
    _save_vector_style(
        "coastline",
        "LineString",
        QgsSingleSymbolRenderer(QgsLineSymbol.createSimple({"color": "#0e7490", "width": "0.6"})),
    )
    _save_ndvi_style()


def _save_ndvi_style() -> None:
    """Raster pseudocolour ramp for NDVI (-0.2 bare/water → 0.8 dense vegetation)."""
    from osgeo import gdal

    gdal.UseExceptions()

    tmp = Path(tempfile.mkdtemp()) / "ndvi.tif"
    ds = gdal.GetDriverByName("GTiff").Create(str(tmp), 2, 2, 1, gdal.GDT_Float32)
    ds.SetGeoTransform([0, 1, 0, 0, 0, -1])
    ds.SetProjection("EPSG:4326")
    ds = None
    layer = QgsRasterLayer(str(tmp), "NDVI", "gdal")
    stops = [
        (-0.2, "#a50026", "≤ -0.2 water / bare"),
        (0.1, "#f46d43", "0.1 sparse"),
        (0.3, "#fee08b", "0.3 low"),
        (0.5, "#a6d96a", "0.5 moderate"),
        (0.8, "#1a9850", "≥ 0.8 dense"),
    ]
    ramp = QgsColorRampShader(-0.2, 0.8)
    ramp.setColorRampType(QgsColorRampShader.Interpolated)
    ramp.setColorRampItemList(
        [QgsColorRampShader.ColorRampItem(v, QColor(c), lbl) for v, c, lbl in stops]
    )
    shader = QgsRasterShader()
    shader.setRasterShaderFunction(ramp)
    renderer = QgsSingleBandPseudoColorRenderer(layer.dataProvider(), 1, shader)
    renderer.setClassificationMin(-0.2)
    renderer.setClassificationMax(0.8)
    layer.setRenderer(renderer)
    msg, ok = layer.saveNamedStyle(str(STYLES / "ndvi.qml"))
    if not ok:
        raise RuntimeError(f"Failed to save NDVI style: {msg}")


def main() -> int:
    qgs = QgsApplication([], False)
    qgs.initQgis()
    try:
        TEMPLATES.mkdir(parents=True, exist_ok=True)
        layout = build_a4_landscape(QgsProject.instance())
        out = TEMPLATES / "plate_a4_landscape.qpt"
        if not layout.saveAsTemplate(str(out), QgsReadWriteContext()):
            raise RuntimeError(f"Failed to write {out}")
        print(f"wrote {out}")
        make_styles()
        print(f"wrote styles to {STYLES}")
    finally:
        qgs.exitQgis()
    return 0


if __name__ == "__main__":
    sys.exit(main())
