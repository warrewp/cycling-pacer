import math
import json
import os
from scipy.optimize import brentq

_SURFACES_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'surfaces.json')

def load_surfaces() -> dict:
    with open(_SURFACES_PATH) as f:
        return json.load(f)


def air_density(temperature_c: float, elevation_m: float, pressure_hpa: float = 1013.25) -> float:
    return 1.225 * (273.15 / (273.15 + temperature_c)) * math.exp(-elevation_m / 8500)


def power_from_speed(
    speed_ms: float,
    gradient: float,
    mass_kg: float,
    cda: float,
    crr: float,
    wind_ms: float,
    rho: float,
    drivetrain_eff: float = 0.97,
) -> float:
    theta = math.atan(gradient)
    f_gravity = mass_kg * 9.8067 * math.sin(theta)
    f_rolling = crr * mass_kg * 9.8067 * math.cos(theta)
    v_air = speed_ms + wind_ms
    f_aero = 0.5 * cda * rho * v_air * abs(v_air)
    total_force = f_gravity + f_rolling + f_aero
    return total_force * speed_ms / drivetrain_eff


def speed_from_power(
    power_w: float,
    gradient: float,
    mass_kg: float,
    cda: float,
    crr: float,
    wind_ms: float,
    rho: float,
    drivetrain_eff: float = 0.97,
) -> float:
    def residual(v):
        return power_from_speed(v, gradient, mass_kg, cda, crr, wind_ms, rho, drivetrain_eff) - power_w

    v_low = 0.01
    v_high = 40.0

    r_low = residual(v_low)
    r_high = residual(v_high)

    if r_low > 0:
        raise ValueError(
            f"Power {power_w:.0f}W insufficient for gradient {gradient*100:.1f}% "
            f"(need >{power_from_speed(v_low, gradient, mass_kg, cda, crr, wind_ms, rho, drivetrain_eff):.0f}W)"
        )

    if r_high < 0:
        v_high = 80.0
        r_high = residual(v_high)
        if r_high < 0:
            raise ValueError(f"No solution found below 80 m/s for {power_w:.0f}W")

    return brentq(residual, v_low, v_high, xtol=1e-6)


def segment_time(power_w: float, segment: dict, rider: dict, env: dict) -> float:
    distance_m = segment['distance_m']
    if distance_m <= 0:
        return 0.0

    gradient = segment.get('gradient', 0.0)
    crr = rider.get('crr_override', segment.get('crr', 0.006))
    mass_kg = rider['mass_kg']
    cda = rider['cda']
    wind_ms = env.get('wind_ms', 0.0)
    rho = env.get('rho', 1.225)
    drivetrain_eff = rider.get('drivetrain_eff', 0.97)

    try:
        speed = speed_from_power(power_w, gradient, mass_kg, cda, crr, wind_ms, rho, drivetrain_eff)
    except ValueError:
        speed = 0.5  # crawl speed fallback

    if speed < 0.01:
        speed = 0.01

    return distance_m / speed
