"""
R5C4: Small-scale optimality comparison.

Compares the proposed heuristic against the true optimum of the original
ratio-based problem P (Eq. 12a) on reduced 3-tier networks of varying size
(N = 20, 30, 40, 50 satellites).

P maximizes (sum U_ij) / (#hops). For each S-D pair, we solve P exactly via
the Dinkelbach algorithm for fractional programming:
  iterate lambda_{k+1} = sum_U(x*)/hops(x*), where x* solves
    max sum x_ij * (U_ij - lambda_k)  s.t. simple s-d path constraints
  (flow conservation + in/out degree <= 1 + MTZ subtour elimination).
The iteration converges to the optimal average utility per hop.
Solver is Gurobi via PuLP, fallback CBC.

Output: figure plotting Proposed/Optimal (%) vs. network size.
"""
import heapq
import os

import numpy as np
import pulp

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

SEED = 42
T_SNAPSHOT = 5.0 * 60
BETA = 0.5
N_PAIRS = 15
TAU_FRAC = 0.5
DINKELBACH_MAX_ITER = 25
DINKELBACH_TOL = 1e-6
ILP_TIME_LIMIT = 120


# ── Solver selection ────────────────────────────────────────────

try:
    if pulp.GUROBI(msg=0).available():
        SOLVER_NAME = "Gurobi"
        def make_solver():
            return pulp.GUROBI(msg=0, timeLimit=ILP_TIME_LIMIT)
    else:
        raise RuntimeError("Gurobi not available")
except Exception:
    SOLVER_NAME = "CBC"
    def make_solver():
        return pulp.PULP_CBC_CMD(msg=0, timeLimit=ILP_TIME_LIMIT)


# ── Network builder ────────────────────────────────────────────

def build_network(N_total, seed=SEED):
    """Build 3-tier network with N_total satellites distributed roughly evenly."""
    rng = np.random.default_rng(seed)

    # Distribute satellites across 3 tiers (≈ N/3 each)
    base = N_total // 3
    rem = N_total - 3 * base
    sats_per_tier = [base + (1 if i < rem else 0) for i in range(3)]
    N = sum(sats_per_tier)

    tier_offset = [0]
    for n in sats_per_tier:
        tier_offset.append(tier_offset[-1] + n)

    edges = {}

    # Intra-tier: ring + skip-1
    for k, n in enumerate(sats_per_tier):
        base_idx = tier_offset[k]
        for idx in range(n):
            for step in (1, 2):
                if step >= n:
                    continue
                i = base_idx + idx
                j = base_idx + (idx + step) % n
                if (i, j) in edges:
                    continue
                dur = rng.uniform(4.0, 6.0) * 60 if step == 1 else rng.uniform(3.5, 5.5) * 60
                cap = rng.uniform(1.2, 1.8) if step == 1 else rng.uniform(1.0, 1.6)
                edges[(i, j)] = {'duration': dur, 'capacity': cap}
                edges[(j, i)] = {'duration': dur, 'capacity': cap}

    # Inter-tier: sparse cross-tier ISLs
    for k1 in range(len(sats_per_tier)):
        for k2 in range(k1 + 1, len(sats_per_tier)):
            n_cross = max(4, int(0.4 * min(sats_per_tier[k1], sats_per_tier[k2])))
            attempts = 0
            added = 0
            while added < n_cross and attempts < n_cross * 10:
                attempts += 1
                i = tier_offset[k1] + int(rng.integers(sats_per_tier[k1]))
                j = tier_offset[k2] + int(rng.integers(sats_per_tier[k2]))
                if (i, j) in edges:
                    continue
                dur = rng.uniform(1.5, 3.5) * 60
                cap = rng.uniform(0.6, 1.2)
                edges[(i, j)] = {'duration': dur, 'capacity': cap}
                edges[(j, i)] = {'duration': dur, 'capacity': cap}
                added += 1

    return N, edges


def compute_utility(edges):
    edge_list = list(edges.keys())
    U_l = {e: edges[e]['duration'] / T_SNAPSHOT for e in edge_list}
    caps = np.array([edges[e]['capacity'] for e in edge_list])
    exp_caps = np.exp(caps - caps.max())
    softmax_sum = exp_caps.sum()
    U_c = {e: exp_caps[idx] / softmax_sum for idx, e in enumerate(edge_list)}
    U = {e: BETA * U_l[e] + (1 - BETA) * U_c[e] for e in edge_list}
    return edge_list, U


def build_adj(edge_list, N):
    adj = {s: [] for s in range(N)}
    rev_adj = {s: [] for s in range(N)}
    for (i, j) in edge_list:
        adj[i].append(j)
        rev_adj[j].append(i)
    return adj, rev_adj


