"""
R2C1: GNN classification accuracy.

Trains a fresh GNN on cycles 0..N_TRAIN-1, then evaluates accuracy/precision/
recall/F1 against LP-derived ground-truth labels on held-out cycles.
"""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config as cfg
from network.constellation import generate_constellation
from network.graph_builder import build_graph
from network.lp_solver import compute_utilization_labels, generate_training_data
from network.gnn_model import (
    GNNLinkPredictor, train_gnn, predict_retention, save_model, load_model
)

N_TRAIN_CYCLES = 20
N_TEST_CYCLES = 20
N_PAIRS_PER_CYCLE = 20
N_EPOCHS = 100
SEED = 42


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
    print("  R2C1: GNN Classification Accuracy")
    print("=" * 60)
    print(f"  Train cycles: 0..{N_TRAIN_CYCLES-1}")
    print(f"  Test cycles:  {cfg.N_CYCLES - N_TEST_CYCLES}..{cfg.N_CYCLES-1}")
    print(f"  Pairs/cycle:  {N_PAIRS_PER_CYCLE}")
    print(f"  Epochs:       {N_EPOCHS}")

    # 1. Generate constellation
    print(f"\n[1/5] Generating constellation ({cfg.N_CYCLES} cycles)...", flush=True)
    pos, vel = generate_constellation()

    # 2. Build train + test graphs
    print(f"\n[2/5] Building graphs...", flush=True)
    all_graphs = {}
    train_cycles = list(range(N_TRAIN_CYCLES))
    test_cycles = list(range(cfg.N_CYCLES - N_TEST_CYCLES, cfg.N_CYCLES))
    for c in sorted(set(train_cycles + test_cycles)):
        all_graphs[c] = build_graph(pos, vel, c)
    print(f"  Built {len(all_graphs)} graphs total", flush=True)

    # 3. Generate training data + train
    print(f"\n[3/5] Generating training labels via LP...", flush=True)
    train_graphs_dict = {c: all_graphs[c] for c in train_cycles}
    train_data, stats = generate_training_data(
        train_graphs_dict, n_pairs_per_cycle=N_PAIRS_PER_CYCLE, n_cycles=N_TRAIN_CYCLES, seed=SEED
    )
    print(f"  Train positive ratio: {stats['positive_ratio']:.3f}", flush=True)

    print(f"\n[4/5] Training GNN ({N_EPOCHS} epochs)...", flush=True)
    model = train_gnn(train_graphs_dict, train_data, n_epochs=N_EPOCHS, lr=1e-3)
    save_model(model, os.path.join('checkpoints', 'gnn_link_predictor.pt'))

    # 4. Eval on test cycles
    print(f"\n[5/5] Evaluating on {N_TEST_CYCLES} test cycles...", flush=True)
    rng = np.random.default_rng(SEED + 1)
    y_true_all, y_pred_all = [], []
    for c in test_cycles:
        G = all_graphs[c]
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
            y_pred_all.append(1 if retention.get((u, v), 0) >= cfg.TAU else 0)

    y_true = np.array(y_true_all)
    y_pred = np.array(y_pred_all)
    acc, prec, rec, f1, tp, fp, tn, fn = metrics(y_true, y_pred)

    print()
    print("=" * 60)
    print("  Test-Set Metrics")
    print("=" * 60)
    print(f"  ISLs evaluated:       {len(y_true)}")
    print(f"  Positive label ratio: {y_true.mean()*100:.1f}%")
    print(f"  Confusion: TP={tp}, FP={fp}, TN={tn}, FN={fn}")
    print()
    print(f"  Accuracy:  {acc*100:.1f}%")
    print(f"  Precision: {prec*100:.1f}%")
    print(f"  Recall:    {rec*100:.1f}%")
    print(f"  F1-score:  {f1*100:.1f}%")
    print("=" * 60)


if __name__ == '__main__':
    main()
