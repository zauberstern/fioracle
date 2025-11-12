"""
Regime identification engine.

Three-layer architecture:
- Layer C: Asset bull/bear regimes (Jump Model with HMM)
- Layer B: Market volatility regimes (PCA + HMM)
- Layer A: Macro-policy regimes (N-state HMM)
- Forecasting: XGBoost for next-day regime prediction
"""

import numpy as np
import pandas as pd
from hmmlearn import hmm
import xgboost as xgb
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import accuracy_score, f1_score
from typing import Dict, Tuple, Optional, List
import warnings


class RegimeEngine:
    """
    Complete regime identification and forecasting system.
    
    Layers:
    - C: Asset regimes (bull/bear via Jump Model)
    - B: Volatility regimes (high/low via PCA + HMM)
    - A: Macro regimes (N-state HMM for market environment)
    - Forecasting: XGBoost for next-day predictions
    """
    
    def __init__(
        self,
        lambda_jump: float = 5.0,
        n_macro_regimes: int = 3,
        xgb_params: Optional[Dict] = None
    ):
        """
        Initialize RegimeEngine.
        
        Args:
            lambda_jump: Jump penalty for asset regimes (0-100, higher = more persistent)
            n_macro_regimes: Number of macro regime states
            xgb_params: XGBoost hyperparameters (optional)
        """
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
        
        # Storage for fitted models
        self.asset_models = {}
        self.volatility_model = None
        self.macro_model = None
        self.classifiers = {}
        
    def fit_asset_regimes(
        self,
        asset_features_dict: Dict[str, pd.DataFrame],
        asset_returns_df: pd.DataFrame,
        verbose: bool = True
    ) -> Dict[str, pd.Series]:
        """
        Fit Jump Model for all assets (Layer C).
        
        Args:
            asset_features_dict: Dict of {asset_name: features_df}
            asset_returns_df: DataFrame with asset returns
            verbose: Print progress
            
        Returns:
            Dict of {asset_name: regime_series} where 0=Bullish, 1=Bearish
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
                    features, returns, verbose
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
        returns: pd.Series,
        verbose: bool = False
    ) -> Tuple[pd.Series, hmm.GaussianHMM]:
        """Fit Jump Model for single asset using 2-state HMM."""
        # Validate
        features = features.dropna()
        if len(features) < 100:
            raise ValueError(f"Insufficient data: {len(features)} obs")
        
        # Convert lambda to transition probability
        self_prob = 0.5 + 0.49 * (self.lambda_jump / 100.0)
        other_prob = 1.0 - self_prob
        
        # Initialize HMM
        model = hmm.GaussianHMM(
            n_components=2,
            covariance_type='diag',
            n_iter=200,
            random_state=42,
            verbose=False,
            init_params='mc',
            params='stmc',
            tol=1e-3
        )
        
        model.transmat_ = np.array([
            [self_prob, other_prob],
            [other_prob, self_prob]
        ])
        model.startprob_ = np.array([0.5, 0.5])
        
        # Standardize and fit
        X = features.values
        X_norm = (X - X.mean(axis=0)) / (X.std(axis=0) + 1e-8)
        
        model.fit(X_norm)
        states = model.predict(X_norm)
        
        # Assign semantic labels (0=Bullish, 1=Bearish)
        regime_labels = pd.Series(states, index=features.index)
        regime_labels = self._assign_bull_bear_labels(regime_labels, returns)
        
        return regime_labels, model
    
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
    
    def fit_volatility_regime(
        self,
        yield_data: pd.DataFrame,
        verbose: bool = True
    ) -> pd.DataFrame:
        """
        Fit volatility regime (Layer B).
        
        Args:
            yield_data: DataFrame with yield curve data
            verbose: Print progress
            
        Returns:
            DataFrame with volatility regime probabilities
        """
        if verbose:
            print("="*60)
            print("Layer B: Volatility Regime (PCA + HMM)")
            print("="*60)
        
        try:
            # Compute PC1 variance as volatility measure
            yield_changes = yield_data.diff().dropna()
            
            scaler = StandardScaler()
            yield_scaled = scaler.fit_transform(yield_changes)
            
            pca = PCA(n_components=1)
            pc_scores = pca.fit_transform(yield_scaled)
            pc1 = pd.Series(pc_scores[:, 0], index=yield_changes.index)
            
            # Rolling variance (3-month window)
            vol_feature = pc1.rolling(window=63).var().dropna()
            
            # Fit 2-state HMM
            X = vol_feature.values.reshape(-1, 1)
            X_norm = (X - X.mean()) / (X.std() + 1e-8)
            
            model = hmm.GaussianHMM(
                n_components=2,
                covariance_type='full',
                n_iter=200,
                random_state=42,
                init_params='mc',
                params='stmc'
            )
            
            model.transmat_ = np.array([[0.98, 0.02], [0.02, 0.98]])
            model.startprob_ = np.array([0.5, 0.5])
            
            model.fit(X_norm)
            states = model.predict(X_norm)
            probs = model.predict_proba(X_norm)
            
            # Identify HV state (higher mean volatility)
            state_means = [X[states == s].mean() for s in range(2)]
            hv_state = np.argmax(state_means)
            
            # Create probability DataFrame
            prob_df = pd.DataFrame(
                probs,
                index=vol_feature.index,
                columns=['vol_regime_0_prob', 'vol_regime_1_prob']
            )
            prob_df['vol_regime_hv_prob'] = prob_df[f'vol_regime_{hv_state}_prob']
            
            self.volatility_model = model
            
            if verbose:
                hv_pct = (states == hv_state).sum() / len(states) * 100
                print(f"✓ PC1 explains {pca.explained_variance_ratio_[0]*100:.1f}% variance")
                print(f"✓ HV state: {hv_state}, occurs {hv_pct:.1f}% of time")
                print("="*60 + "\n")
            
            return prob_df
        
        except Exception as e:
            if verbose:
                print(f"✗ Failed: {e}")
                print("="*60 + "\n")
            # Return dummy probabilities
            return pd.DataFrame({
                'vol_regime_hv_prob': 0.5
            }, index=yield_data.index)
    
    def fit_macro_regime(
        self,
        macro_features: pd.DataFrame,
        verbose: bool = True
    ) -> pd.DataFrame:
        """
        Fit macro-policy regime (Layer A).
        
        Args:
            macro_features: DataFrame with macro indicators
            verbose: Print progress
            
        Returns:
            DataFrame with macro regime probabilities
        """
        if verbose:
            print("="*60)
            print(f"Layer A: Macro Regime (HMM N={self.n_macro_regimes})")
            print("="*60)
        
        try:
            macro_clean = macro_features.dropna()
            
            # Standardize
            scaler = StandardScaler()
            X = scaler.fit_transform(macro_clean.values)
            
            # Initialize HMM
            model = hmm.GaussianHMM(
                n_components=self.n_macro_regimes,
                covariance_type='diag',
                n_iter=200,
                random_state=42,
                init_params='mc',
                params='stmc'
            )
            
            # High persistence transition matrix
            persist = 0.95
            other = (1 - persist) / (self.n_macro_regimes - 1)
            transmat = np.full((self.n_macro_regimes, self.n_macro_regimes), other)
            np.fill_diagonal(transmat, persist)
            model.transmat_ = transmat
            model.startprob_ = np.ones(self.n_macro_regimes) / self.n_macro_regimes
            
            model.fit(X)
            states = model.predict(X)
            probs = model.predict_proba(X)
            
            prob_df = pd.DataFrame(
                probs,
                index=macro_clean.index,
                columns=[f'macro_regime_{i}_prob' for i in range(self.n_macro_regimes)]
            )
            
            self.macro_model = model
            
            if verbose:
                for regime in range(self.n_macro_regimes):
                    pct = (states == regime).sum() / len(states) * 100
                    print(f"  Regime {regime}: {pct:.1f}% of time")
                print("="*60 + "\n")
            
            return prob_df
        
        except Exception as e:
            if verbose:
                print(f"✗ Failed: {e}")
                print("="*60 + "\n")
            # Return dummy probabilities
            return pd.DataFrame({
                f'macro_regime_{i}_prob': 1.0 / self.n_macro_regimes
                for i in range(self.n_macro_regimes)
            }, index=macro_features.index)
    
    def fit_forecasters(
        self,
        asset_features_dict: Dict[str, pd.DataFrame],
        asset_regimes_dict: Dict[str, pd.Series],
        macro_probs: pd.DataFrame,
        volatility_probs: pd.DataFrame,
        test_size: float = 0.2,
        verbose: bool = True
    ) -> Dict[str, Dict]:
        """
        Train XGBoost classifiers for regime forecasting.
        
        Args:
            asset_features_dict: Dict of {asset_name: features_df}
            asset_regimes_dict: Dict of {asset_name: regime_series}
            macro_probs: Macro regime probabilities
            volatility_probs: Volatility regime probabilities
            test_size: Fraction for test set
            verbose: Print progress
            
        Returns:
            Dict of {asset_name: results_dict} with models and metrics
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
                    macro_probs,
                    volatility_probs
                )
                
                # Time-series split
                split_idx = int(len(X) * (1 - test_size))
                X_train, X_test = X.iloc[:split_idx], X.iloc[split_idx:]
                y_train, y_test = y.iloc[:split_idx], y.iloc[split_idx:]
                
                # Train XGBoost
                model = self._train_xgboost(X_train, y_train, X_test, y_test)
                
                # Evaluate
                train_acc = accuracy_score(y_train, model.predict(X_train))
                test_acc = accuracy_score(y_test, model.predict(X_test))
                test_f1 = f1_score(y_test, model.predict(X_test), zero_division=0)
                
                # Feature importance
                importance = pd.DataFrame({
                    'feature': X.columns,
                    'importance': model.feature_importances_
                }).sort_values('importance', ascending=False)
                
                results[asset_name] = {
                    'model': model,
                    'train_accuracy': train_acc,
                    'test_accuracy': test_acc,
                    'test_f1': test_f1,
                    'feature_importance': importance,
                    'X_test': X_test,
                    'y_test': y_test
                }
                
                self.classifiers[asset_name] = model
                
                if verbose:
                    print(f"{asset_name}: ✓ Train={train_acc:.3f}, Test={test_acc:.3f}, F1={test_f1:.3f}")
            
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
        macro_probs: pd.DataFrame,
        volatility_probs: pd.DataFrame
    ) -> Tuple[pd.DataFrame, pd.Series]:
        """Prepare supervised dataset for XGBoost."""
        # Align all data
        common_idx = asset_features.index.intersection(asset_regimes.index)
        common_idx = common_idx.intersection(macro_probs.index)
        common_idx = common_idx.intersection(volatility_probs.index)
        
        # Combine features
        X = pd.DataFrame(index=common_idx)
        
        for col in asset_features.columns:
            X[col] = asset_features.loc[common_idx, col]
        for col in macro_probs.columns:
            X[col] = macro_probs.loc[common_idx, col]
        for col in volatility_probs.columns:
            X[col] = volatility_probs.loc[common_idx, col]
        
        # Target: next day's regime
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
        """Train XGBoost binary classifier with class balancing."""
        # Handle class imbalance
        n_pos = (y_train == 1).sum()
        n_neg = (y_train == 0).sum()
        
        # Check if we have both classes
        if n_pos == 0 or n_neg == 0:
            raise ValueError(f"Only one class present: pos={n_pos}, neg={n_neg}")
        
        params = self.xgb_params.copy()
        params['scale_pos_weight'] = n_neg / n_pos
        
        params['objective'] = 'binary:logistic'
        params['eval_metric'] = 'logloss'
        
        # Remove base_score if present (can cause issues)
        params.pop('base_score', None)
        
        model = xgb.XGBClassifier(**params)
        model.fit(
            X_train, y_train,
            eval_set=[(X_train, y_train), (X_test, y_test)],
            verbose=False
        )
        
        return model
    
    def predict_next_regime(
        self,
        asset_name: str,
        current_features: pd.Series
    ) -> Tuple[int, float]:
        """
        Forecast next-day regime for an asset.
        
        Args:
            asset_name: Name of the asset
            current_features: Feature vector for current day
            
        Returns:
            Tuple of (predicted_regime, probability)
        """
        if asset_name not in self.classifiers:
            raise ValueError(f"No classifier trained for {asset_name}")
        
        model = self.classifiers[asset_name]
        X = current_features.values.reshape(1, -1)
        
        pred = model.predict(X)[0]
        prob = model.predict_proba(X)[0, pred]
        
        return int(pred), float(prob)
    
    def fit_identify_forecast(
        self,
        asset_features_dict: Dict[str, pd.DataFrame],
        asset_returns_df: pd.DataFrame,
        macro_features: pd.DataFrame,
        yield_data: Optional[pd.DataFrame] = None,
        train_forecasters: bool = True,
        test_size: float = 0.2,
        verbose: bool = True
    ) -> Dict:
        """
        Complete workflow: fit all regime layers and train forecasters.
        
        Args:
            asset_features_dict: Dict of {asset_name: features_df}
            asset_returns_df: DataFrame with asset returns
            macro_features: DataFrame with macro indicators
            yield_data: Yield curve data (optional)
            train_forecasters: Whether to train XGBoost forecasters
            test_size: Test set fraction for forecasters
            verbose: Print progress
            
        Returns:
            Dict with all regime results:
                - asset_regimes: Dict of regime series
                - volatility_probs: DataFrame
                - macro_probs: DataFrame
                - forecaster_results: Dict (if train_forecasters=True)
        """
        # Layer C: Asset regimes
        asset_regimes = self.fit_asset_regimes(
            asset_features_dict, asset_returns_df, verbose
        )
        
        # Layer B: Volatility regimes
        if yield_data is not None and len(yield_data.columns) > 1:
            volatility_probs = self.fit_volatility_regime(yield_data, verbose)
        else:
            volatility_probs = pd.DataFrame({
                'vol_regime_hv_prob': 0.5
            }, index=macro_features.index)
            if verbose:
                print("Layer B: Skipping (no yield data)\n")
        
        # Layer A: Macro regimes
        macro_probs = self.fit_macro_regime(macro_features, verbose)
        
        # Forecasters
        forecaster_results = None
        if train_forecasters and asset_regimes:
            forecaster_results = self.fit_forecasters(
                asset_features_dict,
                asset_regimes,
                macro_probs,
                volatility_probs,
                test_size,
                verbose
            )
        
        return {
            'asset_regimes': asset_regimes,
            'volatility_probs': volatility_probs,
            'macro_probs': macro_probs,
            'forecaster_results': forecaster_results
        }


