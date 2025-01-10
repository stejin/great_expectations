import datetime
import re

import numpy as np
import pytest

from great_expectations.util import convert_to_json_serializable, ensure_json_serializable

try:
    from shapely.geometry import LineString, MultiPolygon, Point, Polygon
except ImportError:
    Point = None
    LineString = None
    Polygon = None
    MultiPolygon = None


@pytest.mark.unit
@pytest.mark.skipif(Polygon is None, reason="Requires shapely.geometry.Polygon")
def test_serialization_of_shapely_polygon():
    polygon = Polygon([(0, 0), (2, 0), (2, 2), (0, 2)])
    assert convert_to_json_serializable(polygon) == "POLYGON ((0 0, 2 0, 2 2, 0 2, 0 0))"


@pytest.mark.unit
@pytest.mark.skipif(
    any([MultiPolygon is None, Polygon is None]),
    reason="Requires shapely.geometry.Polygon and MultiPolygon",
)
def test_serialization_of_shapely_multipolygon():
    multi_polygon = MultiPolygon([Polygon([(1, 2), (3, 4), (5, 6)])])
    assert convert_to_json_serializable(multi_polygon) == "MULTIPOLYGON (((1 2, 3 4, 5 6, 1 2)))"


@pytest.mark.unit
@pytest.mark.skipif(Point is None, reason="Requires shapely.geometry.Point")
def test_serialization_of_shapely_point():
    point = Point(1, 2)
    assert convert_to_json_serializable(point) == "POINT (1 2)"


@pytest.mark.unit
@pytest.mark.skipif(LineString is None, reason="Requires shapely.geometry.LineString")
def test_serialization_of_shapely_linestring():
    point = LineString([(0, 0), (1, 1), (1, -1)])
    assert convert_to_json_serializable(point) == "LINESTRING (0 0, 1 1, 1 -1)"


@pytest.mark.unit
def test_serialization_of_bytes():
    data = b"\xc0\xa8\x00\x01"
    assert convert_to_json_serializable(data) == "b'\\xc0\\xa8\\x00\\x01'"


@pytest.mark.unit
def test_serialization_numpy_datetime():
    datetime_to_test = "2022-12-08T12:56:23.423"
    data = np.datetime64(datetime_to_test)
    assert convert_to_json_serializable(data) == datetime_to_test


@pytest.mark.unit
def test_serialization_of_pattern():
    pattern_to_test = r"data_(?P<year>\d{4})-(?P<month>\d{2}).csv"
    data = re.compile(pattern_to_test)
    assert convert_to_json_serializable(data) == pattern_to_test


@pytest.mark.unit
@pytest.mark.parametrize(
    "data", [pytest.param({"t": datetime.time(hour=1, minute=30, second=45)}, id="datetime.time")]
)
def test_convert_to_json_serializable_converts_correctly(data: dict):
    ret = convert_to_json_serializable(data)
    assert ret == {"t": "01:30:45"}


@pytest.mark.unit
@pytest.mark.parametrize(
    "data", [pytest.param({"t": datetime.time(hour=1, minute=30, second=45)}, id="datetime.time")]
)
def test_ensure_json_serializable(data: dict):
    ensure_json_serializable(data)
    # Passes if no exception raised
