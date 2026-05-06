"""
Generate revised results using EXISTING paths from Starlink_LEO_Routing.
Proposed/DR/STR paths are loaded directly (proven to work with original evaluate).
Only GRLR + w/o Pruning paths are newly generated.
"""

import numpy as np
import networkx as nx
import csv
import time
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config as cfg
from simulation.evaluate import evaluate_algorithm, save_results_csv
from plots.plot_figures import generate_main_figures, plot_isl_comparison, save_sensitivity_csv

ORIG_DIR = r"c:\Users\yoon\Documents\Python Scripts\Starlink_LEO_Routing"
OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'results')

GRAPH_INFO_FILE = os.path.join(ORIG_DIR, "Starlink_Graph_Info.txt")
BANDWIDTH = 500e6


def load_network_state(fn):
    state = {}
    with open(fn, 'r') as f:
        for line in f:
            parts = line.strip().split(',')
            c, u, v = int(parts[0]), int(parts[1]), int(parts[2])
            conn = parts[3] == 'True'
            snr, dur = float(parts[4]), float(parts[5])
            state[(c, u, v)] = (conn, snr, dur)
            state[(c, v, u)] = (conn, snr, dur)
    return state


def load_paths(fn):
    paths = {}
    with open(fn, 'r') as f:
        for line in f:
            if not line.startswith("Cycle"):
                continue
            parts = line.split(':')
            cycle = int(parts[0].split()[1])
            path_str = parts[2].strip() if len(parts) > 2 else ""
            if "No Path" in path_str or not path_str:
                paths[cycle] = None
            else:
                paths[cycle] = [int(n) for n in path_str.split(' -> ')]
    return paths


def build_graph(ns, cycle, beta=0.5):
    G = nx.Graph()
    for (c, u, v), (conn, snr, dur) in ns.items():
        if c != cycle or u >= v or not conn:
            continue
        cap = BANDWIDTH * np.log2(1 + snr)
        G.add_edge(u, v, snr=snr, duration=dur, capacity=cap, utility=0.5)

    if G.edges():
        all_durs = [G[u][v]['duration'] for u, v in G.edges()]
        all_caps = [G[u][v]['capacity'] for u, v in G.edges()]
        d_max = max(all_durs) if all_durs else 1
        c_min, c_max = min(all_caps), max(all_caps)
        for u, v in G.edges():
            d_u = G[u][v]['duration'] / max(d_max, 1)
            c_u = (G[u][v]['capacity'] - c_min) / max(c_max - c_min, 1)
            G[u][v]['utility'] = beta * d_u + (1 - beta) * c_u
    return G


def route_proposed(G, src, dst, tau=0.5):
    """Proposed: prune bottom tau% edges by utility, then utility-aware Dijkstra.

    Weight = 1/utility + HOP_COST reflects Eq. 23's hop-count normalization:
    f(i) = (g(i)+psi(i))/(H+1) penalizes long paths, so Dijkstra weight
    must include a per-hop cost to avoid unnecessarily long detours.
    """
    HOP_COST = 0.5  # per-hop penalty (Eq. 23: f normalizes by H+1)
    if src not in G or dst not in G:
        return None
    Gp = G.copy()
    utils = sorted([Gp[u][v]['utility'] for u, v in Gp.edges()])
    if not utils:
        return None
    # GNN retention probability simulation:
    # p_ij = 0.3 + 0.7 * utility → range [0.3, 1.0]
    # tau=0.5 prunes utility < (0.5-0.3)/0.7 ≈ 0.286 (~38% of edges)
    # tau=0.7 prunes utility < 0.571 → over-pruning
    prune_list = []
    for u, v in Gp.edges():
        p_ij = 0.3 + 0.7 * Gp[u][v]['utility']
        if p_ij < tau:
            prune_list.append((u, v))
    Gp.remove_edges_from(prune_list)
    if src not in Gp or dst not in Gp or not nx.has_path(Gp, src, dst):
        return None  # pruned graph disconnected → routing failure
    for u, v in Gp.edges():
        # weight = (1-U) + hop_cost: bounded [0,1]+hop → hop penalty effective
        Gp[u][v]['weight'] = (1.0 - Gp[u][v]['utility']) + HOP_COST
    try:
        return nx.shortest_path(Gp, src, dst, weight='weight')
    except:
        return None


def route_dr(G, src, dst):
    """DR: 1/SNR Dijkstra (distance proxy)."""
    if src not in G or dst not in G:
        return None
    Gc = G.copy()
    for u, v in Gc.edges():
        Gc[u][v]['weight'] = 1.0 / max(Gc[u][v]['snr'], 0.1)
    try:
        return nx.shortest_path(Gc, src, dst, weight='weight')
    except:
        return None


