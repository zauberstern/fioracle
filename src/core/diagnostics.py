"""
XGBoost diagnostics, SHAP analysis, and macro-only baseline.

Provides SHAP feature importance, VIX ablation tests, proper scoring rules,
and conditional return analysis by predicted regime.
"""

import numpy as np
import pandas as pd
from typing import Dict, Optional, Tuple, List
from pathlib import Path
import warnings
import json

try:
    import shap
    SHAP_AVAILABLE = True
except ImportError:
    SHAP_AVAILABLE = False

try:
    import matplotlib.pyplot as plt
    import matplotlib
    matplotlib.use('Agg')
except ImportError:
    pass

from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score, balanced_accuracy_score, 
    brier_score_loss, log_loss, f1_score
)

warnings.filterwarnings('ignore')


def compute_xgb_diagnostics(
    model,
    X_train: pd.DataFrame,
    X_test: pd.DataFrame,
    y_train: pd.Series,
    y_test: pd.Series,
    asset_name: str,
    output_dir: Optional[Path] = None,
    compute_shap: bool = True,
    prediction_horizon: int = 1
) -> Dict:
    """
    Compute comprehensive XGBoost diagnostics including SHAP.
    
    Args:
        model: Trained XGBoost model
        X_train, X_test: Feature DataFrames
        y_train, y_test: Target Series
        asset_name: Name for labeling
        output_dir: Directory for saving plots
        compute_shap: Whether to compute SHAP values
        prediction_horizon: Days ahead for prediction (1=daily, 5=weekly, 21=monthly)
    
    Returns dict with feature importances, SHAP values, and scoring metrics.
    """
    results = {
        'asset': asset_name,
        'prediction_horizon_days': prediction_horizon
    }
    
    # Predictions
    y_pred_train = model.predict(X_train)
    y_pred_test = model.predict(X_test)
    y_prob_train = model.predict_proba(X_train)
    y_prob_test = model.predict_proba(X_test)
    
    # Get model's trained classes (handles class mismatch between train/test)
    model_classes = model.classes_ if hasattr(model, 'classes_') else np.unique(y_train)
    n_classes = len(model_classes)
    n_test_classes = len(np.unique(y_test))
    
    # Accuracy metrics
    results['train_accuracy'] = float(accuracy_score(y_train, y_pred_train))
    results['test_accuracy'] = float(accuracy_score(y_test, y_pred_test))
    results['train_balanced_acc'] = float(balanced_accuracy_score(y_train, y_pred_train))
    results['test_balanced_acc'] = float(balanced_accuracy_score(y_test, y_pred_test))
    
    # F1 score - always use weighted for consistency with multi-class
    results['test_f1'] = float(f1_score(y_test, y_pred_test, average='weighted', zero_division=0))
    
    # Proper scoring rules - pass labels to handle class mismatch
    try:
        if n_classes == 2 and n_test_classes == 2:
            results['test_brier_score'] = float(brier_score_loss(y_test, y_prob_test[:, 1]))
            results['test_log_loss'] = float(log_loss(y_test, y_prob_test, labels=model_classes))
        else:
            # Multi-class: average Brier score per class
            brier_total = 0.0
            valid_classes = 0
            for i, c in enumerate(model_classes):
                y_binary = (y_test == c).astype(int)
                if y_binary.sum() > 0 and i < y_prob_test.shape[1]:
                    brier_total += brier_score_loss(y_binary, y_prob_test[:, i])
                    valid_classes += 1
            results['test_brier_score'] = float(brier_total / max(valid_classes, 1))
            results['test_log_loss'] = float(log_loss(y_test, y_prob_test, labels=model_classes))
    except Exception as e:
        results['test_brier_score'] = np.nan
        results['test_log_loss'] = np.nan
        results['scoring_error'] = str(e)
    
    # Feature importance (XGBoost native)
    importance = pd.DataFrame({
        'feature': X_train.columns,
        'importance': model.feature_importances_
    }).sort_values('importance', ascending=False)
    results['feature_importance'] = importance.to_dict('records')
    
    # Macro feature importance
    macro_cols = [c for c in X_train.columns if 'macro' in c.lower()]
    if macro_cols:
        macro_importance = importance[importance['feature'].isin(macro_cols)]
        results['macro_feature_importance'] = macro_importance.to_dict('records')
        results['total_macro_importance'] = float(macro_importance['importance'].sum())
    
    # Identify specific macro features
    for macro_type in ['vix', 'gpr', 'hy_oas', 'inflation', 'yield', 'debt', 'gdp', 'unemployment', 'epu']:
        macro_type_cols = [c for c in macro_cols if macro_type in c.lower()]
        if macro_type_cols:
            type_importance = importance[importance['feature'].isin(macro_type_cols)]['importance'].sum()
            results[f'{macro_type}_importance'] = float(type_importance)
    
    # SHAP analysis
    if compute_shap and SHAP_AVAILABLE and output_dir is not None:
        try:
            explainer = shap.TreeExplainer(model)
            
            # Use a sample if too many test points
            X_shap = X_test.iloc[:min(500, len(X_test))]
            shap_values = explainer.shap_values(X_shap)
            
            # Mean absolute SHAP per feature
            if isinstance(shap_values, list):
                # Multi-class: average across classes
                shap_mean = np.mean([np.abs(sv).mean(axis=0) for sv in shap_values], axis=0)
            else:
                shap_mean = np.abs(shap_values).mean(axis=0)
            
            shap_importance = pd.DataFrame({
                'feature': X_shap.columns,
                'mean_abs_shap': shap_mean
            }).sort_values('mean_abs_shap', ascending=False)
            
            results['shap_importance'] = shap_importance.to_dict('records')
            
            # SHAP statistics
            results['shap_stats'] = {
                'top_5_features': shap_importance.head(5).to_dict('records'),
                'total_shap_macro': float(shap_importance[
                    shap_importance['feature'].str.contains('macro', case=False)
                ]['mean_abs_shap'].sum()),
                'total_shap_return': float(shap_importance[
                    ~shap_importance['feature'].str.contains('macro', case=False)
                ]['mean_abs_shap'].sum())
            }
            
            # Save SHAP plots
            shap_dir = output_dir / 'shap'
            shap_dir.mkdir(parents=True, exist_ok=True)
            
            # Summary plot (bar)
            plt.figure(figsize=(12, 8))
            if isinstance(shap_values, list):
                shap.summary_plot(shap_values[0], X_shap, show=False, plot_size=(12, 8), plot_type='bar')
            else:
                shap.summary_plot(shap_values, X_shap, show=False, plot_size=(12, 8), plot_type='bar')
            plt.title(f'SHAP Feature Importance: {asset_name}', fontsize=14, fontweight='bold')
            plt.tight_layout()
            plt.savefig(shap_dir / f'{asset_name}_shap_bar.png', dpi=150, bbox_inches='tight')
            plt.close()
            
            # Summary plot (beeswarm)
            plt.figure(figsize=(12, 8))
            if isinstance(shap_values, list):
                shap.summary_plot(shap_values[0], X_shap, show=False, plot_size=(12, 8))
            else:
                shap.summary_plot(shap_values, X_shap, show=False, plot_size=(12, 8))
            plt.title(f'SHAP Summary: {asset_name}', fontsize=14, fontweight='bold')
            plt.tight_layout()
            plt.savefig(shap_dir / f'{asset_name}_shap_summary.png', dpi=150, bbox_inches='tight')
            plt.close()
            
            results['shap_plots_saved'] = True
            
        except Exception as e:
            results['shap_error'] = str(e)
    
    return results


