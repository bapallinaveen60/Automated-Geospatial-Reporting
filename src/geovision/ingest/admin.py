"""Administrative location (state / district) for a site via OSM Nominatim reverse geocoding.

One request per report, well inside Nominatim's usage policy (≤ 1 req/s, identifying
User-Agent). Names are for the report text only; map boundaries must still come from the
Survey of India.
"""

from dataclasses import dataclass
from typing import Any

import requests

from geovision import __version__
from geovision.contracts.lineage import InputRef

NOMINATIM_URL = "https://nominatim.openstreetmap.org/reverse"
USER_AGENT = f"GeoVision-site-screening/{__version__} (automated environmental screening)"


@dataclass(frozen=True)
class AdminLocation:
    state: str | None
    district: str | None
    village_or_town: str | None


def parse_address(address: dict[str, Any]) -> AdminLocation:
    """Pick Indian admin levels from a Nominatim ``address`` block."""
    return AdminLocation(
        state=address.get("state"),
        district=address.get("state_district") or address.get("county") or address.get("district"),
        village_or_town=(
            address.get("village")
            or address.get("town")
            or address.get("suburb")
            or address.get("city")
        ),
    )


def reverse_admin(lon: float, lat: float, timeout: float = 20) -> tuple[AdminLocation, InputRef]:
    resp = requests.get(
        NOMINATIM_URL,
        params={
            "lat": str(lat),
            "lon": str(lon),
            "format": "jsonv2",
            "zoom": "14",
            "addressdetails": "1",
        },
        headers={"User-Agent": USER_AGENT, "Accept-Language": "en"},
        timeout=timeout,
    )
    resp.raise_for_status()
    loc = parse_address(resp.json().get("address", {}))
    ref = InputRef(
        kind="vector_source",
        id="nominatim_reverse",
        href=NOMINATIM_URL,
        licence="ODbL 1.0 (© OpenStreetMap contributors)",
        extra={"lon": round(lon, 6), "lat": round(lat, 6)},
    )
    return loc, ref
