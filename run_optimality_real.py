"""
R5C4: Small-scale optimality comparison using REAL paper code.

For each network size N in {30, 50, 70}, generates a small Walker-delta
3-tier constellation using the actual generate_constellation + build_graph
from network/, then for 20 source-destination pairs:
  1. Enumerates all simple paths up to max_hops=MAX_HOPS via NetworkX.
  2. Optimal = max average ISL utility per hop, summed across pairs.
  3. Proposed = paper heuristic (route_proposed with tau=0.5).
  4. Ratio = Proposed / Optimal * 100.
"""
import os
import sys

import numpy as np
import networkx as nx

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config as cfg
from network import constellation as constellation_mod
from network import graph_builder as graph_builder_mod
from simulation.evaluate import evaluate_algorithm

# Spec: enumerate ALL simple paths up to 8 hops
MAX_HOPS = 8
N_PAIRS = 500
SEED = 42


def route_proposed(G, src, dst, tau=None):
    """Inlined from run_simulation.py."""
    if tau is None:
        tau = cfg.TAU
    utilities = [G[u][v]['utility'] for u, v in G.edges()]
    if not utilities:
        return None
    threshold = tau * max(utilities)
    G_pruned = G.copy()
    G_pruned.remove_edges_from(
        [(u, v) for u, v in G_pruned.edges() if G_pruned[u][v]['utility'] < threshold]
    )
    if src not in G_pruned or dst not in G_pruned:
        G_pruned = G.copy()
    for u, v in G_pruned.edges():
        G_pruned[u][v]['weight'] = max(1.0 - G_pruned[u][v]['utility'], 1e-6)
    try:
        paths = list(nx.all_shortest_paths(G_pruned, src, dst, weight='weight'))
        return min(paths, key=len)
    except (nx.NetworkXNoPath, nx.NodeNotFound):
        G_full = G.copy()
        for u, v in G_full.edges():
            G_full[u][v]['weight'] = max(1.0 - G_full[u][v]['utility'], 1e-6)
        try:
            return nx.shortest_path(G_full, src, dst, weight='weight')
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            return None


def path_avg_utility(G, path):
    hops = len(path) - 1
    if hops == 0:
        return 0.0
    return sum(G[path[i]][path[i+1]]['utility'] for i in range(hops)) / hops


def solve_optimum_enumerate(G, s, d, max_hops=MAX_HOPS):
    """Enumerate all simple paths up to max_hops; pick max avg-utility path."""
    if s not in G or d not in G or not nx.has_path(G, s, d):
        return None, 0.0, 0
    best_path, best_avg = None, -1.0
    n_explored = 0
    for path in nx.all_simple_paths(G, s, d, cutoff=max_hops):
        n_explored += 1
        avg = path_avg_utility(G, path)
        if avg > best_avg:
            best_avg = avg
            best_path = path
    return best_path, best_avg, n_explored


def configure_network(target_N):
    """Override cfg for the target satellite count. Returns (sats_per_tier, n_planes)."""
    if target_N == 30:
        cfg.SATS_PER_TIER = 10
        cfg.N_ORBITAL_PLANES = 2
    elif target_N == 50:
        cfg.SATS_PER_TIER = 17
        cfg.N_ORBITAL_PLANES = 3
    elif target_N == 70:
        cfg.SATS_PER_TIER = 23
        cfg.N_ORBITAL_PLANES = 3
    elif target_N == 100:
        cfg.SATS_PER_TIER = 33
        cfg.N_ORBITAL_PLANES = 4
    else:
        raise ValueError(f"Unsupported target_N={target_N}")
    cfg.N_SATELLITES = cfg.N_TIERS * cfg.SATS_PER_TIER
    return cfg.SATS_PER_TIER, cfg.N_ORBITAL_PLANES


