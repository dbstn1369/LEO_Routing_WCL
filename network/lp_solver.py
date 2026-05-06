"""
Label generation for GNN training.
Uses utility-weighted shortest paths (equivalent to LP solution due to
total unimodularity of flow conservation constraints).
Generates ISL utilization rate I_ij (Eq. 20) and binary labels y_ij (Eq. 21).
"""

import numpy as np
import networkx as nx
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import config as cfg


def solve_optimal_path(G, src, dst):
    """
    Find the utility-maximizing path (= LP optimal solution).
    Weight = 1 - utility -> Dijkstra minimizes this = maximizes utility.

    Returns:
        used_edges: set of (u,v) tuples on optimal path, or empty set
    """
    if src not in G or dst not in G:
        return set()

    if not nx.has_path(G, src, dst):
        return set()

    # Set utility-based weights
    G_copy = G.copy()
    for u, v in G_copy.edges():
        G_copy[u][v]['lp_weight'] = 1.0 - G_copy[u][v].get('utility', 0.5)

    try:
        path = nx.shortest_path(G_copy, src, dst, weight='lp_weight')
        used = set()
        for u, v in zip(path[:-1], path[1:]):
            used.add((u, v))
            used.add((v, u))  # undirected
        return used
    except (nx.NetworkXNoPath, nx.NodeNotFound):
        return set()


def compute_utilization_labels(G, src_dst_pairs, tau_train=None):
    """
    Compute ISL utilization rate I_ij (Eq. 20) and binary labels y_ij (Eq. 21).
    Uses optimal paths equivalent to LP solution.
    """
    if tau_train is None:
        tau_train = cfg.TAU_TRAIN

    edges = list(G.edges())
    edge_count = {(u, v): 0 for u, v in edges}
    n_solved = 0

    for src, dst in src_dst_pairs:
        used = solve_optimal_path(G, src, dst)
        if used:
            for u, v in edges:
                if (u, v) in used:
                    edge_count[(u, v)] += 1
            n_solved += 1

    utilization = {}
    labels = {}
    for u, v in edges:
        I_ij = edge_count[(u, v)] / max(n_solved, 1)
        utilization[(u, v)] = I_ij
        utilization[(v, u)] = I_ij
        labels[(u, v)] = 1 if I_ij >= tau_train else 0
        labels[(v, u)] = labels[(u, v)]

    return labels, utilization


def generate_training_data(graphs, n_pairs_per_cycle=20, n_cycles=None, seed=42):
    """Generate GNN training data from optimal path labels across multiple cycles."""
    np.random.seed(seed)

    if n_cycles is None:
        n_cycles = min(len(graphs), 20)

    cycle_keys = sorted(graphs.keys())[:n_cycles]
    all_data = []
    total_pos = 0
    total_neg = 0

    for idx, cycle in enumerate(cycle_keys):
        G = graphs[cycle]
        nodes = list(G.nodes())
        mid_nodes = [n for n in nodes if cfg.SATS_PER_TIER <= n < 2 * cfg.SATS_PER_TIER]
        if len(mid_nodes) < 2:
            mid_nodes = nodes

        # Generate diverse src-dst pairs
        pairs = []
        for _ in range(n_pairs_per_cycle):
            if len(mid_nodes) >= 2:
                s, d = np.random.choice(mid_nodes, 2, replace=False)
                pairs.append((int(s), int(d)))

        labels, utilization = compute_utilization_labels(G, pairs)

        n_pos = sum(1 for v in labels.values() if v == 1) // 2
        n_neg = sum(1 for v in labels.values() if v == 0) // 2
        total_pos += n_pos
        total_neg += n_neg

        all_data.append((cycle, G, labels, utilization))
        print(f"  Label gen cycle {idx+1}/{n_cycles}: {n_pos} pos / {n_neg} neg edges")

    stats = {
        'n_cycles': n_cycles,
        'total_positive': total_pos,
        'total_negative': total_neg,
        'positive_ratio': total_pos / max(total_pos + total_neg, 1),
    }

    return all_data, stats
