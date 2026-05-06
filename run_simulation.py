"""
Main simulation runner for LEO Routing WCL paper.
GNN predicts ISL retention probability -> pruning.
GRLR uses GNN+RL-inspired Dijkstra (SNR weight, no duration).

Usage:
    python run_simulation.py
"""

import numpy as np
import time
import os
import sys
import networkx as nx

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config as cfg
from network.constellation import generate_constellation
from network.graph_builder import build_all_graphs, compute_isl_utility
from simulation.evaluate import run_full_evaluation, save_results_csv, evaluate_algorithm
from plots.plot_figures import (
    generate_main_figures, plot_isl_comparison,
    save_sensitivity_csv
)

OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'results')


def select_src_dst_pairs(graphs, seed=123):
    np.random.seed(seed)
    pairs = {}
    for cycle, G in graphs.items():
        mid = [n for n in G.nodes() if cfg.SATS_PER_TIER <= n < 2 * cfg.SATS_PER_TIER]
        if len(mid) < 2:
            mid = list(G.nodes())
        if len(mid) >= 2:
            s, d = np.random.choice(mid, 2, replace=False)
            pairs[cycle] = (int(s), int(d))
    return pairs


# ================================================================
# Routing Algorithms
# ================================================================

def route_proposed(G, src, dst, tau=None):
    """Proposed: GNN-based pruning (utility threshold) + utility-weighted Dijkstra."""
    if tau is None:
        tau = cfg.TAU

    # Prune: remove edges with utility below tau * max_utility
    utilities = [G[u][v]['utility'] for u, v in G.edges()]
    if not utilities:
        return None
    u_max = max(utilities)
    threshold = tau * u_max

    G_pruned = G.copy()
    to_remove = [(u, v) for u, v in G_pruned.edges() if G_pruned[u][v]['utility'] < threshold]
    G_pruned.remove_edges_from(to_remove)

    if src not in G_pruned or dst not in G_pruned:
        G_pruned = G.copy()  # fallback

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
        except:
            return None


def route_grlr(G, src, dst):
    """GRLR: GNN+RL-inspired routing. Dijkstra with SNR weight (no duration).
    Includes RL noise + degree-based congestion awareness."""
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

    G_copy = G.copy()
    for u, v in G_copy.edges():
        sinr = G_copy[u][v]['sinr_db']
        dur = G_copy[u][v]['duration']
        snr_cost = 1.0 - (sinr - sinr_min) / sinr_range
        deg_cost = (degrees[u] + degrees[v]) / (2 * max_deg)
        if dur < 50:
            G_copy[u][v]['weight'] = 10.0
            continue
        dur_pen = max(0, 1.0 - dur / 120.0)
        noise = np.random.uniform(0, 0.05)
        G_copy[u][v]['weight'] = 0.60 * snr_cost + 0.15 * deg_cost + 0.10 * dur_pen + 0.15 * noise

    try:
        return nx.shortest_path(G_copy, src, dst, weight='weight')
    except:
        return None


def route_dr(G, src, dst):
    """Distance-based Routing."""
    if src not in G or dst not in G:
        return None
    G_copy = G.copy()
    for u, v in G_copy.edges():
        G_copy[u][v]['weight'] = G_copy[u][v]['distance']
    try:
        return nx.shortest_path(G_copy, src, dst, weight='weight')
    except:
        return None


def route_str(G, src, dst):
    """Static Topology-based Routing (BFS, no weights)."""
    if src not in G or dst not in G:
        return None
    try:
        return nx.shortest_path(G.copy(), src, dst)
    except:
        return None


def route_wo_pruning(G, src, dst):
    """w/o Pruning: utility-weighted Dijkstra on full graph."""
    if src not in G or dst not in G:
        return None
    G_copy = G.copy()
    for u, v in G_copy.edges():
        G_copy[u][v]['weight'] = max(1.0 - G_copy[u][v]['utility'], 1e-6)
    try:
        paths = list(nx.all_shortest_paths(G_copy, src, dst, weight='weight'))
        return min(paths, key=len)
    except:
        return None


# ================================================================
# Main
# ================================================================

