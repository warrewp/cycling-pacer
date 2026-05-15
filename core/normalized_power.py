import numpy as np


def weighted_avg_power(power_array: list[float], time_array: list[float]) -> float:
    if not power_array or not time_array:
        return 0.0

    powers = np.array(power_array, dtype=float)
    times = np.array(time_array, dtype=float)

    total_time = np.sum(times)
    if total_time <= 0:
        return 0.0

    dt = 1.0
    expanded_power = []
    for p, t in zip(powers, times):
        n_samples = max(1, int(round(t)))
        expanded_power.extend([p] * n_samples)

    expanded = np.array(expanded_power, dtype=float)

    window = 30
    if len(expanded) < window:
        return float(np.mean(powers))

    rolling = np.convolve(expanded, np.ones(window) / window, mode='valid')
    rolling_4th = rolling ** 4
    mean_4th = np.mean(rolling_4th)
    return float(mean_4th ** 0.25)


def intensity_factor(wap: float, ftp: float) -> float:
    if ftp <= 0:
        return 0.0
    return wap / ftp


def training_stress_score(duration_hours: float, if_: float) -> float:
    return if_ ** 2 * duration_hours * 100


def variability_index(power_array: list[float], time_array: list[float]) -> float:
    if not power_array or not time_array:
        return 1.0

    powers = np.array(power_array, dtype=float)
    times = np.array(time_array, dtype=float)

    total_time = np.sum(times)
    if total_time <= 0:
        return 1.0

    mean_power = np.sum(powers * times) / total_time
    if mean_power <= 0:
        return 1.0

    wap = weighted_avg_power(power_array, time_array)
    return wap / mean_power