def run_macro_only_baseline(
    X_train: pd.DataFrame,
    X_test: pd.DataFrame,
    y_train: pd.Series,
    y_test: pd.Series,
    exclude_vix: bool = True,
    macro_features_config: Optional[List[str]] = None
) -> Dict:
    """
    Run macro-only logistic regression baseline (VIX ablation).
    
    Args:
        X_train, X_test: Full feature DataFrames
        y_train, y_test: Target Series
        exclude_vix: If True, excludes VIX features for ablation test
        macro_features_config: List of specific macro features to use (from config)
    
    Returns dict with accuracy comparison to show VIX value.
    """
    # Select only macro features
    macro_cols = [c for c in X_train.columns if 'macro' in c.lower()]
    
    # If specific features requested from config
    if macro_features_config:
        requested = [f.lower() for f in macro_features_config]
        macro_cols = [c for c in macro_cols if any(r in c.lower() for r in requested)]
    
    if exclude_vix:
        # VIX ablation: exclude VIX features
        macro_cols_no_vix = [c for c in macro_cols if 'vix' not in c.lower()]
        results_with_vix = _run_logistic_baseline(X_train, X_test, y_train, y_test, macro_cols)
        results_no_vix = _run_logistic_baseline(X_train, X_test, y_train, y_test, macro_cols_no_vix)
        
        return {
            'with_vix': results_with_vix,
            'without_vix': results_no_vix,
            'vix_value_added': {
                'accuracy_delta': results_with_vix.get('accuracy', 0) - results_no_vix.get('accuracy', 0),
                'balanced_acc_delta': results_with_vix.get('balanced_accuracy', 0) - results_no_vix.get('balanced_accuracy', 0),
                'log_loss_delta': results_no_vix.get('log_loss', 0) - results_with_vix.get('log_loss', 0)  # Lower is better
            }
        }
    else:
        return _run_logistic_baseline(X_train, X_test, y_train, y_test, macro_cols)


