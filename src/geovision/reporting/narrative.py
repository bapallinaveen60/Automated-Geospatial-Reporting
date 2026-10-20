"""Templated, deterministic narrative sentences for the executive summary.

No language model: every sentence is a fixed template filled from the metrics, so the text is
reproducible and the reviewer can trace each statement to a number in the report.
"""

from geovision.contracts.metrics import MetricsPayload

LAYER_NOUNS = {
    "protected_areas": "protected area",
    "wetlands_water": "water body or wetland",
    "forest": "mapped forest",
    "coastline": "coastline",
}


def _distance(m: float) -> str:
    return f"{m:,.0f} m" if m < 1000 else f"{m / 1000:.1f} km"


def vegetation_class(ndvi_median: float) -> str:
    if ndvi_median < 0.2:
        return "bare ground, built surfaces or water"
    if ndvi_median < 0.4:
        return "sparse to low vegetation"
    if ndvi_median < 0.6:
        return "moderate vegetation"
    return "dense vegetation"


def summary_paragraphs(metrics: MetricsPayload) -> list[str]:
    site = metrics.site
    out: list[str] = []

    where = ", ".join(p for p in (site.locality, site.district, site.state) if p)
    out.append(
        f"The site covers {site.area_ha:,.2f} ha ({site.area_ha * 2.47105:,.1f} acres)"
        + (f" near {where}" if where else "")
        + f", centred at {site.centroid_lat:.5f}° N, {site.centroid_lon:.5f}° E."
    )

    if metrics.lulc:
        top = metrics.lulc[:2]
        text = f"Land cover is dominated by {top[0].label.lower()} ({top[0].percent:.0f}%)"
        if len(top) > 1:
            text += f", followed by {top[1].label.lower()} ({top[1].percent:.0f}%)"
        out.append(text + ".")

    ndvi = metrics.indices.get("ndvi")
    if ndvi and ndvi.median is not None:
        out.append(
            f"Median NDVI in the current period is {ndvi.median:.2f}, typical of "
            f"{vegetation_class(ndvi.median)}."
        )
    ch = next((c for c in metrics.change if c.index == "ndvi"), None)
    if ch:
        out.append(
            f"Between the two periods NDVI fell by more than {ch.threshold:g} over "
            f"{ch.loss_ha:.2f} ha and rose by more than {ch.threshold:g} over {ch.gain_ha:.2f} ha."
        )

    for p in metrics.proximity:
        noun = LAYER_NOUNS.get(p.layer, p.layer.replace("_", " "))
        if p.distance_m is None:
            out.append(f"No {noun} is mapped within {_distance(p.search_radius_m)} of the site.")
        elif p.overlap_ha > 0:
            out.append(f"A {noun} overlaps the site ({p.overlap_ha:.2f} ha).")
        else:
            name = f" ({p.nearest_name})" if p.nearest_name else ""
            out.append(
                f"The nearest {noun}{name} lies {_distance(p.distance_m)} from the site boundary."
            )

    crit = sum(f.severity == "critical" for f in metrics.flags)
    warn = sum(f.severity == "warning" for f in metrics.flags)
    if crit or warn:
        out.append(
            f"Screening rules raised {crit} critical and {warn} warning item(s), "
            "listed below for the reviewer."
        )
    else:
        out.append("No screening rule was triggered.")
    return out
