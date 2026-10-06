"""Load the dashboard settings.

Everything that differs between countries lives in ``settings.toml`` at the
repository root. Two values can also be overridden *without touching the
code or the repository*, from the Streamlit "Secrets" box (or environment
variables when running somewhere else):

    [gee]
    asset_folder = "projects/<your-gee-project>/assets/<folder>"
    project      = "<your-gee-project>"     # optional

This is what makes moving to a new Earth Engine account a settings change
instead of a code change.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

try:  # Python 3.11+
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python 3.10 fallback
    import tomli as tomllib  # type: ignore[no-redef]


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SETTINGS_PATH = REPO_ROOT / "settings.toml"

# Earth Engine asset folders look like
#   projects/<cloud-project-id>/assets/<folder>[/<sub-folder>...]
#   users/<user-name>/<folder>          (legacy)
ASSET_FOLDER_RE = re.compile(
    r"^(projects/[a-z][a-z0-9-]{4,28}[a-z0-9]/assets|users/[A-Za-z0-9_.-]+)(/[A-Za-z0-9_.-]+)+$"
)
HEX_COLOUR_RE = re.compile(r"^#[0-9a-fA-F]{6}$")


class SettingsError(ValueError):
    """Raised when settings.toml (or an override) is missing or invalid."""


@dataclass(frozen=True)
class Parameter:
    key: str            # must match the asset-name prefix, e.g. "abstraction_mm"
    label_en: str
    label_ar: str
    unit: str
    palette: tuple[str, ...]
    unit_ar: str = ""
    vis_min: float | None = None   # fixed colour-scale limits (optional)
    vis_max: float | None = None

    def label(self, lang: str) -> str:
        return self.label_ar if lang == "ar" else self.label_en

    def unit_label(self, lang: str) -> str:
        return (self.unit_ar or self.unit) if lang == "ar" else self.unit


@dataclass(frozen=True)
class Settings:
    country_en: str
    country_ar: str
    region_en: str
    region_ar: str
    asset_folder: str
    center_lat: float
    center_lon: float
    zoom: int
    parameters: tuple[Parameter, ...]
    gee_project: str | None = None
    pixel_scale_m: float = 20.0
    stats_scale_m: float = 100.0
    default_language: str = "en"
    organisation: str = ""
    contact: str = ""
    asset_folder_source: str = "settings.toml"

    def parameter(self, key: str) -> Parameter:
        for p in self.parameters:
            if p.key == key:
                return p
        raise KeyError(key)

    @property
    def parameter_keys(self) -> tuple[str, ...]:
        return tuple(p.key for p in self.parameters)

    def place(self, lang: str) -> str:
        if lang == "ar":
            return f"{self.region_ar}، {self.country_ar}"
        return f"{self.region_en}, {self.country_en}"


# --------------------------------------------------------------------------- helpers

def _require(table: Mapping[str, Any], key: str, where: str) -> Any:
    if key not in table or table[key] in (None, ""):
        raise SettingsError(f"settings.toml: '{key}' is missing in [{where}]")
    return table[key]


def _as_float(value: Any, name: str, lo: float, hi: float) -> float:
    try:
        f = float(value)
    except (TypeError, ValueError) as exc:
        raise SettingsError(f"settings.toml: '{name}' must be a number (got {value!r})") from exc
    if not lo <= f <= hi:
        raise SettingsError(f"settings.toml: '{name}' must be between {lo} and {hi} (got {f})")
    return f


def validate_asset_folder(folder: str, source: str = "settings") -> str:
    folder = (folder or "").strip().rstrip("/")
    if not ASSET_FOLDER_RE.match(folder):
        raise SettingsError(
            f"The Earth Engine asset folder from {source} does not look right: {folder!r}. "
            "Expected something like 'projects/my-gee-project/assets/GW_Analysis_Jericho'."
        )
    return folder


def _parse_parameter(raw: Mapping[str, Any], idx: int) -> Parameter:
    where = f"parameters #{idx + 1}"
    key = str(_require(raw, "key", where))
    if not re.fullmatch(r"[A-Za-z0-9_]+", key):
        raise SettingsError(f"settings.toml: parameter key {key!r} may only use letters, digits and '_'")
    palette = tuple(raw.get("palette") or ())
    if len(palette) < 2 or not all(HEX_COLOUR_RE.match(str(c)) for c in palette):
        raise SettingsError(f"settings.toml: parameter {key!r} needs a palette of at least two '#rrggbb' colours")
    vis_min = raw.get("vis_min")
    vis_max = raw.get("vis_max")
    if (vis_min is None) != (vis_max is None):
        raise SettingsError(f"settings.toml: parameter {key!r} must set both vis_min and vis_max, or neither")
    if vis_min is not None:
        vis_min = _as_float(vis_min, f"{key}.vis_min", -1e12, 1e12)
        vis_max = _as_float(vis_max, f"{key}.vis_max", -1e12, 1e12)
    if vis_min is not None and vis_min >= vis_max:
        raise SettingsError(f"settings.toml: parameter {key!r} needs vis_min < vis_max")
    return Parameter(
        key=key,
        label_en=str(raw.get("label_en", key)),
        label_ar=str(raw.get("label_ar", raw.get("label_en", key))),
        unit=str(raw.get("unit", "")),
        unit_ar=str(raw.get("unit_ar", "")),
        palette=palette,
        vis_min=None if vis_min is None else float(vis_min),
        vis_max=None if vis_max is None else float(vis_max),
    )


def _secret_section(secrets: Mapping[str, Any] | None, name: str) -> Mapping[str, Any]:
    if not secrets:
        return {}
    try:
        section = secrets.get(name) if hasattr(secrets, "get") else None
    except Exception:  # st.secrets raises if no secrets file exists
        return {}
    return section or {}


# --------------------------------------------------------------------------- public API

def load_settings(
    path: str | os.PathLike[str] | None = None,
    secrets: Mapping[str, Any] | None = None,
    env: Mapping[str, str] | None = None,
) -> Settings:
    """Read settings.toml and apply overrides (secrets first, then environment)."""
    path = Path(path) if path else DEFAULT_SETTINGS_PATH
    env = os.environ if env is None else env
    if not path.exists():
        raise SettingsError(f"Cannot find {path.name} next to the app.")
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        raise SettingsError(f"{path.name} is not valid TOML: {exc}") from exc

    site = data.get("site", {})
    gee = data.get("gee", {})
    mp = data.get("map", {})
    raw_params = data.get("parameters", [])
    if not raw_params:
        raise SettingsError("settings.toml: add at least one [[parameters]] block")

    params = tuple(_parse_parameter(p, i) for i, p in enumerate(raw_params))
    keys = [p.key for p in params]
    if len(set(keys)) != len(keys):
        raise SettingsError("settings.toml: parameter keys must be unique")

    # ---- asset folder & project: settings.toml < environment < Streamlit secrets
    asset_folder, source = _require(gee, "asset_folder", "gee"), "settings.toml"
    project = gee.get("project") or None
    if env.get("GEE_ASSET_FOLDER"):
        asset_folder, source = env["GEE_ASSET_FOLDER"], "environment variable GEE_ASSET_FOLDER"
    if env.get("GEE_PROJECT"):
        project = env["GEE_PROJECT"]
    sec = _secret_section(secrets, "gee")
    if sec.get("asset_folder"):
        asset_folder, source = sec["asset_folder"], "Streamlit secrets [gee]"
    if sec.get("project"):
        project = sec["project"]
    asset_folder = validate_asset_folder(str(asset_folder), source)

    lang = str(site.get("default_language", "en"))
    if lang not in ("en", "ar"):
        raise SettingsError("settings.toml: default_language must be 'en' or 'ar'")

    return Settings(
        country_en=str(_require(site, "country_en", "site")),
        country_ar=str(site.get("country_ar", site.get("country_en"))),
        region_en=str(_require(site, "region_en", "site")),
        region_ar=str(site.get("region_ar", site.get("region_en"))),
        asset_folder=asset_folder,
        asset_folder_source=source,
        gee_project=str(project) if project else None,
        center_lat=_as_float(_require(mp, "center_lat", "map"), "center_lat", -90, 90),
        center_lon=_as_float(_require(mp, "center_lon", "map"), "center_lon", -180, 180),
        zoom=int(_as_float(mp.get("zoom", 10), "zoom", 1, 18)),
        pixel_scale_m=_as_float(gee.get("pixel_scale_m", 20), "pixel_scale_m", 1, 100000),
        stats_scale_m=_as_float(gee.get("stats_scale_m", 100), "stats_scale_m", 1, 100000),
        parameters=params,
        default_language=lang,
        organisation=str(site.get("organisation", "")),
        contact=str(site.get("contact", "")),
    )
