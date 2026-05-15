import pytest
from core.physics import air_density, speed_from_power, power_from_speed, segment_time


def test_flat_no_wind():
    speed = speed_from_power(200, 0.0, 80, 0.35, 0.006, 0.0, 1.225)
    assert 8.5 < speed < 9.2  # ~31-33 km/h


def test_roundtrip():
    p_in = 250
    speed = speed_from_power(p_in, 0.03, 75, 0.32, 0.006, 0.0, 1.225)
    p_out = power_from_speed(speed, 0.03, 75, 0.32, 0.006, 0.0, 1.225)
    assert abs(p_in - p_out) < 0.5


def test_air_density_altitude():
    rho_sea = air_density(20, 0)
    rho_leadville = air_density(20, 3094)
    assert rho_leadville < rho_sea
    assert 0.65 < rho_leadville / rho_sea < 0.75


def test_air_density_sea_level():
    rho = air_density(15, 0)
    assert 1.10 < rho < 1.20


def test_headwind_reduces_speed():
    speed_calm = speed_from_power(200, 0.0, 80, 0.35, 0.006, 0.0, 1.225)
    speed_head = speed_from_power(200, 0.0, 80, 0.35, 0.006, 5.0, 1.225)
    assert speed_head < speed_calm


def test_tailwind_increases_speed():
    speed_calm = speed_from_power(200, 0.0, 80, 0.35, 0.006, 0.0, 1.225)
    speed_tail = speed_from_power(200, 0.0, 80, 0.35, 0.006, -5.0, 1.225)
    assert speed_tail > speed_calm


def test_uphill_slower_than_flat():
    speed_flat = speed_from_power(200, 0.0, 80, 0.35, 0.006, 0.0, 1.225)
    speed_up = speed_from_power(200, 0.05, 80, 0.35, 0.006, 0.0, 1.225)
    assert speed_up < speed_flat


def test_downhill_faster_than_flat():
    speed_flat = speed_from_power(200, 0.0, 80, 0.35, 0.006, 0.0, 1.225)
    speed_down = speed_from_power(200, -0.05, 80, 0.35, 0.006, 0.0, 1.225)
    assert speed_down > speed_flat


def test_segment_time_basic():
    seg = {'distance_m': 1000, 'gradient': 0.0, 'crr': 0.006}
    rider = {'mass_kg': 80, 'cda': 0.35}
    env = {'wind_ms': 0.0, 'rho': 1.225}
    t = segment_time(200, seg, rider, env)
    assert 100 < t < 140  # ~1km at ~30 km/h = ~120s


def test_segment_time_zero_distance():
    seg = {'distance_m': 0, 'gradient': 0.0}
    rider = {'mass_kg': 80, 'cda': 0.35}
    env = {'rho': 1.225}
    assert segment_time(200, seg, rider, env) == 0.0


def test_power_from_speed_basic():
    power = power_from_speed(8.33, 0.0, 80, 0.35, 0.006, 0.0, 1.225)
    assert 150 < power < 190


def test_roundtrip_downhill():
    p_in = 100
    speed = speed_from_power(p_in, -0.03, 75, 0.32, 0.006, 0.0, 1.225)
    p_out = power_from_speed(speed, -0.03, 75, 0.32, 0.006, 0.0, 1.225)
    assert abs(p_in - p_out) < 0.5
