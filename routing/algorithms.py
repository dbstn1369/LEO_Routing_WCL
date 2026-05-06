"""
Four routing algorithms for multi-tier LEO mega-constellation.
  1. Proposed: GNN-based pruning + utility-based heuristic routing
  2. GRLR:    GNN+RL greedy hop-by-hop routing (SNR-aware, no duration)
  3. DR:      Distance-based routing (Dijkstra on distance weights)
  4. STR:     Static topology-based routing (unweighted shortest path)
"""

import networkx as nx
import numpy as np
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import config as cfg


# ═══════════════════════════════════════════════════════════════
# 1. PROPOSED: GNN Pruning + Utility-Based Heuristic
# ═══════════════════════════════════════════════════════════════

def _prune_graph(G, tau=None):
    """
    Simulate GNN-based link pruning.
    Remove ISLs with utility < tau * max_utility.
    """
    if tau is None:
        tau = cfg.TAU

    utilities = [G[u][v]['utility'] for u, v in G.edges()]
    if not utilities:
        return G.copy()

    u_max = max(utilities)
    threshold = tau * u_max

    G_pruned = G.copy()
    to_remove = [(u, v) for u, v in G_pruned.edges()
                 if G_pruned[u][v]['utility'] < threshold]
    G_pruned.remove_edges_from(to_remove)
    return G_pruned


def _set_proposed_weights(G):
    """
    Set edge weights using ISL utility U_ij = β·U_l + (1-β)·U_c (Eq. 11).
    Weight = 1 - utility. Lower weight → better link.
    """
    for u, v in G.edges():
        G[u][v]['weight'] = max(1.0 - G[u][v]['utility'], 1e-6)


def route_proposed(G, src, dst, tau=None):
    """
    Proposed algorithm: prune graph by utility, then Dijkstra with
    joint duration+capacity weight. Among equal-weight paths, select
    the one with fewest hops.
    """
    G_pruned = _prune_graph(G, tau)

    if src not in G_pruned or dst not in G_pruned:
        return None

    _set_proposed_weights(G_pruned)

    try:
        paths = list(nx.all_shortest_paths(G_pruned, src, dst, weight='weight'))
        return min(paths, key=len)
    except (nx.NetworkXNoPath, nx.NodeNotFound):
        # Fallback to unpruned graph
        G_full = G.copy()
        _set_proposed_weights(G_full)
        try:
            return nx.shortest_path(G_full, src, dst, weight='weight')
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            return None


# ═══════════════════════════════════════════════════════════════
# 2. GRLR: GNN + RL Greedy Hop-by-Hop Routing
# ═══════════════════════════════════════════════════════════════

def route_grlr(G, src, dst, max_hops=50):
    """
    GRLR-inspired routing: Dijkstra with SNR-based weight (capacity-aware).
    Uses link capacity (from SNR) but does NOT use link duration.
    Key difference from Proposed: no joint duration×capacity optimization.
    Includes small noise to model RL policy approximation error.
    """
    if src not in G or dst not in G:
        return None

    # Set GRLR weights: based on SNR/capacity only, no duration
    sinrs = [G[u][v]['sinr_db'] for u, v in G.edges()]
    if not sinrs:
        return None

    sinr_max = max(sinrs)
    sinr_min = min(sinrs)
    sinr_range = sinr_max - sinr_min if sinr_max > sinr_min else 1.0
    degrees = dict(G.degree())
    max_deg = max(degrees.values()) if degrees else 1

    np.random.seed(hash((src, dst)) % 2**31)

    for u, v in G.edges():
        sinr = G[u][v]['sinr_db']
        dur = G[u][v]['duration']
        # SNR-based cost (lower SINR → higher cost)
        snr_cost = 1.0 - (sinr - sinr_min) / sinr_range
        # Degree-based congestion proxy (GNN structural feature)
        deg_cost = (degrees[u] + degrees[v]) / (2 * max_deg)
        # Implicit stability: RL learns to avoid unreliable short-lived links
        if dur < 50:
            G[u][v]['weight'] = 10.0  # Hard avoidance of very short links
            continue
        dur_penalty = max(0, 1.0 - dur / 120.0)  # Mild penalty for links < 120s
        # RL exploration noise
        noise = np.random.uniform(0, 0.05)
        G[u][v]['weight'] = 0.60 * snr_cost + 0.15 * deg_cost + 0.10 * dur_penalty + 0.15 * noise

    try:
        return nx.shortest_path(G, src, dst, weight='weight')
    except (nx.NetworkXNoPath, nx.NodeNotFound):
        return None


# ═══════════════════════════════════════════════════════════════
# 3. DR: Distance-Based Routing
# ═══════════════════════════════════════════════════════════════

def route_dr(G, src, dst):
    """
    Distance-based Routing: Dijkstra minimizing physical ISL distance.
    """
    if src not in G or dst not in G:
        return None

    for u, v in G.edges():
        G[u][v]['weight'] = G[u][v]['distance']

    try:
        return nx.shortest_path(G, src, dst, weight='weight')
    except (nx.NetworkXNoPath, nx.NodeNotFound):
        return None


# ═══════════════════════════════════════════════════════════════
# 4. STR: Static Topology-Based Routing
# ═══════════════════════════════════════════════════════════════

def route_str(G, src, dst):
    """
    Static Topology-based Routing: unweighted BFS shortest path (hop-count).
    Uses fixed topology structure without considering dynamic ISL states.
    """
    if src not in G or dst not in G:
        return None

    try:
        return nx.shortest_path(G, src, dst)  # No weight → BFS
    except (nx.NetworkXNoPath, nx.NodeNotFound):
        return None


# ═══════════════════════════════════════════════════════════════
# Unified interface
# ═══════════════════════════════════════════════════════════════

ROUTERS = {
    cfg.ALG_PROPOSED: route_proposed,
    cfg.ALG_GRLR:     route_grlr,
    cfg.ALG_DR:       route_dr,
    cfg.ALG_STR:      route_str,
}


def find_paths_all_algorithms(graphs, src_dst_pairs, tau=None):
    """
    Run all routing algorithms on all cycles.

    Returns:
        results: dict {alg_name: {cycle: path_or_None}}
    """
    results = {alg: {} for alg in cfg.ALGORITHMS}

    for cycle, G in graphs.items():
        if cycle not in src_dst_pairs:
            for alg in cfg.ALGORITHMS:
                results[alg][cycle] = None
            continue

        src, dst = src_dst_pairs[cycle]

        for alg_name in cfg.ALGORITHMS:
            G_copy = G.copy()
            if alg_name == cfg.ALG_PROPOSED:
                path = route_proposed(G_copy, src, dst, tau)
            elif alg_name == cfg.ALG_GRLR:
                path = route_grlr(G_copy, src, dst)
            elif alg_name == cfg.ALG_DR:
                path = route_dr(G_copy, src, dst)
            elif alg_name == cfg.ALG_STR:
                path = route_str(G_copy, src, dst)
            else:
                path = None
            results[alg_name][cycle] = path

    return results
