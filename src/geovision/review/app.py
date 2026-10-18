"""Human-in-the-loop review app (Phase 6 scaffold).

Run:  uv run --extra review streamlit run src/geovision/review/app.py
"""

from pathlib import Path

import streamlit as st

from geovision.core.config import get_settings

st.set_page_config(page_title="GeoVision review", layout="wide")
st.title("Pending report drafts")

root = Path(get_settings().data_root)
drafts = sorted(root.glob("*/metrics/metrics.json")) if root.exists() else []
if not drafts:
    st.info(f"No drafts found under {root}.")
for path in drafts:
    project_id = path.parts[-3]
    with st.expander(project_id):
        st.json(path.read_text(encoding="utf-8"))
        # TODO(Phase 6): PDF preview, map with COG overlays, flag overrides, approval + audit log.