def gen_pairs(N, adj, n_pairs, seed=SEED):
    rng = np.random.default_rng(seed + 1)

    def reachable(s):
        visited = {s}
        q = [s]
        while q:
            node = q.pop(0)
            for nb in adj[node]:
                if nb not in visited:
                    visited.add(nb)
                    q.append(nb)
        return visited

    pairs = []
    seen = set()
    attempts = 0
    while len(pairs) < n_pairs and attempts < 1000:
        attempts += 1
        s = int(rng.integers(N))
        d = int(rng.integers(N))
        if s == d or (s, d) in seen:
            continue
        if d in reachable(s):
            pairs.append((s, d))
            seen.add((s, d))
    return pairs


# ── Optimal: Dinkelbach + ILP with MTZ ─────────────────────────

def solve_subproblem(s, d, lambda_k, edge_list, U, adj, rev_adj, N):
    prob = pulp.LpProblem(f"din_{s}_{d}", pulp.LpMaximize)
    x = {e: pulp.LpVariable(f"x_{e[0]}_{e[1]}", cat='Binary') for e in edge_list}
    prob += pulp.lpSum(x[e] * (U[e] - lambda_k) for e in edge_list)

    for node in range(N):
        out = pulp.lpSum(x[(node, j)] for j in adj[node])
        inp = pulp.lpSum(x[(j, node)] for j in rev_adj[node])
        if node == s:
            prob += (out == 1)
            prob += (inp == 0)
        elif node == d:
            prob += (out == 0)
            prob += (inp == 1)
        else:
            prob += (out <= 1)
            prob += (inp <= 1)
            prob += (out - inp == 0)

    u = {node: pulp.LpVariable(f"u_{node}", lowBound=0, upBound=N, cat='Continuous')
         for node in range(N)}
    prob += (u[s] == 0)
    for (i, j) in edge_list:
        if j != s:
            prob += (u[i] - u[j] + N * x[(i, j)] <= N - 1)

    prob.solve(make_solver())
    if prob.status != 1:
        return None

    active = {i: j for (i, j) in edge_list
              if x[(i, j)].varValue is not None and x[(i, j)].varValue > 0.5}
    path = [s]
    cur = s
    visited = {s}
    while cur != d:
        if cur not in active or active[cur] in visited:
            break
        cur = active[cur]
        path.append(cur)
        visited.add(cur)
    if path[-1] != d:
        return None
    K = len(path) - 1
    sum_U_path = sum(U[(path[i], path[i+1])] for i in range(K))
    return path, sum_U_path, K


def solve_optimal_dinkelbach(s, d, edge_list, U, adj, rev_adj, N):
    lambda_k = 0.0
    best_path, best_avg = None, -1.0
    for it in range(DINKELBACH_MAX_ITER):
        result = solve_subproblem(s, d, lambda_k, edge_list, U, adj, rev_adj, N)
        if result is None:
            break
        path, sum_U, K = result
        new_avg = sum_U / K
        sub_obj = sum_U - lambda_k * K
        if best_path is None or new_avg > best_avg:
            best_path = path
            best_avg = new_avg
        if sub_obj <= DINKELBACH_TOL or new_avg - lambda_k <= DINKELBACH_TOL:
            break
        lambda_k = new_avg
    return best_path, best_avg


# ── Proposed heuristic ─────────────────────────────────────────

def heuristic_route(s, d, graph_adj, utility, N):
    psi = {}
    for node in range(N):
        nbrs = graph_adj.get(node, [])
        psi[node] = max((utility[(node, nb)] for nb in nbrs), default=0.0)

    g = {s: 0.0}
    H = {s: 0}
    pred = {s: None}
    best_f = {s: psi[s]}
    pq = [(-best_f[s], s)]
    visited = set()
    while pq:
        _, i = heapq.heappop(pq)
        if i in visited:
            continue
        visited.add(i)
        if i == d:
            path = [d]
            cur = d
            while pred[cur] is not None:
                cur = pred[cur]
                path.append(cur)
            return list(reversed(path))
        for j in graph_adj.get(i, []):
            if j in visited or (i, j) not in utility:
                continue
            new_g = g[i] + utility[(i, j)]
            new_H = H[i] + 1
            new_f = (new_g + psi[j]) / (new_H + 1)
            if j not in best_f or new_f > best_f[j]:
                g[j] = new_g
                H[j] = new_H
                pred[j] = i
                best_f[j] = new_f
                heapq.heappush(pq, (-new_f, j))
    return None


def path_avg_util(path, U):
    hops = len(path) - 1
    if hops == 0:
        return 0.0
    return sum(U[(path[i], path[i+1])] for i in range(hops)) / hops