def _run_logistic_baseline(
    X_train: pd.DataFrame,
    X_test: pd.DataFrame,
    y_train: pd.Series,
    y_test: pd.Series,
    feature_cols: List[str]
) -> Dict:
    """Internal helper to run logistic regression baseline."""
    if len(feature_cols) == 0:
        return {'error': 'No features available'}
    
    X_train_filtered = X_train[feature_cols]
    X_test_filtered = X_test[feature_cols]
    
    # Handle NaN
    valid_train = ~X_train_filtered.isna().any(axis=1)
    valid_test = ~X_test_filtered.isna().any(axis=1)
    
    X_train_clean = X_train_filtered[valid_train]
    y_train_clean = y_train[valid_train]
    X_test_clean = X_test_filtered[valid_test]
    y_test_clean = y_test[valid_test]
    
    if len(X_train_clean) < 50 or len(X_test_clean) < 10:
        return {'error': 'Insufficient data after cleaning'}
    
    n_classes = len(y_train_clean.unique())
    
    try:
        # Fit logistic regression
        lr = LogisticRegression(
            multi_class='multinomial' if n_classes > 2 else 'auto',
            max_iter=1000,
            random_state=42,
            solver='lbfgs'
        )
        lr.fit(X_train_clean, y_train_clean)
        
        # Predictions
        y_pred = lr.predict(X_test_clean)
        y_prob = lr.predict_proba(X_test_clean)
        model_classes = lr.classes_
        n_test_classes = len(np.unique(y_test_clean))
        
        results = {
            'n_features': len(feature_cols),
            'features': feature_cols,
            'accuracy': float(accuracy_score(y_test_clean, y_pred)),
            'balanced_accuracy': float(balanced_accuracy_score(y_test_clean, y_pred)),
        }
        
        # F1 score - always use weighted for consistency
        results['f1'] = float(f1_score(y_test_clean, y_pred, average='weighted', zero_division=0))
        
        # Proper scoring rules with labels to handle class mismatch
        try:
            results['log_loss'] = float(log_loss(y_test_clean, y_prob, labels=model_classes))
            
            if n_classes == 2 and n_test_classes == 2:
                results['brier_score'] = float(brier_score_loss(y_test_clean, y_prob[:, 1]))
            else:
                brier_total = 0.0
                valid_classes = 0
                for i, c in enumerate(model_classes):
                    y_binary = (y_test_clean == c).astype(int)
                    if y_binary.sum() > 0 and i < y_prob.shape[1]:
                        brier_total += brier_score_loss(y_binary, y_prob[:, i])
                        valid_classes += 1
                results['brier_score'] = float(brier_total / max(valid_classes, 1))
        except Exception as e:
            results['log_loss'] = np.nan
            results['brier_score'] = np.nan
            results['scoring_error'] = str(e)
        
        return results
        
    except Exception as e:
        return {'error': str(e)}


def compute_persistent_baseline(y_train: pd.Series, y_test: pd.Series) -> Dict:
    """
    Compute persistent-regime baseline.
    
    Two baselines:
    1. Most frequent: Always predict most common training regime
    2. Previous day: Predict same regime as previous day
    """
    results = {}
    
    # Most frequent baseline
    most_frequent = y_train.mode().iloc[0]
    y_pred_freq = np.full(len(y_test), most_frequent)
    
    results['most_frequent_baseline'] = {
        'most_frequent_regime': int(most_frequent),
        'accuracy': float(accuracy_score(y_test, y_pred_freq)),
        'baseline_type': 'most_frequent'
    }
    
    # Previous day baseline (persistence)
    if len(y_test) > 1:
        y_pred_persist = np.concatenate([[y_test.iloc[0]], y_test.iloc[:-1].values])
        results['persistence_baseline'] = {
            'accuracy': float(accuracy_score(y_test, y_pred_persist)),
            'baseline_type': 'previous_day'
        }
    
    return results


