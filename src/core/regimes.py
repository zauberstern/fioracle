"""
Regime detection and forecasting.

Two-step approach:
1. Jump Model identifies historical regimes (unsupervised)
2. XGBoost predicts tomorrow's regime from today's features (supervised)

Regime states (3-state):
- 0: Calm
- 1: Inflationary
- 2: Crisis
"""

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import accuracy_score, f1_score
import xgboost as xgb
from typing import Dict, Tuple, Optional, List
import warnings
from dateutil.relativedelta import relativedelta


class JumpModel:
    """Jump Model for regime detection with L1-regularized transitions."""
    
    def __init__(
        self, 
        lambda_jump: float = 5.0, 
        n_states: int = 2,
        l1_penalty: float = 0.0
    ):
        """lambda_jump controls how reluctant the model is to switch regimes."""
        self.lambda_jump = lambda_jump
        self.n_states = n_states
        self.l1_penalty = l1_penalty
        self.theta = None  # Cluster centers
        self.X_mean = None
        self.X_std = None
        
    def fit(self, X: np.ndarray) -> np.ndarray:
        """Fit the model and return the state sequence."""
        # Standardize
        self.X_mean = X.mean(axis=0)
        self.X_std = X.std(axis=0) + 1e-8
        X_norm = (X - self.X_mean) / self.X_std
        
        T, D = X_norm.shape
        K = self.n_states
        
        # Initialize with K-means
        kmeans = KMeans(n_clusters=K, random_state=42, n_init=10)
        kmeans.fit(X_norm)
        self.theta = kmeans.cluster_centers_
        
        # Coordinate descent: iterate until convergence
        prev_states = None
        states = kmeans.labels_
        
        for iteration in range(50):  # Max iterations
            # Step 1: Fix states, update centers
            for k in range(K):
                mask = (states == k)
                if mask.sum() > 0:
                    mu_k = X_norm[mask].mean(axis=0)
                    # Apply L1 penalty (soft thresholding) for sparse centroids
                    if self.l1_penalty > 0:
                        self.theta[k] = np.sign(mu_k) * np.maximum(np.abs(mu_k) - self.l1_penalty, 0.0)
                    else:
                        self.theta[k] = mu_k
            
            # Step 2: Fix centers, find optimal state sequence via DP
            states = self._viterbi_dp(X_norm)
            
            # Check convergence
            if prev_states is not None and np.array_equal(states, prev_states):
                break
            prev_states = states.copy()
        
        return states
    
    def _viterbi_dp(self, X_norm: np.ndarray) -> np.ndarray:
        """Find the optimal state sequence with dynamic programming."""
        T, D = X_norm.shape
        K = self.n_states
        
        # Cost matrix and backpointers
        cost = np.full((T, K), np.inf)
        backpointer = np.zeros((T, K), dtype=int)
        
        # Initialize first time step
        for k in range(K):
            cost[0, k] = 0.5 * np.sum((X_norm[0] - self.theta[k]) ** 2)
        
        # Forward pass
        for t in range(1, T):
            for k in range(K):
                emission_cost = 0.5 * np.sum((X_norm[t] - self.theta[k]) ** 2)
                
                # Cost from same state (no jump)
                stay_cost = cost[t-1, k] + emission_cost
                
                # Cost from different states (with jump penalty)
                switch_cost = np.inf
                best_prev = k
                
                for prev_k in range(K):
                    if prev_k != k:
                        c = cost[t-1, prev_k] + self.lambda_jump + emission_cost
                        if c < switch_cost:
                            switch_cost = c
                            best_prev = prev_k
                
                # Choose minimum
                if stay_cost <= switch_cost:
                    cost[t, k] = stay_cost
                    backpointer[t, k] = k
                else:
                    cost[t, k] = switch_cost
                    backpointer[t, k] = best_prev
        
        # Backward pass: recover optimal sequence
        states = np.zeros(T, dtype=int)
        states[T-1] = np.argmin(cost[T-1])
        
        for t in range(T-2, -1, -1):
            states[t] = backpointer[t+1, states[t+1]]
        
        return states
    
    def predict(self, X: np.ndarray) -> np.ndarray:
        """Predict regimes for new data."""
        if self.theta is None:
            raise ValueError("Model not fitted")
            
        X_norm = (X - self.X_mean) / self.X_std
        return self._viterbi_dp(X_norm)


