""" Loss functions on scattering moments. """
from typing import *
import numpy as np
import torch.nn as nn
import torch

from scatcov.layers.described_tensor import DescribedTensor


class MSELossScat(nn.Module):
    """ Implements l2 norm on the scattering coefficients or scattering covariances. """
    def __init__(self):
        super(MSELossScat, self).__init__()
        self.max_gap, self.mean_gap_pct, self.max_gap_pct = {}, {}, {}  # tracking

    def compute_gap(self, input: Optional[DescribedTensor], target: DescribedTensor, weights):
        if input is None:
            gap = torch.zeros_like(target.y) - target.y
        else:
            gap = input.y - target.y
        gap = gap[:, :, 0]

        gap = gap if weights is None else weights.unsqueeze(-1) * gap

        for c_type in np.unique(target.descri['c_type']):
            # discard very small coefficients
            mask_ctype = target.descri.where(c_type=c_type)
            mask_small = (torch.abs(target.y[:, :, 0].mean(0)) < 0.01).cpu().numpy()
            mask = mask_ctype & ~mask_small

            if mask.sum() == 0:
                self.max_gap[c_type] = self.mean_gap_pct[c_type] = self.max_gap_pct[c_type] = 0.0
                continue

            self.max_gap[c_type] = torch.max(torch.abs(gap[:, mask])).item()

            mean_gap_pct = torch.abs(gap[:, mask]).mean()
            mean_gap_pct /= torch.abs(target.select(mask)[:, :, 0]).mean()
            self.mean_gap_pct[c_type] = mean_gap_pct.item()

            max_gap_pct = torch.max(torch.abs(gap[:, mask] / target.select(mask)[:, :, 0]))
            self.max_gap_pct[c_type] = max_gap_pct.item()

        return gap

    def forward(self, input, target, weights_gap, weights_l2):
        """ Computes l2 norm. """
        gap = self.compute_gap(input, target, weights_gap)
        if weights_l2 is None:
            loss = torch.abs(gap).pow(2.0).mean()
        else:
            loss = (weights_l2 * torch.abs(gap).pow(2.0)).sum()
        return loss


class MSELossCov(nn.Module):
    def __init__(self):
        super(MSELossCov, self).__init__()
        self.max_gap = {}

    def forward(self, input, target):
        gap = torch.zeros_like(target.y)

        # exp
        gap[target.descri.where(q=1), :] = target.select(q=1) * (input.select(q=1) - target.select(q=1))

        # cov
        gap[target.descri.where(q=2), :] = input.select(q=2) - target.select(q=2)

        self.max_gap = {c_type: torch.max(torch.abs(gap[target.descri.where(c_type=c_type)])).item()
                        for c_type in np.unique(target.descri['c_type'])}

        return torch.abs(gap).pow(2.0).mean()
