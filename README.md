# 💧 Groundwater Analysis Dashboard – Jericho, Palestine

[![tests](https://github.com/wateraccounting/GW_Dashboard_Palestine/actions/workflows/tests.yml/badge.svg)](https://github.com/wateraccounting/GW_Dashboard_Palestine/actions/workflows/tests.yml) ![Python](https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.13-blue) ![License: MIT](https://img.shields.io/badge/license-MIT-green)

Interactive web dashboard showing **monthly groundwater abstraction and recharge** for
**Jericho (Palestine)**, computed with Google Earth Engine (GEE) and served with
[Streamlit](https://streamlit.io).

**Live app:** not deployed yet – follow *Deploy on Streamlit Community Cloud* below.

| Map | Statistics | Time series |
|---|---|---|
| Monthly layers on satellite or OpenStreetMap background, with legend | Minimum, mean and maximum for the selected month | Click any point → full monthly history, downloadable as CSV |

Interface in **English and Arabic**.

---

## Contents

| Path | What it is |
|---|---|
| `streamlit_app.py` | The app (Streamlit entry point) |
| `settings.toml` | **Country settings** – names, map position, GEE data folder, colours. The only file you normally edit |
| `gw_dashboard/` | Code: Earth Engine access (`gee.py`), settings loader, maps/charts, English/Arabic text |
| `.streamlit/secrets.toml.example` | Template showing how to supply the GEE key – **contains no real secret** |
| `tools/check_setup.py` | Checks credentials, data folder and one live computation |
| `tools/key_to_secrets.py` | Converts a downloaded JSON key into the text for the Secrets box |
| `tools/copy_assets.py` | Copies the GEE images to a new GEE project (for the move to the team's own account) |
| `tests/` | Automated tests (run without any Earth Engine access) |
| `.github/workflows/tests.yml` | Runs the tests on every push |

## How credentials are kept private

The app reads a Google **service-account key**. That key is **never in this repository**:

* Online, it is pasted into the app's **Secrets** box on Streamlit Community Cloud.
  Secrets are stored by Streamlit, not in GitHub, so a public repo shows nothing.
* Locally, it goes in `.streamlit/secrets.toml`, which `.gitignore` blocks from being committed.
* `tests/test_no_secrets_in_repo.py` (run with `pytest` **before** committing, and again by GitHub Actions)
  flags anything that looks like a private key. On GitHub, also switch on
  *Settings → Code security → Secret scanning → Push protection* – it blocks a key **before** it is pushed.
* The app never shows the key: error messages are cleaned before they are displayed.

Visitors of the app and of the public repo cannot see the key. **Everyone with write access to this
GitHub repo can open the app's settings on Streamlit Cloud and read the secrets** – which is why the
service account should be a read-only one used for this app only (see below).

## Deploy on Streamlit Community Cloud

1. Sign in at <https://share.streamlit.io> with GitHub. **Deploying** needs **admin** rights on this repo;
   afterwards, anyone with **write** access can manage the app. For an organisation repo, an organisation
   owner must first allow Streamlit (*GitHub → Settings → Applications → Authorized OAuth Apps → Streamlit → Grant*).
2. **Create app → Deploy a public app from GitHub.**
3. Repository: `wateraccounting/GW_Dashboard_Palestine` · Branch: `main` · Main file path: `streamlit_app.py`.
4. App URL: choose a name, e.g. `gw-dashboard-palestine`.
5. Open **Advanced settings**:
   * Python version: **3.12**
   * **Secrets**: paste the `[gee_credentials]` block with the real key – same format as
     `.streamlit/secrets.toml.example`. `python tools/key_to_secrets.py key.json` produces it from a
     downloaded JSON key. (Or let the key owner paste it – see "Handing over the key" below.)
6. **Deploy.** First start takes 2–4 minutes.

To change secrets later: app → **⋮ → Settings → Secrets** → edit → **Save** (the app restarts automatically).

### Handing over the key safely

* Never send the key by e-mail, chat, or in a commit.
* Easiest: the key owner signs in to Streamlit Cloud (they need write access to this repo) and pastes the
  secrets into the deployed app themselves – the person deploying never sees the key.
* Otherwise share the JSON file through an access-restricted channel (e.g. a OneDrive/SharePoint
  link restricted to one person, or a password manager) and delete it afterwards.

## Moving to the Water Accounting team's own Earth Engine account

The data folder and the credentials are **settings, not code**. Moving takes three steps and no code change.

**1. Create a service account in the new GEE project** (Google Cloud Console):
   * Project must be registered for Earth Engine (<https://code.earthengine.google.com/register>)
     and have the *Earth Engine API* enabled.
   * *IAM & Admin → Service Accounts → Create*. Give it the roles
     **Earth Engine Resource Viewer** and **Service Usage Consumer** (read-only is enough for this app).
   * *Keys → Add key → JSON* → download.

**2. Copy the images** to the new project (run once, from this folder, with Python installed):

```bash
pip install -r requirements.txt
earthengine authenticate                      # log in with your own Google account
python tools/copy_assets.py --dest projects/NEW-PROJECT/assets/GW_Analysis_Jericho --dry-run
python tools/copy_assets.py --dest projects/NEW-PROJECT/assets/GW_Analysis_Jericho
```

Your Google account needs read access to the current folder (`projects/steel-sonar-428908-v8/assets/GW_Analysis_Jericho`) –
ask the current owner to share it – and write access to the new project. Sharing settings are not copied:
the new service account reads the copies because it belongs to the new project (step 1).

**3. Point the app to the new account** – in Streamlit Cloud *Settings → Secrets*:
   * replace the `[gee_credentials]` block with the new key
     (`python tools/key_to_secrets.py new-key.json` prints it), and
   * add
     ```toml
     [gee]
     asset_folder = "projects/NEW-PROJECT/assets/GW_Analysis_Jericho"
     ```
   Save. Optionally also update `asset_folder` in `settings.toml` so the repo documents the new location.

## Updating the data

Add new monthly images to the GEE folder, named **`<parameter>_YYYY_MM`**, for example
`abstraction_m3_2026_03`, `abstraction_mm_2026_03`, `recharge_2026_03`. The dashboard finds new months
automatically within one hour. If you **replace** an existing image (same name), click *⋮ → Reboot app* so
the cached statistics and time series are refreshed. Any band name works; the first
band of each image is used. Parameters shown are those listed in `settings.toml`.

## Run on your own computer

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate      macOS/Linux: source .venv/bin/activate
pip install -r requirements-dev.txt
copy .streamlit\secrets.toml.example .streamlit\secrets.toml   # macOS/Linux: cp …   then fill it in
python tools/check_setup.py          # checks key, data folder and one live computation
streamlit run streamlit_app.py       # opens http://localhost:8501
pytest                               # automated tests, no GEE access needed
```

## `settings.toml` in brief

| Section | Key | Meaning |
|---|---|---|
| `[site]` | `country_en/ar`, `region_en/ar` | Names shown in the title (English/Arabic) |
| | `organisation`, `contact` | Shown under "About" |
| | `default_language` | `"en"` or `"ar"` |
| `[gee]` | `asset_folder` | GEE folder with the monthly images (overridable in Secrets `[gee]`) |
| | `project` | Optional GEE project for computation (default: the service account's project) |
| | `pixel_scale_m` | Native pixel size, used for point time series (20 m) |
| | `stats_scale_m` | Resolution for map statistics (100 m – larger is faster) |
| `[map]` | `center_lat`, `center_lon`, `zoom` | Start view |
| `[[parameters]]` | `key` | Asset-name prefix, e.g. `recharge` |
| | `label_en/ar`, `unit`, `unit_ar`, `palette` | Display name, unit (English/Arabic), colours (`#rrggbb`) |
| | `vis_min`, `vis_max` | Optional fixed colour-scale limits (otherwise 2–98 % stretch per month) |

## Troubleshooting

| Message in the app | Fix |
|---|---|
| *Earth Engine credentials are missing or not valid* | Secrets box empty or key pasted incorrectly – compare with `.streamlit/secrets.toml.example` (keep the `"""` around `private_key`). |
| *Could not connect to Google Earth Engine* | Project not registered for EE, EE API disabled, or service account lacks the two roles above. |
| *No images were found…* | Wrong `asset_folder`, or the service account cannot read it. Run `python tools/check_setup.py`. |
| Month missing from the list | That image is not in the folder or is mis-named (`<parameter>_YYYY_MM`). |
| App asleep ("Zzzz") | Free Streamlit apps sleep after inactivity – click *Yes, get this app back up*. |

## Credits & licence

Original development: **Ahmed G. El-Naggar**, IHE Delft Institute for Water Education.
Maintained by the IHE Delft Water Accounting team. Released under the MIT licence (see `LICENSE`).
Basemap © Esri / © OpenStreetMap contributors. Data processing: Google Earth Engine.
