import os
import tempfile
import pytest
from core.gpx_parser import parse_gpx, build_segments, assign_surface

SAMPLE_GPX = """<?xml version="1.0" encoding="UTF-8"?>
<gpx version="1.1" creator="test">
  <trk>
    <name>Test Route</name>
    <trkseg>
      <trkpt lat="40.0000" lon="-105.0000"><ele>1600</ele></trkpt>
      <trkpt lat="40.0009" lon="-105.0000"><ele>1605</ele></trkpt>
      <trkpt lat="40.0018" lon="-105.0000"><ele>1610</ele></trkpt>
      <trkpt lat="40.0027" lon="-105.0000"><ele>1615</ele></trkpt>
      <trkpt lat="40.0036" lon="-105.0000"><ele>1620</ele></trkpt>
      <trkpt lat="40.0045" lon="-105.0000"><ele>1625</ele></trkpt>
      <trkpt lat="40.0054" lon="-105.0000"><ele>1630</ele></trkpt>
      <trkpt lat="40.0063" lon="-105.0000"><ele>1635</ele></trkpt>
      <trkpt lat="40.0072" lon="-105.0000"><ele>1640</ele></trkpt>
      <trkpt lat="40.0081" lon="-105.0000"><ele>1645</ele></trkpt>
      <trkpt lat="40.0090" lon="-105.0000"><ele>1650</ele></trkpt>
    </trkseg>
  </trk>
</gpx>"""


@pytest.fixture
def gpx_file():
    with tempfile.NamedTemporaryFile(mode='w', suffix='.gpx', delete=False) as f:
        f.write(SAMPLE_GPX)
        path = f.name
    yield path
    os.unlink(path)


def test_parse_gpx_returns_points(gpx_file):
    points = parse_gpx(gpx_file)
    assert len(points) == 11
    assert points[0]['lat'] == 40.0
    assert points[0]['elevation_m'] == 1600


def test_build_segments_basic(gpx_file):
    points = parse_gpx(gpx_file)
    segments = build_segments(points, segment_length_m=200)
    assert len(segments) > 0
    assert all(s['distance_m'] > 0 for s in segments)
    assert segments[0]['cumulative_m'] == 0.0


def test_segments_cover_total_distance(gpx_file):
    points = parse_gpx(gpx_file)
    segments = build_segments(points, segment_length_m=200)
    total = sum(s['distance_m'] for s in segments)
    assert total > 900  # ~1km route


def test_gradient_clipping(gpx_file):
    points = parse_gpx(gpx_file)
    segments = build_segments(points, segment_length_m=200)
    for s in segments:
        assert -0.30 <= s['gradient'] <= 0.30


def test_zone_labels(gpx_file):
    points = parse_gpx(gpx_file)
    segments = build_segments(points, segment_length_m=200)
    for s in segments:
        assert s['zone_label'] in ('climb', 'descent', 'flat')


def test_assign_surface_default(gpx_file):
    points = parse_gpx(gpx_file)
    segments = build_segments(points, segment_length_m=200)
    segments = assign_surface(segments)
    for s in segments:
        assert 'crr' in s
        assert s['crr'] > 0


def test_assign_surface_custom(gpx_file):
    points = parse_gpx(gpx_file)
    segments = build_segments(points, segment_length_m=200)
    surface_map = {'0-2': 'paved_road', '3-99': 'dirt_soft'}
    segments = assign_surface(segments, surface_map)
    assert segments[0]['surface'] == 'paved_road'
    if len(segments) > 3:
        assert segments[3]['surface'] == 'dirt_soft'


def test_parse_gpx_no_elevation():
    gpx_no_ele = """<?xml version="1.0" encoding="UTF-8"?>
    <gpx version="1.1" creator="test">
      <trk><trkseg>
        <trkpt lat="40.0" lon="-105.0"></trkpt>
        <trkpt lat="40.001" lon="-105.0"></trkpt>
        <trkpt lat="40.002" lon="-105.0"></trkpt>
      </trkseg></trk>
    </gpx>"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.gpx', delete=False) as f:
        f.write(gpx_no_ele)
        path = f.name
    try:
        points = parse_gpx(path)
        assert all(p['elevation_m'] == 0.0 for p in points)
    finally:
        os.unlink(path)
