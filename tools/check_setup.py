"""Check that credentials, settings and Earth Engine data are ready.

Run from the repository folder:

    python tools/check_setup.py

It reads .streamlit/secrets.toml (or the environment variables
GEE_SERVICE_ACCOUNT_JSON / GOOGLE_APPLICATION_CREDENTIALS), connects to
Earth Engine, lists the data folder and tests one map, one statistic and
one time series. The private key is never printed.

Exit code 0 = everything OK, 1 = something needs fixing.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib  # type: ignore[no-redef]

from gw_dashboard import gee  # noqa: E402
from gw_dashboard.settings import SettingsError, load_settings  # noqa: E402

OK, BAD, WARN = "  [OK]  ", "  [FAIL]", "  [WARN]"


def num(v) -> str:
    return "–" if v is None else f"{float(v):.2f}"


def month_gaps(months: list[str]) -> list[str]:
    """Months missing between the first and last available month."""
    if not months:
        return []
    y, m = map(int, months[0].split("-"))
    end = months[-1]
    have, gaps = set(months), []
    while f"{y:04d}-{m:02d}" <= end:
        key = f"{y:04d}-{m:02d}"
        if key not in have:
            gaps.append(key)
        m += 1
        if m == 13:
            y, m = y + 1, 1
    return gaps


def main() -> int:
    print("\nGroundwater dashboard – setup check\n" + "=" * 40)
    secrets_file = ROOT / ".streamlit" / "secrets.toml"
    secrets = {}
    if secrets_file.exists():
        try:
            secrets = tomllib.loads(secrets_file.read_text(encoding="utf-8"))
            print(f"{OK} found {secrets_file.relative_to(ROOT)}")
        except tomllib.TOMLDecodeError as exc:
            print(f"{BAD} {secrets_file.relative_to(ROOT)} is not valid TOML: {exc}")
            return 1
    else:
        print(f"{WARN} no .streamlit/secrets.toml – will look at environment variables")

    # 1. settings
    try:
        cfg = load_settings(secrets=secrets)
    except SettingsError as exc:
        print(f"{BAD} settings: {exc}")
        return 1
    print(f"{OK} settings.toml: {cfg.region_en}, {cfg.country_en}")
    print(f"        data folder: {cfg.asset_folder}  (from {cfg.asset_folder_source})")

    # 2. credentials
    try:
        info, source = gee.find_service_account(secrets=secrets)
    except gee.CredentialsError as exc:
        print(f"{BAD} credentials: {exc}")
        return 1
    print(f"{OK} credentials from {source}: {info['client_email']}")

    # 3. connect
    try:
        project = gee.initialize(info, cfg.gee_project)
    except Exception as exc:  # noqa: BLE001
        print(f"{BAD} could not connect to Earth Engine: {gee.redact(str(exc))}")
        print("        Check: Earth Engine API enabled and project registered for Earth Engine;")
        print("        service account has the roles 'Earth Engine Resource Viewer' and 'Service Usage Consumer'.")
        return 1
    print(f"{OK} connected to Earth Engine (project {project})")

    # 4. assets
    try:
        ids = gee.list_image_assets(cfg.asset_folder)
    except Exception as exc:  # noqa: BLE001
        print(f"{BAD} cannot list {cfg.asset_folder}: {gee.redact(str(exc))}")
        print("        Does the folder exist, and can this service account read it?")
        return 1
    catalogue = gee.index_assets(ids, cfg.parameter_keys)
    print(f"{OK} {len(ids)} images in the data folder")
    failed = False
    for p in cfg.parameters:
        months = list(catalogue[p.key])
        if not months:
            print(f"{BAD} {p.key}: no images named {p.key}_YYYY_MM")
            failed = True
            continue
        gaps = month_gaps(months)
        line = f"{p.key}: {len(months)} months, {months[0]} -> {months[-1]}"
        print((WARN if gaps else OK) + " " + line + (f"  (missing: {', '.join(gaps)})" if gaps else ""))
    ignored = gee.unmatched_assets(ids, cfg.parameter_keys)
    if ignored:
        print(f"{WARN} {len(ignored)} images ignored (name not <parameter>_YYYY_MM): {', '.join(ignored[:8])}"
              + (" …" if len(ignored) > 8 else ""))
    if failed:
        return 1

    # 5. one real map, statistic and time series
    p = cfg.parameters[0]
    last_month, last_id = list(catalogue[p.key].items())[-1]
    try:
        stats = gee.image_stats(last_id, cfg.stats_scale_m)
        lo, hi = gee.colour_range(stats, p.vis_min, p.vis_max)
        print(f"{OK} statistics {p.key} {last_month}: min {num(stats['min'])}, mean {num(stats['mean'])}, max {num(stats['max'])}")
        url = gee.tile_url(last_id, lo, hi, p.palette)
        print(f"{OK} map tiles available ({url[:60]}…)")
        rows = gee.time_series(catalogue[p.key], cfg.center_lat, cfg.center_lon, cfg.pixel_scale_m)
        n = sum(r["value"] is not None for r in rows)
        print((OK if n else WARN) + f" time series at map centre: {n}/{len(rows)} months with data"
              + ("" if n else " (centre may fall outside the data – not an error)"))
    except Exception as exc:  # noqa: BLE001
        print(f"{BAD} Earth Engine computation failed: {gee.redact(str(exc))}")
        return 1

    print("\nAll checks passed – run:  streamlit run streamlit_app.py\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
