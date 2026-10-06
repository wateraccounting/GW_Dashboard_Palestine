"""settings.toml loading, validation and overrides."""
from pathlib import Path

import pytest

from gw_dashboard.settings import SettingsError, load_settings, validate_asset_folder

ROOT = Path(__file__).resolve().parent.parent

GOOD = """
[site]
country_en = "Testland"
region_en = "Test valley"
[gee]
asset_folder = "projects/test-project-123/assets/GW_Test"
[map]
center_lat = 31.9
center_lon = 35.4
zoom = 11
[[parameters]]
key = "recharge"
label_en = "Recharge"
unit = "mm"
palette = ["#ff0000", "#00ff00"]
"""


def write(tmp_path, text):
    p = tmp_path / "settings.toml"
    p.write_text(text, encoding="utf-8")
    return p


def test_repository_settings_file_is_valid():
    cfg = load_settings(ROOT / "settings.toml", secrets={}, env={})
    assert cfg.parameters, "at least one parameter"
    assert cfg.asset_folder.startswith(("projects/", "users/"))
    keys = cfg.parameter_keys
    assert len(set(keys)) == len(keys)


def test_minimal_settings(tmp_path):
    cfg = load_settings(write(tmp_path, GOOD), secrets={}, env={})
    assert cfg.asset_folder == "projects/test-project-123/assets/GW_Test"
    assert cfg.asset_folder_source == "settings.toml"
    assert cfg.zoom == 11 and cfg.pixel_scale_m == 20
    assert cfg.parameter("recharge").label("ar") == "Recharge"  # falls back to English
    assert cfg.place("en") == "Test valley, Testland"


def test_override_order_secrets_beat_env_beat_file(tmp_path):
    path = write(tmp_path, GOOD)
    env = {"GEE_ASSET_FOLDER": "projects/env-project-1/assets/F", "GEE_PROJECT": "env-project-1"}
    cfg = load_settings(path, secrets={}, env=env)
    assert cfg.asset_folder.endswith("env-project-1/assets/F") and cfg.gee_project == "env-project-1"
    secrets = {"gee": {"asset_folder": "projects/wa-project-9/assets/GW_X/", "project": "wa-project-9"}}
    cfg = load_settings(path, secrets=secrets, env=env)
    assert cfg.asset_folder == "projects/wa-project-9/assets/GW_X"  # trailing slash removed
    assert cfg.gee_project == "wa-project-9"
    assert "secrets" in cfg.asset_folder_source


@pytest.mark.parametrize("folder", [
    "projects/x/assets/F",                      # project id too short
    "projects/my-project-1/F",                  # missing /assets/
    "projects/my-project-1/assets",             # no folder
    "C:/Users/me/data",
    "",
])
def test_bad_asset_folders_rejected(folder):
    with pytest.raises(SettingsError):
        validate_asset_folder(folder)


def test_legacy_user_folder_accepted():
    assert validate_asset_folder("users/someone/GW_Analysis_Jafr") == "users/someone/GW_Analysis_Jafr"


@pytest.mark.parametrize("bad, fragment", [
    (GOOD.replace('palette = ["#ff0000", "#00ff00"]', 'palette = ["red"]'), "palette"),
    (GOOD.replace('center_lat = 31.9', 'center_lat = 200'), "center_lat"),
    (GOOD.replace('key = "recharge"', 'key = "re charge"'), "letters"),
    (GOOD.replace('unit = "mm"', 'unit = "mm"\nvis_min = 5'), "vis_max"),
    (GOOD.replace('asset_folder = "projects/test-project-123/assets/GW_Test"', ''), "asset_folder"),
    (GOOD + GOOD[GOOD.index("[[parameters]]"):], "unique"),
    ("this is = = not toml", "TOML"),
])
def test_invalid_settings_give_clear_errors(tmp_path, bad, fragment):
    with pytest.raises(SettingsError, match=fragment):
        load_settings(write(tmp_path, bad), secrets={}, env={})


def test_missing_file(tmp_path):
    with pytest.raises(SettingsError, match="Cannot find"):
        load_settings(tmp_path / "nope.toml", secrets={}, env={})
