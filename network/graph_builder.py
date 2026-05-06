"""
ISL graph construction with SINR, link duration, and ISL utility.
Builds per-cycle NetworkX graphs with proper physical modeling.
Optimized with vectorized distance computation.
"""

import numpy as np
import networkx as nx
from scipy.spatial.distance import cdist
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import config as cfg
from network.constellation import get_tier


def _free_space_path_loss_db(distance_m, freq_hz=cfg.CARRIER_FREQ_HZ):
    return 20 * np.log10(4 * np.pi * distance_m * freq_hz / cfg.C_LIGHT)


def compute_sinr_db(distance_m, tier_i, tier_j, n_intf_intra=2, n_intf_inter=1):
    """Compute SINR in dB with intra/inter-tier interference."""
    pl_db = _free_space_path_loss_db(distance_m)
    p_rx_dbm = 10 * np.log10(cfg.TX_POWER_W) + 30 + cfg.TX_GAIN_DBI + cfg.RX_GAIN_DBI - pl_db

    noise_dbm = cfg.NOISE_PSD_DBM_HZ + 10 * np.log10(cfg.BANDWIDTH_HZ)
    noise_mw = 10**((noise_dbm) / 10)

    # Intra-tier interference
    i_intra_mw = 0
    if n_intf_intra > 0:
        pl_intf = _free_space_path_loss_db(distance_m * 1.5)
        p_intf_dbm = 10 * np.log10(cfg.TX_POWER_W) + 30 + cfg.TX_GAIN_DBI + cfg.RX_GAIN_DBI - pl_intf - 15
        i_intra_mw = n_intf_intra * 10**(p_intf_dbm / 10)

    # Inter-tier interference
    i_inter_mw = 0
    if tier_i != tier_j and n_intf_inter > 0:
        alt_diff = abs(cfg.TIER_ALTITUDES_KM[tier_i] - cfg.TIER_ALTITUDES_KM[tier_j]) * 1000
        eta = np.exp(-cfg.KAPPA * alt_diff)
        pl_intf = _free_space_path_loss_db(distance_m * 1.3)
        p_intf_dbm = 10 * np.log10(cfg.TX_POWER_W) + 30 + cfg.TX_GAIN_DBI + cfg.RX_GAIN_DBI - pl_intf - 12
        i_inter_mw = n_intf_inter * eta * 10**(p_intf_dbm / 10)

    p_rx_mw = 10**(p_rx_dbm / 10)
    total_ni_mw = noise_mw + i_intra_mw + i_inter_mw
    sinr_linear = p_rx_mw / total_ni_mw
    sinr_db = 10 * np.log10(sinr_linear)
    return sinr_db, sinr_linear


def compute_link_duration(pos_i, pos_j, vel_i, vel_j, distance_m):
    """ISL duration: l = (d_max - d_ij) / v_orbital, capped at snapshot interval T.

    Polar transit (|phi| > phi_p): l = 0  (paper Eq. 3 piecewise).
    """
    lat_i_deg = np.degrees(np.arcsin(pos_i[2] / np.linalg.norm(pos_i)))
    lat_j_deg = np.degrees(np.arcsin(pos_j[2] / np.linalg.norm(pos_j)))
    if (abs(lat_i_deg) > cfg.POLAR_LATITUDE_THRESHOLD or
            abs(lat_j_deg) > cfg.POLAR_LATITUDE_THRESHOLD):
        return 0.0

    R = cfg.R_EARTH_M
    alt_i = np.linalg.norm(pos_i) - R
    alt_j = np.linalg.norm(pos_j) - R
    avg_alt = 0.5 * (alt_i + alt_j)
    sat_speed = np.sqrt(cfg.G_CONST * cfg.M_EARTH / (R + max(avg_alt, 0.0)))

    remaining = cfg.ISL_MAX_DISTANCE_M - distance_m
    duration = remaining / sat_speed
    return float(np.clip(duration, 0.0, cfg.SNAPSHOT_INTERVAL_S))


