"""Everything that talks to Google Earth Engine (GEE).

The functions here take and return plain Python values (strings, numbers,
lists, dicts) so they are easy to cache in Streamlit and easy to test
without a network connection.
"""

from __future__ import annotations

import json
import re
from typing import Any, Iterable, Mapping

import ee

from .keys import (  # noqa: F401 - re-exported for the app and tools
    REQUIRED_KEY_FIELDS,
    SECRET_SECTIONS,
    CredentialsError,
    find_service_account,
    redact,
    validate_service_account,
)

# Asset names must end with _YYYY_MM, e.g. "abstraction_m3_2018_01".
ASSET_NAME_RE = re.compile(r"^(?P<param>[A-Za-z0-9_]+?)_(?P<year>\d{4})_(?P<month>\d{2})$")


# --------------------------------------------------------------------------- asset names

def parse_asset_name(asset_id: str) -> tuple[str, str] | None:
    """Return (parameter, 'YYYY-MM') for '.../abstraction_m3_2018_01', else None."""
    name = asset_id.rstrip("/").rsplit("/", 1)[-1]
    m = ASSET_NAME_RE.match(name)
    if not m:
        return None
    year, month = int(m["year"]), int(m["month"])
    if not (1900 <= year <= 2200 and 1 <= month <= 12):
        return None
    return m["param"], f"{year:04d}-{month:02d}"


def index_assets(asset_ids: Iterable[str], parameter_keys: Iterable[str]) -> dict[str, dict[str, str]]:
    """Group asset IDs as {parameter: {'YYYY-MM': asset_id}} (months sorted).

    Only exact parameter matches are kept, so 'abstraction_mm' and
    'abstraction_m3' can never be confused. Unknown names are ignored.
    """
    keys = list(parameter_keys)
    out: dict[str, dict[str, str]] = {k: {} for k in keys}
    for aid in asset_ids:
        parsed = parse_asset_name(aid)
        if parsed and parsed[0] in out:
            out[parsed[0]][parsed[1]] = aid
    return {k: dict(sorted(v.items())) for k, v in out.items()}


def unmatched_assets(asset_ids: Iterable[str], parameter_keys: Iterable[str]) -> list[str]:
    """Asset names that the dashboard will ignore (useful for diagnostics)."""
    keys = set(parameter_keys)
    bad = []
    for aid in asset_ids:
        parsed = parse_asset_name(aid)
        if not parsed or parsed[0] not in keys:
            bad.append(aid.rsplit("/", 1)[-1])
    return bad


# --------------------------------------------------------------------------- credentials

def initialize(info: Mapping[str, Any], project: str | None = None) -> str:
    """Initialise Earth Engine with a service account. Returns the project used.

    Errors are re-raised with the private key removed from the message, because
    some google-auth errors echo the whole key back.
    """
    project = project or info.get("project_id")
    try:
        credentials = ee.ServiceAccountCredentials(info["client_email"], key_data=json.dumps(dict(info)))
    except Exception:  # noqa: BLE001 - never chain: the original message may contain the key
        raise CredentialsError(
            "The private_key could not be read. Paste it again exactly as in the JSON key file "
            "(all lines, between triple quotes)."
        ) from None
    try:
        ee.Initialize(credentials, project=project)
        ee.Number(1).getInfo()  # cheap round-trip to prove the credentials work
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(redact(f"{exc.__class__.__name__}: {exc}")) from None
    return str(project) if project else "(service-account default)"


# --------------------------------------------------------------------------- data access

def list_image_assets(folder: str) -> list[str]:
    """IDs of all images directly inside an Earth Engine folder (handles paging)."""
    resp = ee.data.listAssets({"parent": folder})
    return [a["id"] for a in resp.get("assets", []) if a.get("type", "IMAGE") == "IMAGE"]


def _first_band(asset_id: str) -> ee.Image:
    # Band names differ between datasets ("b1", "abstraction_m3", ...): always use band 0.
    return ee.Image(asset_id).select([0], ["value"])


def image_stats(asset_id: str, scale: float) -> dict[str, float | None]:
    """min / max / mean and the 2nd & 98th percentiles of one image."""
    img = _first_band(asset_id)
    reducer = (
        ee.Reducer.minMax()
        .combine(reducer2=ee.Reducer.mean(), sharedInputs=True)
        .combine(reducer2=ee.Reducer.percentile([2, 98]), sharedInputs=True)
    )
    d = img.reduceRegion(
        reducer=reducer, geometry=img.geometry(), scale=scale, maxPixels=1e10, bestEffort=True
    ).getInfo() or {}
    return {
        "min": d.get("value_min"),
        "max": d.get("value_max"),
        "mean": d.get("value_mean"),
        "p2": d.get("value_p2"),
        "p98": d.get("value_p98"),
    }


def colour_range(stats: Mapping[str, float | None], vis_min: float | None = None, vis_max: float | None = None) -> tuple[float, float]:
    """Choose legend limits: fixed limits if configured, else the 2-98 % stretch."""
    if vis_min is not None and vis_max is not None:
        return float(vis_min), float(vis_max)
    lo, hi = stats.get("p2"), stats.get("p98")
    if lo is None or hi is None or hi <= lo:
        lo, hi = stats.get("min"), stats.get("max")
    if lo is None or hi is None:
        return 0.0, 1.0
    lo, hi = float(lo), float(hi)
    if hi <= lo:
        hi = lo + 1.0
    return lo, hi


def tile_url(asset_id: str, vmin: float, vmax: float, palette: tuple[str, ...]) -> str:
    """XYZ tile URL for showing an image on a Leaflet / folium map."""
    vis = {"min": vmin, "max": vmax, "palette": [c.lstrip("#") for c in palette]}
    map_id = _first_band(asset_id).getMapId(vis)
    return map_id["tile_fetcher"].url_format


def time_series(months: Mapping[str, str], lat: float, lon: float, scale: float) -> list[dict[str, Any]]:
    """Value at one point for every month. months = {'YYYY-MM': asset_id}.

    Returns [{'month': 'YYYY-MM', 'value': float | None}, ...] sorted by month.
    One Earth Engine request for the whole series.
    """
    if not months:
        return []
    point = ee.Geometry.Point([lon, lat])
    images = [_first_band(aid).set("month", ym) for ym, aid in months.items()]

    def sample(img):
        value = img.reduceRegion(reducer=ee.Reducer.first(), geometry=point, scale=scale).get("value")
        return ee.Feature(None, {"month": img.get("month"), "value": value})

    info = ee.ImageCollection.fromImages(images).map(sample).getInfo()
    rows = []
    for feat in info.get("features", []):
        props = feat.get("properties", {})
        v = props.get("value")
        rows.append({"month": props.get("month"), "value": None if v is None else float(v)})
    rows.sort(key=lambda r: r["month"] or "")
    return rows
