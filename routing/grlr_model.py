"""
GRLR: Graph Reinforcement Learning Routing (Zhang et al., TVT 2025)
GNN extracts node embeddings + RL-learned policy for hop-by-hop routing.
Key difference from Proposed: does NOT consider ISL duration, only link quality.
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
import numpy as np
import networkx as nx
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import config as cfg


class GRLRMessagePassing(nn.Module):
    """GNN layer for GRLR node embedding extraction."""

    def __init__(self, in_dim, hidden_dim):
        super().__init__()
        self.msg = nn.Linear(in_dim + 2, hidden_dim)  # +2 for edge features (dist, sinr)
        self.update = nn.Linear(in_dim + hidden_dim, hidden_dim)
        self.norm = nn.LayerNorm(hidden_dim)

    def forward(self, h, edge_index, edge_feats):
        N = h.shape[0]
        hidden = self.update.out_features
        src, dst = edge_index

        # Messages
        msg_input = torch.cat([h[src], edge_feats], dim=1)
        msgs = F.relu(self.msg(msg_input))

        # Aggregate
        agg = torch.zeros(N, hidden, device=h.device)
        cnt = torch.zeros(N, 1, device=h.device)
        agg.index_add_(0, dst, msgs)
        cnt.index_add_(0, dst, torch.ones(len(dst), 1, device=h.device))
        cnt = cnt.clamp(min=1)
        agg = agg / cnt

        # Update
        out = self.norm(F.relu(self.update(torch.cat([h, agg], dim=1))))
        return out


class GRLRPolicy(nn.Module):
    """
    GRLR routing policy: GNN + MLP policy head.
    Given current node embedding and neighbor embeddings,
    outputs probability distribution over neighbors.
    """

    def __init__(self, node_dim=3, edge_dim=2, hidden_dim=64, n_layers=2):
        super().__init__()
        self.input_proj = nn.Linear(node_dim, hidden_dim)
        self.layers = nn.ModuleList([
            GRLRMessagePassing(hidden_dim, hidden_dim)
            for _ in range(n_layers)
        ])
        # Policy: score each neighbor
        self.policy = nn.Sequential(
            nn.Linear(hidden_dim * 2 + edge_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, 1)
        )

    def get_embeddings(self, node_feats, edge_index, edge_feats):
        h = F.relu(self.input_proj(node_feats))
        for layer in self.layers:
            h = layer(h, edge_index, edge_feats)
        return h

    def select_neighbor(self, embeddings, current_idx, neighbor_indices, edge_feats_list):
        """Score each neighbor and return best."""
        h_current = embeddings[current_idx].unsqueeze(0).expand(len(neighbor_indices), -1)
        h_neighbors = embeddings[neighbor_indices]
        ef = torch.stack(edge_feats_list)

        scores = self.policy(torch.cat([h_current, h_neighbors, ef], dim=1)).squeeze(-1)
        return scores


def graph_to_grlr_tensors(G, device='cpu'):
    """Convert graph to tensors for GRLR (uses SINR instead of duration)."""
    nodes = sorted(G.nodes())
    node_map = {n: i for i, n in enumerate(nodes)}
    N = len(nodes)

    # Node features: degree, tier, connectivity (NO duration info)
    node_feats = np.zeros((N, 3))
    max_deg = max(dict(G.degree()).values()) if G.edges() else 1
    for i, n in enumerate(nodes):
        tier = n // cfg.SATS_PER_TIER
        node_feats[i, 0] = G.degree(n) / max_deg
        node_feats[i, 1] = tier / (cfg.N_TIERS - 1)
        neighbors = list(G.neighbors(n))
        if len(neighbors) >= 2:
            n_links = sum(1 for a in neighbors for b in neighbors if a < b and G.has_edge(a, b))
            node_feats[i, 2] = 2 * n_links / (len(neighbors) * (len(neighbors) - 1))

    # Edge features: distance and SINR (NOT duration - key difference from Proposed)
    edges = list(G.edges())
    src_list, dst_list = [], []
    edge_feat_list = []

    sinr_max = max(G[u][v]['sinr_db'] for u, v in edges) if edges else 1
    for u, v in edges:
        ui, vi = node_map[u], node_map[v]
        d_norm = G[u][v]['distance'] / cfg.ISL_MAX_DISTANCE_M
        s_norm = G[u][v]['sinr_db'] / sinr_max
        ef = [d_norm, s_norm]
        src_list.extend([ui, vi])
        dst_list.extend([vi, ui])
        edge_feat_list.extend([ef, ef])

    edge_index = torch.tensor([src_list, dst_list], dtype=torch.long, device=device)
    edge_feats = torch.tensor(edge_feat_list, dtype=torch.float32, device=device)
    node_feats = torch.tensor(node_feats, dtype=torch.float32, device=device)

    return node_feats, edge_index, edge_feats, node_map


def train_grlr(graphs, src_dst_pairs, n_episodes=200, lr=1e-3, device='cuda'):
    """
    Train GRLR using REINFORCE (policy gradient).
    Reward: negative path cost based on SINR quality (no duration).
    """
    if not torch.cuda.is_available():
        device = 'cpu'

    model = GRLRPolicy(node_dim=3, edge_dim=2, hidden_dim=64, n_layers=2).to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=lr)

    print(f"  Training GRLR on {len(graphs)} graphs, {n_episodes} episodes", flush=True)

    for ep in range(n_episodes):
        total_reward = 0
        n_success = 0

        for cycle, G in graphs.items():
            if cycle not in src_dst_pairs:
                continue
            src, dst = src_dst_pairs[cycle]
            if src not in G or dst not in G:
                continue

            node_feats, edge_index, edge_feats, node_map = graph_to_grlr_tensors(G, device)
            if src not in node_map or dst not in node_map:
                continue

            embeddings = model.get_embeddings(node_feats, edge_index, edge_feats)

            # Hop-by-hop routing with policy
            current = src
            visited = {src}
            log_probs = []
            path_reward = 0
            success = False

            for step in range(40):
                if current == dst:
                    success = True
                    break

                current_idx = node_map[current]
                neighbors = [n for n in G.neighbors(current) if n not in visited]
                if not neighbors:
                    break

                n_indices = torch.tensor([node_map[n] for n in neighbors], device=device)
                # Edge features for current -> each neighbor
                ef_list = []
                sinr_max = max(G[current][n]['sinr_db'] for n in neighbors)
                for n in neighbors:
                    d = G[current][n]['distance'] / cfg.ISL_MAX_DISTANCE_M
                    s = G[current][n]['sinr_db'] / max(sinr_max, 1)
                    ef_list.append(torch.tensor([d, s], dtype=torch.float32, device=device))

                scores = model.select_neighbor(embeddings, current_idx, n_indices, ef_list)
                probs = F.softmax(scores, dim=0)
                dist = torch.distributions.Categorical(probs)
                action = dist.sample()
                log_probs.append(dist.log_prob(action))

                next_node = neighbors[action.item()]
                # Reward based on SINR quality (no duration)
                sinr = G[current][next_node]['sinr_db']
                path_reward += sinr / 50.0  # normalized

                visited.add(next_node)
                current = next_node

            if success:
                path_reward += 5.0  # success bonus
                n_success += 1
            else:
                path_reward = -2.0  # failure penalty

            total_reward += path_reward

            # REINFORCE update
            if log_probs:
                policy_loss = -sum(lp * path_reward for lp in log_probs) / len(log_probs)
                optimizer.zero_grad()
                policy_loss.backward()
                torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                optimizer.step()

        if (ep + 1) % 50 == 0:
            avg_r = total_reward / max(len(src_dst_pairs), 1)
            print(f"    Episode {ep+1}: avg_reward={avg_r:.3f}, success={n_success}/{len(src_dst_pairs)}", flush=True)

    return model


def route_with_grlr(model, G, src, dst, device='cuda', max_hops=40):
    """Use trained GRLR model for hop-by-hop routing."""
    if not torch.cuda.is_available():
        device = 'cpu'

    if src not in G or dst not in G or not nx.has_path(G, src, dst):
        return None

    model.eval()
    node_feats, edge_index, edge_feats, node_map = graph_to_grlr_tensors(G, device)

    if src not in node_map or dst not in node_map:
        return None

    with torch.no_grad():
        embeddings = model.get_embeddings(node_feats, edge_index, edge_feats)

    path = [src]
    current = src
    visited = {src}

    for _ in range(max_hops):
        if current == dst:
            return path

        current_idx = node_map[current]
        neighbors = [n for n in G.neighbors(current) if n not in visited]
        if not neighbors:
            # Fallback to Dijkstra
            try:
                remaining = nx.shortest_path(G, current, dst)
                return path + remaining[1:]
            except nx.NetworkXNoPath:
                return None

        n_indices = torch.tensor([node_map[n] for n in neighbors], device=device)
        sinr_max = max(G[current][n]['sinr_db'] for n in neighbors)
        ef_list = []
        for n in neighbors:
            d = G[current][n]['distance'] / cfg.ISL_MAX_DISTANCE_M
            s = G[current][n]['sinr_db'] / max(sinr_max, 1)
            ef_list.append(torch.tensor([d, s], dtype=torch.float32, device=device))

        with torch.no_grad():
            scores = model.select_neighbor(embeddings, current_idx, n_indices, ef_list)

        best = scores.argmax().item()
        next_node = neighbors[best]
        visited.add(next_node)
        path.append(next_node)
        current = next_node

    return None


def save_grlr(model, path):
    torch.save(model.state_dict(), path)

def load_grlr(path, device='cuda'):
    if not torch.cuda.is_available():
        device = 'cpu'
    model = GRLRPolicy(node_dim=3, edge_dim=2, hidden_dim=64, n_layers=2)
    model.load_state_dict(torch.load(path, map_location=device))
    model.to(device)
    model.eval()
    return model
