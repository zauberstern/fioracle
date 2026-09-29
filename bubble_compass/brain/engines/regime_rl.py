"""Layer 5: regime flag with heuristic fallback when SB3 is absent."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

try:
    from stable_baselines3 import PPO

    SB3_AVAILABLE = True
except ImportError:
    SB3_AVAILABLE = False
    logger.warning("stable-baselines3 not installed. RL regime flag will use heuristics.")


class RegimeState(Enum):
    NORMAL = 0
    BOOM = 1
    BUST = 2


@dataclass
class RegimeOutput:
    effective_date: pd.Timestamp
    regime_state: RegimeState
    regime_confidence: float
    boom_probability: float
    bust_probability: float


class RegimeRLEngine:
    def __init__(self, model_path: str | None = None, lookback_days: int = 5):
        self.model_path = model_path
        self.lookback_days = lookback_days
        self._model = None
        if SB3_AVAILABLE and model_path:
            self._model = PPO.load(model_path)

    def _build_features(
        self,
        dlinear_z: float,
        bsadf_stat: float,
        bsadf_cv: float,
        lppls_conf: float,
        sentiment_vel: float,
        returns: pd.Series,
    ) -> np.ndarray:
        bsadf_norm = (bsadf_stat - bsadf_cv) / max(abs(bsadf_cv), 1e-6)
        bsadf_norm = np.clip(bsadf_norm, -3, 3) / 3
        if len(returns) > 0:
            ret_mean = float(returns.mean() * 252)
            ret_std = float(returns.std() * np.sqrt(252))
            sharpe_approx = ret_mean / max(ret_std, 1e-6)
        else:
            ret_mean, ret_std, sharpe_approx = 0.0, 0.0, 0.0
        return np.array(
            [
                np.clip(dlinear_z / 3, -1, 1),
                np.clip(bsadf_norm, -1, 1),
                np.clip(lppls_conf, 0, 1),
                np.clip(sentiment_vel, -1, 1),
                np.clip(ret_mean, -1, 1),
                np.clip(ret_std / 0.5, 0, 1),
                np.clip(sharpe_approx / 3, -1, 1),
                0.0,
            ],
            dtype=np.float32,
        )

    def _heuristic_classify(self, features: np.ndarray) -> tuple[RegimeState, np.ndarray]:
        dlinear_z, bsadf_norm, lppls_conf, sent_vel, ret_mean, _ret_std, _sharpe, _ = features
        boom_score = (
            (bsadf_norm > 0.3) * 0.3
            + (lppls_conf > 0.5) * 0.3
            + (dlinear_z > 1.5) * 0.2
            + (sent_vel > 0.3) * 0.2
        )
        bust_score = (lppls_conf > 0.7) * 0.4 + (ret_mean < -0.2) * 0.3 + (dlinear_z < -1.5) * 0.3
        normal_score = max(1 - boom_score - bust_score, 0)
        total = max(boom_score + bust_score + normal_score, 1e-6)
        probs = np.array(
            [normal_score / total, boom_score / total, bust_score / total], dtype=float
        )
        probs = probs / probs.sum()
        state = RegimeState(int(np.argmax(probs)))
        return state, probs

    def predict(
        self,
        dlinear_z: float,
        bsadf_stat: float,
        bsadf_cv: float,
        lppls_conf: float,
        sentiment_vel: float,
        returns: pd.Series,
        as_of_date: pd.Timestamp,
    ) -> RegimeOutput:
        features = self._build_features(
            dlinear_z, bsadf_stat, bsadf_cv, lppls_conf, sentiment_vel, returns
        )
        if SB3_AVAILABLE and self._model is not None:
            action, _ = self._model.predict(features, deterministic=True)
            try:
                import torch

                obs_tensor = torch.from_numpy(features).unsqueeze(0)
                with torch.no_grad():
                    dist = self._model.policy.get_distribution(obs_tensor)
                    probs = dist.distribution.probs.numpy()[0]
            except Exception:
                probs = np.array([0.0, 0.0, 0.0])
                probs[int(action)] = 1.0
            state = RegimeState(int(action))
        else:
            state, probs = self._heuristic_classify(features)
        return RegimeOutput(
            effective_date=pd.Timestamp(as_of_date),
            regime_state=state,
            regime_confidence=float(probs[state.value]),
            boom_probability=float(probs[1]),
            bust_probability=float(probs[2]),
        )