def run_for_N(target_N):
    sats_per_tier, n_planes = configure_network(target_N)
    print(f"\n{'='*60}")
    print(f"  N_total = {cfg.N_SATELLITES} ({sats_per_tier}/tier × {cfg.N_TIERS} tiers, "
          f"{n_planes} planes)")
    print(f"{'='*60}")

    pos, vel = constellation_mod.generate_constellation(n_cycles=1)
    G = graph_builder_mod.build_graph(pos, vel, cycle=0)
    print(f"  Graph: {G.number_of_nodes()} satellites, {G.number_of_edges()} ISLs")

    rng = np.random.default_rng(SEED)
    nodes = list(G.nodes())
    pairs = []
    seen = set()
    attempts = 0
    while len(pairs) < N_PAIRS and attempts < 5000:
        attempts += 1
        s, d = rng.choice(nodes, 2, replace=False)
        s, d = int(s), int(d)
        if (s, d) in seen:
            continue
        if nx.has_path(G, s, d):
            pairs.append((s, d))
            seen.add((s, d))

    # Build network state for evaluate_algorithm: {(cycle, u, v): (connected, snr_lin, duration)}
    # Each pair treated as a separate "cycle" so evaluate_algorithm averages across pairs.
    opt_paths_dict = {}
    prop_paths_dict = {}
    ns = {}
    for idx, (s, d) in enumerate(pairs):
        opt_path, opt_avg, _ = solve_optimum_enumerate(G, s, d)
        if opt_path is None:
            continue
        prop_path = route_proposed(G.copy(), s, d, tau=cfg.TAU)
        opt_paths_dict[idx] = opt_path
        prop_paths_dict[idx] = prop_path
        for u, v in G.edges():
            snr_lin = G[u][v].get('sinr_linear', G[u][v].get('snr', 1.0))
            dur = G[u][v]['duration']
            ns[(idx, u, v)] = (True, snr_lin, dur)
            ns[(idx, v, u)] = (True, snr_lin, dur)

    opt_metric = evaluate_algorithm(opt_paths_dict, ns, 2.8, 100)
    prop_metric = evaluate_algorithm(prop_paths_dict, ns, 2.8, 100)

    thr_ratio = prop_metric['throughput'] / opt_metric['throughput'] * 100 \
                if opt_metric['throughput'] > 0 else 0
    plr_diff = prop_metric['packet_loss_rate'] - opt_metric['packet_loss_rate']

    print(f"\n  Throughput (Gbps):  Optimal={opt_metric['throughput']:.3f}, "
          f"Proposed={prop_metric['throughput']:.3f}, Ratio={thr_ratio:.1f}%")
    print(f"  PLR (%):            Optimal={opt_metric['packet_loss_rate']:.1f}, "
          f"Proposed={prop_metric['packet_loss_rate']:.1f}, Diff={plr_diff:+.1f} pp")
    return {
        'N': cfg.N_SATELLITES,
        'isls': G.number_of_edges(),
        'opt_thr': opt_metric['throughput'],
        'prop_thr': prop_metric['throughput'],
        'thr_ratio': thr_ratio,
        'opt_plr': opt_metric['packet_loss_rate'],
        'prop_plr': prop_metric['packet_loss_rate'],
        'plr_diff': plr_diff,
    }


def main():
    print("=" * 60)
    print("  R5C4: Small-Scale Optimality Comparison")
    print(f"  TAU={cfg.TAU}, BETA={cfg.BETA}, MAX_HOPS={MAX_HOPS}, N_PAIRS={N_PAIRS}")
    print("=" * 60)

    results = []
    for target_N in [30, 50, 70, 100]:
        results.append(run_for_N(target_N))

    print()
    print("=" * 80)
    print("  Throughput / PLR Optimality Comparison")
    print("=" * 80)
    print(f"  {'N':>4s}  {'ISLs':>5s}  {'Opt Thpt':>9s}  {'Prop Thpt':>10s}  "
          f"{'Ratio':>7s}  {'Opt PLR':>8s}  {'Prop PLR':>9s}  {'Diff (pp)':>10s}")
    for r in results:
        print(f"  {r['N']:>4d}  {r['isls']:>5d}  {r['opt_thr']:>9.3f}  "
              f"{r['prop_thr']:>10.3f}  {r['thr_ratio']:>6.1f}%  "
              f"{r['opt_plr']:>8.1f}  {r['prop_plr']:>9.1f}  {r['plr_diff']:>+10.1f}")
    print("=" * 80)


if __name__ == '__main__':
    main()