def compute_conditional_returns(
    y_pred: pd.Series,
    returns: pd.Series,
    regime_names: Dict[int, str] = None,
    horizon: int = 1
) -> Dict:
    """
    Compute average returns conditional on predicted regime.
    
    Args:
        y_pred: Predicted regime series
        returns: Asset return series
        regime_names: Mapping of regime int to name (0: calm, 1: inflationary, 2: crisis)
        horizon: Number of days ahead to measure returns
    
    For each predicted regime r, compute mean of next-horizon returns.
    """
    if regime_names is None:
        regime_names = {0: 'calm', 1: 'inflationary', 2: 'crisis'}
    
    # Align predictions with returns (shifted forward)
    returns_shifted = returns.shift(-horizon)
    common_idx = y_pred.index.intersection(returns_shifted.dropna().index)
    
    if len(common_idx) < 50:
        return {'error': f'Insufficient data ({len(common_idx)} days)'}
    
    pred_aligned = y_pred.loc[common_idx]
    ret_aligned = returns_shifted.loc[common_idx]
    
    results = {'horizon_days': horizon, 'by_regime': {}}
    
    for regime in sorted(pred_aligned.unique()):
        mask = pred_aligned == regime
        if mask.sum() < 10:
            continue
            
        regime_returns = ret_aligned[mask]
        regime_name = regime_names.get(int(regime), f'regime_{regime}')
        
        results['by_regime'][regime_name] = {
            'regime_id': int(regime),
            'n_days': int(mask.sum()),
            'pct_of_total': float(mask.sum() / len(pred_aligned) * 100),
            'mean_return_daily': float(regime_returns.mean()),
            'mean_return_ann': float(regime_returns.mean() * 252),
            'std_return_ann': float(regime_returns.std() * np.sqrt(252)),
            'sharpe': float(regime_returns.mean() / (regime_returns.std() + 1e-10) * np.sqrt(252)),
            'hit_rate': float((regime_returns > 0).mean())
        }
    
    return results


def run_full_diagnostics(
    regime_engine,
    asset_name: str,
    X_train: pd.DataFrame,
    X_test: pd.DataFrame,
    y_train: pd.Series,
    y_test: pd.Series,
    returns: pd.Series,
    output_dir: Path,
    config: dict
) -> Dict:
    """
    Run comprehensive diagnostics for a single asset.
    
    Includes:
    - XGBoost feature importance + SHAP
    - Macro-only baseline (with/without VIX)
    - Persistent baseline comparison
    - Conditional returns by regime
    """
    results = {'asset': asset_name}
    
    diag_cfg = config.get('regimes', {}).get('diagnostics', {})
    if not diag_cfg.get('enabled', False):
        return results
    
    # Get model for this asset
    if not hasattr(regime_engine, 'classifiers') or asset_name not in regime_engine.classifiers:
        results['error'] = 'No classifier found for asset'
        return results
    
    model = regime_engine.classifiers[asset_name]
    
    # Get prediction horizon from config
    horizon_cfg = config.get('regimes', {}).get('xgboost', {}).get('forecast_horizon', {})
    horizon = horizon_cfg.get('horizon_days', 1)
    
    # XGBoost diagnostics
    if diag_cfg.get('shap_plots', False):
        xgb_diag = compute_xgb_diagnostics(
            model=model,
            X_train=X_train,
            X_test=X_test,
            y_train=y_train,
            y_test=y_test,
            asset_name=asset_name,
            output_dir=output_dir,
            compute_shap=True,
            prediction_horizon=horizon
        )
        results['xgb_diagnostics'] = xgb_diag
    
    # Macro-only baseline (VIX ablation)
    if diag_cfg.get('macro_baseline', False):
        macro_features = config.get('portfolio', {}).get('mu_model', {}).get('macro_features', [])
        macro_baseline = run_macro_only_baseline(
            X_train=X_train,
            X_test=X_test,
            y_train=y_train,
            y_test=y_test,
            exclude_vix=True,
            macro_features_config=macro_features if macro_features else None
        )
        results['macro_baseline'] = macro_baseline
    
    # Persistent baseline
    persistent = compute_persistent_baseline(y_train, y_test)
    results['persistent_baseline'] = persistent
    
    # Compare to XGBoost
    if 'xgb_diagnostics' in results:
        xgb_acc = results['xgb_diagnostics'].get('test_accuracy', 0)
        freq_acc = persistent['most_frequent_baseline']['accuracy']
        results['accuracy_vs_baseline'] = {
            'xgb_accuracy': xgb_acc,
            'baseline_accuracy': freq_acc,
            'improvement': xgb_acc - freq_acc,
            'improvement_pct': (xgb_acc - freq_acc) / (freq_acc + 1e-10) * 100
        }
    
    # Conditional returns
    if len(returns) > 0:
        y_pred_full = pd.Series(model.predict(X_test), index=X_test.index)
        cond_returns = compute_conditional_returns(
            y_pred=y_pred_full,
            returns=returns.reindex(X_test.index),
            horizon=horizon
        )
        results['conditional_returns'] = cond_returns
    
    return results