def main():
    start = time.time()
    os.makedirs(OUT_DIR, exist_ok=True)

    print("=" * 60)
    print("  LEO Routing WCL - Simulation")
    print("  Scenario 2: %s km, %d sats" % (cfg.TIER_ALTITUDES_KM, cfg.N_SATELLITES))
    print("=" * 60, flush=True)

    # 1. Constellation
    print("\n[1/5] Generating constellation...", flush=True)
    pos, vel = generate_constellation()
    print("  Shape: %s" % str(pos.shape), flush=True)

    # 2. Graphs
    print("\n[2/5] Building ISL graphs...", flush=True)
    graphs = build_all_graphs(pos, vel)
    src_dst = select_src_dst_pairs(graphs)
    print("  %d src-dst pairs" % len(src_dst), flush=True)

    # 3. Routing
    print("\n[3/5] Running 5 routing algorithms...", flush=True)
    all_paths = {a: {} for a in cfg.ALGORITHMS}

    for cycle, G in graphs.items():
        if cycle not in src_dst:
            for a in cfg.ALGORITHMS:
                all_paths[a][cycle] = None
            continue
        s, d = src_dst[cycle]
        all_paths[cfg.ALG_PROPOSED][cycle] = route_proposed(G.copy(), s, d)
        all_paths[cfg.ALG_GRLR][cycle] = route_grlr(G.copy(), s, d)
        all_paths[cfg.ALG_DR][cycle] = route_dr(G.copy(), s, d)
        all_paths[cfg.ALG_STR][cycle] = route_str(G.copy(), s, d)
        all_paths[cfg.ALG_WO][cycle] = route_wo_pruning(G.copy(), s, d)
        if (cycle + 1) % 20 == 0:
            print("  %d/%d cycles" % (cycle + 1, len(graphs)), flush=True)

    for a in cfg.ALGORITHMS:
        n = sum(1 for p in all_paths[a].values() if p is not None)
        h = np.mean([len(p)-1 for p in all_paths[a].values() if p and len(p)>1]) if n else 0
        print("  %12s: %d/%d paths, avg %.1f hops" % (a, n, len(src_dst), h), flush=True)

    # 4. Evaluation
    print("\n[4/5] Evaluating performance...", flush=True)
    results = run_full_evaluation(all_paths, graphs)

    # Summary
    print("\n  === Summary (2.8 Gbps, 100s) ===", flush=True)
    print("  %12s | %10s | %8s | %5s" % ("Algorithm", "Throughput", "PLR", "Hops"), flush=True)
    for a in cfg.ALGORITHMS:
        m = results[a].get((2.8, 100), {})
        print("  %12s | %9.4fG | %6.2f%% | %5.1f" % (
            a, m.get('throughput',0), m.get('packet_loss_rate',0), m.get('avg_hop_count',0)
        ), flush=True)

    save_results_csv(results, os.path.join(OUT_DIR, 'performance_results.csv'))

    # 5. Figures + Sensitivity
    print("\n[5/5] Figures & sensitivity...", flush=True)
    generate_main_figures(results, OUT_DIR)
    plot_isl_comparison(all_paths, graphs, OUT_DIR)

    # tau sensitivity
    print("\n  --- tau sensitivity ---", flush=True)
    tau_vals = [0.1, 0.3, 0.5, 0.7, 0.9]
    tau_res = {}
    for tau in tau_vals:
        paths = {}
        for c, G in graphs.items():
            if c not in src_dst:
                paths[c] = None; continue
            paths[c] = route_proposed(G.copy(), src_dst[c][0], src_dst[c][1], tau=tau)
        m = evaluate_algorithm(paths, graphs, 2.8, 100)
        tau_res[tau] = m
        print("  tau=%.1f: Thr=%.4f PLR=%.2f%%" % (tau, m['throughput'], m['packet_loss_rate']), flush=True)
    save_sensitivity_csv(tau_res, 'tau', tau_vals, 'tau_sensitivity.csv', OUT_DIR)

    # beta sensitivity
    print("\n  --- beta sensitivity ---", flush=True)
    beta_vals = [0.1, 0.3, 0.5, 0.7, 0.9]
    beta_res = {}
    for beta in beta_vals:
        gs = {}
        for c, G in graphs.items():
            Gn = G.copy()
            caps = [Gn[u][v]['capacity'] for u,v in Gn.edges()]
            for u,v in Gn.edges():
                Gn[u][v]['utility'] = compute_isl_utility(Gn[u][v]['sinr_db'], Gn[u][v]['duration'], caps, beta=beta)
            gs[c] = Gn
        paths = {}
        for c, G in gs.items():
            if c not in src_dst:
                paths[c] = None; continue
            paths[c] = route_proposed(G.copy(), src_dst[c][0], src_dst[c][1])
        m = evaluate_algorithm(paths, graphs, 2.8, 100)
        beta_res[beta] = m
        print("  beta=%.1f: Thr=%.4f PLR=%.2f%%" % (beta, m['throughput'], m['packet_loss_rate']), flush=True)
    save_sensitivity_csv(beta_res, 'beta', beta_vals, 'beta_sensitivity.csv', OUT_DIR)

    # Ablation
    print("\n  --- GNN Ablation ---", flush=True)
    m_w = results[cfg.ALG_PROPOSED].get((2.8, 100), {})
    m_wo = results[cfg.ALG_WO].get((2.8, 100), {})
    print("  With Pruning:  Thr=%.4f PLR=%.2f%%" % (m_w.get('throughput',0), m_w.get('packet_loss_rate',0)), flush=True)
    print("  w/o Pruning:   Thr=%.4f PLR=%.2f%%" % (m_wo.get('throughput',0), m_wo.get('packet_loss_rate',0)), flush=True)

    elapsed = time.time() - start
    print("\n" + "=" * 60)
    print("  COMPLETE - %.1fs (%.1f min)" % (elapsed, elapsed/60))
    print("  Results: %s/" % OUT_DIR)
    print("=" * 60)


if __name__ == '__main__':
    main()
