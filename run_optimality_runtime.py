"""
Optimality + runtime measurement for small-scale networks.
N in {30, 50, 70}: enumerate all simple paths up to MAX_HOPS=8, compare with Proposed.
Measures wall-clock runtime for both Proposed and Optimal (enumeration).
"""
import os
import sys
import time

import numpy as np
import networkx as nx

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config as cfg
from network import constellation as constellation_mod
from network import graph_builder as graph_builder_mod
from simulation.evaluate import evaluate_algorithm

MAX_HOPS = 8
N_PAIRS = 50
SEED = 42
ALPHA_DUR = 2.0
LAMBDA_CAP = 0.3


def route_proposed(G, src, dst, tau=None):
    if tau is None:
        tau = cfg.TAU
    if src not in G or dst not in G:
        return None
    utils = [G[u][v]['utility'] for u, v in G.edges()]
    if not utils:
        return None
    threshold = tau * max(utils)
    Gp = G.copy()
    Gp.remove_edges_from([(u, v) for u, v in Gp.edges() if Gp[u][v]['utility'] < threshold])
    if src not in Gp or dst not in Gp or not nx.has_path(Gp, src, dst):
        Gp = G.copy()
    for u, v in Gp.edges():
        l = Gp[u][v]['duration']
        w_dur = np.log1p(ALPHA_DUR / max(l, 1e-3))
        u_full = Gp[u][v]['utility']
        Gp[u][v]['weight'] = w_dur + LAMBDA_CAP * (1.0 - u_full)
    try:
        return nx.shortest_path(Gp, src, dst, weight='weight')
    except (nx.NetworkXNoPath, nx.NodeNotFound):
        return None


def path_avg_utility(G, path):
    hops = len(path) - 1
    if hops == 0:
        return 0.0
    return sum(G[path[i]][path[i+1]]['utility'] for i in range(hops)) / hops


def solve_optimum_enumerate(G, s, d, max_hops=MAX_HOPS):
    if s not in G or d not in G or not nx.has_path(G, s, d):
        return None, 0.0
    best_path, best_avg = None, -1.0
    for path in nx.all_simple_paths(G, s, d, cutoff=max_hops):
        avg = path_avg_utility(G, path)
        if avg > best_avg:
            best_avg = avg
            best_path = path
    return best_path, best_avg


def configure_network(target_N):
    if target_N == 30:
        cfg.SATS_PER_TIER = 10
        cfg.N_ORBITAL_PLANES = 2
    elif target_N == 50:
        cfg.SATS_PER_TIER = 17
        cfg.N_ORBITAL_PLANES = 3
    elif target_N == 70:
        cfg.SATS_PER_TIER = 23
        cfg.N_ORBITAL_PLANES = 3
    cfg.N_SATELLITES = cfg.N_TIERS * cfg.SATS_PER_TIER


