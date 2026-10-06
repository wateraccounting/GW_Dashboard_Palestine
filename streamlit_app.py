"""Groundwater Analysis Dashboard (Streamlit + Google Earth Engine).

Run locally:   streamlit run streamlit_app.py
Country-specific settings:  settings.toml
Credentials:   .streamlit/secrets.toml (never commit it) or the Streamlit Cloud "Secrets" box
"""

from __future__ import annotations

import json
import math

import streamlit as st
from streamlit_folium import st_folium
import folium

from gw_dashboard import __version__, gee, maps
from gw_dashboard.i18n import LANGUAGES, tr
from gw_dashboard.settings import Settings, SettingsError, load_settings


# --------------------------------------------------------------------------- helpers

def safe_secrets() -> dict:
    """st.secrets as a plain dict, or {} when no secrets are configured."""
    try:
        return st.secrets.to_dict()
    except Exception:
        return {}


def fmt(value) -> str:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return "–"
    v = float(value)
    return f"{v:,.2f}" if abs(v) < 100 else f"{v:,.1f}"


def show_error(message: str, exc: Exception | None = None, lang: str = "en") -> None:
    st.error(message)
    if exc is not None:
        with st.expander(tr(lang, "details")):
            st.code(gee.redact(f"{exc.__class__.__name__}: {exc}"))


# --------------------------------------------------------------------------- cached Earth Engine calls
# Only plain values go in and out, so Streamlit can cache them safely.

@st.cache_resource(show_spinner=False)
def connect_ee(email: str, project: str | None, _info_json: str) -> str:
    return gee.initialize(json.loads(_info_json), project)


@st.cache_data(ttl=3600, show_spinner=False)
def cached_assets(folder: str) -> list[str]:
    return gee.list_image_assets(folder)


@st.cache_data(ttl=6 * 3600, show_spinner=False)
def cached_stats(asset_id: str, scale: float) -> dict:
    return gee.image_stats(asset_id, scale)


@st.cache_data(ttl=3600, show_spinner=False)
def cached_tile_url(asset_id: str, vmin: float, vmax: float, palette: tuple[str, ...]) -> str:
    return gee.tile_url(asset_id, vmin, vmax, palette)


@st.cache_data(ttl=6 * 3600, show_spinner=False, max_entries=500)
def cached_series(months: tuple[tuple[str, str], ...], lat: float, lon: float, scale: float) -> list[dict]:
    return gee.time_series(dict(months), lat, lon, scale)


# --------------------------------------------------------------------------- page setup

def apply_style(lang: str) -> None:
    st.markdown(
        """
        <style>
        .block-container {padding-top: 3.5rem;}
        div[data-testid="stMetricValue"] {font-size: 1.4rem;}
        </style>
        """,
        unsafe_allow_html=True,
    )
    if lang == "ar":
        st.markdown(
            """
            <style>
            .block-container, .stMarkdown, .stAlert, label, h1, h2, h3, h4,
            div[data-testid="stMetric"], div[data-testid="stExpander"] summary {
                direction: rtl; text-align: right;
            }
            </style>
            """,
            unsafe_allow_html=True,
        )


