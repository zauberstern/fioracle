"""
Regime identification and forecasting engine.

Hybrid Regime Identification-Forecasting Framework (JM-XGB):

Step I: Jump Model (JM) for unsupervised regime identification
  Solves: min_{Θ,S} Σ_{t=0}^{T-1} l(x_t, θ_{s_t}) + λ Σ_{t=1}^{T-1} 1_{s_{t-1} ≠ s_t}
  where l(x,θ) = (1/2) ||x - θ||_2^2
  
Step II: XGBoost for supervised regime forecasting
  Predicts s_{t+1} using expanded features x_t
  Post-processing: exponential smoothing to restore persistence
  
Rolling Framework:
  - 11-year lookback training window
  - Biannual (6-month) model updates
  - 5-year validation window for lambda tuning
  - 0/1 strategy Sharpe ratio criterion for lambda selection
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
    """
    Statistical Jump Model for regime identification.
    
    Solves optimization problem (Equation 1):
    min_{Θ,S} Σ_{t=0}^{T-1} l(x_t, θ_{s_t}) + λ Σ_{t=1}^{T-1} 1_{s_{t-1} ≠ s_t}
    
    where:
    - l(x,θ) = (1/2) ||x - θ||_2^2 (scaled squared L2 distance)
    - λ is the jump penalty controlling regime persistence
    - S is the state sequence (0=Bullish, 1=Bearish)
    - Θ is the set of cluster centers
    """
    
    def __init__(self, lambda_jump: float = 5.0, n_states: int = 2):
        self.lambda_jump = lambda_jump
        self.n_states = n_states
        self.theta = None  # Cluster centers
        self.X_mean = None
        self.X_std = None
        
    def fit(self, X: np.ndarray) -> np.ndarray:
        """
        Fit Jump Model using coordinate descent.
        
        Args:
            X: Feature matrix (T x D)
            
        Returns:
            Optimal state sequence (T,)
        """
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
                    self.theta[k] = X_norm[mask].mean(axis=0)
            
            # Step 2: Fix centers, find optimal state sequence via DP
            states = self._viterbi_dp(X_norm)
            
            # Check convergence
            if prev_states is not None and np.array_equal(states, prev_states):
                break
            prev_states = states.copy()
        
        return states
    
    def _viterbi_dp(self, X_norm: np.ndarray) -> np.ndarray:
        """
        Dynamic programming (Viterbi-like) to find optimal state sequence.
        
        Cost[t][k] = minimum cost up to time t ending in state k
        """
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
        """Predict states for new data using fitted centers."""
        if self.theta is None:
            raise ValueError("Model not fitted")
            
        X_norm = (X - self.X_mean) / self.X_std
        return self._viterbi_dp(X_norm)


class RegimeEngine:
    """
    Complete regime identification and forecasting system.
    
    Implements:
    - Jump Model for asset-specific regime identification
    - XGBoost for regime forecasting
    - Lambda tuning via 0/1 strategy Sharpe ratio
    - Output probability smoothing with halflife selection
    """
    
    def __init__(
        self,
        lambda_jump: float = 5.0,
        n_macro_regimes: int = 3,
        xgb_params: Optional[Dict] = None
    ):
        self.lambda_jump = lambda_jump
        self.n_macro_regimes = n_macro_regimes
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
        
    def fit_asset_regimes(
        self,
        asset_features_dict: Dict[str, pd.DataFrame],
        asset_returns_df: pd.DataFrame,
        verbose: bool = True
    ) -> Dict[str, pd.Series]:
        """
        Fit Jump Model for all assets (Layer C).
        
        Returns: Dict of {asset_name: regime_series} where 0=Bullish, 1=Bearish
        """
        if verbose:
            print("="*60)
            print(f"Layer C: Asset Regimes (Jump Model λ={self.lambda_jump})")
            print("="*60)
        
        regimes = {}
        
        for asset_name, features in asset_features_dict.items():
            if asset_name not in asset_returns_df.columns:
                if verbose:
                    print(f"{asset_name}: ✗ No return data")
                continue
            
            try:
                returns = asset_returns_df[asset_name]
                regime_labels, model = self._fit_single_asset_regime(
                    features, returns
                )
                
                regimes[asset_name] = regime_labels
                self.asset_models[asset_name] = model
                
                if verbose:
                    n_switches = (regime_labels != regime_labels.shift(1)).sum() - 1
                    bull_days = (regime_labels == 0).sum()
                    bear_days = (regime_labels == 1).sum()
                    print(f"{asset_name}: ✓ Bull={bull_days} ({bull_days/len(regime_labels)*100:.1f}%), "
                          f"Bear={bear_days} ({bear_days/len(regime_labels)*100:.1f}%), "
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
        """Fit Jump Model for single asset."""
        features = features.dropna()
        if len(features) < 100:
            raise ValueError(f"Insufficient data: {len(features)} obs")
        
        X = features.values
        
        # Fit Jump Model
        jm = JumpModel(lambda_jump=self.lambda_jump, n_states=2)
        states = jm.fit(X)
        
        # Assign semantic labels
        regime_labels = pd.Series(states, index=features.index)
        regime_labels = self._assign_bull_bear_labels(regime_labels, returns)
        
        return regime_labels, jm
    
    def _assign_bull_bear_labels(
        self,
        states: pd.Series,
        returns: pd.Series
    ) -> pd.Series:
        """Map states to bull (0) / bear (1) based on cumulative returns."""
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
    
    def fit_forecasters(
        self,
        asset_features_dict: Dict[str, pd.DataFrame],
        asset_regimes_dict: Dict[str, pd.Series],
        macro_features: pd.DataFrame,
        asset_returns_dict: Optional[Dict[str, pd.Series]] = None,
        test_size: float = 0.2,
        verbose: bool = True
    ) -> Dict[str, Dict]:
        """
        Train XGBoost classifiers for regime forecasting.
        
        Includes exponential smoothing halflife selection to maximize
        0/1 strategy Sharpe ratio.
        """
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
                
                # Train XGBoost
                model = self._train_xgboost(X_train, y_train, X_test, y_test)
                
                # Get probability predictions (probability of bullish = class 0)
                p_train = model.predict_proba(X_train)[:, 0]
                p_test = model.predict_proba(X_test)[:, 0]
                
                # Select optimal halflife for smoothing
                halflife_candidates = [0, 2, 4, 8]
                optimal_halflife = 0
                
                if asset_returns_dict and asset_name in asset_returns_dict:
                    returns = asset_returns_dict[asset_name].reindex(X_train.index)
                    best_sharpe = -np.inf
                    
                    for halflife in halflife_candidates:
                        if halflife > 0:
                            alpha = 1 - np.exp(-np.log(2) / halflife)
                            p_smooth = pd.Series(p_train, index=X_train.index).ewm(alpha=alpha, adjust=False).mean()
                        else:
                            p_smooth = pd.Series(p_train, index=X_train.index)
                        
                        # Binary prediction with 0.5 threshold
                        pred_regimes = (p_smooth < 0.5).astype(int)  # <0.5 bullish prob = bearish
                        
                        # 0/1 Strategy returns
                        strategy_rets = returns.copy()
                        strategy_rets[pred_regimes == 1] = 0.0  # Bearish → risk-free
                        
                        # Sharpe ratio
                        if strategy_rets.std() > 0:
                            sharpe = (strategy_rets.mean() / strategy_rets.std()) * np.sqrt(252)
                            if sharpe > best_sharpe:
                                best_sharpe = sharpe
                                optimal_halflife = halflife
                
                # Apply optimal smoothing
                if optimal_halflife > 0:
                    alpha = 1 - np.exp(-np.log(2) / optimal_halflife)
                    p_test_smooth = pd.Series(p_test, index=X_test.index).ewm(alpha=alpha, adjust=False).mean()
                else:
                    p_test_smooth = pd.Series(p_test, index=X_test.index)
                
                # Binary predictions
                pred_test = (p_test_smooth < 0.5).astype(int)
                
                # Evaluate
                train_acc = accuracy_score(y_train, model.predict(X_train))
                test_acc = accuracy_score(y_test, pred_test)
                test_f1 = f1_score(y_test, pred_test, zero_division=0)
                
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
        """
        Prepare supervised dataset for XGBoost.
        
        Target: regime shifted forward by one day (predict s_{t+1} from x_t)
        """
        # Align all data
        common_idx = asset_features.index.intersection(asset_regimes.index)
        common_idx = common_idx.intersection(macro_features.index)
        
        # Combine features
        X = pd.DataFrame(index=common_idx)
        
        for col in asset_features.columns:
            X[col] = asset_features.loc[common_idx, col]
        for col in macro_features.columns:
            X[f'macro_{col}'] = macro_features.loc[common_idx, col]
        
        # Target: shifted forward by one day
        y = asset_regimes.loc[common_idx].shift(-1)
        
        # Drop last row and NaN
        X = X.iloc[:-1]
        y = y.iloc[:-1]
        valid = ~(X.isna().any(axis=1) | y.isna())
        
        return X[valid], y[valid]
    
    def _train_xgboost(
        self,
        X_train: pd.DataFrame,
        y_train: pd.Series,
        X_test: pd.DataFrame,
        y_test: pd.Series
    ) -> xgb.XGBClassifier:
        """Train XGBoost classifier with class balancing."""
        n_pos = (y_train == 1).sum()
        n_neg = (y_train == 0).sum()
        
        if n_pos == 0 or n_neg == 0:
            raise ValueError(f"Only one class present: pos={n_pos}, neg={n_neg}")
        
        params = self.xgb_params.copy()
        params['scale_pos_weight'] = n_neg / n_pos
        params['objective'] = 'binary:logistic'
        params['eval_metric'] = 'logloss'
        
        model = xgb.XGBClassifier(**params)
        model.fit(
            X_train, y_train,
            eval_set=[(X_test, y_test)],
            verbose=False
        )
        
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
        """
        Tune lambda using 0/1 strategy Sharpe ratio over validation window.
        
        Per paper Algorithm 2: for each lambda candidate, compute regime forecasts
        and select the one maximizing Sharpe ratio.
        """
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
                jm = JumpModel(lambda_jump=lam, n_states=2)
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
        """
        Complete workflow: fit all regime layers and train forecasters.
        """
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
    
    def predict_next_regime(
        self,
        asset_name: str,
        current_features: pd.Series,
        previous_prob: Optional[float] = None
    ) -> Tuple[int, float]:
        """
        Forecast next-day regime for an asset.
        
        Applies exponential smoothing if halflife > 0.
        Decision rule: probability threshold of 0.5.
        """
        if asset_name not in self.classifiers:
            raise ValueError(f"No classifier trained for {asset_name}")
        
        model = self.classifiers[asset_name]
        X = current_features.values.reshape(1, -1)
        
        # Get probability of bullish regime (class 0)
        prob_raw = model.predict_proba(X)[0, 0]
        
        # Apply exponential smoothing
        halflife = self.halflives.get(asset_name, 0)
        if halflife > 0 and previous_prob is not None:
            alpha = 1 - np.exp(-np.log(2) / halflife)
            prob_smooth = alpha * prob_raw + (1 - alpha) * previous_prob
        else:
            prob_smooth = prob_raw
        
        # Binary prediction (0.5 threshold)
        pred = 0 if prob_smooth >= 0.5 else 1
        
        return int(pred), float(prob_smooth)


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
    verbose: bool = True
) -> Tuple[Dict[str, pd.Series], Dict[str, float]]:
    """
    Rolling time-series framework with biannual updates (Algorithm 1).
    
    Every 6 months:
    1. Tune lambda over 5-year validation window
    2. Fit JM with optimal lambda on 11-year training window
    3. Train XGBoost forecaster
    4. Generate daily forecasts for next 6 months
    
    Returns:
        Tuple of (forecasts_dict, optimal_lambdas_dict)
    """
    if lambda_candidates is None:
        lambda_candidates = [0.0, 0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 20.0, 50.0, 100.0]
    
    forecasts = {asset: pd.Series(dtype=float) for asset in asset_features_dict.keys()}
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
                
            engine = RegimeEngine(lambda_jump=5.0)
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
                
                engine = RegimeEngine(lambda_jump=update_lambdas[asset_name])
                results = engine.fit_identify_forecast(
                    single_features, single_returns, macro_train,
                    train_forecasters=True, verbose=False
                )
                
                if asset_name not in engine.classifiers:
                    continue
                
                # Generate forecasts for next 6 months
                forecast_features = asset_features_dict[asset_name].loc[current_date:update_end]
                forecast_macro = macro_features.loc[current_date:update_end]
                
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
                forecasts[asset_name] = pd.concat([forecasts[asset_name], forecast_series])
                
            except Exception as e:
                if verbose:
                    print(f"  {asset_name}: ✗ {e}")
        
        current_date = update_end
    
    if verbose:
        print(f"\n{'='*60}")
        print(f"Completed {update_count} rolling updates")
        print(f"{'='*60}\n")
    
    return forecasts, all_optimal_lambdas