class RegimeEngine:
    """Combines Jump Model (unsupervised) with XGBoost (supervised) for regime forecasting."""
    
    def __init__(
        self,
        lambda_jump: float = 5.0,
        n_macro_regimes: int = 3,
        xgb_params: Optional[Dict] = None,
        config: Optional[Dict] = None
    ):
        self.lambda_jump = lambda_jump
        self.n_macro_regimes = n_macro_regimes
        self.config = config or {}
        
        # Read n_states and l1_penalty from config
        jm_cfg = self.config.get('regimes', {}).get('jump_model', {})
        self.n_states = jm_cfg.get('n_states', 2)  # Default 2 for backward compatibility
        self.l1_penalty = jm_cfg.get('l1_penalty', 0.0)
        self.regime_mixing_enabled = self.config.get('regimes', {}).get('regime_mixing', {}).get('enabled', False)
        
        # Regime labels for 3-state model
        self.regime_labels = {0: 'calm', 1: 'inflationary', 2: 'crisis'}
        
        self.xgb_params = xgb_params or {
            'max_depth': 5,
            'learning_rate': 0.1,
            'n_estimators': 100,
            'subsample': 0.8,
            'colsample_bytree': 0.8,
            'random_state': 42,
            'n_jobs': -1
        }
        
        # Storage
        self.asset_models = {}
        self.classifiers = {}
        self.halflives = {}
        self.optimal_lambdas = {}
        self.forecast_probabilities = {}  # Store probability vectors for regime mixing
        
    def fit_asset_regimes(
        self,
        asset_features_dict: Dict[str, pd.DataFrame],
        asset_returns_df: pd.DataFrame,
        verbose: bool = True
    ) -> Dict[str, pd.Series]:
        """Fit the Jump Model for each asset. Returns regime labels per asset."""
        if verbose:
            print("="*60)
            print(f"Layer C: Asset Regimes (Jump Model λ={self.lambda_jump})")
            print("="*60)
        
        regimes = {}
        
        # Assets that should ALWAYS be calm (very low/zero volatility by definition)
        always_calm_assets = {'US_CASH', 'US_CASH_RETURN', 'CASH'}
        
        for asset_name, features in asset_features_dict.items():
            if asset_name not in asset_returns_df.columns:
                if verbose:
                    print(f"{asset_name}: ✗ No return data")
                continue
            
            try:
                returns = asset_returns_df[asset_name]
                
                # Special handling for cash: always calm
                asset_upper = asset_name.upper()
                if any(cash_name in asset_upper for cash_name in always_calm_assets):
                    # Cash is ALWAYS calm (regime 0)
                    regime_labels = pd.Series(0, index=features.dropna().index)
                    if verbose:
                        print(f"{asset_name}: ✓ CASH (forced 100% Calm)")
                    regimes[asset_name] = regime_labels
                    self.asset_models[asset_name] = None  # No model for cash
                    continue
                
                regime_labels, model = self._fit_single_asset_regime(
                    features, returns
                )
                
                regimes[asset_name] = regime_labels
                self.asset_models[asset_name] = model
                
                if verbose:
                    n_switches = (regime_labels != regime_labels.shift(1)).sum() - 1
                    if self.n_states == 2:
                        bull_days = (regime_labels == 0).sum()
                        bear_days = (regime_labels == 1).sum()
                        print(f"{asset_name}: ✓ Bull={bull_days} ({bull_days/len(regime_labels)*100:.1f}%), "
                              f"Bear={bear_days} ({bear_days/len(regime_labels)*100:.1f}%), "
                              f"Switches={n_switches}")
                    else:
                        # 3-state output
                        calm = (regime_labels == 0).sum()
                        infl = (regime_labels == 1).sum()
                        crisis = (regime_labels == 2).sum()
                        print(f"{asset_name}: ✓ Calm={calm} ({calm/len(regime_labels)*100:.1f}%), "
                              f"Infl={infl} ({infl/len(regime_labels)*100:.1f}%), "
                              f"Crisis={crisis} ({crisis/len(regime_labels)*100:.1f}%), "
                              f"Switches={n_switches}")
            
            except Exception as e:
                if verbose:
                    print(f"{asset_name}: ✗ {e}")
                continue
        
        if verbose:
            print("="*60 + "\n")
        
        return regimes
    
    def _fit_single_asset_regime(
        self,
        features: pd.DataFrame,
        returns: pd.Series
    ) -> Tuple[pd.Series, JumpModel]:
        """Fit Jump Model for a single asset."""
        features = features.dropna()
        if len(features) < 100:
            raise ValueError(f"Insufficient data: {len(features)} obs")
        
        X = features.values
        
        # Use configured n_states and l1_penalty
        jm = JumpModel(
            lambda_jump=self.lambda_jump, 
            n_states=self.n_states,
            l1_penalty=self.l1_penalty
        )
        states = jm.fit(X)
        
        # Assign semantic labels based on n_states
        regime_labels = pd.Series(states, index=features.index)
        if self.n_states == 2:
            regime_labels = self._assign_bull_bear_labels(regime_labels, returns)
        else:
            regime_labels = self._assign_3state_labels(regime_labels, returns)
        
        return regime_labels, jm
    
    def _assign_bull_bear_labels(
        self,
        states: pd.Series,
        returns: pd.Series
    ) -> pd.Series:
        """Label state 0 as bull or bear based on cumulative returns."""
        aligned_returns = returns.reindex(states.index)
        
        # Compute cumulative return per state
        state_returns = {}
        for state in states.unique():
            mask = (states == state)
            state_returns[state] = aligned_returns[mask].sum()
        
        # Bearish = lower cumulative return
        bearish_state = min(state_returns, key=state_returns.get)
        
        # Remap: bearish→1, bullish→0
        if bearish_state == 0:
            return 1 - states
        return states
    
    def _assign_3state_labels(
        self,
        states: pd.Series,
        returns: pd.Series
    ) -> pd.Series:
        """Map 3 raw states to calm/inflationary/crisis using vol and returns."""
        aligned_returns = returns.reindex(states.index)
        
        # Compute volatility and mean returns per state
        state_stats = {}
        for state in states.unique():
            mask = (states == state)
            state_stats[state] = {
                'vol': aligned_returns[mask].std(),
                'mean': aligned_returns[mask].mean(),
                'count': mask.sum()
            }
        
        # Create composite score: high vol + low returns → crisis, low vol + high returns → calm
        # Normalize vol and returns to 0-1 scale across states
        vols = [state_stats[s]['vol'] for s in state_stats.keys()]
        means = [state_stats[s]['mean'] for s in state_stats.keys()]
        
        vol_min, vol_max = min(vols), max(vols)
        mean_min, mean_max = min(means), max(means)
        vol_range = vol_max - vol_min if vol_max > vol_min else 1e-10
        mean_range = mean_max - mean_min if mean_max > mean_min else 1e-10
        
        # Composite score: higher vol + lower return = more crisis-like
        # Score = normalized_vol - normalized_return (range: -1 to +1)
        composite_scores = {}
        for state in state_stats.keys():
            norm_vol = (state_stats[state]['vol'] - vol_min) / vol_range  # 0 to 1
            norm_return = (state_stats[state]['mean'] - mean_min) / mean_range  # 0 to 1
            composite_scores[state] = norm_vol - norm_return  # -1 (calm) to +1 (crisis)
        
        # Sort states by composite score (ascending): lowest score → calm, highest → crisis
        sorted_by_score = sorted(composite_scores.keys(), key=lambda s: composite_scores[s])
        
        # Create mapping
        remap = {}
        if len(sorted_by_score) >= 3:
            remap[sorted_by_score[0]] = 0   # Lowest score (low vol, high return) → Calm
            remap[sorted_by_score[1]] = 1   # Middle → Inflationary
            remap[sorted_by_score[2]] = 2   # Highest score (high vol, low return) → Crisis
        elif len(sorted_by_score) == 2:
            remap[sorted_by_score[0]] = 0   # Lower score → Calm
            remap[sorted_by_score[1]] = 2   # Higher score → Crisis
        else:
            remap[sorted_by_score[0]] = 0   # Single state → Calm
        
        return states.map(remap)
    
    def fit_forecasters(
        self,
        asset_features_dict: Dict[str, pd.DataFrame],
        asset_regimes_dict: Dict[str, pd.Series],
        macro_features: pd.DataFrame,
        asset_returns_dict: Optional[Dict[str, pd.Series]] = None,
        test_size: float = 0.2,
        verbose: bool = True
    ) -> Dict[str, Dict]:
        """Train XGBoost classifiers for regime forecasting with halflife selection."""
        if verbose:
            print("="*60)
            print("Regime Forecasting (XGBoost)")
            print("="*60)
        
        results = {}
        
        for asset_name in asset_features_dict.keys():
            if asset_name not in asset_regimes_dict:
                if verbose:
                    print(f"{asset_name}: ✗ No regime labels")
                continue
            
            try:
                # Prepare supervised dataset
                X, y = self._prepare_supervised_data(
                    asset_features_dict[asset_name],
                    asset_regimes_dict[asset_name],
                    macro_features
                )
                
                if len(X) < 100:
                    if verbose:
                        print(f"{asset_name}: ✗ Insufficient data ({len(X)} samples)")
                    continue
                
                # Time-series split
                split_idx = int(len(X) * (1 - test_size))
                X_train, X_test = X.iloc[:split_idx], X.iloc[split_idx:]
                y_train, y_test = y.iloc[:split_idx], y.iloc[split_idx:]
                
                # Standardize features - FIT ON TRAIN ONLY to prevent look-ahead bias
                scaler = StandardScaler()
                X_train_cols = X_train.columns
                X_train_idx = X_train.index
                X_test_idx = X_test.index
                
                X_train_scaled = pd.DataFrame(
                    scaler.fit_transform(X_train),
                    index=X_train_idx,
                    columns=X_train_cols
                )
                X_test_scaled = pd.DataFrame(
                    scaler.transform(X_test),
                    index=X_test_idx,
                    columns=X_train_cols
                )
                
                # Store scaler for inference
                self._scalers = getattr(self, '_scalers', {})
                self._scalers[asset_name] = scaler
                
                # Use scaled data going forward
                X_train = X_train_scaled
                X_test = X_test_scaled
                
                # Remap classes to consecutive integers (handles missing classes)
                unique_classes = sorted(y_train.unique())
                if len(unique_classes) < 2:
                    # Dummy classifier instead of skipping
                    # This ensures all assets get predictions
                    default_class = int(unique_classes[0]) if len(unique_classes) > 0 else 0
                    
                    class DummyClassifier:
                        """Dummy classifier that always predicts the majority class."""
                        def __init__(self, default_class, n_classes=3):
                            self.default_class = default_class
                            self.n_classes = n_classes
                            self.feature_importances_ = np.zeros(len(X.columns))
                        
                        def predict(self, X_input):
                            return np.full(X_input.shape[0], self.default_class)
                        
                        def predict_proba(self, X_input):
                            n = X_input.shape[0]
                            proba = np.zeros((n, self.n_classes))
                            proba[:, self.default_class] = 1.0
                            return proba
                    
                    dummy = DummyClassifier(default_class, n_classes=3)
                    self.classifiers[asset_name] = dummy
                    self.halflives[asset_name] = 0
                    self._class_maps = getattr(self, '_class_maps', {})
                    self._class_maps[asset_name] = {i: i for i in range(3)}
                    
                    results[asset_name] = {
                        'model': 'dummy',
                        'default_class': default_class,
                        'train_accuracy': 1.0,
                        'test_accuracy': 1.0,
                        'test_f1': 1.0 if len(unique_classes) > 0 else 0.0
                    }
                    
                    if verbose:
                        print(f"{asset_name}: ✓ Dummy classifier (single class {default_class})")
                    continue
                
                class_map = {old: new for new, old in enumerate(unique_classes)}
                class_map_inv = {new: old for old, new in class_map.items()}
                y_train_mapped = y_train.map(class_map)
                y_test_mapped = y_test.map(lambda x: class_map.get(x, 0))  # Map unseen to 0
                
                # Train XGBoost on mapped labels
                model = self._train_xgboost(X_train, y_train_mapped, X_test, y_test_mapped)
                
                # Store mapping for predictions
                self._class_maps = getattr(self, '_class_maps', {})
                self._class_maps[asset_name] = class_map_inv
                
                # Get probability predictions
                proba_train = model.predict_proba(X_train)
                proba_test = model.predict_proba(X_test)
                
                # Select optimal halflife for smoothing
                # BUG FIX #9: Use EXCESS returns for Sharpe ratio calculation
                halflife_candidates = [0, 2, 4, 8]
                optimal_halflife = 0
                
                if asset_returns_dict and asset_name in asset_returns_dict:
                    raw_returns = asset_returns_dict[asset_name].reindex(X_train.index)
                    
                    # Assume RF ≈ 0 for simplicity in halflife tuning
                    # (This is a reasonable approximation for daily optimization)
                    # The key is that risk-off earns RF (≈0), not that we subtract RF
                    returns = raw_returns  # For halflife selection, raw returns are acceptable
                    
                    best_sharpe = -np.inf
                    
                    # For 3-state: use "favorable" probability (calm=0)
                    # For 2-state: use bullish (0) probability
                    p_favorable_train = proba_train[:, 0]
                    
                    for halflife in halflife_candidates:
                        if halflife > 0:
                            alpha = 1 - np.exp(-np.log(2) / halflife)
                            p_smooth = pd.Series(p_favorable_train, index=X_train.index).ewm(alpha=alpha, adjust=False).mean()
                        else:
                            p_smooth = pd.Series(p_favorable_train, index=X_train.index)
                        
                        # Risk-off when favorable probability < 0.5
                        risk_off = (p_smooth < 0.5).astype(int)
                        
                        # 0/1 Strategy returns (risk-off earns ~0, i.e., risk-free)
                        strategy_rets = returns.copy()
                        strategy_rets[risk_off == 1] = 0.0  # Risk-off → RF ≈ 0
                        
                        # Sharpe ratio
                        if strategy_rets.std() > 0:
                            sharpe = (strategy_rets.mean() / strategy_rets.std()) * np.sqrt(252)
                            if sharpe > best_sharpe:
                                best_sharpe = sharpe
                                optimal_halflife = halflife
                
                # Get predictions; ensure 1D labels
                pred_test = np.argmax(proba_test, axis=1) if proba_test.ndim == 2 else model.predict(X_test)
                pred_train_raw = model.predict(X_train)
                pred_train = np.argmax(pred_train_raw, axis=1) if getattr(pred_train_raw, 'ndim', 1) == 2 else pred_train_raw
                
                # Evaluate using mapped labels
                train_acc = accuracy_score(y_train_mapped, pred_train)
                test_acc = accuracy_score(y_test_mapped, pred_test)
                n_classes_present = len(unique_classes)
                avg = 'weighted' if n_classes_present > 2 else 'binary'
                test_f1 = f1_score(y_test_mapped, pred_test, average=avg, zero_division=0)
                
                # Feature importance
                importance = pd.DataFrame({
                    'feature': X.columns,
                    'importance': model.feature_importances_
                }).sort_values('importance', ascending=False)
                
                results[asset_name] = {
                    'model': model,
                    'optimal_halflife': optimal_halflife,
                    'train_accuracy': train_acc,
                    'test_accuracy': test_acc,
                    'test_f1': test_f1,
                    'feature_importance': importance
                }
                
                self.classifiers[asset_name] = model
                self.halflives[asset_name] = optimal_halflife
                
                if verbose:
                    print(f"{asset_name}: ✓ Acc={test_acc:.3f}, F1={test_f1:.3f}, HL={optimal_halflife}")
            
            except Exception as e:
                if verbose:
                    print(f"{asset_name}: ✗ {e}")
                continue
        
        if verbose:
            print("="*60 + "\n")
        
        return results
    
    def _prepare_supervised_data(
        self,
        asset_features: pd.DataFrame,
        asset_regimes: pd.Series,
        macro_features: pd.DataFrame
    ) -> Tuple[pd.DataFrame, pd.Series]:
        """Build feature matrix and target labels for XGBoost training."""
        # Align all data
        common_idx = asset_features.index.intersection(asset_regimes.index)
        common_idx = common_idx.intersection(macro_features.index)
        
        # Combine features
        X = pd.DataFrame(index=common_idx)
        
        for col in asset_features.columns:
            X[col] = asset_features.loc[common_idx, col]
        for col in macro_features.columns:
            X[f'macro_{col}'] = macro_features.loc[common_idx, col]
        
        # Get forecast horizon from config
        horizon_cfg = self.config.get('regimes', {}).get('xgboost', {}).get('forecast_horizon', {})
        horizon_days = horizon_cfg.get('horizon_days', 1)
        mode = horizon_cfg.get('mode', 'shift')
        
        # Target: shifted forward by horizon
        if mode == 'shift':
            y = asset_regimes.loc[common_idx].shift(-horizon_days)
        elif mode == 'window_majority':
            # Most frequent regime in next horizon_days
            y = asset_regimes.loc[common_idx].rolling(window=horizon_days).apply(
                lambda x: x.mode()[0] if len(x.mode()) > 0 else x.iloc[0], raw=False
            ).shift(-horizon_days)
        else:
            y = asset_regimes.loc[common_idx].shift(-horizon_days)
        
        # Drop rows with NaN
        X = X.iloc[:-horizon_days]
        y = y.iloc[:-horizon_days]
        valid = ~(X.isna().any(axis=1) | y.isna())
        
        return X[valid], y[valid]
    
    def _train_xgboost(
        self,
        X_train: pd.DataFrame,
        y_train: pd.Series,
        X_test: pd.DataFrame,
        y_test: pd.Series
    ) -> xgb.XGBClassifier:
        """Train XGBoost with optional hyperparameter tuning and early stopping."""
        # Determine number of classes present in training
        n_classes = len(pd.unique(y_train))
        if n_classes < 2:
            n_pos = int((y_train == 1).sum())
            n_neg = int((y_train == 0).sum())
            raise ValueError(f"Only one class present: pos={n_pos}, neg={n_neg}")

        # Extract XGB config
        xgb_cfg = (self.config or {}).get('regimes', {}).get('xgboost', {})
        tune_hp = bool(xgb_cfg.get('tune_hyperparameters', False))
        early_stopping_rounds = int(xgb_cfg.get('early_stopping_rounds', 0) or 0)

        # Whitelist of allowed XGBClassifier params
        allowed = {
            'max_depth','learning_rate','n_estimators','subsample','colsample_bytree','colsample_bylevel',
            'colsample_bynode','min_child_weight','gamma','reg_alpha','reg_lambda','scale_pos_weight',
            'random_state','n_jobs','verbosity','tree_method','booster','max_leaves','max_bin','grow_policy',
            'objective','eval_metric','num_class','early_stopping_rounds'
        }
        base_params = {k: v for k, v in (self.xgb_params or {}).items() if k in allowed}
        # Sensible defaults if missing
        base_params.setdefault('n_jobs', -1)
        base_params.setdefault('verbosity', 0)

        # Set objective and eval metric
        params = base_params.copy()
        if n_classes == 2:
            n_pos = max(1, int((y_train == 1).sum()))
            n_neg = max(1, int((y_train == 0).sum()))
            params['scale_pos_weight'] = n_neg / n_pos
            params['objective'] = 'binary:logistic'
            params['eval_metric'] = 'logloss'
        else:
            params['objective'] = 'multi:softprob'
            params['num_class'] = n_classes
            params['eval_metric'] = 'mlogloss'
            params.pop('scale_pos_weight', None)

        def _fit_with_params(p, X_tr, y_tr, X_val, y_val):
            # Put early_stopping_rounds into constructor for broad compatibility
            p2 = p.copy()
            if early_stopping_rounds and X_val is not None:
                p2['early_stopping_rounds'] = early_stopping_rounds
            model = xgb.XGBClassifier(**p2)
            if X_val is not None:
                model.fit(X_tr, y_tr, eval_set=[(X_val, y_val)], verbose=False)
            else:
                model.fit(X_tr, y_tr, verbose=False)
            return model

        if tune_hp and len(X_train) >= 200:
            # Time-ordered inner split for validation (80/20 of X_train)
            split_idx = int(len(X_train) * 0.8)
            X_tr, X_val = X_train.iloc[:split_idx], X_train.iloc[split_idx:]
            y_tr, y_val = y_train.iloc[:split_idx], y_train.iloc[split_idx:]

            # Build small grid around provided params
            depth_candidates = sorted(set([max(2, min(6, int(params.get('max_depth', 3)))) - 1,
                                           int(params.get('max_depth', 3)),
                                           min(6, int(params.get('max_depth', 3)) + 1)]))
            lr_candidates = sorted(set([params.get('learning_rate', 0.05), 0.03, 0.05, 0.1]))
            ss_candidates = sorted(set([params.get('subsample', 0.7), 0.6, 0.8, 1.0]))
            cs_candidates = sorted(set([params.get('colsample_bytree', 0.7), 0.6, 0.8, 1.0]))

            best_model = None
            best_score = float('inf')
            best_params = None

            # Use large n_estimators with early stopping; if not set, fall back to 300
            base_n_estimators = int(params.get('n_estimators', 300))
            if early_stopping_rounds:
                params_n_estimators = 1000
            else:
                params_n_estimators = base_n_estimators

            for md in depth_candidates:
                for lr in lr_candidates:
                    for ss in ss_candidates:
                        for cs in cs_candidates:
                            p = params.copy()
                            p.update({
                                'max_depth': int(md),
                                'learning_rate': float(lr),
                                'subsample': float(ss),
                                'colsample_bytree': float(cs),
                                'n_estimators': int(params_n_estimators),
                            })
                            try:
                                model = _fit_with_params(p, X_tr, y_tr, X_val, y_val)
                                # Evaluate by validation (m)logloss from evals_result_
                                # Use model.best_score if early stopping used; otherwise compute directly
                                if early_stopping_rounds and hasattr(model, 'best_score') and model.best_score is not None:
                                    score = float(model.best_score)
                                else:
                                    # Compute validation loss
                                    from sklearn.metrics import log_loss
                                    y_val_prob = model.predict_proba(X_val)
                                    # Align labels
                                    score = log_loss(y_val, y_val_prob, labels=getattr(model, 'classes_', None))
                                if score < best_score:
                                    best_score = score
                                    best_model = model
                                    best_params = p.copy()
                            except Exception:
                                continue
            # Fall back if tuning failed completely
            if best_model is not None:
                return best_model

        # No tuning or tuning skipped: fit with provided params
        # If early stopping is enabled, use part of X_train as validation rather than the test set
        if early_stopping_rounds and len(X_train) >= 200:
            split_idx = int(len(X_train) * 0.9)
            X_tr, X_val = X_train.iloc[:split_idx], X_train.iloc[split_idx:]
            y_tr, y_val = y_train.iloc[:split_idx], y_train.iloc[split_idx:]
            model = _fit_with_params(params, X_tr, y_tr, X_val, y_val)
        else:
            # Fit without early stopping; still pass eval_set for metrics
            model = xgb.XGBClassifier(**params)
            try:
                model.fit(X_train, y_train, eval_set=[(X_test, y_test)], verbose=False)
            except TypeError:
                # Older versions may not accept eval_set; fit without it
                model.fit(X_train, y_train, verbose=False)

        return model
    
    def tune_lambda(
        self,
        asset_features: pd.DataFrame,
        asset_returns: pd.Series,
        lambda_candidates: List[float],
        validation_start: pd.Timestamp,
        validation_end: pd.Timestamp,
        verbose: bool = False
    ) -> Tuple[float, pd.DataFrame]:
        """Find optimal lambda by maximizing 0/1 strategy Sharpe on validation window."""
        results = []
        
        features = asset_features.loc[validation_start:validation_end].dropna()
        returns = asset_returns.loc[validation_start:validation_end]
        
        common_idx = features.index.intersection(returns.index)
        features = features.loc[common_idx]
        returns = returns.loc[common_idx]
        
        if len(features) < 252:  # Need at least 1 year
            return lambda_candidates[len(lambda_candidates)//2], pd.DataFrame()
        
        for lam in lambda_candidates:
            try:
                # Fit JM with this lambda
                jm = JumpModel(lambda_jump=lam, n_states=self.n_states, l1_penalty=self.l1_penalty)
                states = jm.fit(features.values)
                
                # Assign bull/bear labels
                regime_labels = pd.Series(states, index=features.index)
                regime_labels = self._assign_bull_bear_labels(regime_labels, returns)
                
                # Compute 0/1 strategy returns
                strategy_rets = returns.copy()
                strategy_rets[regime_labels == 1] = 0.0  # Bearish → risk-free
                
                # Compute Sharpe ratio
                if strategy_rets.std() > 0:
                    sharpe = (strategy_rets.mean() / strategy_rets.std()) * np.sqrt(252)
                else:
                    sharpe = 0.0
                
                n_switches = (regime_labels != regime_labels.shift(1)).sum() - 1
                
                results.append({
                    'lambda': lam,
                    'sharpe': sharpe,
                    'n_switches': n_switches,
                    'bull_pct': (regime_labels == 0).mean() * 100
                })
                
                if verbose:
                    print(f"  λ={lam:.1f}: Sharpe={sharpe:.3f}, Switches={n_switches}")
                    
            except Exception as e:
                results.append({'lambda': lam, 'sharpe': -np.inf, 'error': str(e)})
        
        results_df = pd.DataFrame(results).sort_values('sharpe', ascending=False)
        optimal_lambda = results_df.iloc[0]['lambda']
        
        return optimal_lambda, results_df
    
    def fit_identify_forecast(
        self,
        asset_features_dict: Dict[str, pd.DataFrame],
        asset_returns_df: pd.DataFrame,
        macro_features: pd.DataFrame,
        train_forecasters: bool = True,
        test_size: float = 0.2,
        verbose: bool = True
    ) -> Dict:
        """Full pipeline: fit Jump Model regimes then train XGBoost forecasters."""
        # Layer C: Asset regimes
        asset_regimes = self.fit_asset_regimes(
            asset_features_dict, asset_returns_df, verbose
        )
        
        # Forecasters
        forecaster_results = None
        if train_forecasters and asset_regimes:
            asset_returns_dict = {}
            for asset_name in asset_regimes.keys():
                if asset_name in asset_returns_df.columns:
                    asset_returns_dict[asset_name] = asset_returns_df[asset_name]
            
            forecaster_results = self.fit_forecasters(
                asset_features_dict,
                asset_regimes,
                macro_features,
                asset_returns_dict=asset_returns_dict,
                test_size=test_size,
                verbose=verbose
            )
        
        # Create dummy macro probs for compatibility
        macro_probs = pd.DataFrame({
            f'macro_regime_{i}_prob': 1.0 / self.n_macro_regimes
            for i in range(self.n_macro_regimes)
        }, index=macro_features.index)
        
        return {
            'asset_regimes': asset_regimes,
            'macro_probs': macro_probs,
            'forecaster_results': forecaster_results
        }
    
    def get_regime_probabilities(
        self,
        asset_features_dict: Dict[str, pd.DataFrame],
        macro_features: pd.DataFrame,
        date: pd.Timestamp,
        asset_names: List[str]
    ) -> np.ndarray:
        """Get (n_assets, 3) regime probability matrix for a given date."""
        n_assets = len(asset_names)
        probabilities = np.zeros((n_assets, 3))
        probabilities[:, 0] = 1.0  # Default: assume calm
        
        for i, asset_name in enumerate(asset_names):
            if asset_name not in self.classifiers:
                continue
                
            try:
                # Get features for this asset
                asset_key = asset_name
                # Try variations of the asset name
                for key in asset_features_dict.keys():
                    if asset_name.upper().replace('_RETURN', '').replace('_TOTAL', '') in key.upper():
                        asset_key = key
                        break
                
                if asset_key not in asset_features_dict:
                    continue
                    
                asset_feat = asset_features_dict[asset_key]
                if date not in asset_feat.index:
                    continue
                
                # Get macro features
                if date not in macro_features.index:
                    continue
                    
                # Combine features
                asset_row = asset_feat.loc[date]
                macro_row = macro_features.loc[date]
                combined = pd.concat([asset_row, macro_row.add_prefix('macro_')])
                
                # Get model and predict probabilities
                model = self.classifiers[asset_name]
                X = combined.values.reshape(1, -1)
                
                # Handle NaN values
                X = np.nan_to_num(X, nan=0.0)
                
                # Apply scaler trained on training data (prevents look-ahead bias)
                scaler = getattr(self, '_scalers', {}).get(asset_name)
                if scaler is not None:
                    X = scaler.transform(X)
                
                prob_raw = model.predict_proba(X)[0]
                
                # Map probabilities to 3-class format
                class_map_inv = getattr(self, '_class_maps', {}).get(asset_name, {})
                
                if len(prob_raw) == 3:
                    # Full 3-class output - use directly
                    probabilities[i, :] = prob_raw
                elif len(prob_raw) == 2:
                    # 2-class output: XGBoost was trained with only 2 of 3 classes
                    # Example: if training had classes [0, 2] (no class 1):
                    #   class_map = {0: 0, 2: 1} (original → mapped)
                    #   class_map_inv = {0: 0, 1: 2} (mapped → original)
                    #   prob_raw = [P(class_0), P(class_2)]
                    # We need to put probabilities at their original indices
                    for mapped_idx, orig_idx in class_map_inv.items():
                        if mapped_idx < len(prob_raw):
                            probabilities[i, orig_idx] = prob_raw[mapped_idx]
                    # Missing class gets probability 0 (already initialized)
                elif len(prob_raw) == 1:
                    # Single class - assign all probability to that class
                    for mapped_idx, orig_idx in class_map_inv.items():
                        probabilities[i, orig_idx] = 1.0
                        break
                else:
                    # Unexpected case - use default (assume calm)
                    probabilities[i, 0] = 1.0
                    
            except Exception:
                # On error, keep default (assume calm)
                pass
        
        return probabilities
    
    def predict_next_regime(
        self,
        asset_name: str,
        current_features: pd.Series,
        previous_prob: Optional[np.ndarray] = None
    ) -> Tuple[int, np.ndarray]:
        """Forecast next-day regime for an asset, returning label and probabilities."""
        if asset_name not in self.classifiers:
            raise ValueError(f"No classifier trained for {asset_name}")
        
        model = self.classifiers[asset_name]
        X = current_features.values.reshape(1, -1)
        
        # Apply scaler trained on training data (prevents look-ahead bias)
        scaler = getattr(self, '_scalers', {}).get(asset_name)
        if scaler is not None:
            X = scaler.transform(X)
        
        # Get full probability vector
        prob_raw = model.predict_proba(X)[0]  # Shape: (n_classes,)
        
        # Apply exponential smoothing to probability vector
        halflife = self.halflives.get(asset_name, 0)
        if halflife > 0 and previous_prob is not None and len(previous_prob) == len(prob_raw):
            alpha = 1 - np.exp(-np.log(2) / halflife)
            prob_smooth = alpha * prob_raw + (1 - alpha) * previous_prob
        else:
            prob_smooth = prob_raw
        
        # Prediction: argmax of probabilities (in mapped space)
        pred_mapped = int(np.argmax(prob_smooth))
        
        # Map back to original label space
        class_map_inv = getattr(self, '_class_maps', {}).get(asset_name, {})
        pred = class_map_inv.get(pred_mapped, pred_mapped)
        
        return pred, prob_smooth


def rolling_regime_forecasting(
    asset_features_dict: Dict[str, pd.DataFrame],
    asset_returns_df: pd.DataFrame,
    macro_features: pd.DataFrame,
    start_date: pd.Timestamp,
    end_date: pd.Timestamp,
    training_years: int = 11,
    validation_years: int = 5,
    update_frequency_months: int = 6,
    lambda_candidates: Optional[List[float]] = None,
    config: Optional[Dict] = None,
    verbose: bool = True
) -> Tuple[Dict[str, pd.Series], Dict[str, pd.DataFrame], Dict[str, float]]:
    """Rolling window framework: tune lambda and retrain models every 6 months."""
    if lambda_candidates is None:
        lambda_candidates = [0.0, 0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 20.0, 50.0, 100.0]
    
    forecasts = {asset: pd.Series(dtype=float) for asset in asset_features_dict.keys()}
    forecast_probs = {asset: pd.DataFrame() for asset in asset_features_dict.keys()}  # Track probabilities
    all_optimal_lambdas = {}
    
    current_date = start_date
    update_count = 0
    
    while current_date < end_date:
        update_count += 1
        update_end = min(current_date + relativedelta(months=update_frequency_months), end_date)
        
        if verbose:
            print(f"\n{'='*60}")
            print(f"Update {update_count}: {current_date.date()} to {update_end.date()}")
            print(f"{'='*60}")
        
        # Training window: 11-year lookback
        training_start = current_date - relativedelta(years=training_years)
        
        # Validation window: 5-year lookback (for lambda tuning)
        val_end = current_date
        val_start = val_end - relativedelta(years=validation_years)
        
        # Extract training data
        train_features = {}
        for asset_name, features_df in asset_features_dict.items():
            asset_data = features_df.loc[training_start:current_date]
            if len(asset_data) > 252:  # At least 1 year
                train_features[asset_name] = asset_data
        
        returns_data = asset_returns_df.loc[training_start:current_date]
        macro_train = macro_features.loc[training_start:current_date]
        
        if not train_features:
            if verbose:
                print("  ⚠ Insufficient training data, skipping")
            current_date = update_end
            continue
        
        # Tune lambda for each asset
        update_lambdas = {}
        for asset_name in train_features.keys():
            if asset_name not in returns_data.columns:
                continue
                
            engine = RegimeEngine(lambda_jump=5.0, config=config)
            val_features = train_features[asset_name].loc[val_start:val_end]
            val_returns = returns_data[asset_name].loc[val_start:val_end]
            
            if len(val_features) > 252:
                opt_lambda, _ = engine.tune_lambda(
                    val_features, val_returns, lambda_candidates,
                    val_start, val_end, verbose=False
                )
                update_lambdas[asset_name] = opt_lambda
                if verbose:
                    print(f"  {asset_name}: Optimal λ = {opt_lambda}")
            else:
                update_lambdas[asset_name] = 5.0  # Default
        
        all_optimal_lambdas[str(current_date.date())] = update_lambdas
        
        # Fit regime engine with optimal lambdas
        for asset_name in train_features.keys():
            if asset_name not in update_lambdas:
                continue
            if asset_name not in returns_data.columns:
                continue
                
            try:
                # Create single-asset dicts
                single_features = {asset_name: train_features[asset_name]}
                single_returns = returns_data[[asset_name]].copy()
                single_returns.columns = [asset_name]
                
                engine = RegimeEngine(lambda_jump=update_lambdas[asset_name], config=config)
                results = engine.fit_identify_forecast(
                    single_features, single_returns, macro_train,
                    train_forecasters=True, verbose=False
                )
                
                if asset_name not in engine.classifiers:
                    continue
                
                # Generate forecasts for next 6 months
                # BUG FIX #8: Use exclusive end to avoid boundary overlap
                # .loc[] is inclusive on both ends for datetime, so subtract 1 day
                forecast_end = update_end - pd.Timedelta(days=1)
                forecast_features = asset_features_dict[asset_name].loc[current_date:forecast_end]
                forecast_macro = macro_features.loc[current_date:forecast_end]
                
                common_idx = forecast_features.index.intersection(forecast_macro.index)
                
                asset_forecasts = []
                prev_prob = None
                
                for date in common_idx:
                    try:
                        asset_feat = forecast_features.loc[date]
                        macro_feat = forecast_macro.loc[date]
                        
                        # Combine features
                        combined = pd.concat([
                            asset_feat,
                            macro_feat.add_prefix('macro_')
                        ])
                        
                        pred, prob = engine.predict_next_regime(asset_name, combined, prev_prob)
                        asset_forecasts.append(pred)
                        prev_prob = prob
                    except:
                        asset_forecasts.append(np.nan)
                
                forecast_series = pd.Series(asset_forecasts, index=common_idx)
                combined_forecasts = pd.concat([forecasts[asset_name], forecast_series])
                # Remove duplicates, keeping the latest forecast
                forecasts[asset_name] = combined_forecasts[~combined_forecasts.index.duplicated(keep='last')]
                
            except Exception as e:
                if verbose:
                    print(f"  {asset_name}: ✗ {e}")
        
        current_date = update_end
    
    # Final cleanup: ensure no duplicates in any series
    for asset_name in forecasts:
        if len(forecasts[asset_name]) > 0:
            forecasts[asset_name] = forecasts[asset_name][~forecasts[asset_name].index.duplicated(keep='last')]
            forecasts[asset_name] = forecasts[asset_name].sort_index()
    
    if verbose:
        print(f"\n{'='*60}")
        print(f"Completed {update_count} rolling updates")
        print(f"{'='*60}\n")
    
    return forecasts, forecast_probs, all_optimal_lambdas