def save_diagnostics_summary(
    results: Dict,
    output_dir: Path,
    split_name: str
) -> None:
    """Save diagnostics results to JSON."""
    diag_dir = output_dir / 'diagnostics' / split_name
    diag_dir.mkdir(parents=True, exist_ok=True)
    
    # Convert numpy types to Python types for JSON serialization
    def convert_types(obj):
        if isinstance(obj, np.integer):
            return int(obj)
        elif isinstance(obj, np.floating):
            return float(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        elif isinstance(obj, pd.DataFrame):
            return obj.to_dict('records')
        elif isinstance(obj, pd.Timestamp):
            return str(obj)
        elif isinstance(obj, dict):
            return {k: convert_types(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [convert_types(i) for i in obj]
        return obj
    
    results_clean = convert_types(results)
    
    with open(diag_dir / 'xgb_diagnostics.json', 'w') as f:
        json.dump(results_clean, f, indent=2)
    
    print(f"  Diagnostics saved to {diag_dir}")


def plot_feature_importance_comparison(
    all_results: Dict[str, Dict],
    output_dir: Path,
    top_n: int = 15
) -> None:
    """Plot aggregate feature importance across all assets."""
    if not all_results:
        return
    
    # Aggregate importance
    importance_agg = {}
    
    for asset_name, results in all_results.items():
        if 'xgb_diagnostics' not in results:
            continue
        for feat_dict in results['xgb_diagnostics'].get('feature_importance', []):
            feat = feat_dict['feature']
            imp = feat_dict['importance']
            if feat not in importance_agg:
                importance_agg[feat] = []
            importance_agg[feat].append(imp)
    
    if not importance_agg:
        return
    
    # Average importance
    avg_importance = {k: np.mean(v) for k, v in importance_agg.items()}
    sorted_feats = sorted(avg_importance.items(), key=lambda x: x[1], reverse=True)[:top_n]
    
    # Plot
    plt.figure(figsize=(12, 8))
    feats, imps = zip(*sorted_feats)
    
    # Color by type
    colors = []
    for f in feats:
        if 'macro' in f.lower():
            if 'vix' in f.lower():
                colors.append('#e53e3e')  # Red for VIX
            elif 'gpr' in f.lower():
                colors.append('#d69e2e')  # Orange for GPR
            else:
                colors.append('#38a169')  # Green for other macro
        else:
            colors.append('#2b6cb0')  # Blue for return features
    
    plt.barh(range(len(feats)), imps, color=colors)
    plt.yticks(range(len(feats)), feats)
    plt.xlabel('Average Feature Importance', fontsize=12)
    plt.title('Aggregate Feature Importance Across Assets', fontsize=14, fontweight='bold')
    plt.gca().invert_yaxis()
    
    # Legend
    from matplotlib.patches import Patch
    legend_elements = [
        Patch(facecolor='#e53e3e', label='VIX'),
        Patch(facecolor='#d69e2e', label='GPR'),
        Patch(facecolor='#38a169', label='Other Macro'),
        Patch(facecolor='#2b6cb0', label='Return Features')
    ]
    plt.legend(handles=legend_elements, loc='lower right')
    
    plt.tight_layout()
    plt.savefig(output_dir / 'aggregate_feature_importance.png', dpi=150, bbox_inches='tight')
    plt.close()
