"""Run Scenario 1 (540/550/560 km) using same evaluate model as Scenario 2."""

import numpy as np
import networkx as nx
import time
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config as cfg
from simulation.evaluate import evaluate_algorithm, save_results_csv
from plots.plot_figures import generate_main_figures, plot_isl_comparison
from run_from_existing import (load_network_state, load_paths, build_graph,
                                route_proposed, route_grlr, route_dr, route_str,
                                route_wo_pruning)

ORIG_DIR = r"c:\Users\yoon\Documents\Python Scripts\Starlink_LEO_Routing"
OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'results_s1')

GRAPH_INFO_FILE = os.path.join(ORIG_DIR, "Starlink_Graph_Info_500.txt")


def main():
    start = time.time()
    os.makedirs(OUT_DIR, exist_ok=True)

    print("=" * 60)
    print("  LEO Routing WCL - Scenario 1 (540/550/560 km)")
    print("=" * 60, flush=True)

    print("\n[1/4] Loading...", flush=True)
    ns = load_network_state(GRAPH_INFO_FILE)
    cycles = sorted(set(c for c, u, v in ns.keys()))

    orig_proposed = load_paths(os.path.join(ORIG_DIR, "Starlink_Proposed_500_Path.txt"))
    src_dst = {}
    for c, p in orig_proposed.items():
        if p is not None:
            src_dst[c] = (p[0], p[-1])

    print("\n[2/4] Generating paths...", flush=True)
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

    for alg in cfg.ALGORITHMS + ["w/o Pruning"]:
        n = sum(1 for p in all_paths[alg].values() if p is not None)
        hops = [len(p)-1 for p in all_paths[alg].values() if p and len(p)>1]
        print(f"  {alg}: {n} paths, avg {np.mean(hops):.1f} hops", flush=True)

    print("\n[3/4] Evaluating...", flush=True)
    results = {}
    for alg in cfg.ALGORITHMS + ["w/o Pruning"]:
        results[alg] = {}
        for rate in cfg.DATA_RATES_GBPS:
            for dur in cfg.DURATIONS_S:
                results[alg][(rate, dur)] = evaluate_algorithm(
                    all_paths[alg], ns, rate, dur)

    print("\n  === 2.8 Gbps, 100s ===", flush=True)
    for a in cfg.ALGORITHMS + ["w/o Pruning"]:
        m = results[a][(2.8, 100)]
        print(f"  {a:>12s}: Thr={m['throughput']:.3f}G PLR={m['packet_loss_rate']:.1f}%", flush=True)

    save_results_csv(results, os.path.join(OUT_DIR, 'performance_results_s1.csv'))

    print("\n[4/4] Figures...", flush=True)
    fig_results = {a: results[a] for a in cfg.ALGORITHMS}
    generate_main_figures(fig_results, OUT_DIR)

    print(f"\n{'='*60}")
    print(f"  DONE - {time.time()-start:.0f}s")
    print(f"{'='*60}")


if __name__ == '__main__':
    main()
