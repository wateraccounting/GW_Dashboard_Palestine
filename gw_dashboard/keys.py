"""Service-account credentials: finding, checking and hiding them.

No Earth Engine import here, so helper scripts can use it with plain Python.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any, Mapping

# Keys accepted in Streamlit secrets for the service-account JSON.
SECRET_SECTIONS = ("gee_credentials", "gcp_service_account")
REQUIRED_KEY_FIELDS = ("type", "client_email", "private_key")


class CredentialsError(RuntimeError):
    """Raised when no usable Earth Engine credentials are configured."""


_PEM_BLOCK_RE = re.compile(r"-----BEGIN[^-]*PRIVATE KEY-----.*?(-----END[^-]*PRIVATE KEY-----|$)", re.S)
_KEY_FIELD_RE = re.compile(r"""(['"]?private_key['"]?\s*[:=]\s*)(['"]).*?(\2|$)""", re.S)


def redact(text: str) -> str:
    """Remove anything that looks like a private key from a message before showing it."""
    text = _PEM_BLOCK_RE.sub("[private key removed]", str(text))
    return _KEY_FIELD_RE.sub(r"\1'[removed]'", text)


def _normalise_key(info: dict[str, Any]) -> dict[str, Any]:
    info = dict(info)
    pk = info.get("private_key")
    if isinstance(pk, str) and "\\n" in pk and "\n" not in pk:
        # Pasted with literal "\n" sequences (common TOML/env mistake) -> real newlines.
        info["private_key"] = pk.replace("\\n", "\n")
    return info


def validate_service_account(info: Mapping[str, Any]) -> list[str]:
    """Return a list of human-readable problems (empty list = looks fine).

    Never includes secret values in the messages.
    """
    problems = []
    for field in REQUIRED_KEY_FIELDS:
        if not info.get(field):
            problems.append(f"'{field}' is missing")
    if info.get("type") and info.get("type") != "service_account":
        problems.append("'type' must be \"service_account\"")
    email = str(info.get("client_email", ""))
    if email and not email.endswith(".iam.gserviceaccount.com"):
        problems.append("'client_email' does not look like a service-account e-mail")
    pk = str(info.get("private_key", ""))
    if pk and "BEGIN PRIVATE KEY" not in pk:
        problems.append("'private_key' does not look like a PEM private key")
    return problems


def find_service_account(
    secrets: Mapping[str, Any] | None = None,
    env: Mapping[str, str] | None = None,
) -> tuple[dict[str, Any], str]:
    """Locate service-account credentials.

    Search order:
      1. Streamlit secrets  [gee_credentials]  (or [gcp_service_account])
      2. env GEE_SERVICE_ACCOUNT_JSON  (the whole JSON key as one string)
      3. env GOOGLE_APPLICATION_CREDENTIALS  (path to the JSON key file)

    Returns (info_dict, where_it_was_found). Raises CredentialsError.
    """
    env = os.environ if env is None else env
    if secrets:
        for section in SECRET_SECTIONS:
            try:
                value = secrets.get(section) if hasattr(secrets, "get") else None
            except Exception:  # st.secrets raises when no secrets file exists
                value = None
            if value:
                if isinstance(value, str):  # whole JSON key pasted as one string
                    try:
                        value = json.loads(value)
                    except json.JSONDecodeError:
                        raise CredentialsError(
                            f"Streamlit secrets [{section}] is text that is not valid JSON – "
                            "use the format shown in .streamlit/secrets.toml.example"
                        ) from None
                if not isinstance(value, Mapping):
                    raise CredentialsError(f"Streamlit secrets [{section}] must be a table of key = value lines")
                info = _normalise_key(dict(value))
                problems = validate_service_account(info)
                if problems:
                    raise CredentialsError(f"Streamlit secrets [{section}]: " + "; ".join(problems))
                return info, f"Streamlit secrets [{section}]"

    raw = env.get("GEE_SERVICE_ACCOUNT_JSON")
    if raw:
        try:
            info = _normalise_key(json.loads(raw))
        except json.JSONDecodeError as exc:
            raise CredentialsError("GEE_SERVICE_ACCOUNT_JSON is not valid JSON") from exc
        problems = validate_service_account(info)
        if problems:
            raise CredentialsError("GEE_SERVICE_ACCOUNT_JSON: " + "; ".join(problems))
        return info, "environment variable GEE_SERVICE_ACCOUNT_JSON"

    path = env.get("GOOGLE_APPLICATION_CREDENTIALS")
    if path:
        try:
            with open(path, encoding="utf-8") as fh:
                info = _normalise_key(json.load(fh))
        except (OSError, json.JSONDecodeError) as exc:
            raise CredentialsError(f"Could not read the key file in GOOGLE_APPLICATION_CREDENTIALS ({exc.__class__.__name__})") from exc
        problems = validate_service_account(info)
        if problems:
            raise CredentialsError("GOOGLE_APPLICATION_CREDENTIALS file: " + "; ".join(problems))
        return info, "GOOGLE_APPLICATION_CREDENTIALS key file"

    raise CredentialsError(
        "No Earth Engine credentials found. Add the service-account key to the app's "
        "Streamlit secrets under [gee_credentials] (see .streamlit/secrets.toml.example)."
    )
