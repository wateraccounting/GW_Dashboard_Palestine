"""Turn a Google service-account JSON key into text for the Streamlit "Secrets" box.

    python tools/key_to_secrets.py path/to/key.json                 # print to screen
    python tools/key_to_secrets.py path/to/key.json -o .streamlit/secrets.toml
    python tools/key_to_secrets.py key.json --asset-folder projects/NEW/assets/GW_X

Copy the printed text into: share.streamlit.io -> your app -> ⋮ -> Settings -> Secrets.
Treat the output like a password: do not e-mail it or commit it.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from gw_dashboard.keys import validate_service_account  # noqa: E402
from gw_dashboard.settings import validate_asset_folder  # noqa: E402


def toml_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)  # a JSON string is a valid TOML basic string


def to_toml(info: dict, asset_folder: str | None = None, project: str | None = None) -> str:
    lines = ["[gee_credentials]"]
    for key, value in info.items():
        if key == "private_key":
            lines.append(f'private_key = """{value.rstrip()}\n"""')
        elif isinstance(value, (str, int, float, bool)):
            lines.append(f"{key} = {toml_string(str(value)) if isinstance(value, str) else json.dumps(value)}")
    if asset_folder or project:
        lines += ["", "[gee]"]
        if asset_folder:
            lines.append(f"asset_folder = {toml_string(validate_asset_folder(asset_folder, '--asset-folder'))}")
        if project:
            lines.append(f"project = {toml_string(project)}")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("key", help="service-account JSON key file downloaded from Google Cloud")
    ap.add_argument("-o", "--output", help="write to this file instead of the screen")
    ap.add_argument("--asset-folder", help="optional: add [gee] asset_folder override")
    ap.add_argument("--project", help="optional: add [gee] project override")
    args = ap.parse_args(argv)

    info = json.loads(Path(args.key).read_text(encoding="utf-8"))
    problems = validate_service_account(info)
    if problems:
        print("This does not look like a service-account key: " + "; ".join(problems), file=sys.stderr)
        return 1
    text = to_toml(info, args.asset_folder, args.project)
    if args.output:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8")
        protected = out.resolve() == (ROOT / ".streamlit" / "secrets.toml").resolve()
        print(f"Written to {out}.")
        print("This file is git-ignored – keep it private." if protected else
              "WARNING: keep this file private and outside the repository – it contains the key. "
              "Use  -o .streamlit/secrets.toml  for the git-ignored location.")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
