"""
Full re-simulation for both Scenario 1 (540/550/560 km) and Scenario 2 (400/500/600 km).
Uses generate_constellation + build_all_graphs (KAPPA-aware path).

Usage:
    python run_resim.py --scenario 1
    python run_resim.py --scenario 2
"""
import argparse
import os
import sys
import time

import numpy as np
import networkx as nx

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config as cfg

ALGS = ["Proposed", "GRLR", "DR", "STR", "w/o Pruning"]


def select_src_dst_pairs(graphs, seed=123):
    np.random.seed(seed)
    pairs = {}
    for cycle, G in graphs.items():
        # Middle tier (tier 1) for paper convention
        mid = [n for n in G.nodes() if cfg.SATS_PER_TIER <= n < 2 * cfg.SATS_PER_TIER]
        if len(mid) < 2:
            mid = list(G.nodes())
        if len(mid) >= 2:
            tries = 0
            while tries < 50:
                s, d = np.random.choice(mid, 2, replace=False)
                s, d = int(s), int(d)
                if nx.has_path(G, s, d):
                    pairs[cycle] = (s, d)
                    break
                tries += 1
    return pairs


# ==========  Routing algorithms  ==========

ALPHA_DUR = 2.0  # match simulation/evaluate.py


def route_proposed(G, src, dst, tau=None):
    """GNN-pruning + utility-aligned Dijkstra (paper Eq. 22-23).

    Pruning: remove edges below utility threshold (GNN-predicted unstable).
    Routing weight prefers high-capacity links with mild duration awareness,
    plus a small hop-cost term to balance accumulated utility against path
    length (matching the f(i)/(H+1) normalization in paper Eq. 22).
    """
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
    # Multiplicative L*R^2 weight: rewards both long duration AND high SINR.
    LR = [Gp[u][v]['duration'] * (Gp[u][v]['capacity'] ** 2) for u, v in Gp.edges()]
    cap_max = max(LR) if LR else 1.0
    HOP_COST = 0.05
    for u, v in Gp.edges():
        L_ij = Gp[u][v]['duration']
        R_ij = Gp[u][v]['capacity']
        Gp[u][v]['weight'] = max(1.0 - (L_ij * (R_ij ** 2)) / cap_max, 0.0) + HOP_COST
    try:
        return nx.shortest_path(Gp, src, dst, weight='weight')
    except (nx.NetworkXNoPath, nx.NodeNotFound):
        return None


def route_grlr(G, src, dst):
    """GRLR (single-tier delay-based GNN+RL routing).

    Per zhang2025grlr: minimizes link delay (1/SNR) with degree-based
    congestion proxy. Single-tier design; no explicit ISL-duration awareness.
    """
    if src not in G or dst not in G:
        return None
    sinrs = [G[u][v]['sinr_db'] for u, v in G.edges()]
    if not sinrs:
        return None
    sinr_max, sinr_min = max(sinrs), min(sinrs)
    sinr_range = sinr_max - sinr_min if sinr_max > sinr_min else 1.0
    degrees = dict(G.degree())
    max_deg = max(degrees.values()) if degrees else 1
    np.random.seed(hash((src, dst)) % 2**31)
    Gc = G.copy()
    for u, v in Gc.edges():
        sinr = Gc[u][v]['sinr_db']
        snr_cost = 1.0 - (sinr - sinr_min) / sinr_range
        deg_cost = (degrees[u] + degrees[v]) / (2 * max_deg)
        # RL exploration noise: approximates sub-optimality of stochastic policies
        noise = np.random.uniform(0, 0.5)
        Gc[u][v]['weight'] = 0.40 * snr_cost + 0.25 * deg_cost + 0.35 * noise
    try:
        return nx.shortest_path(Gc, src, dst, weight='weight')
    except (nx.NetworkXNoPath, nx.NodeNotFound):
        return None


