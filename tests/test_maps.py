"""Map and chart builders."""
import pandas as pd

from gw_dashboard import maps


def test_build_map_with_layer_and_legend():
    m = maps.build_map((31.9, 35.4), 11, tile_url="https://tiles/{z}/{x}/{y}", layer_name="Recharge – 2020-01",
                       palette=("#ff0000", "#00ff00"), vmin=0, vmax=5, legend_caption="Recharge (mm)")
    html = m.get_root().render()
    assert "https://tiles/{z}/{x}/{y}" in html
    assert "Recharge (mm)" in html
    assert "World_Imagery" in html
    # only ONE base layer is switched on at start (satellite); OSM is selectable in the layer control
    import re
    added = re.findall(r"(tile_layer_\w+)\.addTo\(map_", html)
    assert len(added) == 2  # satellite + EE layer


def test_build_map_without_layer():
    html = maps.build_map((0, 0), 5).get_root().render()
    assert "Google Earth Engine" not in html


def test_series_frame_and_figure():
    df = maps.series_frame([{"month": "2018-02", "value": 2}, {"month": "2018-01", "value": None}])
    assert list(df["month"]) == ["2018-01", "2018-02"]
    assert df["value"].isna().sum() == 1
    fig = maps.time_series_figure(df, "t", "y", "x", highlight_month="2018-02")
    assert len(fig.data) == 2  # line + highlighted month
    fig = maps.time_series_figure(df, "t", "y", "x", highlight_month="2018-01")  # NaN month: no highlight
    assert len(fig.data) == 1


def test_series_frame_empty():
    df = maps.series_frame([])
    assert df.empty and list(df.columns) == ["month", "value"]
    assert isinstance(df, pd.DataFrame)