def run_for_N(target_N):
    configure_network(target_N)
    print(f"\n=== N={cfg.N_SATELLITES} ({cfg.SATS_PER_TIER}/tier) ===", flush=True)

    pos, vel = constellation_mod.generate_constellation(n_cycles=1)
    G = graph_builder_mod.build_graph(pos, vel, cycle=0)
    print(f"  Graph: {G.number_of_nodes()} sats, {G.number_of_edges()} ISLs", flush=True)

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

    opt_paths_dict = {}
    prop_paths_dict = {}
    ns = {}

    t_opt = 0.0
    t_prop = 0.0

    for idx, (s, d) in enumerate(pairs):
        t0 = time.time()
        opt_path, _ = solve_optimum_enumerate(G, s, d)
        t_opt += time.time() - t0

        if opt_path is None:
            continue
        t0 = time.time()
        prop_path = route_proposed(G.copy(), s, d, tau=cfg.TAU)
        t_prop += time.time() - t0

        opt_paths_dict[idx] = opt_path
        prop_paths_dict[idx] = prop_path
        for u, v in G.edges():
            snr_lin = G[u][v].get('sinr_linear', G[u][v].get('snr', 1.0))
            dur = G[u][v]['duration']
            ns[(idx, u, v)] = (True, snr_lin, dur)
            ns[(idx, v, u)] = (True, snr_lin, dur)

    opt_metric = evaluate_algorithm(opt_paths_dict, ns, 2.8, 100)
    prop_metric = evaluate_algorithm(prop_paths_dict, ns, 2.8, 100)

    n_pairs = len(opt_paths_dict)
    runtime_opt_ms = (t_opt / max(n_pairs, 1)) * 1000
    runtime_prop_ms = (t_prop / max(n_pairs, 1)) * 1000

    # Edges pruned ratio (Proposed)
    n_edges = G.number_of_edges()
    utils = [G[u][v]['utility'] for u, v in G.edges()]
    threshold = cfg.TAU * max(utils)
    n_pruned = sum(1 for u, v in G.edges() if G[u][v]['utility'] < threshold)
    pct_pruned = 100.0 * n_pruned / n_edges if n_edges else 0

    print(f"  Throughput: Opt={opt_metric['throughput']:.4f}G  "
          f"Prop={prop_metric['throughput']:.4f}G  "
          f"Ratio={prop_metric['throughput']/opt_metric['throughput']*100:.1f}%",
          flush=True)
    print(f"  PLR:        Opt={opt_metric['packet_loss_rate']:.2f}%  "
          f"Prop={prop_metric['packet_loss_rate']:.2f}%",
          flush=True)
    print(f"  Runtime/pair: Opt={runtime_opt_ms:.1f}ms  Prop={runtime_prop_ms:.2f}ms",
          flush=True)
    print(f"  Edges pruned: {n_pruned}/{n_edges} ({pct_pruned:.1f}%)", flush=True)

    return {
        'N': cfg.N_SATELLITES,
        'edges': n_edges,
        'opt_thr': opt_metric['throughput'],
        'prop_thr': prop_metric['throughput'],
        'opt_plr': opt_metric['packet_loss_rate'],
        'prop_plr': prop_metric['packet_loss_rate'],
        'runtime_opt_ms': runtime_opt_ms,
        'runtime_prop_ms': runtime_prop_ms,
        'pct_pruned': pct_pruned,
    }


def main():
    # Force S2 config (paper's main scenario)
    cfg.TIER_ALTITUDES_KM = [400, 500, 600]

    print("=" * 60)
    print("  Optimality + Runtime + Edges-Pruned (Scenario 2)")
    print("=" * 60, flush=True)

    results = []
    for N in [30, 50, 70]:
        results.append(run_for_N(N))

    # Save summary
    out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'results')
    import csv
    with open(os.path.join(out_dir, 'optimality_runtime.csv'), 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['N', 'Edges', 'Prop Thr', 'Opt Thr', 'Prop PLR', 'Opt PLR',
                    'Runtime Prop (ms)', 'Runtime Opt (ms)', 'Edges Pruned (%)'])
        for r in results:
            w.writerow([r['N'], r['edges'],
                       f"{r['prop_thr']:.4f}", f"{r['opt_thr']:.4f}",
                       f"{r['prop_plr']:.2f}", f"{r['opt_plr']:.2f}",
                       f"{r['runtime_prop_ms']:.2f}", f"{r['runtime_opt_ms']:.1f}",
                       f"{r['pct_pruned']:.1f}"])

    print("\nSaved optimality_runtime.csv")

    print("\n" + "=" * 80)
    print("  SUMMARY TABLE")
    print("=" * 80)
    print(f"  {'N':>3s}  {'Edges':>6s}  {'Prop/Opt Thr':>18s}  "
          f"{'Prop/Opt PLR':>18s}  {'Runtime ms':>16s}  {'Pruned':>7s}")
    for r in results:
        print(f"  {r['N']:>3d}  {r['edges']:>6d}  "
              f"{r['prop_thr']:>7.3f}/{r['opt_thr']:.3f}      "
              f"{r['prop_plr']:>5.1f}/{r['opt_plr']:.1f}             "
              f"{r['runtime_prop_ms']:>5.2f}/{r['runtime_opt_ms']:.1f}      "
              f"{r['pct_pruned']:>5.1f}%")


if __name__ == '__main__':
    main()
