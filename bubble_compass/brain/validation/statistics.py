"""Bailey-Lopez de Prado PSR / DSR / PBO helpers."""
from __future__ import annotations

import itertools

import numpy as np
from scipy.stats import norm


def probabilistic_sharpe_ratio(
    sr_hat: float,
    sr_star: float,
    n_obs: int,
    g3: float = 0.0,
    g4: float = 3.0,
) -> float:
    denom = np.sqrt(max(1 - g3 * sr_hat + ((g4 - 1) / 4) * sr_hat**2, 1e-12))
    return float(norm.cdf((sr_hat - sr_star) * np.sqrt(max(n_obs - 1, 1)) / denom))


def deflated_sharpe_ratio(
    sr_hat: float,
    sigma_sr: float,
    n_trials: int,
    n_obs: int,
    g3: float = 0.0,
    g4: float = 3.0,
) -> float:
    gamma = np.euler_gamma
    n_trials = max(int(n_trials), 1)
    sr_star = sigma_sr * (
        (1 - gamma) * norm.ppf(1 - 1 / n_trials) + gamma * norm.ppf(1 - 1 / (n_trials * np.e))
    )
    return probabilistic_sharpe_ratio(sr_hat, sr_star, n_obs, g3, g4)


def probability_of_backtest_overfitting(sharpes: np.ndarray, n_slices: int = 10) -> float:
    """CSCV PBO using even split of contiguous slices."""
    s = np.asarray(sharpes, dtype=float)
    if s.size < n_slices:
        n_slices = max(2, s.size - s.size % 2)
    if n_slices < 2:
        return 1.0
    chunks = np.array_split(s, n_slices)
    half = n_slices // 2
    overfit = 0
    total = 0
    for combo in itertools.combinations(range(n_slices), half):
        is_idx = set(combo)
        oos_idx = [i for i in range(n_slices) if i not in is_idx]
        is_mean = [float(np.nanmean(chunks[i])) for i in combo]
        champ = list(combo)[int(np.nanargmax(is_mean))]
        oos_vals = [float(np.nanmean(chunks[i])) for i in oos_idx]
        champ_oos = float(np.nanmean(chunks[champ]))
        overfit += int(champ_oos < np.median(oos_vals))
        total += 1
    return overfit / max(total, 1)
