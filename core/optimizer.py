import time
import numpy as np
from scipy.optimize import minimize
from core.physics import segment_time, speed_from_power
from core.normalized_power import (
    weighted_avg_power, intensity_factor, training_stress_score, variability_index
)

MAX_SOLVER_SECONDS = 15
SLSQP_MAX_SEGMENTS = 30


def _heuristic_pacing(segments, rider, env, ftp_w, target_if, min_power_w, max_power_w):
    target_power = ftp_w * target_if
    powers = []
    for seg in segments:
        g = seg.get('gradient', 0.0)
        if g > 0.08:
            p = target_power * 1.08
        elif g > 0.03:
            p = target_power * 1.05
        elif g < -0.05:
            p = max(min_power_w, target_power * 0.65)
        elif g < -0.03:
            p = max(min_power_w, target_power * 0.80)
        else:
            p = target_power
        p = max(min_power_w, min(max_power_w, p))
        powers.append(p)

    for _ in range(5):
        times = [segment_time(p, s, rider, env) for p, s in zip(powers, segments)]
        wap = weighted_avg_power(powers, times)
        if wap <= 0:
            break
        scale = target_power / wap
        powers = [max(min_power_w, min(max_power_w, p * scale)) for p in powers]

    times = [segment_time(p, s, rider, env) for p, s in zip(powers, segments)]
    wap = weighted_avg_power(powers, times)
    return powers, times, wap


def _downsample_segments(segments, target_count):
    if len(segments) <= target_count:
        return segments, None

    step = len(segments) / target_count
    downsampled = []
    mapping = []

    i = 0.0
    while int(i) < len(segments):
        start = int(i)
        end = min(int(i + step), len(segments))
        group = segments[start:end]

        merged = {
            'index': len(downsampled),
            'lat': group[0]['lat'],
            'lon': group[0]['lon'],
            'distance_m': sum(s['distance_m'] for s in group),
            'cumulative_m': group[0]['cumulative_m'],
            'elevation_m': group[0]['elevation_m'],
            'gradient': np.mean([s['gradient'] for s in group]),
            'surface': group[0]['surface'],
            'crr': np.mean([s.get('crr', 0.006) for s in group]),
            'zone_label': group[0]['zone_label'],
            '_original_indices': list(range(start, end)),
        }
        downsampled.append(merged)
        mapping.append((start, end))
        i += step

    return downsampled, mapping


def _upsample_powers(powers, mapping, original_count):
    full_powers = [0.0] * original_count
    for power, (start, end) in zip(powers, mapping):
        for j in range(start, end):
            full_powers[j] = power
    return full_powers


def optimize_pacing(
    segments: list[dict],
    rider: dict,
    env: dict,
    ftp_w: float,
    target_if: float = 0.75,
    min_power_w: float = 60,
    max_power_w: float = None,
    solver_tolerance: float = 1e-4,
) -> dict:
    if max_power_w is None:
        max_power_w = ftp_w * 1.15

    original_segments = segments
    mapping = None

    solver_success = False
    solver_message = ""

    if len(segments) <= SLSQP_MAX_SEGMENTS:
        n = len(segments)
        target_wap = ftp_w * target_if

        def objective(power_array):
            times = [segment_time(p, s, rider, env) for p, s in zip(power_array, segments)]
            return sum(times)

        def wap_constraint(power_array):
            times = [segment_time(p, s, rider, env) for p, s in zip(power_array, segments)]
            wap = weighted_avg_power(list(power_array), times)
            return target_wap - wap

        constraints = [{'type': 'ineq', 'fun': wap_constraint}]
        bounds = [(min_power_w, max_power_w)] * n
        x0 = np.full(n, target_wap)

        start_time = time.time()
        try:
            result = minimize(
                objective, x0,
                method='SLSQP',
                bounds=bounds,
                constraints=constraints,
                options={'maxiter': 500, 'ftol': solver_tolerance},
            )
            elapsed = time.time() - start_time

            if result.success and elapsed < MAX_SOLVER_SECONDS:
                powers = list(result.x)
                solver_success = True
                solver_message = "SLSQP optimization successful"
            else:
                powers, _, _ = _heuristic_pacing(segments, rider, env, ftp_w, target_if, min_power_w, max_power_w)
                solver_message = f"SLSQP incomplete ({elapsed:.1f}s); using heuristic"
        except Exception as e:
            powers, _, _ = _heuristic_pacing(segments, rider, env, ftp_w, target_if, min_power_w, max_power_w)
            solver_message = f"Solver error: {str(e)}; using heuristic"
    else:
        powers, _, _ = _heuristic_pacing(segments, rider, env, ftp_w, target_if, min_power_w, max_power_w)
        solver_success = False
        solver_message = f"Course has {len(segments)} segments; using gradient-based heuristic for speed"

    times = [segment_time(p, s, rider, env) for p, s in zip(powers, segments)]
    speeds = []
    for p, s in zip(powers, segments):
        try:
            v = speed_from_power(p, s.get('gradient', 0), rider['mass_kg'], rider['cda'],
                                 s.get('crr', 0.006), env.get('wind_ms', 0), env.get('rho', 1.225),
                                 rider.get('drivetrain_eff', 0.97))
        except ValueError:
            v = 0.5
        speeds.append(v)

    enriched = []
    elapsed_time = 0.0
    for i, seg in enumerate(segments):
        enriched.append({
            **seg,
            'power_w': powers[i],
            'speed_ms': speeds[i],
            'time_s': times[i],
            'elapsed_s': elapsed_time,
        })
        elapsed_time += times[i]

    total_time = sum(times)
    wap = weighted_avg_power(powers, times)
    if_ = intensity_factor(wap, ftp_w)
    duration_hours = total_time / 3600
    tss = training_stress_score(duration_hours, if_)
    vi = variability_index(powers, times)
    mean_power = np.sum(np.array(powers) * np.array(times)) / total_time if total_time > 0 else 0

    return {
        'segments': enriched,
        'total_time_s': total_time,
        'wap_w': wap,
        'intensity_factor': if_,
        'mean_power_w': float(mean_power),
        'variability_index': vi,
        'tss': tss,
        'solver_success': solver_success,
        'solver_message': solver_message,
    }
