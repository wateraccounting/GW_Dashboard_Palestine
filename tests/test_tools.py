"""Helper scripts in tools/ (no Earth Engine access needed)."""
import importlib.util
import json
import sys
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib

from gw_dashboard import gee

ROOT = Path(__file__).resolve().parent.parent
PEM = "-----BEGIN PRIVATE KEY-----\nFAKEKEYFORTESTSONLYxxxxxxxxxxxxx\nAAAA\n-----END PRIVATE KEY-----\n"
KEY = {
    "type": "service_account", "project_id": "demo-project-1", "private_key_id": "abc",
    "private_key": PEM, "client_email": "v@demo-project-1.iam.gserviceaccount.com",
    "client_id": "123", "token_uri": "https://oauth2.googleapis.com/token",
}


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "tools" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_key_to_secrets_round_trip(tmp_path):
    kts = load("key_to_secrets")
    key_file = tmp_path / "key.json"
    key_file.write_text(json.dumps(KEY))
    out = tmp_path / "secrets.toml"
    assert kts.main([str(key_file), "-o", str(out), "--asset-folder", "projects/wa-project-1/assets/GW_X"]) == 0
    parsed = tomllib.loads(out.read_text())
    assert parsed["gee_credentials"]["private_key"] == PEM          # newlines preserved exactly
    assert parsed["gee"]["asset_folder"] == "projects/wa-project-1/assets/GW_X"
    info, _ = gee.find_service_account(secrets=parsed, env={})      # the app accepts it
    assert info["client_email"] == KEY["client_email"]


def test_key_to_secrets_rejects_non_service_account(tmp_path, capsys):
    kts = load("key_to_secrets")
    f = tmp_path / "user.json"
    f.write_text(json.dumps({"type": "authorized_user", "client_id": "x"}))
    assert kts.main([str(f)]) == 1


def test_example_secrets_file_is_valid_toml_and_has_no_real_key():
    text = (ROOT / ".streamlit" / "secrets.toml.example").read_text(encoding="utf-8")
    parsed = tomllib.loads(text)
    assert "PASTE-THE-KEY-LINES-HERE" in parsed["gee_credentials"]["private_key"]


def test_month_gaps():
    cs = load("check_setup")
    assert cs.month_gaps(["2018-11", "2019-02"]) == ["2018-12", "2019-01"]
    assert cs.month_gaps([]) == []


def test_copy_assets_project_parsing():
    ca = load("copy_assets")
    assert ca.project_of("projects/wa-gee-1/assets/GW") == "wa-gee-1"
    assert ca.project_of("users/me/GW") is None