def run_experiment(N_total, n_pairs=N_PAIRS):
    """Run a single experiment for given network size; return (opt_sum, prop_sum, ratio)."""
    print(f"\n== N = {N_total} ==")
    N, edges = build_network(N_total)
    edge_list, U = compute_utility(edges)
    adj, rev_adj = build_adj(edge_list, N)
    print(f"  {N} satellites, {len(edge_list)//2} undirected ISLs")

    pairs = gen_pairs(N, adj, n_pairs)
    print(f"  {len(pairs)} S-D pairs")

    # Optimal
    print(f"  Solving optimal (Dinkelbach + ILP)...")
    opt_sum = 0.0
    opt_avgs = []
    for idx, (s, d) in enumerate(pairs):
        path, avg = solve_optimal_dinkelbach(s, d, edge_list, U, adj, rev_adj, N)
        if path is not None:
            opt_sum += avg
            opt_avgs.append(avg)
        print(f"    [{idx+1}/{len(pairs)}] ({s},{d}): "
              f"hops={len(path)-1 if path else '-'}, avg={avg:.4f}", flush=True)

    # Proposed (with simulated GNN pruning)
    threshold = np.percentile(list(U.values()), TAU_FRAC * 100)
    pruned_U = {e: U[e] for e in edge_list if U[e] >= threshold}
    pruned_adj = {s: [] for s in range(N)}
    for (i, j) in pruned_U:
        pruned_adj[i].append(j)

    prop_sum = 0.0
    prop_avgs = []
    for (s, d) in pairs:
        path = heuristic_route(s, d, pruned_adj, pruned_U, N)
        if path is None:
            path = heuristic_route(s, d, adj, U, N)
        if path:
            avg = path_avg_util(path, U)
            prop_sum += avg
            prop_avgs.append(avg)

    ratio = prop_sum / opt_sum * 100 if opt_sum > 0 else 0.0
    print(f"  Optimal sum: {opt_sum:.4f}, Proposed sum: {prop_sum:.4f}, ratio: {ratio:.1f}%")

    return opt_sum, prop_sum, ratio, opt_avgs, prop_avgs


# ── Main: sweep network sizes and plot ────────────────────────

def main():
    print(f"ILP solver: {SOLVER_NAME}")
    print(f"Per-pair ILP time limit: {ILP_TIME_LIMIT}s")

    N_values = [20, 30, 40, 50]
    results = []
    for N in N_values:
        opt_sum, prop_sum, ratio, opt_avgs, prop_avgs = run_experiment(N)
        results.append({
            'N': N, 'opt_sum': opt_sum, 'prop_sum': prop_sum,
            'ratio': ratio, 'opt_avgs': opt_avgs, 'prop_avgs': prop_avgs
        })

    # ── Print summary ───────────────────────────────────────
    print()
    print("=" * 60)
    print("  Optimality Comparison Summary")
    print("=" * 60)
    print(f"  {'N':>4s}  {'Optimal':>10s}  {'Proposed':>10s}  {'Ratio':>8s}")
    for r in results:
        print(f"  {r['N']:>4d}  {r['opt_sum']:>10.4f}  {r['prop_sum']:>10.4f}  {r['ratio']:>7.1f}%")
    print("=" * 60)

    # ── Plot ────────────────────────────────────────────────
    out_dir = 'results'
    os.makedirs(out_dir, exist_ok=True)

    plt.rcParams.update({
        'font.family': 'Times New Roman',
        'font.size': 32,
        'axes.labelsize': 32,
        'xtick.labelsize': 32,
        'ytick.labelsize': 32,
        'legend.fontsize': 28,
        'axes.grid': True,
        'figure.figsize': (9, 8),
    })

    Ns = [r['N'] for r in results]
    ratios = [r['ratio'] for r in results]

    # Per-pair ratio (Proposed_avg / Optimal_avg) × 100, for error bars
    per_pair_ratios = []
    for r in results:
        rs = []
        for oa, pa in zip(r['opt_avgs'], r['prop_avgs']):
            if oa > 0:
                rs.append(pa / oa * 100)
        per_pair_ratios.append(rs)
    means = [np.mean(rs) if rs else 0 for rs in per_pair_ratios]
    stds = [np.std(rs) if rs else 0 for rs in per_pair_ratios]

    fig, ax = plt.subplots()
    ax.errorbar(Ns, ratios, yerr=stds, marker='o', linestyle='-',
                markersize=12, linewidth=3, capsize=8, capthick=3,
                color='#005EB8', label='Proposed / Optimal')
    ax.axhline(100, color='gray', linestyle='--', linewidth=2, alpha=0.7)
    ax.set_xlabel('Number of Satellites')
    ax.set_ylabel('Optimality Ratio (%)')
    ax.set_xticks(Ns)
    ax.set_ylim(80, 105)
    ax.legend(loc='lower right', framealpha=0.5)
    plt.tight_layout()
    out_eps = os.path.join(out_dir, 'fig_optimality.eps')
    fig.savefig(out_eps, format='eps', bbox_inches='tight')
    fig.savefig(out_eps.replace('.eps', '.png'), format='png',
                bbox_inches='tight', dpi=150)
    plt.close(fig)
    print(f"  Saved: {out_eps} (+png)")


if __name__ == '__main__':
    main()
