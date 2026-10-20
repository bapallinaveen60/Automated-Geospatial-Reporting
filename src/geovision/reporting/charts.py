"""Report charts rendered as SVG (vector, text converted to paths so Typst needs no fonts)."""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from geovision.contracts.metrics import MetricsPayload  # noqa: E402

plt.rcParams.update({"svg.fonttype": "path", "font.size": 9})

# ESA WorldCover legend colours (match carto/styles/worldcover.qml).
WORLDCOVER_COLOURS = {
    10: "#006400",
    20: "#ffbb22",
    30: "#ffff4c",
    40: "#f096ff",
    50: "#fa0000",
    60: "#b4b4b4",
    70: "#f0f0f0",
    80: "#0064c8",
    90: "#0096a0",
    95: "#00cf75",
    100: "#fae6a0",
}
INK = "#344054"


def lulc_bar_chart(metrics: MetricsPayload, out: Path) -> Path | None:
    """Horizontal bar chart of land-cover shares inside the site, largest first."""
    if not metrics.lulc:
        return None
    shares = sorted(metrics.lulc, key=lambda c: c.percent)
    fig, ax = plt.subplots(figsize=(6.2, 0.38 * len(shares) + 0.6))
    bars = ax.barh(
        [c.label for c in shares],
        [c.percent for c in shares],
        color=[WORLDCOVER_COLOURS.get(c.code, "#98a2b3") for c in shares],
        edgecolor="#667085",
        linewidth=0.4,
        height=0.65,
    )
    for bar, c in zip(bars, shares, strict=True):
        ax.text(
            bar.get_width() + 1,
            bar.get_y() + bar.get_height() / 2,
            f"{c.percent:.1f}%  ({c.area_ha:.1f} ha)",
            va="center",
            color=INK,
        )
    ax.set_xlim(0, max(c.percent for c in shares) * 1.35 + 5)
    ax.set_xlabel("Share of site area (%)", color=INK)
    ax.tick_params(colors=INK, length=0)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color("#d0d5dd")
    ax.grid(axis="x", color="#eaecf0", linewidth=0.6)
    ax.set_axisbelow(True)
    fig.tight_layout()
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, format="svg", transparent=True)
    plt.close(fig)
    return out


def render_charts(metrics: MetricsPayload, out_dir: Path) -> list[dict[str, str]]:
    charts = []
    lulc = lulc_bar_chart(metrics, out_dir / "lulc_shares.svg")
    if lulc:
        charts.append({"key": "lulc", "title": "Land cover within the site", "path": str(lulc)})
    return charts
