import pytest
from core.optimizer import optimize_pacing
from core.physics import segment_time


def _make_segments(n=20, gradient=0.0):
    return [
        {
            'index': i,
            'lat': 40.0 + i * 0.001,
            'lon': -105.0,
            'distance_m': 500,
            'cumulative_m': i * 500,
            'elevation_m': 1600 + i * 500 * gradient,
            'gradient': gradient,
            'surface': 'gravel_packed',
            'crr': 0.006,
            'zone_label': 'flat' if abs(gradient) <= 0.03 else ('climb' if gradient > 0 else 'descent'),
        }
        for i in range(n)
    ]


def _make_mixed_segments():
    segs = []
    gradients = [0.0, 0.0, 0.05, 0.05, 0.08, 0.0, -0.03, -0.05, 0.0, 0.02,
                 0.06, 0.04, 0.0, -0.02, -0.04, 0.0, 0.0, 0.03, 0.0, -0.01]
    for i, g in enumerate(gradients):
        segs.append({
            'index': i,
            'lat': 40.0 + i * 0.001,
            'lon': -105.0,
            'distance_m': 500,
            'cumulative_m': i * 500,
            'elevation_m': 1600,
            'gradient': g,
            'surface': 'gravel_packed',
            'crr': 0.006,
            'zone_label': 'flat' if abs(g) <= 0.03 else ('climb' if g > 0 else 'descent'),
        })
    return segs


RIDER = {'mass_kg': 80, 'cda': 0.35, 'drivetrain_eff': 0.97}
ENV = {'wind_ms': 0.0, 'rho': 1.225}


def test_wap_constraint_satisfied():
    segments = _make_mixed_segments()
    result = optimize_pacing(segments, RIDER, ENV, ftp_w=250, target_if=0.75)
    assert result['wap_w'] <= 250 * 0.75 + 2.0


def test_faster_than_constant_power():
    segments = _make_mixed_segments()
    result = optimize_pacing(segments, RIDER, ENV, ftp_w=250, target_if=0.75)
    constant_power = 250 * 0.75
    constant_time = sum(segment_time(constant_power, s, RIDER, ENV) for s in segments)
    assert result['total_time_s'] <= constant_time + 1.0


def test_result_structure():
    segments = _make_segments(10)
    result = optimize_pacing(segments, RIDER, ENV, ftp_w=200, target_if=0.75)
    assert 'segments' in result
    assert 'total_time_s' in result
    assert 'wap_w' in result
    assert 'intensity_factor' in result
    assert 'tss' in result
    assert 'variability_index' in result
    assert 'solver_success' in result
    assert len(result['segments']) == 10


def test_enriched_segments_have_power():
    segments = _make_segments(10)
    result = optimize_pacing(segments, RIDER, ENV, ftp_w=200, target_if=0.75)
    for seg in result['segments']:
        assert 'power_w' in seg
        assert 'speed_ms' in seg
        assert 'time_s' in seg
        assert seg['power_w'] >= 60


def test_power_within_bounds():
    segments = _make_segments(10)
    result = optimize_pacing(segments, RIDER, ENV, ftp_w=200, target_if=0.75, min_power_w=80, max_power_w=250)
    for seg in result['segments']:
        assert 80 <= seg['power_w'] <= 250 + 0.1


def test_flat_course_low_variability():
    segments = _make_segments(20, gradient=0.0)
    result = optimize_pacing(segments, RIDER, ENV, ftp_w=250, target_if=0.75)
    assert result['variability_index'] < 1.10
