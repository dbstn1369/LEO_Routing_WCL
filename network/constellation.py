"""
Walker-delta constellation generator for multi-tier LEO mega-constellation.
Generates 3D ECI positions and velocities for all satellites across snapshots.
"""

import numpy as np
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import config as cfg


def orbital_velocity(altitude_m):
    r = cfg.R_EARTH_M + altitude_m
    return np.sqrt(cfg.G_CONST * cfg.M_EARTH / r)


def orbital_period(altitude_m):
    r = cfg.R_EARTH_M + altitude_m
    return 2 * np.pi * np.sqrt(r**3 / (cfg.G_CONST * cfg.M_EARTH))


def _eci_position(r, raan, inc, arg_lat):
    cos_raan, sin_raan = np.cos(raan), np.sin(raan)
    cos_inc, sin_inc = np.cos(inc), np.sin(inc)
    cos_u, sin_u = np.cos(arg_lat), np.sin(arg_lat)
    x = r * (cos_raan * cos_u - sin_raan * sin_u * cos_inc)
    y = r * (sin_raan * cos_u + cos_raan * sin_u * cos_inc)
    z = r * sin_u * sin_inc
    return np.array([x, y, z])


def generate_constellation(n_cycles=None, dt=None, seed=42):
    if n_cycles is None:
        n_cycles = cfg.N_CYCLES
    if dt is None:
        dt = cfg.SNAPSHOT_INTERVAL_S

    np.random.seed(seed)
    inc = np.radians(53.0)

    all_positions = np.zeros((cfg.N_SATELLITES, n_cycles, 3))
    all_velocities = np.zeros((cfg.N_SATELLITES, n_cycles, 3))

    sat_id = 0
    for tier_idx, alt_km in enumerate(cfg.TIER_ALTITUDES_KM):
        alt_m = alt_km * 1000
        r = cfg.R_EARTH_M + alt_m
        n_mean = np.sqrt(cfg.G_CONST * cfg.M_EARTH / r**3)
        n_planes = cfg.N_ORBITAL_PLANES
        sats_per_plane = cfg.SATS_PER_TIER // n_planes
        remainder = cfg.SATS_PER_TIER - sats_per_plane * n_planes

        for p in range(n_planes):
            raan = 2 * np.pi * p / n_planes
            n_sats_this_plane = sats_per_plane + (1 if p < remainder else 0)

            for s in range(n_sats_this_plane):
                M0 = 2 * np.pi * s / n_sats_this_plane + 2 * np.pi * p / (n_planes * n_sats_this_plane)

                for c in range(n_cycles):
                    t = c * dt
                    arg_lat = M0 + n_mean * t

                    pos = _eci_position(r, raan, inc, arg_lat)
                    all_positions[sat_id, c, :] = pos

                    arg_lat_dt = M0 + n_mean * (t + 1.0)
                    pos_dt = _eci_position(r, raan, inc, arg_lat_dt)
                    all_velocities[sat_id, c, :] = pos_dt - pos

                sat_id += 1

    return all_positions, all_velocities


def get_tier(sat_id):
    return sat_id // cfg.SATS_PER_TIER


def get_altitude_m(sat_id):
    tier = get_tier(sat_id)
    return cfg.TIER_ALTITUDES_KM[tier] * 1000


if __name__ == "__main__":
    pos, vel = generate_constellation(n_cycles=5)
    print(f"Shape: {pos.shape}")
    for tier, alt in enumerate(cfg.TIER_ALTITUDES_KM):
        start = tier * cfg.SATS_PER_TIER
        r = np.linalg.norm(pos[start, 0, :])
        print(f"Tier {tier} ({alt} km): radius = {r/1000:.1f} km, "
              f"altitude = {(r - cfg.R_EARTH_M)/1000:.1f} km")
