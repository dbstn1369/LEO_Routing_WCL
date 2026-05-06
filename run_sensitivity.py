"""
Sensitivity analysis (S2, 2.8 Gbps, 100s) for tau, beta, T.
Reuses paths_graphs_s2.pkl for fast iteration.
"""
import os
import sys
import pickle
import csv

import numpy as np
import networkx as nx

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config as cfg
from network.graph_builder import compute_isl_utility
from simulation.evaluate import evaluate_algorithm

OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'results')

# Force S2 config (sensitivity is S2-only per paper)
cfg.TIER_ALTITUDES_KM = [400, 500, 600]


def route_proposed(G, src, dst, tau):
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
    ALPHA_DUR = 2.0
    LAMBDA_CAP = 0.3
    for u, v in Gp.edges():
        l = Gp[u][v]['duration']
        w_dur = np.log1p(ALPHA_DUR / max(l, 1e-3))
        u_full = Gp[u][v]['utility']
        Gp[u][v]['weight'] = w_dur + LAMBDA_CAP * (1.0 - u_full)
    try:
        return nx.shortest_path(Gp, src, dst, weight='weight')
    except (nx.NetworkXNoPath, nx.NodeNotFound):
        return None


def main():
    print("Loading paths_graphs_s2.pkl ...", flush=True)
    with open(os.path.join(OUT_DIR, 'paths_graphs_s2.pkl'), 'rb') as f:
        s2 = pickle.load(f)
    graphs = s2['graphs']
    src_dst = s2['src_dst']
    ns = s2['ns']

    # ============================================================
    # tau sensitivity
    # ============================================================
    print("\n=== tau sensitivity (β=0.5, T=5min) ===", flush=True)
    tau_values = ['w/o', 0.1, 0.3, 0.5, 0.7, 0.9]
    tau_results = {}
    for tau in tau_values:
        paths = {}
        for cycle, G in graphs.items():
            if cycle not in src_dst:
                paths[cycle] = None
                continue
            s, d = src_dst[cycle]
            if tau == 'w/o':
                # No pruning: use full graph
                paths[cycle] = route_proposed(G.copy(), s, d, tau=0.0)
            else:
                paths[cycle] = route_proposed(G.copy(), s, d, tau=tau)
        m = evaluate_algorithm(paths, ns, 2.8, 100)
        tau_results[tau] = m
        print(f"  tau={tau}: Thr={m['throughput']:.4f}G PLR={m['packet_loss_rate']:.2f}%",
              flush=True)

    # ============================================================
    # beta sensitivity
    # ============================================================
    print("\n=== beta sensitivity (τ=0.5, T=5min) ===", flush=True)
    beta_values = [0.1, 0.3, 0.5, 0.7, 0.9]
    beta_results = {}
    for beta in beta_values:
        # Recompute utilities with new beta
        graphs_b = {}
        for cycle, G in graphs.items():
            Gn = G.copy()
            caps = [Gn[u][v]['capacity'] for u, v in Gn.edges()]
            for u, v in Gn.edges():
                Gn[u][v]['utility'] = compute_isl_utility(
                    Gn[u][v]['sinr_db'], Gn[u][v]['duration'], caps, beta=beta)
            graphs_b[cycle] = Gn

        paths = {}
        for cycle, G in graphs_b.items():
            if cycle not in src_dst:
                paths[cycle] = None
                continue
            s, d = src_dst[cycle]
            paths[cycle] = route_proposed(G.copy(), s, d, tau=cfg.TAU)
        m = evaluate_algorithm(paths, ns, 2.8, 100)
        beta_results[beta] = m
        print(f"  beta={beta}: Thr={m['throughput']:.4f}G PLR={m['packet_loss_rate']:.2f}%",
              flush=True)

    # ============================================================
    # T (snapshot interval) sensitivity — modeled via staleness
    # ============================================================
    print("\n=== T sensitivity (tau=beta=0.5) - staleness model ===", flush=True)
    T_values = [1, 5, 10, 30]  # minutes
    T_results = {}
    # Use Proposed paths from baseline (T=5min) and apply staleness
    # For longer T, more cycles share the same routing decision → links degrade
    paths_baseline = {}
    for cycle, G in graphs.items():
        if cycle not in src_dst:
            paths_baseline[cycle] = None
            continue
        s, d = src_dst[cycle]
        paths_baseline[cycle] = route_proposed(G.copy(), s, d, tau=cfg.TAU)

    # T scaling factor: higher T → fewer reroutes → more stale paths
    # Stale paths suffer reduced effective duration: l_eff = l × (5/T)
    # For T=5: full quality (baseline). For T=30: l_eff = l/6 → much higher PLR.
    for T_min in T_values:
        # T<5: no improvement (TLE data granularity caps freshness)
        # T>5: staleness scales l_eff ~ 5/T
        scale = min(1.0, 5.0 / T_min)
        ns_T = {k: (v[0], v[1], v[2] * scale) for k, v in ns.items()}
        m = evaluate_algorithm(paths_baseline, ns_T, 2.8, 100)
        T_results[T_min] = m
        print(f"  T={T_min}min: Thr={m['throughput']:.4f}G PLR={m['packet_loss_rate']:.2f}%",
              flush=True)

    # Save CSVs
    with open(os.path.join(OUT_DIR, 'tau_sensitivity.csv'), 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['tau', 'Throughput (Gbps)', 'PLR (%)'])
        for tau in tau_values:
            m = tau_results[tau]
            w.writerow([tau, f"{m['throughput']:.4f}", f"{m['packet_loss_rate']:.2f}"])

    with open(os.path.join(OUT_DIR, 'beta_sensitivity.csv'), 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['beta', 'Throughput (Gbps)', 'PLR (%)'])
        for beta in beta_values:
            m = beta_results[beta]
            w.writerow([beta, f"{m['throughput']:.4f}", f"{m['packet_loss_rate']:.2f}"])

    with open(os.path.join(OUT_DIR, 'T_sensitivity.csv'), 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['T (min)', 'Throughput (Gbps)', 'PLR (%)'])
        for T in T_values:
            m = T_results[T]
            w.writerow([T, f"{m['throughput']:.4f}", f"{m['packet_loss_rate']:.2f}"])

    print("\nSaved tau/beta/T sensitivity CSVs.", flush=True)


if __name__ == '__main__':
    main()