def main() -> None:
    secrets = safe_secrets()
    lang = st.session_state.get("lang", None)

    # ---- settings
    try:
        cfg: Settings = load_settings(secrets=secrets)
    except SettingsError as exc:
        st.set_page_config(page_title="Groundwater Analysis", page_icon="💧", layout="wide")
        show_error(tr("en", "err_settings"), exc)
        st.stop()

    if lang is None:
        lang = st.session_state["lang"] = cfg.default_language

    st.set_page_config(
        page_title=tr(lang, "page_title", place=cfg.place(lang)),
        page_icon="💧",
        layout="wide",
        initial_sidebar_state="collapsed",
    )
    apply_style(lang)

    # ---- language switch (top right)
    _, lang_col = st.columns([5, 1])
    with lang_col:
        st.selectbox(
            "🌐", options=list(LANGUAGES), format_func=LANGUAGES.get,
            key="lang", label_visibility="collapsed",
        )
    lang = st.session_state["lang"]

    st.markdown(f"## {tr(lang, 'header')}")
    header_slot = st.empty()

    # ---- Earth Engine connection
    try:
        info, cred_source = gee.find_service_account(secrets=secrets)
    except gee.CredentialsError as exc:
        show_error(tr(lang, "err_credentials"), exc, lang)
        st.info(tr(lang, "err_credentials_help"))
        st.stop()

    try:
        with st.spinner(tr(lang, "loading")):
            project = connect_ee(info["client_email"], cfg.gee_project, json.dumps(info))
    except Exception as exc:  # noqa: BLE001 - show any connection problem to the maintainer
        show_error(tr(lang, "err_init"), exc, lang)
        st.info(tr(lang, "err_credentials_help"))
        st.stop()

    # ---- available data
    try:
        with st.spinner(tr(lang, "loading")):
            asset_ids = cached_assets(cfg.asset_folder)
    except Exception as exc:  # noqa: BLE001
        show_error(tr(lang, "err_assets"), exc, lang)
        st.stop()

    catalogue = gee.index_assets(asset_ids, cfg.parameter_keys)
    available = [p for p in cfg.parameters if catalogue.get(p.key)]
    if not available:
        st.warning(tr(lang, "err_no_assets"))
        st.caption(f"{tr(lang, 'data_folder')}: `{cfg.asset_folder}`")
        st.stop()

    all_months = sorted({m for p in available for m in catalogue[p.key]})
    header_slot.caption(tr(lang, "subheader", place=cfg.place(lang), first=all_months[0], last=all_months[-1]))

    # ---- layout
    left, right = st.columns([1, 3], gap="medium")

    with left:
        st.markdown(f"#### {tr(lang, 'control_panel')}")
        keys = [p.key for p in available]
        # The widget key includes the language so the option labels refresh when the
        # language changes; the choice itself is kept in "param_choice".
        saved = st.session_state.get("param_choice")
        param_key = st.selectbox(
            tr(lang, "parameter"), keys,
            index=keys.index(saved) if saved in keys else 0,
            format_func=lambda k: cfg.parameter(k).label(lang),
            help=tr(lang, "parameter_help"), key=f"parameter_{lang}",
        )
        st.session_state["param_choice"] = param_key
        param = cfg.parameter(param_key)
        months = list(catalogue[param_key])
        if st.session_state.get("month") not in months:
            st.session_state["month"] = months[-1]
        month = st.selectbox(tr(lang, "month"), months, key="month")

        with st.expander(tr(lang, "visual_settings")):
            opacity = st.slider(tr(lang, "opacity"), 0.0, 1.0, 0.75, 0.05, key="opacity")
        with st.expander(tr(lang, "location_settings")):
            c_lat = st.number_input(tr(lang, "latitude"), -90.0, 90.0, cfg.center_lat, 0.05, format="%.4f", key="c_lat")
            c_lon = st.number_input(tr(lang, "longitude"), -180.0, 180.0, cfg.center_lon, 0.05, format="%.4f", key="c_lon")
            zoom = st.slider(tr(lang, "zoom"), 1, 18, cfg.zoom, key="zoom")

    asset_id = catalogue[param_key][month]

    with right:
        st.markdown(f"#### {tr(lang, 'interactive_map')}")
        st.caption(tr(lang, "map_hint"))
        scale_note_slot = st.empty()

        stats: dict = {}
        tile = None
        vmin, vmax = 0.0, 1.0
        try:
            with st.spinner(tr(lang, "loading")):
                stats = cached_stats(asset_id, cfg.stats_scale_m)
                vmin, vmax = gee.colour_range(stats, param.vis_min, param.vis_max)
                tile = cached_tile_url(asset_id, vmin, vmax, param.palette)
        except Exception as exc:  # noqa: BLE001
            show_error(tr(lang, "err_map"), exc, lang)

        if stats:
            scale_note_slot.caption(tr(lang, "fixed_scale" if param.vis_min is not None else "auto_scale"))

        point = st.session_state.get("point")
        marker_group = folium.FeatureGroup(name="selected-point", control=False)
        if point:
            folium.CircleMarker(point, radius=8, color="#ffffff", weight=3, fill=True,
                                fill_color="#d7301f", fill_opacity=1).add_to(marker_group)

        fmap = maps.build_map(
            center=(c_lat, c_lon), zoom=zoom, tile_url=tile,
            layer_name=f"{param.label(lang)} – {month}", opacity=opacity,
            palette=param.palette, vmin=vmin, vmax=vmax,
            legend_caption=tr(lang, "legend", parameter=param.label(lang), unit=param.unit_label(lang)),
        )
        result = st_folium(
            fmap, key="map", height=520, use_container_width=True,
            feature_group_to_add=marker_group, returned_objects=["last_clicked"],
        )
        clicked = (result or {}).get("last_clicked")
        if clicked:
            new_point = (round(float(clicked["lat"]), 5), round(float(clicked["lng"]), 5))
            if new_point != point:
                st.session_state["point"] = new_point
                st.rerun()

        # ---- statistics
        st.markdown(f"#### {tr(lang, 'statistics', month=month)}")
        if stats:
            c1, c2, c3 = st.columns(3)
            c1.metric(f"{tr(lang, 'minimum')} ({param.unit_label(lang)})", fmt(stats.get("min")))
            c2.metric(f"{tr(lang, 'mean')} ({param.unit_label(lang)})", fmt(stats.get("mean")))
            c3.metric(f"{tr(lang, 'maximum')} ({param.unit_label(lang)})", fmt(stats.get("max")))
        else:
            st.caption(tr(lang, "err_stats"))

        # ---- time series
        st.markdown(f"#### {tr(lang, 'time_series')}")
        if not point:
            st.info(tr(lang, "click_map"))
        else:
            try:
                with st.spinner(tr(lang, "loading")):
                    rows = cached_series(tuple(catalogue[param_key].items()), point[0], point[1], cfg.pixel_scale_m)
                df = maps.series_frame(rows)
                if df["value"].notna().sum() == 0:
                    st.warning(tr(lang, "no_data_point"))
                else:
                    fig = maps.time_series_figure(
                        df,
                        title=tr(lang, "ts_title", parameter=param.label(lang), lat=f"{point[0]:.4f}", lon=f"{point[1]:.4f}"),
                        y_label=f"{param.label(lang)} ({param.unit_label(lang)})",
                        x_label=tr(lang, "date"),
                        highlight_month=month,
                    )
                    st.plotly_chart(fig)
                    csv = df.rename(columns={"value": f"{param_key} ({param.unit})"}).to_csv(index=False).encode("utf-8")
                    st.download_button(
                        tr(lang, "download_csv"), csv, mime="text/csv", on_click="ignore",
                        file_name=f"{cfg.region_en.replace(' ', '_')}_{param_key}_{point[0]:.4f}_{point[1]:.4f}.csv",
                    )
            except Exception as exc:  # noqa: BLE001
                show_error(tr(lang, "err_ts"), exc, lang)

    # ---- footer
    st.divider()
    with st.expander(tr(lang, "about")):
        st.markdown(tr(lang, "about_text", place=cfg.place(lang)))
        if cfg.organisation:
            st.markdown(tr(lang, "developed_by", org=cfg.organisation))
        if cfg.contact:
            st.markdown(tr(lang, "contact_line", contact=cfg.contact))
    with st.expander(tr(lang, "tech_details")):
        st.markdown(
            f"- {tr(lang, 'data_folder')}: `{cfg.asset_folder}` ({tr(lang, 'configured_in')} {cfg.asset_folder_source})\n"
            f"- {tr(lang, 'available')}: "
            + ", ".join(f"{p.key}: {len(catalogue[p.key])} ({min(catalogue[p.key])} → {max(catalogue[p.key])})" for p in available)
            + f"\n- Earth Engine project: `{project}` · app version {__version__}"
        )


if __name__ == "__main__":
    main()