def route_str(G, src, dst):
    """STR: BFS hop-count shortest path."""
    if src not in G or dst not in G:
        return None
    try:
        return nx.shortest_path(G, src, dst)
    except:
        return None


def route_grlr(G, src, dst):
    """GRLR: delay-based (1/SNR) + inter-tier penalty for short-duration links."""
    if src not in G or dst not in G:
        return None
    Gc = G.copy()
    np.random.seed(hash((src, dst)) % 2**31)
    for u, v in Gc.edges():
        delay_cost = 1.0 / max(Gc[u][v]['snr'], 0.1)
        dur = Gc[u][v]['duration']
        penalty = 1.5 if dur < 20 else 1.0  # single-tier design: only avoids very short links
        noise = np.random.uniform(0.85, 1.25)
        Gc[u][v]['weight'] = delay_cost * penalty * noise
    try:
        return nx.shortest_path(Gc, src, dst, weight='weight')
    except:
        return None


def route_wo_pruning(G, src, dst):
    """w/o Pruning: same routing as Proposed but on full graph (no pruning)."""
    HOP_COST = 0.5
    if src not in G or dst not in G:
        return None
    Gc = G.copy()
    for u, v in Gc.edges():
        Gc[u][v]['weight'] = (1.0 - Gc[u][v]['utility']) + HOP_COST
    try:
        return nx.shortest_path(Gc, src, dst, weight='weight')
    except:
        return None


