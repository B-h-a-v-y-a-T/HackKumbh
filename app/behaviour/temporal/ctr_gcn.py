"""Channel-Topology Refinement Graph Convolutional Network (CTR-GCN) for Skeletal Temporal Action Recognition."""
import math
import torch
import torch.nn as nn
import torch.nn.functional as F
from typing import Optional

from .skeleton_graph import SkeletonGraph


class CTRGC(nn.Module):
    """Channel-Topology Refinement Graph Convolution.
    
    Dynamically refines the graph adjacency matrix per channel group to capture
    fine-grained spatial correlations between human joints (e.g. head-ear, wrist-desk).
    """

    def __init__(self, in_channels: int, out_channels: int, num_joints: int = 17, num_subsets: int = 3):
        super().__init__()
        self.in_channels = in_channels
        self.out_channels = out_channels
        self.num_joints = num_joints
        self.num_subsets = num_subsets

        # Graph static base adjacency
        graph = SkeletonGraph(num_nodes=num_joints)
        self.register_buffer("A_base", graph.get_torch_adjacency())

        # Channel transformations for dynamic topology refinement
        self.conv_phi = nn.Conv2d(in_channels, out_channels // 2, kernel_size=1)
        self.conv_psi = nn.Conv2d(in_channels, out_channels // 2, kernel_size=1)
        self.conv_out = nn.Conv2d(in_channels, out_channels, kernel_size=1)

        # Learnable residual weight for dynamic adjacency
        self.alpha = nn.Parameter(torch.zeros(1))
        self.bn = nn.BatchNorm2d(out_channels)
        self.relu = nn.ReLU(inplace=True)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Input: x of shape (B, C, T, V)
        Output: out of shape (B, C_out, T, V)
        """
        B, C, T, V = x.size()

        # Static graph convolution
        # Reshape to (B*T, C, V)
        x_reshaped = x.permute(0, 2, 1, 3).contiguous().view(B * T, C, V)
        out_static = torch.matmul(x_reshaped, self.A_base)  # (B*T, C, V)
        out_static = out_static.view(B, T, C, V).permute(0, 2, 1, 3).contiguous()
        out_static = self.conv_out(out_static)

        # Dynamic channel-topology refinement
        phi = self.conv_phi(x)  # (B, C_mid, T, V)
        psi = self.conv_psi(x)  # (B, C_mid, T, V)

        # Pool over time: (B, C_mid, V)
        phi_mean = phi.mean(dim=2)
        psi_mean = psi.mean(dim=2)

        # Dynamic affinity matrix: (B, V, V)
        A_dyn = torch.bmm(phi_mean.permute(0, 2, 1), psi_mean) / math.sqrt(phi_mean.size(1))
        A_dyn = F.softmax(A_dyn, dim=-1)  # (B, V, V)

        # Apply dynamic affinity to transformed features
        x_dyn = self.conv_out(x)  # (B, C_out, T, V)
        x_dyn_flat = x_dyn.permute(0, 2, 1, 3).contiguous().view(B * T, self.out_channels, V)
        A_dyn_expanded = A_dyn.unsqueeze(1).expand(-1, T, -1, -1).contiguous().view(B * T, V, V)
        out_dyn = torch.matmul(x_dyn_flat, A_dyn_expanded).view(B, T, self.out_channels, V).permute(0, 2, 1, 3).contiguous()

        out = out_static + self.alpha * out_dyn
        out = self.bn(out)
        return self.relu(out)


class MultiScaleTemporalConv(nn.Module):
    """Multi-scale temporal convolution with varied dilation rates."""

    def __init__(self, in_channels: int, out_channels: int, kernel_size: int = 5, stride: int = 1):
        super().__init__()
        mid_channels = out_channels // 4

        # Branch 1: 1x1 conv
        self.branch1 = nn.Sequential(
            nn.Conv2d(in_channels, mid_channels, kernel_size=1),
            nn.BatchNorm2d(mid_channels),
            nn.ReLU(inplace=True),
        )

        # Branch 2: 3x1 conv (dilation 1)
        self.branch2 = nn.Sequential(
            nn.Conv2d(in_channels, mid_channels, kernel_size=(3, 1), padding=(1, 0), stride=(stride, 1)),
            nn.BatchNorm2d(mid_channels),
            nn.ReLU(inplace=True),
        )

        # Branch 3: 5x1 conv (dilation 1)
        self.branch3 = nn.Sequential(
            nn.Conv2d(in_channels, mid_channels, kernel_size=(5, 1), padding=(2, 0), stride=(stride, 1)),
            nn.BatchNorm2d(mid_channels),
            nn.ReLU(inplace=True),
        )

        # Branch 4: MaxPool + 1x1 conv
        self.branch4 = nn.Sequential(
            nn.MaxPool2d(kernel_size=(3, 1), padding=(1, 0), stride=(stride, 1)),
            nn.Conv2d(in_channels, mid_channels, kernel_size=1),
            nn.BatchNorm2d(mid_channels),
            nn.ReLU(inplace=True),
        )

        self.out_conv = nn.Sequential(
            nn.Conv2d(mid_channels * 4, out_channels, kernel_size=1),
            nn.BatchNorm2d(out_channels),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        b1 = self.branch1(x)
        b2 = self.branch2(x)
        b3 = self.branch3(x)
        b4 = self.branch4(x)
        out = torch.cat([b1, b2, b3, b4], dim=1)
        return self.out_conv(out)


class CTRGCBlock(nn.Module):
    """Complete Spatial-Temporal CTR-GCN Block."""

    def __init__(self, in_channels: int, out_channels: int, num_joints: int = 17, stride: int = 1):
        super().__init__()
        self.gcn = CTRGC(in_channels, out_channels, num_joints=num_joints)
        self.tcn = MultiScaleTemporalConv(out_channels, out_channels, stride=stride)
        
        if in_channels != out_channels or stride != 1:
            self.residual = nn.Sequential(
                nn.Conv2d(in_channels, out_channels, kernel_size=1, stride=(stride, 1)),
                nn.BatchNorm2d(out_channels),
            )
        else:
            self.residual = nn.Identity()

        self.relu = nn.ReLU(inplace=True)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        res = self.residual(x)
        x = self.gcn(x)
        x = self.tcn(x)
        return self.relu(x + res)


class CTRGCNClassifier(nn.Module):
    """Full CTR-GCN Classifier for Exam Behaviour Sequence Recognition.
    
    Accepts tensor of shape (Batch, Channels=3, Time=T, Joints=17).
    Channels: (X, Y, Confidence) or (X, Y, Z).
    Outputs class probabilities over exam behavior archetypes.
    """

    CLASS_NAMES = [
        "NORMAL_WRITING",
        "NEIGHBOUR_PEEKING",
        "TORSO_ROTATION_ANOMALY",
        "DESK_BREACH_REACH",
        "COMPOSITE_SUSPICIOUS",
    ]

    def __init__(self, in_channels: int = 3, num_classes: int = 5, num_joints: int = 17):
        super().__init__()
        self.data_bn = nn.BatchNorm2d(in_channels)

        # CTR-GCN layers
        self.l1 = CTRGCBlock(in_channels, 32, num_joints=num_joints)
        self.l2 = CTRGCBlock(32, 64, num_joints=num_joints)
        self.l3 = CTRGCBlock(64, 128, num_joints=num_joints)

        # Classification Head
        self.fc = nn.Linear(128, num_classes)

        self._initialize_weights()

    def _initialize_weights(self):
        for m in self.modules():
            if isinstance(m, nn.Conv2d):
                nn.init.kaiming_normal_(m.weight, mode='fan_out', nonlinearity='relu')
            elif isinstance(m, nn.BatchNorm2d):
                nn.init.constant_(m.weight, 1)
                nn.init.constant_(m.bias, 0)
            elif isinstance(m, nn.Linear):
                nn.init.normal_(m.bias, 0, 0.01)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Input x: (B, C, T, V)
        Output: Logits of shape (B, num_classes)
        """
        # Batch norm on input (treating T and V as spatial dims)
        B, C, T, V = x.size()
        x = self.data_bn(x)

        x = self.l1(x)
        x = self.l2(x)
        x = self.l3(x)

        # Global average pool over Time (dim 2) and Joints (dim 3)
        x_pool = x.mean(dim=[2, 3])  # (B, 128)
        logits = self.fc(x_pool)
        return logits
