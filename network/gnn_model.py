"""
GNN model for ISL retention probability prediction (Eq. 16-18).
3-layer message-passing GNN with MLP readout.
Trained with LP-derived labels via binary cross-entropy (Eq. 22).
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
import numpy as np
import networkx as nx
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import config as cfg


class MessagePassingLayer(nn.Module):
    """Single message-passing layer (Eq. 16-17)."""

    def __init__(self, node_dim, edge_dim, hidden_dim):
        super().__init__()
        # Message function: W_M [u_j || e_ij] + b_M
        self.msg_mlp = nn.Linear(node_dim + edge_dim, hidden_dim)
        # Self-state transform: W_S u_i
        self.self_mlp = nn.Linear(node_dim, hidden_dim)
        self.norm = nn.LayerNorm(hidden_dim)

    def forward(self, node_feats, edge_index, edge_feats, adj_list):
        """
        Args:
            node_feats: (N, node_dim)
            edge_index: (2, E) - [src_nodes, dst_nodes]
            edge_feats: (E, edge_dim)
            adj_list: dict {node: [(neighbor, edge_idx), ...]}
        Returns:
            updated_feats: (N, hidden_dim)
        """
        N = node_feats.shape[0]
        hidden_dim = self.self_mlp.out_features

        # Self transform
        h_self = self.self_mlp(node_feats)  # (N, hidden_dim)

        # Message aggregation
        h_agg = torch.zeros(N, hidden_dim, device=node_feats.device)
        counts = torch.zeros(N, 1, device=node_feats.device)

        src, dst = edge_index
        # Message: ReLU(W_M [u_j || e_ij] + b_M)
        neighbor_feats = node_feats[src]  # (E, node_dim)
        msg_input = torch.cat([neighbor_feats, edge_feats], dim=1)  # (E, node_dim + edge_dim)
        messages = F.relu(self.msg_mlp(msg_input))  # (E, hidden_dim)

        # Scatter-add messages to destination nodes
        h_agg.index_add_(0, dst, messages)
        counts.index_add_(0, dst, torch.ones(len(dst), 1, device=node_feats.device))

        # Mean aggregation
        counts = counts.clamp(min=1)
        h_agg = h_agg / counts

        # Update: ReLU(LayerNorm(W_S u_i + mean(m_ij)))
        # ReLU avoids gradient saturation that sigmoid causes when stacked
        # across multiple message-passing layers.
        updated = F.relu(self.norm(h_self + h_agg))
        return updated


class GNNLinkPredictor(nn.Module):
    """
    GNN for ISL retention probability prediction.
    Architecture: L=3 message-passing layers + MLP readout (Eq. 18).
    """

    def __init__(self, node_dim=4, edge_dim=2, hidden_dim=64, n_layers=3):
        super().__init__()
        self.n_layers = n_layers

        # Input projection
        self.input_proj = nn.Linear(node_dim, hidden_dim)

        # Message-passing layers
        self.mp_layers = nn.ModuleList()
        for _ in range(n_layers):
            self.mp_layers.append(MessagePassingLayer(hidden_dim, edge_dim, hidden_dim))

        # MLP readout for link prediction (Eq. 18)
        # Input: [u_i || u_j || e_ij]
        self.readout = nn.Sequential(
            nn.Linear(hidden_dim * 2 + edge_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, 1)
        )

    def forward(self, node_feats, edge_index, edge_feats, adj_list=None):
        """
        Args:
            node_feats: (N, node_dim)
            edge_index: (2, E)
            edge_feats: (E, edge_dim)
        Returns:
            p_hat: (E,) retention probabilities
        """
        # Project to hidden dim
        h = F.relu(self.input_proj(node_feats))

        # Message passing
        for layer in self.mp_layers:
            h = layer(h, edge_index, edge_feats, adj_list)

        # Link prediction
        src, dst = edge_index
        h_src = h[src]  # (E, hidden_dim)
        h_dst = h[dst]  # (E, hidden_dim)
        link_input = torch.cat([h_src, h_dst, edge_feats], dim=1)
        logits = self.readout(link_input).squeeze(-1)  # (E,)
        p_hat = torch.sigmoid(logits)

        return p_hat


def graph_to_tensors(G, device='cpu'):
    """Convert NetworkX graph to PyTorch tensors for GNN."""
    nodes = sorted(G.nodes())
    node_map = {n: i for i, n in enumerate(nodes)}
    N = len(nodes)

    # Node features: [degree, clustering_coeff, altitude_norm]
    node_feats = np.zeros((N, 4))
    for i, n in enumerate(nodes):
        tier = n // cfg.SATS_PER_TIER
        node_feats[i, 0] = G.degree(n) / cfg.MAX_CONNECTIONS  # normalized degree
        # Clustering coefficient
        neighbors = list(G.neighbors(n))
        if len(neighbors) >= 2:
            n_links = sum(1 for a in neighbors for b in neighbors if a < b and G.has_edge(a, b))
            node_feats[i, 1] = 2 * n_links / (len(neighbors) * (len(neighbors) - 1))
        node_feats[i, 2] = tier / (cfg.N_TIERS - 1)  # normalized tier
        node_feats[i, 3] = G.degree(n) / max(dict(G.degree()).values())  # relative degree

    # Edge features and index
    edges = list(G.edges())
    E = len(edges)

    # Build bidirectional edge index
    src_list, dst_list = [], []
    edge_feat_list = []

    sinr_max = max(G[u][v]['sinr_db'] for u, v in edges) if edges else 1
    dur_max = cfg.SNAPSHOT_INTERVAL_S
    dist_max = cfg.ISL_MAX_DISTANCE_M

    for u, v in edges:
        ui, vi = node_map[u], node_map[v]
        d_norm = G[u][v]['distance'] / dist_max
        l_norm = G[u][v]['duration'] / dur_max
        ef = [d_norm, l_norm]

        # Add both directions
        src_list.extend([ui, vi])
        dst_list.extend([vi, ui])
        edge_feat_list.extend([ef, ef])

    edge_index = torch.tensor([src_list, dst_list], dtype=torch.long, device=device)
    edge_feats = torch.tensor(edge_feat_list, dtype=torch.float32, device=device)
    node_feats = torch.tensor(node_feats, dtype=torch.float32, device=device)

    # Edge map: original edge index -> position in edges list
    edge_map = {(u, v): i for i, (u, v) in enumerate(edges)}

    return node_feats, edge_index, edge_feats, node_map, edge_map, edges


def train_gnn(graphs, training_data, n_epochs=100, lr=1e-3, weight_decay=1e-4, device='cuda'):
    """
    Train GNN model using LP-derived labels.

    Args:
        graphs: dict {cycle: nx.Graph}
        training_data: list of (cycle, G, labels, utilization) from LP solver
        n_epochs: number of training epochs
    Returns:
        model: trained GNNLinkPredictor
    """
    if not torch.cuda.is_available():
        device = 'cpu'

    model = GNNLinkPredictor(node_dim=4, edge_dim=2, hidden_dim=64, n_layers=3).to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=lr, weight_decay=weight_decay)

    print(f"  Training GNN on {len(training_data)} snapshots, {n_epochs} epochs, device={device}")

    for epoch in range(n_epochs):
        total_loss = 0
        total_correct = 0
        total_samples = 0

        for cycle, G, labels, utilization in training_data:
            node_feats, edge_index, edge_feats, node_map, edge_map, edges = graph_to_tensors(G, device)

            # Create target labels for original edges
            targets = []
            for u, v in edges:
                targets.append(float(labels.get((u, v), 0)))
            targets = torch.tensor(targets, dtype=torch.float32, device=device)

            # Forward pass
            p_hat_all = model(node_feats, edge_index, edge_feats)
            p_hat = p_hat_all[:len(edges)]

            # Class-weighted BCE loss (Eq. 22) with sqrt rebalancing to avoid
            # over-predicting positives when imbalance is severe.
            n_pos = max(targets.sum().item(), 1)
            n_neg = max(len(targets) - n_pos, 1)
            pos_w = float(np.sqrt(n_neg / n_pos))
            weight = torch.where(targets == 1,
                                 torch.tensor(pos_w, device=device),
                                 torch.ones(1, device=device))
            loss = F.binary_cross_entropy(p_hat.clamp(1e-7, 1-1e-7), targets, weight=weight)

            optimizer.zero_grad()
            loss.backward()
            optimizer.step()

            total_loss += loss.item()
            preds = (p_hat > 0.5).float()
            total_correct += (preds == targets).sum().item()
            total_samples += len(targets)

        if (epoch + 1) % 20 == 0:
            acc = total_correct / max(total_samples, 1) * 100
            avg_loss = total_loss / len(training_data)
            print(f"    Epoch {epoch+1:3d}: loss={avg_loss:.4f}, acc={acc:.1f}%")

    return model


def predict_retention(model, G, device='cuda'):
    """
    Use trained GNN to predict retention probability for each ISL.

    Returns:
        retention: dict {(u,v): p_hat}
    """
    if not torch.cuda.is_available():
        device = 'cpu'

    model.eval()
    node_feats, edge_index, edge_feats, node_map, edge_map, edges = graph_to_tensors(G, device)

    with torch.no_grad():
        p_hat_all = model(node_feats, edge_index, edge_feats)
        p_hat = p_hat_all[:len(edges)].cpu().numpy()

    retention = {}
    for i, (u, v) in enumerate(edges):
        retention[(u, v)] = float(p_hat[i])
        retention[(v, u)] = float(p_hat[i])

    return retention


def prune_with_gnn(model, G, tau=None, device='cuda'):
    """
    Prune graph using trained GNN predictions.
    Remove edges where predicted retention probability < tau.

    Returns:
        G_pruned: pruned NetworkX graph
    """
    if tau is None:
        tau = cfg.TAU

    retention = predict_retention(model, G, device)

    G_pruned = G.copy()
    to_remove = [(u, v) for u, v in G_pruned.edges()
                 if retention.get((u, v), 0) < tau]
    G_pruned.remove_edges_from(to_remove)

    return G_pruned


def save_model(model, path):
    torch.save(model.state_dict(), path)
    print(f"  Model saved: {path}")


def load_model(path, device='cuda'):
    if not torch.cuda.is_available():
        device = 'cpu'
    model = GNNLinkPredictor(node_dim=4, edge_dim=2, hidden_dim=64, n_layers=3)
    model.load_state_dict(torch.load(path, map_location=device))
    model.to(device)
    model.eval()
    return model
