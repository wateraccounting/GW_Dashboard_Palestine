"""Copy the dashboard's Earth Engine images to another GEE project/folder.

Use this once, when the team moves the data to its own Earth Engine account.

    # 1. log in with your own Google account (opens a browser the first time)
    earthengine authenticate

    # 2. preview what will be copied (nothing is changed)
    python tools/copy_assets.py --dest projects/NEW-PROJECT/assets/GW_Analysis_Jericho --dry-run

    # 3. copy for real
    python tools/copy_assets.py --dest projects/NEW-PROJECT/assets/GW_Analysis_Jericho

Your Google account needs READ access to the source folder (ask the current
owner to share it with you) and WRITE access to the destination project.
The source folder defaults to asset_folder in settings.toml – if the app was
already switched to another folder through Streamlit secrets, pass --source.
Existing images in the destination are skipped unless --overwrite is given.
Sharing settings are NOT copied: the app's service account must belong to the
destination project (with the Earth Engine Resource Viewer role) or be given
read access to the new folder.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import ee  # noqa: E402

from gw_dashboard import gee  # noqa: E402
from gw_dashboard.settings import load_settings, validate_asset_folder  # noqa: E402


def project_of(folder: str) -> str | None:
    parts = folder.split("/")
    return parts[1] if len(parts) > 2 and parts[0] == "projects" else None


def exists(asset_id: str) -> bool:
    try:
        ee.data.getAsset(asset_id)
        return True
    except ee.EEException:
        return False


def ensure_folder(folder: str, dry_run: bool) -> None:
    """Create the destination folder (and any missing parent folders)."""
    parts = folder.split("/")
    start = 3 if parts[0] == "projects" else 2  # projects/<p>/assets/... | users/<u>/...
    for i in range(start + 1, len(parts) + 1):
        path = "/".join(parts[:i])
        if not exists(path):
            print(f"  create folder {path}")
            if not dry_run:
                ee.data.createAsset({"type": "FOLDER"}, path)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dest", required=True, help="destination folder, e.g. projects/my-project/assets/GW_Analysis_Jericho")
    ap.add_argument("--source", help="source folder (default: asset_folder in settings.toml, ignoring Streamlit secrets)")
    ap.add_argument("--project", help="Earth Engine project to bill the copy to (default: the destination's project)")
    ap.add_argument("--dry-run", action="store_true", help="only show what would happen")
    ap.add_argument("--overwrite", action="store_true", help="replace images that already exist in the destination")
    args = ap.parse_args(argv)

    source = validate_asset_folder(args.source or load_settings().asset_folder, "--source")
    dest = validate_asset_folder(args.dest, "--dest")
    if source == dest:
        print("Source and destination are the same – nothing to do.")
        return 1

    project = args.project or project_of(dest)
    ee.Initialize(project=project)  # uses the login from `earthengine authenticate`
    print(f"Source:      {source}\nDestination: {dest}\nProject:     {project}\n")

    ids = gee.list_image_assets(source)
    if not ids:
        print("No images found in the source folder (or you cannot read it).")
        return 1
    ensure_folder(dest, args.dry_run)

    copied = skipped = failed = 0
    for i, src in enumerate(sorted(ids), 1):
        dst = f"{dest}/{src.rsplit('/', 1)[-1]}"
        if not args.overwrite and exists(dst):
            skipped += 1
            continue
        print(f"  [{i}/{len(ids)}] {src.rsplit('/', 1)[-1]}")
        if args.dry_run:
            copied += 1
            continue
        try:
            ee.data.copyAsset(src, dst, allowOverwrite=args.overwrite)
            copied += 1
        except ee.EEException as exc:
            print(f"      FAILED: {exc}")
            failed += 1

    verb = "would copy" if args.dry_run else "copied"
    print(f"\nDone: {verb} {copied}, skipped {skipped} (already there), failed {failed}.")
    if not args.dry_run and failed == 0:
        print(
            "\nNext step – point the dashboard at the new folder, either:\n"
            f'  a) settings.toml  ->  asset_folder = "{dest}"   (commit & push), or\n'
            f'  b) Streamlit secrets  ->  [gee]  asset_folder = "{dest}"\n'
            "and replace [gee_credentials] with a service account from the new project."
        )
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
