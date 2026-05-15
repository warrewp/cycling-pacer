import math
import gpxpy
import numpy as np
from core.physics import load_surfaces


def parse_gpx(filepath: str) -> list[dict]:
    with open(filepath, 'r') as f:
        gpx = gpxpy.parse(f)

    if not gpx.tracks:
        raise ValueError("GPX file contains no tracks")

    track = gpx.tracks[0]
    points = []
    for segment in track.segments:
        for pt in segment.points:
            points.append({
                'lat': pt.latitude,
                'lon': pt.longitude,
                'elevation_m': pt.elevation if pt.elevation is not None else 0.0,
            })

    if len(points) > 10000:
        step = max(1, len(points) // 10000)
        points = points[::step]
        if points[-1] != points[-1]:  # ensure last point included
            points.append(points[-1])

    return points


def _haversine(lat1, lon1, lat2, lon2) -> float:
    R = 6371000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def build_segments(trackpoints: list[dict], segment_length_m: float = 200) -> list[dict]:
    if len(trackpoints) < 2:
        raise ValueError("Need at least 2 trackpoints")

    distances = []
    for i in range(1, len(trackpoints)):
        d = _haversine(
            trackpoints[i - 1]['lat'], trackpoints[i - 1]['lon'],
            trackpoints[i]['lat'], trackpoints[i]['lon'],
        )
        distances.append(d)

    cum_dist = 0.0
    segments = []
    seg_start_idx = 0
    seg_start_cum = 0.0

    for i, d in enumerate(distances):
        cum_dist += d
        seg_dist = cum_dist - seg_start_cum

        if seg_dist >= segment_length_m or i == len(distances) - 1:
            if seg_dist < 1.0:
                continue

            elev_start = trackpoints[seg_start_idx]['elevation_m']
            elev_end = trackpoints[i + 1]['elevation_m']
            rise = elev_end - elev_start
            gradient = rise / seg_dist
            gradient = max(-0.30, min(0.30, gradient))

            if gradient > 0.03:
                zone = "climb"
            elif gradient < -0.03:
                zone = "descent"
            else:
                zone = "flat"

            segments.append({
                'index': len(segments),
                'lat': trackpoints[seg_start_idx]['lat'],
                'lon': trackpoints[seg_start_idx]['lon'],
                'distance_m': seg_dist,
                'cumulative_m': seg_start_cum,
                'elevation_m': elev_start,
                'gradient': gradient,
                'surface': 'gravel_packed',
                'zone_label': zone,
            })

            seg_start_idx = i + 1
            seg_start_cum = cum_dist

    return segments


def assign_surface(segments: list[dict], surface_map: dict | None = None) -> list[dict]:
    surfaces = load_surfaces()

    if surface_map is None:
        for seg in segments:
            seg['crr'] = surfaces.get(seg.get('surface', 'gravel_packed'), 0.006)
        return segments

    for seg in segments:
        for range_str, surface_type in surface_map.items():
            parts = range_str.split('-')
            start, end = int(parts[0]), int(parts[1])
            if start <= seg['index'] <= end:
                seg['surface'] = surface_type
                break
        seg['crr'] = surfaces.get(seg.get('surface', 'gravel_packed'), 0.006)

    return segments
