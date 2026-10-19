# Headless PyQGIS renderer for map plates.
# Runs geovision.carto.render (stdlib + qgis only) under a virtual frame buffer.
# Pinned to the QGIS LTR used for template design (keep in sync with local QGIS).
FROM qgis/qgis:3.44.15-noble

RUN apt-get update \
    && apt-get install -y --no-install-recommends xvfb fonts-dejavu-core fonts-noto-core \
    && rm -rf /var/lib/apt/lists/*

ENV QT_QPA_PLATFORM=offscreen \
    XDG_RUNTIME_DIR=/tmp/runtime-root \
    PYTHONPATH=/app/src

WORKDIR /app
COPY src/geovision/__init__.py ./src/geovision/__init__.py
COPY src/geovision/carto ./src/geovision/carto

ENTRYPOINT ["xvfb-run", "-a", "python3", "-m", "geovision.carto.render"]
