"""End-to-end run of the Streamlit app with Earth Engine replaced by fakes."""
from pathlib import Path

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

from gw_dashboard import gee
from gw_dashboard.settings import load_settings

ROOT = Path(__file__).resolve().parent.parent
APP = str(ROOT / "streamlit_app.py")
FAKE_KEY = {
    "type": "service_account",
    "project_id": "demo-project-1",
    "private_key": "-----BEGIN PRIVATE KEY-----\nAAAA\n-----END PRIVATE KEY-----\n",
    "client_email": "viewer@demo-project-1.iam.gserviceaccount.com",
}
CFG = load_settings(ROOT / "settings.toml", secrets={}, env={})
MONTHS = ["2018-01", "2018-02", "2018-03"]


def fake_assets(folder):
    ids = []
    for p in CFG.parameter_keys:
        months = MONTHS[:-1] if p == CFG.parameter_keys[-1] else MONTHS   # last parameter misses one month
        ids += [f"{folder}/{p}_{m.replace('-', '_')}" for m in months]
    return ids + [f"{folder}/something_else"]


@pytest.fixture(autouse=True)
def fake_gee(monkeypatch):
    for var in ("GEE_SERVICE_ACCOUNT_JSON", "GOOGLE_APPLICATION_CREDENTIALS", "GEE_ASSET_FOLDER", "GEE_PROJECT"):
        monkeypatch.delenv(var, raising=False)
    st.cache_data.clear()
    st.cache_resource.clear()
    calls = {"series": 0}
    monkeypatch.setattr(gee, "initialize", lambda info, project=None: project or info["project_id"])
    monkeypatch.setattr(gee, "list_image_assets", fake_assets)
    monkeypatch.setattr(gee, "image_stats", lambda a, s: {"min": 1.0, "max": 250.0, "mean": 42.5, "p2": 2.0, "p98": 90.0})
    monkeypatch.setattr(gee, "tile_url", lambda a, lo, hi, pal: "https://example.test/{z}/{x}/{y}")

    def series(months, lat, lon, scale):
        calls["series"] += 1
        if lat > 80:  # "outside the study area"
            return [{"month": m, "value": None} for m in months]
        return [{"month": m, "value": float(i)} for i, m in enumerate(months)]

    monkeypatch.setattr(gee, "time_series", series)
    return calls


def run(secrets=None, **session):
    at = AppTest.from_file(APP, default_timeout=30)
    at.secrets["gee_credentials"] = FAKE_KEY if secrets is None else secrets
    for k, v in session.items():
        at.session_state[k] = v
    return at.run()


def texts(at):
    return " ".join(e.value for e in list(at.markdown) + list(at.caption) + list(at.info) + list(at.warning) + list(at.error))


def test_app_starts_and_shows_map_controls_and_stats():
    at = run()
    assert not at.exception, at.exception
    assert not at.error
    assert "Groundwater" in texts(at)
    assert at.selectbox(key="parameter_en").value == CFG.parameter_keys[0]
    assert at.selectbox(key="month").value == "2018-03"           # latest month by default
    values = [m.value for m in at.metric]
    assert values == ["1.00", "42.50", "250.0"]
    assert any("Click a location" in i.value for i in at.info)


def test_month_list_follows_parameter():
    at = run()
    at.selectbox(key="parameter_en").set_value(CFG.parameter_keys[-1]).run()
    assert not at.exception
    assert at.selectbox(key="month").options == MONTHS[:-1]
    assert at.selectbox(key="month").value == "2018-02"           # 2018-03 not available -> latest


def test_clicked_point_draws_time_series_and_download():
    at = run(point=(CFG.center_lat, CFG.center_lon))
    assert not at.exception, at.exception
    assert len(at.get("plotly_chart")) == 1
    assert len(at.get("download_button")) == 1


def test_point_without_data_shows_warning():
    at = run(point=(85.0, 10.0))
    assert not at.exception
    assert any("No data at this location" in w.value for w in at.warning)


def test_arabic_interface_keeps_choices():
    at = run()
    at.selectbox(key="parameter_en").set_value(CFG.parameter_keys[1]).run()
    at.selectbox(key="lang").set_value("ar").run()
    assert not at.exception
    assert "لوحة تحليل المياه الجوفية" in texts(at)
    sb = at.selectbox(key="parameter_ar")
    assert sb.options[0] == CFG.parameters[0].label_ar
    assert sb.value == CFG.parameter_keys[1]          # choice survives the language switch


def test_display_settings_survive_language_switch():
    at = run()
    at.slider(key="opacity").set_value(0.3).run()
    at.number_input(key="c_lat").set_value(31.5).run()
    at.selectbox(key="lang").set_value("ar").run()
    assert not at.exception
    assert at.slider(key="opacity").value == 0.3
    assert at.number_input(key="c_lat").value == 31.5


def test_extreme_zoom_in_settings_does_not_crash(tmp_path, monkeypatch):
    import gw_dashboard.settings as S
    text = (ROOT / "settings.toml").read_text(encoding="utf-8")
    import re
    custom = tmp_path / "settings.toml"
    custom.write_text(re.sub(r"zoom = \d+", "zoom = 18", text), encoding="utf-8")
    monkeypatch.setattr(S, "DEFAULT_SETTINGS_PATH", custom)
    at = run()
    assert not at.exception
    assert at.slider(key="zoom").value == 18


def test_missing_credentials_shows_friendly_error_not_crash():
    at = AppTest.from_file(APP, default_timeout=30).run()
    assert not at.exception
    assert any("credentials" in e.value.lower() for e in at.error)
    assert not at.metric


def test_bad_credentials_never_displays_private_key():
    bad = dict(FAKE_KEY, type="user", private_key="TOP-SECRET")
    at = run(secrets=bad)
    assert not at.exception
    page = texts(at) + " ".join(c.value for c in at.code)
    assert "TOP-SECRET" not in page
    assert at.error


def test_connection_failure_is_reported(monkeypatch):
    def boom(info, project=None):
        raise RuntimeError("Earth Engine API has not been used in project")
    monkeypatch.setattr(gee, "initialize", boom)
    at = run()
    assert not at.exception
    assert any("Could not connect" in e.value for e in at.error)


def test_empty_folder_warns(monkeypatch):
    monkeypatch.setattr(gee, "list_image_assets", lambda folder: [])
    at = run()
    assert not at.exception
    assert any("No images" in w.value for w in at.warning)


def test_asset_folder_override_from_secrets(monkeypatch):
    seen = []
    monkeypatch.setattr(gee, "list_image_assets", lambda folder: seen.append(folder) or fake_assets(folder))
    at = AppTest.from_file(APP, default_timeout=30)
    at.secrets["gee_credentials"] = FAKE_KEY
    at.secrets["gee"] = {"asset_folder": "projects/wateraccounting-gee/assets/GW_New"}
    at.run()
    assert not at.exception
    assert seen == ["projects/wateraccounting-gee/assets/GW_New"]
