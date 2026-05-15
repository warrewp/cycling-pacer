import pytest
from core.normalized_power import (
    weighted_avg_power, intensity_factor, training_stress_score, variability_index
)


def test_constant_power_wap():
    powers = [200.0] * 50
    times = [60.0] * 50  # 50 minutes
    wap = weighted_avg_power(powers, times)
    assert abs(wap - 200.0) < 5.0


def test_variable_power_wap_higher():
    constant_powers = [200.0] * 50
    variable_powers = [100.0, 300.0] * 25
    times = [60.0] * 50
    wap_const = weighted_avg_power(constant_powers, times)
    wap_var = weighted_avg_power(variable_powers, times)
    assert wap_var > wap_const


def test_intensity_factor_basic():
    assert abs(intensity_factor(150, 200) - 0.75) < 0.001


def test_intensity_factor_zero_ftp():
    assert intensity_factor(150, 0) == 0.0


def test_training_stress_score_basic():
    tss = training_stress_score(1.0, 0.75)
    assert abs(tss - 56.25) < 0.1


def test_variability_index_constant():
    powers = [200.0] * 50
    times = [60.0] * 50
    vi = variability_index(powers, times)
    assert 0.95 < vi < 1.05


def test_variability_index_variable():
    powers = [100.0, 300.0] * 25
    times = [60.0] * 50
    vi = variability_index(powers, times)
    assert vi > 1.0


def test_empty_inputs():
    assert weighted_avg_power([], []) == 0.0
    assert variability_index([], []) == 1.0