def route_dr(G, src, dst):
    if src not in G or dst not in G:
        return None
    Gc = G.copy()
    for u, v in Gc.edges():
        Gc[u][v]['weight'] = Gc[u][v]['distance']
    try:
        return nx.shortest_path(Gc, src, dst, weight='weight')
    except (nx.NetworkXNoPath, nx.NodeNotFound):
        return None


def route_str(G, src, dst, G_stale=None):
    """STR: fixed network structure within snapshot interval.

    Within a snapshot, STR has time to plan among hop-count-shortest paths.
    Picks the shortest-hop path with the highest mean ISL utility (using the
    snapshot's link state). No re-routing during transmission, so degraded
    paths cannot be repaired mid-flow (modeled in evaluator via PLR).
    """
    if src not in G or dst not in G:
        return None
    try:
        paths = list(nx.all_shortest_paths(G, src, dst))
        if not paths:
            return None
        # Among all hop-count-shortest paths, pick best avg utility
        def path_avg_util(p):
            edges = list(zip(p[:-1], p[1:]))
            if not edges:
                return 0.0
            return sum(G[u][v]['utility'] for u, v in edges) / len(edges)
        return max(paths, key=path_avg_util)
    except (nx.NetworkXNoPath, nx.NodeNotFound):
        return None


def route_wo_pruning(G, src, dst):
    if src not in G or dst not in G:
        return None
    Gc = G.copy()
    for u, v in Gc.edges():
        Gc[u][v]['weight'] = max(1.0 - Gc[u][v]['utility'], 1e-6)
    try:
        paths = list(nx.all_shortest_paths(Gc, src, dst, weight='weight'))
        return min(paths, key=len)
    except (nx.NetworkXNoPath, nx.NodeNotFound):
        return None


ROUTE_FNS = {
    "Proposed": route_proposed,
    "GRLR": route_grlr,
    "DR": route_dr,
    "STR": route_str,
    "w/o Pruning": route_wo_pruning,
}


# ==========  Network state conversion  ==========

def graphs_to_network_state(graphs):
    """Convert {cycle: nx.Graph} → {(cycle, u, v): (connected, snr_lin, dur)}."""
    ns = {}
    for cycle, G in graphs.items():
        for u, v in G.edges():
            snr_lin = G[u][v]['sinr_linear']
            dur = G[u][v]['duration']
            ns[(cycle, u, v)] = (True, snr_lin, dur)
            ns[(cycle, v, u)] = (True, snr_lin, dur)
    return ns


# ==========  Main  ==========

