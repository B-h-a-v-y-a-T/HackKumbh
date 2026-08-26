"""COCO Skeleton Graph Topology and Adjacency Matrix."""
import numpy as np
import torch
from typing import List, Tuple

# 17 COCO joints:
# 0: nose, 1: l_eye, 2: r_eye, 3: l_ear, 4: r_ear
# 5: l_sh, 6: r_sh, 7: l_elb, 8: r_elb, 9: l_wri, 10: r_wri
# 11: l_hip, 12: r_hip, 13: l_knee, 14: r_knee, 15: l_ank, 16: r_ank

COCO_GRAPH_EDGES: List[Tuple[int, int]] = [
    # Head connections
    (0, 1), (0, 2), (1, 3), (2, 4),
    # Head to upper body
    (0, 5), (0, 6),
    # Shoulders and arms
    (5, 6), (5, 7), (7, 9), (6, 8), (8, 10),
    # Upper body to hips
    (5, 11), (6, 12), (11, 12),
    # Legs
    (11, 13), (13, 15), (12, 14), (14, 16),
]


class SkeletonGraph:
    """Graph structure representation for 17-joint COCO human skeleton."""

    def __init__(self, num_nodes: int = 17, edges: List[Tuple[int, int]] = None):
        self.num_nodes = num_nodes
        self.edges = edges or COCO_GRAPH_EDGES
        self.A = self._build_adjacency_matrix()

    def _build_adjacency_matrix(self) -> np.ndarray:
        """Build normalized adjacency matrix with self-loops."""
        adj = np.zeros((self.num_nodes, self.num_nodes), dtype=np.float32)
        for i, j in self.edges:
            adj[i, j] = 1.0
            adj[j, i] = 1.0  # undirected skeletal connection

        # Add self-loops (Identity)
        adj += np.eye(self.num_nodes, dtype=np.float32)

        # Degree matrix normalization D^(-1/2) A D^(-1/2)
        row_sum = np.sum(adj, axis=1)
        d_inv_sqrt = np.power(row_sum, -0.5)
        d_inv_sqrt[np.isinf(d_inv_sqrt)] = 0.0
        d_mat_inv_sqrt = np.diag(d_inv_sqrt)

        norm_adj = d_mat_inv_sqrt.dot(adj).dot(d_mat_inv_sqrt)
        return norm_adj.astype(np.float32)

    def get_torch_adjacency(self) -> torch.Tensor:
        """Returns adjacency matrix as PyTorch FloatTensor."""
        return torch.from_numpy(self.A)
