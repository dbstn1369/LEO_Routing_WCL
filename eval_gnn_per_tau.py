"""
R2C1: GNN classification accuracy per τ.

Loads the trained GNN, runs inference on held-out test snapshots, and
computes accuracy for each τ in {0.1, 0.3, 0.5, 0.7, 0.9}. The GNN's
predicted retention probabilities p_hat are computed once per ISL; only
the threshold τ varies between rows.
"""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config as cfg
from network.constellation import generate_constellation
from network.graph_builder import build_graph
from network.lp_solver import compute_utilization_labels
from network.gnn_model import predict_retention, load_model

N_TEST_CYCLES = 20
N_PAIRS_PER_CYCLE = 20
SEED = 43  # different from training
TAU_VALUES = [0.1, 0.3, 0.5, 0.7, 0.9]


def metrics(y_true, y_pred):
    n = len(y_true)
    tp = int(((y_pred == 1) & (y_true == 1)).sum())
    fp = int(((y_pred == 1) & (y_true == 0)).sum())
    tn = int(((y_pred == 0) & (y_true == 0)).sum())
    fn = int(((y_pred == 0) & (y_true == 1)).sum())
    acc = (tp + tn) / n if n else 0
    prec = tp / (tp + fp) if (tp + fp) else 0
    rec = tp / (tp + fn) if (tp + fn) else 0
    f1 = 2 * prec * rec / (prec + rec) if (prec + rec) else 0
    return acc, prec, rec, f1, tp, fp, tn, fn


def main():
    print("=" * 60)
    print("  R2C1: GNN Accuracy per τ on Test Snapshots")
    print("=" * 60)

    print(f"\n[1/4] Generating constellation ({cfg.N_CYCLES} cycles)...", flush=True)
    pos, vel = generate_constellation()

    test_start = max(0, cfg.N_CYCLES - N_TEST_CYCLES)
    print(f"\n[2/4] Building {N_TEST_CYCLES} test graphs (cycles {test_start}-{cfg.N_CYCLES-1})...",
          flush=True)
    test_graphs = {}
    for c in range(test_start, cfg.N_CYCLES):
        test_graphs[c] = build_graph(pos, vel, c)
        if (c - test_start + 1) % 5 == 0:
            print(f"  {c - test_start + 1}/{N_TEST_CYCLES}", flush=True)

    print(f"\n[3/4] Generating LP labels + GNN predictions on test...", flush=True)
    model_path = os.path.join('checkpoints', 'gnn_link_predictor.pt')
    if not os.path.exists(model_path):
        print(f"  ERROR: trained model not found at {model_path}")
        return
    model = load_model(model_path)

    rng = np.random.default_rng(SEED)
    y_true_all = []
    p_hat_all = []
    for c in sorted(test_graphs.keys()):
        G = test_graphs[c]
        nodes = list(G.nodes())
        mid = [n for n in nodes if cfg.SATS_PER_TIER <= n < 2 * cfg.SATS_PER_TIER]
        if len(mid) < 2:
            mid = nodes
        pairs = [tuple(map(int, rng.choice(mid, 2, replace=False)))
                 for _ in range(N_PAIRS_PER_CYCLE)]
        labels, _ = compute_utilization_labels(G, pairs)
        retention = predict_retention(model, G)
        for u, v in G.edges():
            if u >= v:
                continue
            y_true_all.append(int(labels.get((u, v), 0)))
            p_hat_all.append(float(retention.get((u, v), 0)))

    y_true = np.array(y_true_all)
    p_hat = np.array(p_hat_all)
    pos_ratio = y_true.mean()

    print(f"  ISLs evaluated: {len(y_true)}")
    print(f"  Positive label ratio: {pos_ratio*100:.1f}%")
    print(f"  p_hat range: [{p_hat.min():.3f}, {p_hat.max():.3f}], mean={p_hat.mean():.3f}")

    print(f"\n[4/4] Per-τ metrics:")
    print(f"  {'τ':>5s} | {'Acc':>6s} | {'Prec':>6s} | {'Rec':>6s} | {'F1':>6s} | "
          f"{'TP':>5s} {'FP':>5s} {'TN':>5s} {'FN':>5s}")
    print("  " + "-" * 70)
    rows = []
    for tau in TAU_VALUES:
        y_pred = (p_hat >= tau).astype(int)
        acc, prec, rec, f1, tp, fp, tn, fn = metrics(y_true, y_pred)
        rows.append((tau, acc, prec, rec, f1))
        print(f"  {tau:>5.1f} | {acc*100:>5.1f}% | {prec*100:>5.1f}% | {rec*100:>5.1f}% | "
              f"{f1*100:>5.1f}% | {tp:>5d} {fp:>5d} {tn:>5d} {fn:>5d}")

    # LaTeX-friendly summary
    print()
    print("=" * 60)
    print("  Summary (for Table I integration)")
    print("=" * 60)
    print("  τ       :   " + "   ".join(f"{r[0]:.1f}" for r in rows))
    print("  Accuracy:  " + "  ".join(f"{r[1]*100:>4.1f}" for r in rows))
    print("=" * 60)


if __name__ == '__main__':
    main()