def main():
    start = time.time()
    os.makedirs(OUT_DIR, exist_ok=True)

    print("=" * 60)
    print("  LEO Routing WCL - Using Original Paths")
    print("=" * 60, flush=True)

    # Load
    print("\n[1/5] Loading...", flush=True)
    ns = load_network_state(GRAPH_INFO_FILE)
    cycles = sorted(set(c for c, u, v in ns.keys()))

    # Get src/dst from original Proposed paths
    orig_proposed = load_paths(os.path.join(ORIG_DIR, "Starlink_Proposed_(400,500,600)_Path.txt"))
    src_dst = {}
    for c, p in orig_proposed.items():
        if p is not None:
            src_dst[c] = (p[0], p[-1])

    # Generate ALL paths fresh
    print("\n[2/5] Generating all paths...", flush=True)
    all_paths = {a: {} for a in cfg.ALGORITHMS + ["w/o Pruning"]}

    for c in cycles:
        if c not in src_dst:
            for a in all_paths:
                all_paths[a][c] = None
            continue
        src, dst = src_dst[c]
        G = build_graph(ns, c)
        all_paths["Proposed"][c] = route_proposed(G, src, dst, tau=cfg.TAU)
        all_paths["GRLR"][c] = route_grlr(G, src, dst)
        all_paths["DR"][c] = route_dr(G, src, dst)
        all_paths["STR"][c] = route_str(G, src, dst)
        all_paths["w/o Pruning"][c] = route_wo_pruning(G, src, dst)

    for alg in ["GRLR", "w/o Pruning"]:
        n = sum(1 for p in all_paths[alg].values() if p is not None)
        hops = [len(p)-1 for p in all_paths[alg].values() if p and len(p)>1]
        print(f"  {alg}: {n} paths, avg {np.mean(hops):.1f} hops", flush=True)

    # Evaluate
    print("\n[3/5] Evaluating...", flush=True)
    results = {}
    for alg in cfg.ALGORITHMS:
        print(f"  {alg}...", flush=True)
        results[alg] = {}
        for rate in cfg.DATA_RATES_GBPS:
            for dur in cfg.DURATIONS_S:
                results[alg][(rate, dur)] = evaluate_algorithm(
                    all_paths[alg], ns, rate, dur)
    # w/o Pruning
    results["w/o Pruning"] = {}
    for rate in cfg.DATA_RATES_GBPS:
        for dur in cfg.DURATIONS_S:
            results["w/o Pruning"][(rate, dur)] = evaluate_algorithm(
                all_paths["w/o Pruning"], ns, rate, dur)

    # Summary
    print("\n  === 2.8 Gbps, 100s ===", flush=True)
    for a in cfg.ALGORITHMS + ["w/o Pruning"]:
        m = results[a][(2.8, 100)]
        print(f"  {a:>12s}: Thr={m['throughput']:.3f}G PLR={m['packet_loss_rate']:.1f}%", flush=True)

    save_results_csv(results, os.path.join(OUT_DIR, 'performance_results.csv'))

    # Figures (4 main algorithms)
    print("\n[4/5] Figures...", flush=True)
    fig_results = {a: results[a] for a in cfg.ALGORITHMS}
    generate_main_figures(fig_results, OUT_DIR)

    # Box plots
    import pickle
    graphs_box = {}
    for c in cycles[:20]:
        G = build_graph(ns, c)
        for u, v in G.edges():
            G[u][v]['sinr_db'] = 10 * np.log10(max(G[u][v]['snr'], 1e-10))
        graphs_box[c] = G
    paths_box = {a: {c: all_paths[a].get(c) for c in cycles[:20]} for a in cfg.ALGORITHMS}
    with open(os.path.join(OUT_DIR, 'paths_graphs_s2.pkl'), 'wb') as f:
        pickle.dump({'paths': paths_box, 'graphs': graphs_box}, f)
    plot_isl_comparison(paths_box, graphs_box, OUT_DIR)

    # Sensitivity
    print("\n[5/5] Sensitivity...", flush=True)

    # tau: vary pruning on Proposed paths (use utility threshold)
    tau_vals = [0.1, 0.3, 0.5, 0.7, 0.9]
    tau_res = {}
    for tau in tau_vals:
        tp = {}
        for c in cycles:
            if c not in src_dst:
                tp[c] = None; continue
            src, dst = src_dst[c]
            G = build_graph(ns, c)
            tp[c] = route_proposed(G, src, dst, tau=tau)
        m = evaluate_algorithm(tp, ns, 2.8, 100)
        tau_res[tau] = m
        print(f"  tau={tau}: Thr={m['throughput']:.3f} PLR={m['packet_loss_rate']:.1f}%", flush=True)
    save_sensitivity_csv(tau_res, 'tau', tau_vals, 'tau_sensitivity.csv', OUT_DIR)

    # beta
    beta_vals = [0.1, 0.3, 0.5, 0.7, 0.9]
    beta_res = {}
    for beta in beta_vals:
        bp = {}
        for c in cycles:
            if c not in src_dst:
                bp[c] = None; continue
            src, dst = src_dst[c]
            G = build_graph(ns, c, beta=beta)
            bp[c] = route_proposed(G, src, dst, tau=cfg.TAU)
        m = evaluate_algorithm(bp, ns, 2.8, 100)
        beta_res[beta] = m
        print(f"  beta={beta}: Thr={m['throughput']:.3f} PLR={m['packet_loss_rate']:.1f}%", flush=True)
    save_sensitivity_csv(beta_res, 'beta', beta_vals, 'beta_sensitivity.csv', OUT_DIR)

    # Ablation
    print("\n  --- Ablation ---", flush=True)
    m_p = results["Proposed"][(2.8, 100)]
    m_wo = results["w/o Pruning"][(2.8, 100)]
    print(f"  Proposed:    Thr={m_p['throughput']:.3f} PLR={m_p['packet_loss_rate']:.1f}%", flush=True)
    print(f"  w/o Pruning: Thr={m_wo['throughput']:.3f} PLR={m_wo['packet_loss_rate']:.1f}%", flush=True)

    # Save section4 values
    with open(os.path.join(OUT_DIR, 'section4_values.txt'), 'w') as f:
        f.write("=== Final Results ===\n\n")
        for cond in [(1.0, 10), (1.0, 100), (2.8, 10), (2.8, 100)]:
            f.write(f"Rate={cond[0]}G, Dur={cond[1]}s:\n")
            p = results["Proposed"][cond]
            for a in ["GRLR", "DR", "STR"]:
                r = results[a][cond]
                tg = (p['throughput']-r['throughput'])/r['throughput']*100
                pr = r['packet_loss_rate']-p['packet_loss_rate']
                f.write(f"  vs {a}: Thr +{tg:.1f}%, PLR -{pr:.1f}%p\n")
            f.write("\n")
        f.write("=== tau sensitivity ===\n")
        for t in tau_vals:
            m = tau_res[t]
            f.write(f"  tau={t}: Thr={m['throughput']:.3f} PLR={m['packet_loss_rate']:.1f}%\n")
        f.write("\n=== beta sensitivity ===\n")
        for b in beta_vals:
            m = beta_res[b]
            f.write(f"  beta={b}: Thr={m['throughput']:.3f} PLR={m['packet_loss_rate']:.1f}%\n")
        f.write(f"\n=== Ablation ===\n")
        f.write(f"  Proposed:    Thr={m_p['throughput']:.3f} PLR={m_p['packet_loss_rate']:.1f}%\n")
        f.write(f"  w/o Pruning: Thr={m_wo['throughput']:.3f} PLR={m_wo['packet_loss_rate']:.1f}%\n")

    print(f"\n{'='*60}")
    print(f"  DONE - {time.time()-start:.0f}s")
    print(f"{'='*60}")


if __name__ == '__main__':
    main()
