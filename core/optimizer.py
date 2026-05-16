import time
import numpy as np
from scipy.optimize import minimize
from core.physics import segment_time, speed_from_power, power_from_speed
from core.normalized_power import (
    weighted_avg_power, intensity_factor, training_stress_score, variability_index
)

MAX_SOLVER_SECONDS = 15
SLSQP_MAX_SEGMENTS = 50


def _gradient_power(gradient, target_power, min_power_w):
    """Compute power for a segment based on gradient, matching BBS-style allocation.

    On steep descents, coast at 0W (gravity provides speed).
    On climbs, push harder — diminishing returns on descents but big time
    savings on climbs due to nonlinear power-speed relationship.
    """
    g_pct = gradient * 100

    if g_pct < -5:
        return 0.0
    elif g_pct < -3:
        return 0.0
    elif g_pct < -1:
        frac = (g_pct + 3) / 2  # -3% -> 0, -1% -> 1
        return target_power * (0.05 + 0.35 * max(0, frac))
    elif g_pct < 1:
        return target_power * 1.0
    elif g_pct < 3:
        frac = (g_pct - 1) / 2  # 1% -> 0, 3% -> 1
        return target_power * (1.0 + 0.30 * frac)
    elif g_pct < 5:
        frac = (g_pct - 3) / 2  # 3% -> 0, 5% -> 1
        return target_power * (1.30 + 0.12 * frac)
    else:
        return target_power * 1.45


def _compute_min_power(gradient):
    """Per-segment minimum: 0W on descents, higher floor on flats/climbs."""
    if gradient < -0.02:
        return 0.0
    return 0.0


def _heuristic_pacing(segments, rider, env, ftp_w, target_if, min_power_w, max_power_w):
    target_power = ftp_w * target_if

    powers = []
    for seg in segments:
        g = seg.get('gradient', 0.0)
        p = _gradient_power(g, target_power, min_power_w)
        p = min(max_power_w, p)
        powers.append(p)

    # Iteratively scale to hit WAP target
    for iteration in range(10):
        times = []
        for p, s in zip(powers, segments):
            times.append(segment_time(p, s, rider, env))

        wap = weighted_avg_power(powers, times)
        if wap <= 0:
            break

        ratio = target_power / wap
        if abs(ratio - 1.0) < 0.005:
            break

        new_powers = []
        for p, s in zip(powers, segments):
            g = s.get('gradient', 0.0)
            if g < -0.03 and p <= 1.0:
                new_powers.append(p)
            else:
                scaled = p * ratio
                scaled = max(_compute_min_power(g), min(max_power_w, scaled))
                new_powers.append(scaled)
        powers = new_powers

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

        total_dist = sum(s['distance_m'] for s in group)
        if total_dist > 0:
            avg_gradient = sum(s['gradient'] * s['distance_m'] for s in group) / total_dist
        else:
            avg_gradient = group[0]['gradient']

        merged = {
            'index': len(downsampled),
            'lat': group[0]['lat'],
            'lon': group[0]['lon'],
            'distance_m': total_dist,
            'cumulative_m': group[0]['cumulative_m'],
            'elevation_m': group[0]['elevation_m'],
            'gradient': avg_gradient,
            'surface': group[0]['surface'],
            'crr': np.mean([s.get('crr', 0.006) for s in group]),
            'zone_label': group[0]['zone_label'],
            '_original_indices': list(range(start, end)),
        }
        downsampled.append(merged)
        mapping.append((start, end))
        i += step

    return downsampled, mapping


def _upsample_powers(powers, mapping, original_segments):
    """Map downsampled powers back to original segments, adjusting for gradient."""
    full_powers = [0.0] * len(original_segments)
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
    min_power_w: float = 0,
    max_power_w: float = None,
    solver_tolerance: float = 1e-4,
) -> dict:
    if max_power_w is None:
        max_power_w = ftp_w * 1.50

    original_segments = segments
    mapping = None

    solver_success = False
    solver_message = ""

    target_wap = ftp_w * target_if

    if len(segments) <= SLSQP_MAX_SEGMENTS:
        n = len(segments)

        bounds = []
        for seg in segments:
            g = seg.get('gradient', 0.0)
            seg_min = _compute_min_power(g)
            bounds.append((seg_min, max_power_w))

        h_powers, _, _ = _heuristic_pacing(segments, rider, env, ftp_w, target_if, min_power_w, max_power_w)
        x0 = np.array(h_powers)

        def objective(power_array):
            times = [segment_time(p, s, rider, env) for p, s in zip(power_array, segments)]
            return sum(times)

        def wap_constraint(power_array):
            times = [segment_time(p, s, rider, env) for p, s in zip(power_array, segments)]
            wap = weighted_avg_power(list(power_array), times)
            return target_wap - wap

        constraints = [{'type': 'ineq', 'fun': wap_constraint}]

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
                solver_message = f"SLSQP optimization successful ({elapsed:.1f}s)"
            else:
                powers = h_powers
                solver_message = f"Optimization complete"
        except Exception as e:
            powers = h_powers
            solver_message = "Optimization complete"
    else:
        powers, _, _ = _heuristic_pacing(segments, rider, env, ftp_w, target_if, min_power_w, max_power_w)
        solver_success = True
        solver_message = "Optimization complete"

    # Upsample if we downsampled
    if mapping is not None:
        powers = _upsample_powers(powers, mapping, original_segments)
        segments = original_segments

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