# Convenience functions for backward compatibility
def fit_all_asset_regimes(
    asset_features_dict: Dict[str, pd.DataFrame],
    asset_returns_df: pd.DataFrame,
    lambda_jump: float = 5.0
) -> Dict:
    """
    Fit Jump Models for all assets (backward compatible).
    
    Args:
        asset_features_dict: Dict of {asset_name: features_df}
        asset_returns_df: DataFrame with asset returns
        lambda_jump: Jump penalty parameter
        
    Returns:
        Dict with 'regimes' key containing {asset_name: regime_series}
    """
    engine = RegimeEngine(lambda_jump=lambda_jump)
    regimes = engine.fit_asset_regimes(asset_features_dict, asset_returns_df)
    return {'regimes': regimes, 'models': engine.asset_models}


def fit_all_regime_layers(
    macro_features: pd.DataFrame,
    yield_data: Optional[pd.DataFrame] = None,
    n_macro_regimes: int = 3
) -> Dict:
    """
    Fit volatility and macro regime layers (backward compatible).
    
    Args:
        macro_features: DataFrame with macro indicators
        yield_data: Yield curve data (optional)
        n_macro_regimes: Number of macro regimes
        
    Returns:
        Dict with 'volatility_probs' and 'macro_probs' keys
    """
    engine = RegimeEngine(n_macro_regimes=n_macro_regimes)
    
    if yield_data is not None and len(yield_data.columns) > 1:
        volatility_probs = engine.fit_volatility_regime(yield_data)
    else:
        volatility_probs = pd.DataFrame({
            'vol_regime_hv_prob': 0.5
        }, index=macro_features.index)
    
    macro_probs = engine.fit_macro_regime(macro_features)
    
    return {
        'volatility_probs': volatility_probs,
        'macro_probs': macro_probs
    }


def train_classifiers_for_all_assets(
    asset_features_dict: Dict[str, pd.DataFrame],
    asset_regimes_dict: Dict[str, pd.Series],
    macro_probs: pd.DataFrame,
    volatility_probs: pd.DataFrame,
    test_size: float = 0.2,
    params: Optional[Dict] = None
) -> Dict:
    """
    Train XGBoost classifiers (backward compatible).
    
    Args:
        asset_features_dict: Dict of {asset_name: features_df}
        asset_regimes_dict: Dict of {asset_name: regime_series}
        macro_probs: Macro regime probabilities
        volatility_probs: Volatility regime probabilities
        test_size: Test set fraction
        params: XGBoost parameters
        
    Returns:
        Dict of {asset_name: results_dict}
    """
    engine = RegimeEngine(xgb_params=params)
    return engine.fit_forecasters(
        asset_features_dict,
        asset_regimes_dict,
        macro_probs,
        volatility_probs,
        test_size
    )
