"""Earth Engine calls, with the `ee` library replaced by a mock (no network)."""
from unittest import mock

import pytest

from gw_dashboard import gee


@pytest.fixture
def fake_ee(monkeypatch):
    fake = mock.MagicMock(name="ee")
    monkeypatch.setattr(gee, "ee", fake)
    return fake


def test_list_image_assets_keeps_images_only(fake_ee):
    fake_ee.data.listAssets.return_value = {"assets": [
        {"id": "projects/p-12345/assets/F/recharge_2018_01", "type": "IMAGE"},
        {"id": "projects/p-12345/assets/F/sub", "type": "FOLDER"},
        {"id": "projects/p-12345/assets/F/table", "type": "TABLE"},
    ]}
    assert gee.list_image_assets("projects/p-12345/assets/F") == ["projects/p-12345/assets/F/recharge_2018_01"]
    fake_ee.data.listAssets.assert_called_once_with({"parent": "projects/p-12345/assets/F"})


def test_list_image_assets_empty_folder(fake_ee):
    fake_ee.data.listAssets.return_value = {}
    assert gee.list_image_assets("projects/p-12345/assets/F") == []


def test_image_stats_uses_first_band_whatever_its_name(fake_ee):
    img = fake_ee.Image.return_value.select.return_value
    img.reduceRegion.return_value.getInfo.return_value = {
        "value_min": 0.5, "value_max": 9.0, "value_mean": 3.0, "value_p2": 1.0, "value_p98": 8.0}
    stats = gee.image_stats("projects/p-12345/assets/F/x_2020_01", 100)
    assert stats == {"min": 0.5, "max": 9.0, "mean": 3.0, "p2": 1.0, "p98": 8.0}
    fake_ee.Image.return_value.select.assert_called_with([0], ["value"])
    kwargs = img.reduceRegion.call_args.kwargs
    assert kwargs["scale"] == 100 and kwargs["bestEffort"] is True


def test_image_stats_handles_empty_result(fake_ee):
    fake_ee.Image.return_value.select.return_value.reduceRegion.return_value.getInfo.return_value = None
    assert gee.image_stats("a", 100)["mean"] is None


def test_tile_url_strips_hash_from_palette(fake_ee):
    img = fake_ee.Image.return_value.select.return_value
    img.getMapId.return_value = {"tile_fetcher": mock.Mock(url_format="https://tiles/{z}/{x}/{y}")}
    url = gee.tile_url("a", 0, 10, ("#ff0000", "#00ff00"))
    assert url == "https://tiles/{z}/{x}/{y}"
    img.getMapId.assert_called_once_with({"min": 0, "max": 10, "palette": ["ff0000", "00ff00"]})


def test_time_series_parses_and_sorts(fake_ee):
    fc = fake_ee.ImageCollection.fromImages.return_value.map.return_value
    fc.getInfo.return_value = {"features": [
        {"properties": {"month": "2018-02", "value": 2}},
        {"properties": {"month": "2018-01", "value": 1.5}},
        {"properties": {"month": "2018-03", "value": None}},
    ]}
    rows = gee.time_series({"2018-01": "a", "2018-02": "b", "2018-03": "c"}, 31.9, 35.4, 20)
    assert rows == [{"month": "2018-01", "value": 1.5}, {"month": "2018-02", "value": 2.0},
                    {"month": "2018-03", "value": None}]
    fake_ee.Geometry.Point.assert_called_once_with([35.4, 31.9])  # lon, lat order!


def test_time_series_no_months(fake_ee):
    assert gee.time_series({}, 0, 0, 20) == []
    fake_ee.ImageCollection.fromImages.assert_not_called()