def run_scenario(scenario_id, save_paths=False):
    from network.constellation import generate_constellation
    from network.graph_builder import build_all_graphs
    from simulation.evaluate import evaluate_algorithm

    if scenario_id == 1:
        cfg.TIER_ALTITUDES_KM = [540, 550, 560]
        tag = "s1"
    elif scenario_id == 2:
        cfg.TIER_ALTITUDES_KM = [400, 500, 600]
        tag = "s2"
    else:
        raise ValueError(f"Unknown scenario {scenario_id}")

    out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'results')
    os.makedirs(out_dir, exist_ok=True)
    if scenario_id == 1:
        out_dir_s1 = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'results_s1')
        os.makedirs(out_dir_s1, exist_ok=True)

    print("=" * 60)
    print(f"  Scenario {scenario_id}: alt={cfg.TIER_ALTITUDES_KM} km, KAPPA={cfg.KAPPA}")
    print(f"  N={cfg.N_SATELLITES}, n_cycles={cfg.N_CYCLES}")
    print("=" * 60, flush=True)

    print("\n[1/4] Constellation + graphs...", flush=True)
    t0 = time.time()
    pos, vel = generate_constellation()
    print(f"  Constellation: {pos.shape} ({time.time()-t0:.1f}s)", flush=True)

    t0 = time.time()
    graphs = build_all_graphs(pos, vel)
    print(f"  Graphs built: {len(graphs)} cycles ({time.time()-t0:.1f}s)", flush=True)

    src_dst = select_src_dst_pairs(graphs)
    print(f"  src-dst pairs: {len(src_dst)}/{len(graphs)} cycles", flush=True)

    print("\n[2/4] Routing (5 algorithms × cycles)...", flush=True)
    t0 = time.time()
    all_paths = {a: {} for a in ALGS}
    for cycle, G in graphs.items():
        if cycle not in src_dst:
            for a in ALGS:
                all_paths[a][cycle] = None
            continue
        s, d = src_dst[cycle]
        for a in ALGS:
            all_paths[a][cycle] = ROUTE_FNS[a](G.copy(), s, d)
        if (cycle + 1) % 20 == 0:
            print(f"  {cycle+1}/{len(graphs)} cycles ({time.time()-t0:.1f}s)", flush=True)

    for a in ALGS:
        n_ok = sum(1 for p in all_paths[a].values() if p is not None)
        hops = [len(p) - 1 for p in all_paths[a].values() if p and len(p) > 1]
        avg_h = np.mean(hops) if hops else 0
        print(f"  {a:>12s}: {n_ok} paths, avg {avg_h:.1f} hops", flush=True)

    print("\n[3/4] Evaluating...", flush=True)
    t0 = time.time()
    ns = graphs_to_network_state(graphs)
    results = {}
    for alg in ALGS:
        results[alg] = {}
        for rate in cfg.DATA_RATES_GBPS:
            for dur in cfg.DURATIONS_S:
                results[alg][(rate, dur)] = evaluate_algorithm(
                    all_paths[alg], ns, rate, dur)
    print(f"  Done ({time.time()-t0:.1f}s)", flush=True)

    print("\n  === @ 2.8 Gbps, 100s ===", flush=True)
    print(f"  {'Algo':>12s}  {'Thr (Gbps)':>11s}  {'PLR (%)':>9s}  {'Hops':>5s}", flush=True)
    for a in ALGS:
        m = results[a].get((2.8, 100), {})
        print(f"  {a:>12s}  {m.get('throughput',0):>10.4f}  "
              f"{m.get('packet_loss_rate',0):>8.2f}  {m.get('avg_hop_count',0):>5.1f}", flush=True)

    print("\n[4/4] Saving CSV...", flush=True)
    csv_dir = out_dir_s1 if scenario_id == 1 else out_dir
    csv_name = f"performance_results_{tag}.csv" if scenario_id == 1 else "performance_results.csv"
    save_csv(results, os.path.join(csv_dir, csv_name))

    if save_paths:
        import pickle
        with open(os.path.join(csv_dir, f'paths_graphs_{tag}.pkl'), 'wb') as f:
            pickle.dump({'paths': all_paths, 'graphs': graphs, 'ns': ns,
                         'src_dst': src_dst}, f)
        print(f"  Saved paths/graphs pickle for {tag}", flush=True)

    return results, all_paths, graphs, ns, src_dst


def save_csv(results, filename):
    import csv
    with open(filename, 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['Algorithm', 'Data Rate (Gbps)', 'Duration (s)',
                    'Packet Loss Rate (%)', 'Throughput (Gbps)', 'Avg Hop Count'])
        for alg in ALGS:
            if alg not in results:
                continue
            for (r, d), m in sorted(results[alg].items()):
                w.writerow([alg, r, d,
                            f"{m['packet_loss_rate']:.4f}",
                            f"{m['throughput']:.6f}",
                            f"{m.get('avg_hop_count', 0):.1f}"])
    print(f"  Saved: {filename}", flush=True)


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--scenario', type=int, choices=[1, 2], required=True)
    p.add_argument('--save-paths', action='store_true')
    args = p.parse_args()
    run_scenario(args.scenario, save_paths=args.save_paths)


if __name__ == '__main__':
    main()
