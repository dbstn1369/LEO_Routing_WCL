"""
Configuration for LEO Routing WCL Simulation
Paper: "Link-Aware Routing in Multi-Tier LEO Mega-Constellations"
Scenario 2: 400 / 500 / 600 km, 1500 satellites (3 tiers × 500)
"""

import numpy as np

# ── Constellation ──────────────────────────────────────────────
N_TIERS = 3
SATS_PER_TIER = 500
N_SATELLITES = N_TIERS * SATS_PER_TIER  # 1500
N_ORBITAL_PLANES = 17  # per tier

TIER_ALTITUDES_KM = [400, 500, 600]  # Scenario 2
TIER_ALTITUDE_TOLERANCE_KM = 30      # ±30 km for layer assignment

# ── Physical Constants ─────────────────────────────────────────
G_CONST = 6.67430e-11       # Gravitational constant (m^3/s^2)
M_EARTH = 5.972e24          # Earth mass (kg)
R_EARTH_M = 6_371_000       # Earth radius (m)
C_LIGHT = 3e8               # Speed of light (m/s)

# ── ISL Parameters ─────────────────────────────────────────────
ISL_MAX_DISTANCE_M = 1_500_000   # 1500 km (matches Starlink_LEO_Routing reference)
MAX_CONNECTIONS = 8               # per satellite
BEAMWIDTH_DEG = 60                # antenna beamwidth

# ── Radio / Channel ────────────────────────────────────────────
TX_POWER_W = 10.0                 # P_o
TX_GAIN_DBI = 38.0                # G_t
RX_GAIN_DBI = 38.0                # G_r
CARRIER_FREQ_HZ = 26e9            # Ka-band (26 GHz)
BANDWIDTH_HZ = 500e6              # B = 500 MHz
NOISE_PSD_DBM_HZ = -174.0         # N_0 = -174 dBm/Hz
NOISE_POWER_W = 10**((NOISE_PSD_DBM_HZ - 30) / 10) * BANDWIDTH_HZ
KAPPA = 3e-5                      # altitude-dependent attenuation coefficient (m^-1)
                                  # S1 (Δh=10–20 km): η ∈ [0.74, 0.55] (moderate interference)
                                  # S2 (Δh=100–200 km): η ∈ [0.050, 0.0025] (low interference)
                                  # → moderate S1 vs S2 contrast, mirrors paper figure
POLAR_LATITUDE_THRESHOLD = 70     # φ_p in degrees

# ── Snapshot ───────────────────────────────────────────────────
SNAPSHOT_INTERVAL_S = 300         # T = 5 min
N_CYCLES = 80                    # number of snapshots

# ── Utility / Pruning ─────────────────────────────────────────
BETA = 0.5                       # weighting factor (duration vs capacity)
TAU = 0.5                        # inference pruning threshold
TAU_TRAIN = 0.05                 # labeling threshold for GNN training

# ── Simulation ─────────────────────────────────────────────────
DATA_RATES_GBPS = np.array([1.0, 1.2, 1.4, 1.6, 1.8, 2.0, 2.2, 2.4, 2.6, 2.8])
DURATIONS_S = np.array([10, 20, 30, 40, 50, 60, 70, 80, 90, 100])
PACKET_SIZE_BITS = 512 * 8       # 512 bytes = 4096 bits

# ── Algorithm Names ────────────────────────────────────────────
ALG_PROPOSED = "Proposed"
ALG_GRLR = "GRLR"
ALG_DR = "DR"
ALG_STR = "STR"
ALG_WO = "w/o Pruning"
ALGORITHMS = [ALG_PROPOSED, ALG_GRLR, ALG_DR, ALG_STR]  # for figures
ALGORITHMS_ALL = [ALG_PROPOSED, ALG_GRLR, ALG_DR, ALG_STR, ALG_WO]  # includes ablation

# ── Plot Style ─────────────────────────────────────────────────
PLOT_MARKERS = {"Proposed": "o", "GRLR": "D", "DR": "s", "STR": "^", "w/o Pruning": "v"}
PLOT_LINES   = {"Proposed": "-", "GRLR": "--", "DR": "-.", "STR": ":", "w/o Pruning": (0,(3,1,1,1))}
PLOT_COLORS  = {"Proposed": "#1f77b4", "GRLR": "#ff7f0e", "DR": "#2ca02c", "STR": "#d62728", "w/o Pruning": "#9467bd"}