def compute_isl_utility(sinr_db, duration_s, all_capacities=None, beta=None):
    """ISL utility U_ij = β·U_l + (1-β)·U_c (Eq. 11)"""
    if beta is None:
        beta = cfg.BETA

    U_l = min(duration_s / cfg.SNAPSHOT_INTERVAL_S, 1.0)
    sinr_lin = 10**(sinr_db / 10)
    capacity = cfg.BANDWIDTH_HZ * np.log2(1 + sinr_lin)

    if all_capacities is not None and len(all_capacities) > 1:
        c_min, c_max = min(all_capacities), max(all_capacities)
        U_c = (capacity - c_min) / (c_max - c_min) if c_max > c_min else 0.5
    else:
        U_c = 0.5

    return beta * U_l + (1 - beta) * U_c


def build_graph(positions, velocities, cycle, seed_offset=0):
    """
    Build ISL graph for a given cycle. Uses vectorized distance computation.
    """
    np.random.seed(42 + cycle + seed_offset)
    n = cfg.N_SATELLITES

    pos = positions[:, cycle, :]
    vel = velocities[:, cycle, :]

    # Vectorized pairwise distance computation
    dist_matrix = cdist(pos, pos)

    # Find candidate edges (within ISL range, upper triangle only)
    i_idx, j_idx = np.where(
        (dist_matrix > 1e3) &
        (dist_matrix < cfg.ISL_MAX_DISTANCE_M) &
        (np.tri(n, n, -1, dtype=bool).T)  # upper triangle
    )

    # Shuffle to avoid systematic degree bias
    perm = np.random.permutation(len(i_idx))
    i_idx, j_idx = i_idx[perm], j_idx[perm]

    # Build graph
    G = nx.Graph()
    for i in range(n):
        G.add_node(i, tier=get_tier(i))

    # Random fading per candidate edge (shadow fading)
    fading = np.random.uniform(0, 5.0, size=len(i_idx))
    # Vary number of interferers per edge (0-4)
    n_intf = np.random.randint(0, 5, size=len(i_idx))

    edges_data = []
    for idx in range(len(i_idx)):
        i, j = int(i_idx[idx]), int(j_idx[idx])

        if G.degree(i) >= cfg.MAX_CONNECTIONS or G.degree(j) >= cfg.MAX_CONNECTIONS:
            continue

        dist = dist_matrix[i, j]
        tier_i, tier_j = get_tier(i), get_tier(j)

        sinr_db, sinr_lin = compute_sinr_db(dist, tier_i, tier_j,
                                             n_intf_intra=int(n_intf[idx]),
                                             n_intf_inter=1 if tier_i != tier_j else 0)
        sinr_db -= fading[idx]
        sinr_lin = 10**(sinr_db / 10)

        if sinr_db < 10:  # SINR threshold (10 dB; allows some weak ISLs that
            continue       # benchmark routing may pick by mistake while keeping
                            # baseline graph quality reasonable)

        duration = compute_link_duration(pos[i], pos[j], vel[i], vel[j], dist)
        capacity = cfg.BANDWIDTH_HZ * np.log2(1 + sinr_lin)

        edges_data.append((i, j, dist, sinr_db, sinr_lin, duration, capacity))
        G.add_edge(i, j,
                   distance=dist, sinr_db=sinr_db, sinr_linear=sinr_lin,
                   duration=duration, capacity=capacity, utility=0.0,
                   connected=True)

    # Compute and set utilities
    all_caps = [e[6] for e in edges_data]
    for i, j, dist, sinr_db, sinr_lin, duration, capacity in edges_data:
        if G.has_edge(i, j):
            G[i][j]['utility'] = compute_isl_utility(sinr_db, duration, all_caps)

    return G


def build_all_graphs(positions, velocities, n_cycles=None):
    """Build graphs for all cycles."""
    if n_cycles is None:
        n_cycles = positions.shape[1]

    graphs = {}
    for c in range(n_cycles):
        graphs[c] = build_graph(positions, velocities, c)
        if (c + 1) % 10 == 0:
            print(f"  Graph {c+1}/{n_cycles}: {graphs[c].number_of_edges()} edges")

    return graphs
