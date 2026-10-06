"""Folium map and Plotly chart builders (no Earth Engine calls in here)."""

from __future__ import annotations

from typing import Any, Sequence

import folium
import pandas as pd
import plotly.graph_objects as go
from branca.colormap import LinearColormap
from folium.plugins import Fullscreen, MousePosition

ESRI_IMAGERY = "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"


def build_map(
    center: tuple[float, float],
    zoom: int,
    tile_url: str | None = None,
    layer_name: str = "Layer",
    opacity: float = 0.7,
    palette: Sequence[str] = (),
    vmin: float = 0.0,
    vmax: float = 1.0,
    legend_caption: str = "",
    marker: tuple[float, float] | None = None,
) -> folium.Map:
    m = folium.Map(location=list(center), zoom_start=zoom, control_scale=True, tiles=None)
    folium.TileLayer(tiles=ESRI_IMAGERY, attr="Esri, Maxar, Earthstar Geographics", name="Satellite").add_to(m)
    folium.TileLayer("OpenStreetMap", name="OpenStreetMap", show=False).add_to(m)  # satellite is the default

    if tile_url:
        folium.TileLayer(
            tiles=tile_url,
            attr="Google Earth Engine",
            name=layer_name,
            overlay=True,
            control=True,
            opacity=opacity,
        ).add_to(m)
        if len(palette) >= 2:
            LinearColormap(colors=list(palette), vmin=vmin, vmax=vmax, caption=legend_caption).add_to(m)

    if marker:
        folium.Marker(location=list(marker), icon=folium.Icon(color="red", icon="info-sign")).add_to(m)

    Fullscreen(position="topleft", force_separate_button=True).add_to(m)
    MousePosition(position="bottomleft", separator=" | ", num_digits=4, prefix="Lat | Lon:").add_to(m)
    folium.LayerControl(collapsed=True).add_to(m)
    return m


def series_frame(rows: Sequence[dict[str, Any]]) -> pd.DataFrame:
    """Rows from gee.time_series -> tidy DataFrame (month as text, value as float)."""
    df = pd.DataFrame(list(rows), columns=["month", "value"])
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    return df.sort_values("month").reset_index(drop=True)


def time_series_figure(
    df: pd.DataFrame,
    title: str,
    y_label: str,
    x_label: str,
    highlight_month: str | None = None,
    colour: str = "#1f6fb2",
) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=df["month"],
            y=df["value"],
            mode="lines+markers",
            line=dict(color=colour, width=2),
            marker=dict(size=6, color=colour),
            hovertemplate="%{x}: %{y:.2f}<extra></extra>",
            connectgaps=False,
            name=y_label,
        )
    )
    if highlight_month is not None and highlight_month in set(df["month"]):
        row = df[df["month"] == highlight_month].iloc[0]
        if pd.notna(row["value"]):
            fig.add_trace(
                go.Scatter(
                    x=[highlight_month], y=[row["value"]], mode="markers",
                    marker=dict(size=13, color="#d7301f", line=dict(width=2, color="white")),
                    hovertemplate="%{x}: %{y:.2f}<extra></extra>", showlegend=False,
                )
            )
    fig.update_layout(
        title=title,
        xaxis=dict(title=x_label, type="category", tickangle=-45, nticks=24, showgrid=True),
        yaxis=dict(title=y_label, showgrid=True, zeroline=True),
        template="plotly_white",
        height=380,
        margin=dict(t=50, b=80, l=60, r=20),
        showlegend=False,
    )
    return fig
