"""
T (Snapshot Interval) Sensitivity Analysis.

Reuses load_network_state and route_proposed from run_from_existing.py
(the same pipeline that produced beta_sensitivity.csv and tau_sensitivity.csv).

Modeling T effect:
  Original data is sampled at T_orig = 5 min granularity.
  - T = T_orig: fresh routing every cycle (baseline; identical for T <= T_orig).
  - T > T_orig: a routing decision is made every k = T / T_orig cycles and
    held for the subsequent k-1 cycles. The held path is evaluated against
    the actual (stale-relative) network state at each cycle.

T_vals = [60, 300, 600, 1800]  (1, 5, 10, 30 min)
Setup: Scenario 2, 2.8 Gbps, 100 s, beta = 0.5, tau = 0.5
"""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config as cfg
from simulation.evaluate import evaluate_algorithm
from plots.plot_figures import save_sensitivity_csv
from run_from_existing import (
    load_network_state, load_paths, build_graph, route_proposed,
    ORIG_DIR, OUT_DIR, GRAPH_INFO_FILE,
)

PROPOSED_PATHS_FILE = os.path.join(
    ORIG_DIR, "Starlink_Proposed_(400,500,600)_Path.txt"
)

T_ORIG_S = 300                         # data granularity (5 min)
T_VALS_S = [60, 300, 600, 1800]        # 1, 5, 10, 30 min
DATA_RATE_GBPS = 2.8
DURATION_S = 100


def select_src_dst_pairs():
    """Match run_from_existing.py: extract (src, dst) from original Proposed paths."""
    orig = load_paths(PROPOSED_PATHS_FILE)
    src_dst = {c: (p[0], p[-1]) for c, p in orig.items() if p is not None}
    return src_dst


def run_T(ns, cycles, src_dst, T_s):
    """Simulate routing under snapshot interval T_s.

    Routing is recomputed at cycles c where c % k == 0 (k = T_s / T_orig,
    floored at 1). Between recomputations, the most recent path is held
    and evaluated against the actual (stale-relative) network state.
    """
    k = max(int(round(T_s / T_ORIG_S)), 1)
    paths = {}
    last_path = None
    last_route_cycle = None
    for c in cycles:
        if c not in src_dst:
            paths[c] = None
            continue
        src, dst = src_dst[c]
        if last_route_cycle is None or (c - last_route_cycle) >= k:
            G = build_graph(ns, c)
            last_path = route_proposed(G, src, dst, tau=cfg.TAU)
            last_route_cycle = c
        paths[c] = last_path
    metric = evaluate_algorithm(paths, ns, DATA_RATE_GBPS, DURATION_S)
    return metric


def main():
    print("=" * 60)
    print("  T (Snapshot Interval) Sensitivity")
    print("=" * 60)
    print(f"  Data granularity: T_orig = {T_ORIG_S} s")
    print(f"  T values:         {T_VALS_S} s ({[t//60 for t in T_VALS_S]} min)")
    print(f"  Setup:            {DATA_RATE_GBPS} Gbps, {DURATION_S} s, "
          f"beta={cfg.BETA}, tau={cfg.TAU}")

    print(f"\n[1/3] Loading network state from {GRAPH_INFO_FILE} ...", flush=True)
    ns = load_network_state(GRAPH_INFO_FILE)
    cycles = sorted(set(c for (c, _, _) in ns.keys()))
    print(f"  {len(cycles)} cycles loaded", flush=True)

    print(f"\n[2/3] Selecting source-destination pairs ...", flush=True)
    src_dst = select_src_dst_pairs()
    print(f"  {len(src_dst)} pairs (matched to original Proposed paths)", flush=True)

    print(f"\n[3/3] Running T sweep ...", flush=True)
    T_res = {}
    for T_s in T_VALS_S:
        m = run_T(ns, cycles, src_dst, T_s)
        T_res[T_s] = m
        print(f"  T={T_s:>5d}s ({T_s/60:>4.1f} min): "
              f"Throughput={m['throughput']:.3f} Gbps, "
              f"PLR={m['packet_loss_rate']:.1f}%, "
              f"Hops={m.get('avg_hop_count', 0):.1f}", flush=True)

    csv_path = os.path.join(OUT_DIR, 'T_sensitivity.csv')
    save_sensitivity_csv(T_res, 'T_seconds', T_VALS_S, 'T_sensitivity.csv', OUT_DIR)

    print()
    print("=" * 60)
    print("  T Sensitivity Results")
    print("=" * 60)
    print(f"  {'T (min)':>8s}  {'Throughput (Gbps)':>18s}  {'PLR (%)':>8s}")
    for T_s in T_VALS_S:
        m = T_res[T_s]
        print(f"  {T_s/60:>8.1f}  {m['throughput']:>18.3f}  {m['packet_loss_rate']:>8.1f}")
    print("=" * 60)


if __name__ == '__main__':
    main()
