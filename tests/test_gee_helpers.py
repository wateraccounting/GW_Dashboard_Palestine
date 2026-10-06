"""Pure helpers in gw_dashboard.gee – no network needed."""
import json

import pytest

from gw_dashboard import gee

FAKE_PEM = "-----BEGIN PRIVATE KEY-----\nAAAA\n-----END PRIVATE KEY-----\n"
FAKE_KEY = {
    "type": "service_account",
    "project_id": "demo-project-1",
    "private_key": FAKE_PEM,
    "client_email": "viewer@demo-project-1.iam.gserviceaccount.com",
}
ROOT = "projects/demo-project-1/assets/GW"


@pytest.mark.parametrize("asset_id, expected", [
    (f"{ROOT}/abstraction_m3_2018_01", ("abstraction_m3", "2018-01")),
    (f"{ROOT}/abstraction_mm_2026_12", ("abstraction_mm", "2026-12")),
    ("recharge_2020_07", ("recharge", "2020-07")),
    (f"{ROOT}/recharge_2020_13", None),     # month 13
    (f"{ROOT}/recharge_2020_1", None),      # one-digit month
    (f"{ROOT}/recharge_2020-01", None),
    (f"{ROOT}/README", None),
])
def test_parse_asset_name(asset_id, expected):
    assert gee.parse_asset_name(asset_id) == expected


def test_index_assets_exact_parameter_match_and_sorting():
    ids = [f"{ROOT}/abstraction_mm_2018_02", f"{ROOT}/abstraction_m3_2018_01",
           f"{ROOT}/abstraction_mm_2018_01", f"{ROOT}/recharge_2018_01", f"{ROOT}/junk"]
    cat = gee.index_assets(ids, ["abstraction_mm", "abstraction_m3", "recharge"])
    assert list(cat["abstraction_mm"]) == ["2018-01", "2018-02"]
    assert list(cat["abstraction_m3"]) == ["2018-01"]
    assert cat["abstraction_m3"]["2018-01"].endswith("abstraction_m3_2018_01")
    assert gee.unmatched_assets(ids, ["abstraction_mm", "abstraction_m3"]) == ["recharge_2018_01", "junk"]


def test_index_assets_parameter_without_images():
    assert gee.index_assets([], ["recharge"]) == {"recharge": {}}


@pytest.mark.parametrize("stats, fixed, expected", [
    ({"p2": 1.0, "p98": 9.0, "min": 0.0, "max": 50.0}, (None, None), (1.0, 9.0)),
    ({"p2": 2.0, "p98": 2.0, "min": 0.0, "max": 50.0}, (None, None), (0.0, 50.0)),
    ({"p2": None, "p98": None, "min": 3.0, "max": 3.0}, (None, None), (3.0, 4.0)),
    ({}, (None, None), (0.0, 1.0)),
    ({"p2": 1.0, "p98": 9.0}, (0.0, 100.0), (0.0, 100.0)),
])
def test_colour_range(stats, fixed, expected):
    assert gee.colour_range(stats, *fixed) == expected


def test_service_account_from_streamlit_secrets():
    info, source = gee.find_service_account(secrets={"gee_credentials": FAKE_KEY}, env={})
    assert info["client_email"] == FAKE_KEY["client_email"] and "gee_credentials" in source


def test_alternative_secret_section_name():
    _, source = gee.find_service_account(secrets={"gcp_service_account": FAKE_KEY}, env={})
    assert "gcp_service_account" in source


def test_service_account_from_env_json_and_literal_newlines():
    key = dict(FAKE_KEY, private_key=FAKE_PEM.replace("\n", "\\n"))
    info, source = gee.find_service_account(secrets={}, env={"GEE_SERVICE_ACCOUNT_JSON": json.dumps(key)})
    assert "\n" in info["private_key"] and "\\n" not in info["private_key"]
    assert "GEE_SERVICE_ACCOUNT_JSON" in source


def test_service_account_from_key_file(tmp_path):
    f = tmp_path / "key.json"
    f.write_text(json.dumps(FAKE_KEY))
    _, source = gee.find_service_account(secrets=None, env={"GOOGLE_APPLICATION_CREDENTIALS": str(f)})
    assert "key file" in source


def test_no_credentials_gives_helpful_error():
    with pytest.raises(gee.CredentialsError, match="secrets"):
        gee.find_service_account(secrets={}, env={})


def test_broken_secrets_object_is_tolerated():
    class Exploding:
        def get(self, _):
            raise FileNotFoundError("no secrets.toml")
    with pytest.raises(gee.CredentialsError):
        gee.find_service_account(secrets=Exploding(), env={})


def test_invalid_key_errors_never_leak_the_private_key():
    bad = dict(FAKE_KEY, type="authorized_user", client_email="someone@gmail.com",
               private_key="TOP-SECRET-VALUE")
    with pytest.raises(gee.CredentialsError) as err:
        gee.find_service_account(secrets={"gee_credentials": bad}, env={})
    msg = str(err.value)
    assert "TOP-SECRET-VALUE" not in msg
    assert "type" in msg and "client_email" in msg and "private_key" in msg


def test_initialize_passes_project(monkeypatch):
    calls = {}

    class FakeNumber:
        def __init__(self, n): pass
        def getInfo(self): return 1

    monkeypatch.setattr(gee.ee, "ServiceAccountCredentials", lambda email, key_data: ("creds", email, json.loads(key_data)["project_id"]))
    monkeypatch.setattr(gee.ee, "Initialize", lambda creds, project=None: calls.update(creds=creds, project=project))
    monkeypatch.setattr(gee.ee, "Number", FakeNumber)
    assert gee.initialize(FAKE_KEY) == "demo-project-1"
    assert calls["project"] == "demo-project-1"
    assert gee.initialize(FAKE_KEY, project="other-project") == "other-project"


def _real_pem():
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                             serialization.NoEncryption()).decode()


def test_corrupted_key_with_real_library_never_leaks():
    """A key that lost a line while pasting: google-auth may echo the key; we must not."""
    lines = _real_pem().splitlines()
    broken = "\n".join(lines[:5] + lines[6:]) + "\n"
    info = dict(FAKE_KEY, private_key=broken)
    with pytest.raises(gee.CredentialsError) as err:
        gee.initialize(info)                       # real `ee` library, fails before any network call
    msg = str(err.value)
    assert "Paste it again" in msg
    assert lines[3] not in msg and "BEGIN PRIVATE KEY" not in msg
    assert err.value.__cause__ is None and err.value.__suppress_context__


def test_json_string_in_secrets_is_accepted():
    info, _ = gee.find_service_account(secrets={"gee_credentials": json.dumps(FAKE_KEY)}, env={})
    assert info["client_email"] == FAKE_KEY["client_email"]


def test_garbage_string_in_secrets_is_a_clear_error():
    with pytest.raises(gee.CredentialsError, match="not valid JSON"):
        gee.find_service_account(secrets={"gee_credentials": "paste here"}, env={})


def test_redact_removes_keys_in_any_shape():
    pem = _real_pem()
    body = pem.splitlines()[2]
    samples = [
        f"ValueError: {pem}",
        str({"private_key": pem, "client_email": "x"}),
        json.dumps({"private_key": pem}),
        "private_key = '" + pem.replace("\n", "\\n") + "'",
    ]
    for s in samples:
        out = gee.redact(s)
        assert body not in out, out[:200]
    assert gee.redact("plain message") == "plain message"
