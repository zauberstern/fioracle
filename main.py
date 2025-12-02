#!/usr/bin/env python3
"""
Fioracle: Regime-aware Fixed Income Portfolio Optimization

Main pipeline runner implementing the complete JM-XGB framework:

1. Data Loading: Asset universe (fixed income) + Macro indicators
2. Feature Engineering: 8 return features + macro features
3. Regime Identification: Jump Model with lambda tuning
4. Regime Forecasting: XGBoost with PROPER train/test separation
5. Portfolio Construction: MinVar/MV/EW with regime integration
6. Performance Evaluation: Comprehensive metrics and visualizations

Key Principles:
- NO look-ahead bias: strict temporal separation in all training
- Capital preservation focus for fixed income
- Regime-aware dynamic allocation based on macro/geopolitical factors
"""

import json
import sys
import traceback
import shutil
from pathlib import Path
from typing import Dict, Optional
from datetime import datetime

import pandas as pd
import numpy as np

sys.path.insert(0, str(Path(__file__).parent / 'src'))

from core import (
    setup_logging, load_config, DataPipeline, engineer_features, 
    RegimeEngine, PortfolioEngine, Evaluator
)

# ============================================================================
# CONFIGURATION
# ============================================================================

CONFIG_PATH = 'config/config.yaml'
OUTPUT_DIR = 'output'
SPLITS = ['train', 'val', 'test']
PORTFOLIO_STRATEGIES = ['minvar', 'mv', 'ew']

# Framework parameters per methodology
TRAINING_YEARS = 11           # 11-year lookback
VALIDATION_YEARS = 5          # 5-year validation for lambda tuning
UPDATE_FREQUENCY_MONTHS = 6   # Biannual updates

TUNE_LAMBDA = True
TRAIN_FORECASTERS = True
VERBOSE = True

# =============================================================================
# QUICK MODE - For fast sanity checks with smaller date ranges
# =============================================================================
# Set to True for quick test runs instead of full 80+ year backtest
# Can also use: python main.py --quick
QUICK_MODE = '--quick' in sys.argv

# Quick mode date overrides (used when QUICK_MODE = True)
# Extended dates for comprehensive analysis including all visualizations
QUICK_DATES = {
    'train_start': '1990-01-01',
    'train_end': '2005-12-31',
    'val_start': '2006-01-01',
    'val_end': '2010-12-31',
    'test_start': '2011-01-01',
    'test_end': '2023-12-31',
}


def log_with_timestamp(message: str, level: str = 'INFO'):
    """Print message with timestamp."""
    ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"[{ts}] [{level}] {message}")


def cleanup_output_directory(output_dir: Path):
    """
    Clean up output directory before a new run.
    Removes all previous results to ensure clean state.
    """
    if output_dir.exists():
        log_with_timestamp(f"Cleaning output directory: {output_dir}")
        try:
            for item in output_dir.iterdir():
                if item.is_dir():
                    shutil.rmtree(item)
                else:
                    item.unlink()
            log_with_timestamp("Output directory cleaned successfully")
        except Exception as e:
            log_with_timestamp(f"Warning: Could not fully clean output: {e}", 'WARNING')


def run_pipeline(config: dict, output_dir: Path) -> Dict:
    """
    Run complete JM-XGB pipeline.
    
    Implements walk-forward validation with:
    - 11-year training window
    - 5-year validation window for lambda tuning
    - Biannual model updates
    """
    results = {}
    
    # Create directories
    figures_dir = output_dir / 'figures'
    results_dir = output_dir / 'results'
    models_dir = output_dir / 'models'
    regime_stats_dir = output_dir / 'regime_statistics'
    
    for dir_path in [figures_dir, results_dir, models_dir, regime_stats_dir]:
        dir_path.mkdir(parents=True, exist_ok=True)
    
    # Apply QUICK_MODE date overrides if enabled
    if QUICK_MODE:
        log_with_timestamp("*** QUICK MODE ENABLED - Using shortened date ranges ***", 'WARNING')
        config['data']['train_start'] = QUICK_DATES['train_start']
        config['data']['train_end'] = QUICK_DATES['train_end']
        config['data']['val_start'] = QUICK_DATES['val_start']
        config['data']['val_end'] = QUICK_DATES['val_end']
        config['data']['test_start'] = QUICK_DATES['test_start']
        config['data']['test_end'] = QUICK_DATES['test_end']
        config['data']['start_date'] = QUICK_DATES['train_start']
        config['data']['end_date'] = QUICK_DATES['test_end']
    
    mode_label = "QUICK MODE" if QUICK_MODE else "FULL MODE"
    
    print("\n" + "="*75)
    print(f"Fioracle - Fixed Income Regime-Aware Portfolio Management ({mode_label})")
    print("="*75)
    print(f"Training Period:   {config['data']['train_start']} to {config['data']['train_end']}")
    print(f"Validation Period: {config['data']['val_start']} to {config['data']['val_end']}")
    print(f"Testing Period:    {config['data']['test_start']} to {config['data']['test_end']}")
    print("="*75 + "\n")
    
    # ========================================================================
    # STEP 1: Load Full Dataset
    # ========================================================================
    
    log_with_timestamp("STEP 1/6: Loading Data")
    print("-" * 50)
    
    try:
        pipeline = DataPipeline()
        full_data = pipeline.load(
            config['data']['start_date'],
            config['data']['end_date']
        )
        
        if len(full_data) == 0:
            log_with_timestamp("No data loaded!", 'ERROR')
            return results
        
        log_with_timestamp(f"Loaded {len(full_data)} rows, {len(full_data.columns)} columns")
        log_with_timestamp(f"Date range: {full_data.index[0]} to {full_data.index[-1]}")
        
        # Get asset availability
        asset_availability = pipeline.get_asset_availability(full_data)
        log_with_timestamp(f"Asset availability tracking: {len(asset_availability)} assets")
        
        results['data_shape'] = full_data.shape
        results['date_range'] = (str(full_data.index[0]), str(full_data.index[-1]))
        
    except Exception as e:
        log_with_timestamp(f"Data loading failed: {e}", 'ERROR')
        traceback.print_exc()
        return results
    
    print()
    
    # ========================================================================
    # STEP 2: Engineer Features
    # ========================================================================
    
    log_with_timestamp("STEP 2/6: Engineering Features")
    print("-" * 50)
    
    try:
        asset_features, macro_features = engineer_features(full_data)
        
        log_with_timestamp(f"Asset features: {len(asset_features)} assets")
        log_with_timestamp(f"Macro features: {len(macro_features.columns)} features")
        
        if len(asset_features) == 0:
            log_with_timestamp("No asset features computed!", 'ERROR')
            return results
        
        # Show feature names
        sample_asset = list(asset_features.keys())[0]
        log_with_timestamp(f"Features per asset: {list(asset_features[sample_asset].columns)}")
        
        results['n_assets'] = len(asset_features)
        results['n_macro_features'] = len(macro_features.columns)
        
    except Exception as e:
        log_with_timestamp(f"Feature engineering failed: {e}", 'ERROR')
        traceback.print_exc()
        return results
    
    print()
    
    # ========================================================================
    # STEP 3: Build Asset Returns
    # ========================================================================
    
    log_with_timestamp("STEP 3/6: Building Asset Returns")
    print("-" * 50)
    
    try:
        # Extract risk-free rate from ANCILLARY data (NOT an investable asset!)
        # RF data is a TOTAL RETURN INDEX (starts at 100), use pct_change() for daily returns
        rf_col = [c for c in full_data.columns if 'ancillary_risk_free' in c.lower()]
        if rf_col:
            rf_index = full_data[rf_col[0]]
            risk_free_rate = rf_index.pct_change()
            # Forward-fill short gaps (weekends/holidays), don't assume 0 for missing data
            risk_free_rate = risk_free_rate.ffill(limit=5)
            rf_mean = risk_free_rate.dropna().mean()
            log_with_timestamp(f"Using ancillary risk-free rate (mean daily: {rf_mean*100:.6f}%)")
        else:
            log_with_timestamp("No risk-free rate found in ancillary data", 'WARNING')
            risk_free_rate = pd.Series(dtype=float, index=full_data.index)  # NaN series, not zeros
        
        # Build INVESTABLE set from config (these ALWAYS take priority)
        investable_assets = set()
        for inv in config['assets'].get('investable', []):
            inv_clean = inv.replace('.csv', '').replace('_TOTAL_RETURN', '').replace('_RETURN', '').upper()
            investable_assets.add(inv_clean)
            investable_assets.add(inv.replace('.csv', '').upper())
        
        # Build EXCLUDED list from config (but investable takes priority!)
        excluded_assets = set()
        for excl in config['assets'].get('excluded', []):
            excl_clean = excl.replace('.csv', '').replace('_TOTAL_RETURN', '').replace('_RETURN', '').upper()
            # Only add to excluded if NOT in investable list
            if excl_clean not in investable_assets and excl.replace('.csv', '').upper() not in investable_assets:
                excluded_assets.add(excl_clean)
                excluded_assets.add(excl.replace('.csv', '').upper())
        
        # NEVER include ancillary data as investable (unless explicitly in investable)
        ancillary_exclusions = {
            'SP500_TOTAL_RETURN', 'SP500',
            'US_RISK_FREE_RATE', 'RISK_FREE_RATE',
            'YIELD_2Y', 'YIELD_SLOPE',
            'ANCILLARY_SP500', 'ANCILLARY_RISK_FREE_RATE',
            'ANCILLARY_YIELD_2Y', 'ANCILLARY_YIELD_SLOPE',
        }
        # Only add ancillary exclusions if not in investable
        for anc in ancillary_exclusions:
            if anc not in investable_assets:
                excluded_assets.add(anc)
        
        log_with_timestamp(f"Investable assets from config: {sorted(investable_assets)}")
        log_with_timestamp(f"Excluded from portfolio: {sorted(excluded_assets)}")
        
        # Build returns DataFrame - ONLY asset_ columns (NOT ancillary_ or macro_)
        asset_returns = {}
        
        for col in full_data.columns:
            # Only process asset_ columns
            if not col.startswith('asset_'):
                continue
            
            # Use RAW returns (not excess) - RF subtraction happens in metrics
            asset_return = full_data[col].pct_change()
            
            # Clean asset name
            asset_name = col.replace('asset_', '').upper()
            
            # PRIORITY CHECK: If asset is in investable list, INCLUDE it
            # Otherwise, check if it's in excluded list
            is_investable = asset_name in investable_assets
            is_excluded = asset_name in excluded_assets
            
            if is_excluded and not is_investable:
                # Only skip if excluded AND not explicitly investable
                continue
            
            # Only include if we have features for this asset
            if asset_name in asset_features:
                asset_returns[asset_name] = asset_return
            elif is_investable:
                # Even without features, include investable assets for returns
                asset_returns[asset_name] = asset_return
        
        returns_df = pd.DataFrame(asset_returns)
        
        # Align with features
        common_idx = returns_df.index.intersection(macro_features.index)
        returns_df = returns_df.loc[common_idx]
        # Align RF and forward-fill short gaps, but don't assume 0 for truly missing data
        risk_free_rate = risk_free_rate.reindex(common_idx).ffill(limit=5)
        
        log_with_timestamp(f"Returns shape: {returns_df.shape}")
        log_with_timestamp(f"Assets: {list(returns_df.columns)[:5]}...")
        
        results['assets'] = list(returns_df.columns)
        
    except Exception as e:
        log_with_timestamp(f"Returns building failed: {e}", 'ERROR')
        traceback.print_exc()
        return results
    
    print()
    
    # ========================================================================
    # STEP 4: Train Models on Training Data ONLY (No Look-Ahead)
    # ========================================================================
    
    log_with_timestamp("STEP 4/6: Training Models on Training Data (NO Look-Ahead)")
    print("-" * 50)
    
    # =========================================================================
    # TEMPORAL BOUNDARIES - Explicit logging for audit transparency
    # =========================================================================
    train_start = pd.Timestamp(config['data']['train_start'])
    train_end = pd.Timestamp(config['data']['train_end'])
    val_start = pd.Timestamp(config['data']['val_start'])
    val_end = pd.Timestamp(config['data']['val_end'])
    test_start = pd.Timestamp(config['data']['test_start'])
    test_end = pd.Timestamp(config['data']['test_end'])
    
    log_with_timestamp("TEMPORAL BOUNDARIES (No Look-Ahead Guarantee):")
    log_with_timestamp(f"  TRAIN:      {train_start.date()} to {train_end.date()} (JM fitting, XGB training, λ tuning)")
    log_with_timestamp(f"  VALIDATION: {val_start.date()} to {val_end.date()} (hyperparameter selection)")
    log_with_timestamp(f"  TEST:       {test_start.date()} to {test_end.date()} (out-of-sample evaluation)")
    if config.get('regimes', {}).get('rolling', {}).get('enabled', False):
        rolling_cfg = config['regimes']['rolling']
        log_with_timestamp(f"  WALK-FORWARD: {rolling_cfg.get('training_years', 10)}yr train, "
                          f"{rolling_cfg.get('validation_years', 2)}yr val, "
                          f"{rolling_cfg.get('update_frequency_months', 6)}mo updates")
    print("-" * 50)
    
    # Filter training data
    train_mask = (returns_df.index >= train_start) & (returns_df.index <= train_end)
    train_returns = returns_df.loc[train_mask]
    train_macro = macro_features.loc[train_mask]
    train_rf = risk_free_rate.loc[train_mask]
    
    train_asset_features = {}
    for asset_name, features in asset_features.items():
        # Skip excluded assets (SP500, etc.) - only train on investable assets
        if asset_name in excluded_assets:
            continue
        train_feat = features.loc[train_mask]
        if len(train_feat.dropna()) > 100:
            train_asset_features[asset_name] = train_feat
    
    log_with_timestamp(f"Training data: {len(train_returns)} days, {len(train_asset_features)} assets")
    
    # Lambda tuning on training data
    lambda_candidates = config['regimes']['jump_model']['lambda_candidates']
    lambda_jump = config['regimes']['jump_model']['default_lambda']
    
    if TUNE_LAMBDA:
        log_with_timestamp("Tuning lambda on training data...")
        try:
            evaluator = Evaluator(transaction_cost=config['portfolio']['transaction_cost'])
            first_asset = list(train_asset_features.keys())[0]
            if first_asset in train_returns.columns:
                optimal_lambda, _ = evaluator.tune_lambda_fast(
                    train_asset_features[first_asset],
                    train_returns[first_asset],
                    lambda_candidates=lambda_candidates,
                    n_splits=5
                )
                lambda_jump = optimal_lambda
                log_with_timestamp(f"Optimal λ: {lambda_jump:.2f}")
        except Exception as e:
            log_with_timestamp(f"Lambda tuning failed: {e}", 'WARNING')
    
    # Train regime engine on training data ONLY
    log_with_timestamp(f"Training regime engine (λ={lambda_jump})...")
    regime_engine = RegimeEngine(
        lambda_jump=lambda_jump,
        n_macro_regimes=config['regimes']['hmm']['n_states'],
        xgb_params=config['regimes'].get('xgboost', {}),
        config=config
    )
    
    training_regime_results = regime_engine.fit_identify_forecast(
        asset_features_dict=train_asset_features,
        asset_returns_df=train_returns,
        macro_features=train_macro,
        train_forecasters=TRAIN_FORECASTERS,
        verbose=VERBOSE
    )
    
    trained_regimes_df = pd.DataFrame(training_regime_results['asset_regimes'])
    log_with_timestamp(f"Trained models on {len(trained_regimes_df.columns)} assets")
    
    results['trained_lambda'] = lambda_jump
    results['trained_assets'] = list(trained_regimes_df.columns)
    
    print()
    
    # ========================================================================
    # STEP 5: Evaluate on All Splits
    # For test split: use walk-forward validation if enabled
    # For train/val: use pre-trained models
    # ========================================================================
    
    # Check if walk-forward is enabled
    walk_forward_enabled = config.get('regimes', {}).get('rolling', {}).get('enabled', False)
    training_years = config.get('regimes', {}).get('rolling', {}).get('training_years', 11)
    validation_years = config.get('regimes', {}).get('rolling', {}).get('validation_years', 5)
    update_months = config.get('regimes', {}).get('rolling', {}).get('update_frequency_months', 6)
    
    for split_name in SPLITS:
        log_with_timestamp(f"STEP 5/6: Evaluating {split_name.upper()} Split")
        print("-" * 50)
        
        try:
            # Use walk-forward for test split if enabled
            if split_name == 'test' and walk_forward_enabled:
                log_with_timestamp("Using WALK-FORWARD validation (biannual model updates)")
                from core.regimes import rolling_regime_forecasting
                
                test_start = pd.Timestamp(config['data']['test_start'])
                test_end = pd.Timestamp(config['data']['test_end'])
                
                # Run walk-forward regime forecasting
                wf_forecasts, wf_probs, wf_lambdas = rolling_regime_forecasting(
                    asset_features_dict=asset_features,
                    asset_returns_df=returns_df,
                    macro_features=macro_features,
                    start_date=test_start,
                    end_date=test_end,
                    training_years=training_years,
                    validation_years=validation_years,
                    update_frequency_months=update_months,
                    lambda_candidates=config['regimes']['jump_model']['lambda_candidates'],
                    config=config,
                    verbose=VERBOSE
                )
                
                # Convert forecasts to DataFrame
                wf_regimes_df = pd.DataFrame(wf_forecasts)
                
                log_with_timestamp(f"Walk-forward completed: {len(wf_lambdas)} updates")
                
                # Run portfolio optimization with walk-forward forecasts
                split_results = run_split_with_trained_model(
                    split_name=split_name,
                    config=config,
                    asset_features=asset_features,
                    macro_features=macro_features,
                    returns_df=returns_df,
                    risk_free_rate=risk_free_rate,
                    regime_engine=regime_engine,
                    trained_regimes_df=wf_regimes_df,  # Use walk-forward forecasts
                    output_dir=output_dir,
                    excluded_assets=excluded_assets
                )
                
                # Save walk-forward statistics
                results['walk_forward_updates'] = wf_lambdas
            else:
                # Standard evaluation with pre-trained model
                split_results = run_split_with_trained_model(
                    split_name=split_name,
                    config=config,
                    asset_features=asset_features,
                    macro_features=macro_features,
                    returns_df=returns_df,
                    risk_free_rate=risk_free_rate,
                    regime_engine=regime_engine,
                    trained_regimes_df=trained_regimes_df,
                    output_dir=output_dir,
                    excluded_assets=excluded_assets
                )
            
            results[split_name] = split_results
            
        except Exception as e:
            log_with_timestamp(f"{split_name} split failed: {e}", 'ERROR')
            traceback.print_exc()
            results[split_name] = {'error': str(e)}
        
        print()
    
    # ========================================================================
    # STEP 6: Generate Regime Drivers Visualization
    # ========================================================================
    
    log_with_timestamp("STEP 6/6: Generating Regime Drivers Visualization")
    print("-" * 50)
    
    try:
        from visualizations.regime_drivers import visualize_regime_drivers
        
        regime_analysis_dir = output_dir / 'figures' / 'regime_analysis'
        visualize_regime_drivers(
            start_date=config['data']['train_start'],
            end_date=config['data']['test_end'],
            output_dir=str(regime_analysis_dir),
            show_plot=False
        )
        log_with_timestamp(f"Regime drivers saved to {regime_analysis_dir}")
    except Exception as e:
        log_with_timestamp(f"Regime drivers visualization failed: {e}", 'WARNING')
        traceback.print_exc()
    
    # ========================================================================
    # STEP 6b: Generate Historical Time Series Visualization
    # ========================================================================
    
    log_with_timestamp("Generating Historical Time Series Visualization")
    
    try:
        from visualizations.historical_series import (
            create_combined_timeseries_plot,
            create_regime_prediction_timeline
        )
        
        historical_dir = output_dir / 'figures' / 'historical'
        historical_dir.mkdir(parents=True, exist_ok=True)
        
        # Combined time series (asset returns + macro indicators)
        create_combined_timeseries_plot(
            output_dir=str(historical_dir),
            start_date=config['data']['train_start'],
            end_date=config['data']['test_end']
        )
        
        # Regime prediction timeline (Jump Model vs XGBoost)
        create_regime_prediction_timeline(
            output_dir=str(historical_dir),
            start_date=config['data']['train_start'],
            end_date=config['data']['test_end']
        )
        
        log_with_timestamp(f"Historical visualizations saved to {historical_dir}")
    except Exception as e:
        log_with_timestamp(f"Historical visualization failed: {e}", 'WARNING')
        traceback.print_exc()
    
    print()
    
    # ========================================================================
    # STEP 7: Summary
    # ========================================================================
    
    log_with_timestamp("STEP 7/7: Generating Summary")
    print("-" * 50)
    
    try:
        summary = generate_summary(results, results_dir)
        log_with_timestamp(f"Summary saved to {results_dir / 'pipeline_summary.json'}")
    except Exception as e:
        log_with_timestamp(f"Summary generation failed: {e}", 'WARNING')
    
    print()
    
    # ========================================================================
    # STEP 6: Final Report
    # ========================================================================
    
    print("="*75)
    print("PIPELINE COMPLETE")
    print("="*75)
    print(f"\nOutputs saved to: {output_dir}/")
    print("\nGenerated files:")
    
    for f in sorted(output_dir.rglob('*')):
        if f.is_file():
            rel_path = f.relative_to(output_dir)
            size_kb = f.stat().st_size / 1024
            print(f"  ✓ {rel_path} ({size_kb:.1f} KB)")
    
    print("="*75 + "\n")
    
    return results


def run_split_with_trained_model(
    split_name: str,
    config: dict,
    asset_features: Dict[str, pd.DataFrame],
    macro_features: pd.DataFrame,
    returns_df: pd.DataFrame,
    risk_free_rate: pd.Series,
    regime_engine: RegimeEngine,
    trained_regimes_df: pd.DataFrame,
    output_dir: Path,
    excluded_assets: set = None
) -> Dict:
    """
    Run evaluation on a split using PRE-TRAINED models (NO look-ahead bias).
    
    For training split: Uses the regimes identified during training
    For val/test splits: Uses classifiers trained on training data to make predictions
    """
    
    split_dates = {
        'train': (config['data']['train_start'], config['data']['train_end']),
        'val': (config['data']['val_start'], config['data']['val_end']),
        'test': (config['data']['test_start'], config['data']['test_end']),
    }
    
    start_date, end_date = split_dates[split_name]
    start_ts = pd.Timestamp(start_date)
    end_ts = pd.Timestamp(end_date)
    
    log_with_timestamp(f"Date range: {start_date} to {end_date}")
    
    # Create split directories
    figures_dir = output_dir / 'figures' / split_name
    results_dir = output_dir / 'results' / split_name
    models_dir = output_dir / 'models' / split_name
    regime_stats_dir = output_dir / 'regime_statistics' / split_name
    
    for dir_path in [figures_dir, results_dir, models_dir, regime_stats_dir]:
        dir_path.mkdir(parents=True, exist_ok=True)
    
    split_results = {}
    
    # Filter data to split period
    mask = (returns_df.index >= start_ts) & (returns_df.index <= end_ts)
    split_returns = returns_df.loc[mask]
    split_macro = macro_features.loc[mask]
    split_rf = risk_free_rate.loc[mask]
    
    # Filter asset features (exclude non-investable assets)
    # Build investable set from config for priority checking
    investable_set = set()
    for inv in config.get('assets', {}).get('investable', []):
        inv_clean = inv.replace('.csv', '').replace('_TOTAL_RETURN', '').replace('_RETURN', '').upper()
        investable_set.add(inv_clean)
        investable_set.add(inv.replace('.csv', '').upper())
    
    if excluded_assets is None:
        excluded_assets = {'SP500_TOTAL_RETURN', 'SP500', 'US_RISK_FREE_RATE'}
    
    split_asset_features = {}
    for asset_name, features in asset_features.items():
        # Investable assets are NEVER excluded
        is_investable = asset_name in investable_set
        if asset_name in excluded_assets and not is_investable:
            continue
        split_feat = features.loc[mask]
        if len(split_feat.dropna()) > 50:  # Lower threshold for val/test
            split_asset_features[asset_name] = split_feat
    
    log_with_timestamp(f"Split data: {len(split_returns)} rows, {len(split_asset_features)} assets")
    
    if len(split_returns) < 100:
        log_with_timestamp("Insufficient data for split", 'WARNING')
        return split_results
    
    # ========================================================================
    # Generate Regime Forecasts using PRE-TRAINED Models
    # ========================================================================
    
    if split_name == 'train':
        # For training: use the regimes already identified (filter by date range)
        train_regime_mask = (trained_regimes_df.index >= start_ts) & (trained_regimes_df.index <= end_ts)
        regimes_df = trained_regimes_df.loc[train_regime_mask]
        log_with_timestamp(f"Using pre-identified training regimes for {len(regimes_df.columns)} assets")
    else:
        # For val/test: generate TRUE out-of-sample predictions
        log_with_timestamp("Generating out-of-sample regime predictions...")
        
        regimes_dict = {}
        for asset_name in split_asset_features.keys():
            if asset_name not in regime_engine.classifiers:
                # Fallback: use JM on this data (but with pre-tuned lambda)
                continue
            
            try:
                # Get features and macro for prediction
                asset_feat = split_asset_features[asset_name]
                common_idx = asset_feat.index.intersection(split_macro.index)
                
                # Build feature matrix for prediction
                X_pred = pd.DataFrame(index=common_idx)
                for col in asset_feat.columns:
                    X_pred[col] = asset_feat.loc[common_idx, col]
                for col in split_macro.columns:
                    X_pred[f'macro_{col}'] = split_macro.loc[common_idx, col]
                
                X_pred = X_pred.dropna()
                
                if len(X_pred) < 10:
                    continue
                
                # Get predictions from trained classifier
                model = regime_engine.classifiers[asset_name]
                probs_all = model.predict_proba(X_pred.values)  # Shape: (n_samples, n_classes)
                
                # Get number of states from config (default 3)
                n_states = config.get('regimes', {}).get('jump_model', {}).get('n_states', 3)
                
                # Apply smoothing to full probability matrix
                halflife = regime_engine.halflives.get(asset_name, 0)
                if halflife > 0:
                    alpha = 1 - np.exp(-np.log(2) / halflife)
                    probs_df = pd.DataFrame(probs_all, index=X_pred.index)
                    probs_smooth = probs_df.ewm(alpha=alpha, adjust=False).mean()
                else:
                    probs_smooth = pd.DataFrame(probs_all, index=X_pred.index)
                
                # Use argmax for 3-state regimes (0=calm, 1=inflationary, 2=crisis)
                # This preserves all 3 states instead of collapsing to binary
                regimes_dict[asset_name] = probs_smooth.values.argmax(axis=1)
                regimes_dict[asset_name] = pd.Series(regimes_dict[asset_name], index=X_pred.index)
                
            except Exception as e:
                log_with_timestamp(f"  {asset_name} prediction failed: {e}", 'WARNING')
        
        regimes_df = pd.DataFrame(regimes_dict)
        log_with_timestamp(f"Generated predictions for {len(regimes_df.columns)} assets")
    
    if len(regimes_df.columns) == 0:
        log_with_timestamp("No regime predictions available", 'WARNING')
        return split_results
    
    # Save regime results
    regimes_df.to_csv(results_dir / 'asset_regimes.csv')
    
    # Compute regime statistics (3-state: calm/inflationary/crisis)
    regime_stats = {}
    n_states = config.get('regimes', {}).get('jump_model', {}).get('n_states', 3)
    for asset in regimes_df.columns:
        regimes = regimes_df[asset].dropna()
        if len(regimes) > 0:
            n_calm = (regimes == 0).sum()          # Calm/Bullish
            n_inflationary = (regimes == 1).sum()  # Inflationary/Neutral
            n_crisis = (regimes == 2).sum()        # Crisis/Bearish
            n_switches = (regimes.diff() != 0).sum()
            
            regime_stats[asset] = {
                'calm_days': int(n_calm),
                'inflationary_days': int(n_inflationary),
                'crisis_days': int(n_crisis),
                'calm_pct': f"{n_calm/len(regimes)*100:.1f}%",
                'inflationary_pct': f"{n_inflationary/len(regimes)*100:.1f}%",
                'crisis_pct': f"{n_crisis/len(regimes)*100:.1f}%",
                'n_switches': int(n_switches),
                'n_states': n_states
            }
    
    with open(regime_stats_dir / 'regime_statistics.json', 'w') as f:
        json.dump(regime_stats, f, indent=2)
    
    split_results['regime_stats'] = regime_stats
    
    # ========================================================================
    # Portfolio Optimization
    # ========================================================================
    
    log_with_timestamp("Running portfolio optimization...")
    
    # For portfolio: regime forecasts = current regimes shifted forward 1 day
    regime_forecasts_df = regimes_df.shift(1).bfill()
    
    all_portfolio_results = {}
    
    for strategy in PORTFOLIO_STRATEGIES:
        log_with_timestamp(f"  Strategy: {strategy.upper()} (JM-XGB)")
        
        try:
            portfolio_engine = PortfolioEngine(
                gamma_risk=config['portfolio']['gamma_risk'],
                gamma_trade=config['portfolio']['gamma_trade'],
                transaction_cost=config['portfolio']['transaction_cost'],
                min_bullish_assets=config['portfolio'].get('min_bullish_assets', 3),
                max_weight=config['portfolio']['max_weight'],
                covariance_halflife=config['portfolio'].get('covariance_halflife', 252),
                lookback_years=TRAINING_YEARS,
                bearish_return_cap=config['portfolio'].get('bearish_return_cap', -0.001),
                bullish_return_minvar=config['portfolio'].get('bullish_return_minvar', 0.001),
                strategy=strategy.upper(),
                config=config
            )
            
            # Enable regime mixing by providing the regime engine and features
            # This allows soft regime transitions using XGBoost probability outputs
            if config.get('portfolio', {}).get('regime_mixing', {}).get('enabled', False):
                portfolio_engine.set_regime_engine(regime_engine, split_asset_features)
            
            backtest_results = portfolio_engine.backtest(
                returns_df=split_returns,
                regimes_df=regimes_df,
                regime_forecasts_df=regime_forecasts_df,
                start_date=start_ts,
                end_date=end_ts,
                verbose=True,
                macro_features=split_macro,  # For macro-conditioned mu in MV strategy
                risk_free_rate=split_rf  # For excess return calculation
            )
            
            all_portfolio_results[strategy] = backtest_results
            
            # Save results
            strategy_dir = results_dir / strategy
            strategy_dir.mkdir(exist_ok=True)
            
            backtest_results['portfolio_weights'].to_csv(strategy_dir / 'portfolio_weights.csv')
            backtest_results['portfolio_returns'].to_csv(strategy_dir / 'portfolio_returns.csv')
            
            log_with_timestamp(f"    ✓ {len(backtest_results['portfolio_returns'])} trading days")
            
        except Exception as e:
            log_with_timestamp(f"    ✗ {strategy} failed: {e}", 'WARNING')
            traceback.print_exc()
    
    # ========================================================================
    # Performance Evaluation
    # ========================================================================
    
    log_with_timestamp("Evaluating performance...")
    
    evaluator = Evaluator(
        annualization_factor=252,
        transaction_cost=config['portfolio']['transaction_cost']
    )
    
    # Build multiple benchmarks (EW + 60/40 + Barbell + Diversified Core)
    from core.evaluation import build_all_benchmarks, generate_benchmark_comparison_report
    benchmarks = build_all_benchmarks(split_returns, config)
    
    # Default benchmark for backward compatibility
    if benchmarks:
        primary_benchmark_name = list(benchmarks.keys())[0]
        benchmark_returns = benchmarks[primary_benchmark_name]
        benchmark_name = primary_benchmark_name
    else:
        available_assets = [c for c in split_returns.columns if not split_returns[c].isna().all()]
        benchmark_returns = split_returns[available_assets].mean(axis=1) if len(available_assets) >= 2 else split_returns.mean(axis=1)
        benchmark_name = "EW Buy-and-Hold"
        benchmarks = {benchmark_name: benchmark_returns}
    
    log_with_timestamp(f"Benchmarks: {list(benchmarks.keys())}")
    
    all_metrics = {}
    
    for strategy, backtest_results in all_portfolio_results.items():
        try:
            portfolio_returns = backtest_results['portfolio_returns']
            portfolio_weights = backtest_results['portfolio_weights']
            
            if len(portfolio_returns) == 0:
                continue
            
            # Evaluate against all benchmarks
            strategy_metrics = {}
            for bench_name, bench_rets in benchmarks.items():
                metrics = evaluator.compute_portfolio_metrics(
                    portfolio_returns=portfolio_returns,
                    portfolio_weights=portfolio_weights,
                    benchmark_returns=bench_rets,
                    risk_free_rate=split_rf
                )
                strategy_metrics[bench_name] = metrics
            
            # Use primary benchmark for summary
            metrics = strategy_metrics[primary_benchmark_name]
            all_metrics[strategy] = {
                'primary': metrics,
                'all_benchmarks': strategy_metrics
            }
            
            # Print key metrics
            log_with_timestamp(f"  {strategy.upper()}: Sharpe={metrics['sharpe_ratio']:.2f}, "
                             f"MDD={metrics['max_drawdown']*100:.1f}%, "
                             f"TotalRet={metrics['total_return']*100:.1f}%")
            
            # Save metrics
            strategy_dir = results_dir / strategy
            with open(strategy_dir / 'performance_metrics.json', 'w') as f:
                json.dump({k: float(v) if isinstance(v, (int, float, np.floating)) else v 
                          for k, v in metrics.items()}, f, indent=2)
            
            # Generate benchmark comparison report
            try:
                generate_benchmark_comparison_report(
                    portfolio_returns=portfolio_returns,
                    portfolio_weights=portfolio_weights,
                    benchmarks=benchmarks,
                    strategy_name=f"{strategy.upper()} (JM-XGB)",
                    save_dir=str(strategy_dir),
                    risk_free_rate=split_rf
                )
            except Exception as e:
                log_with_timestamp(f"Benchmark comparison failed: {e}", 'WARNING')
            
            # Generate separate plots (with all benchmarks)
            evaluator.generate_all_plots(
                portfolio_returns=portfolio_returns,
                portfolio_weights=portfolio_weights,
                benchmark_returns=benchmark_returns,
                benchmark_name=benchmark_name,
                strategy_name=f"{strategy.upper()} (JM-XGB)",
                save_dir=str(figures_dir / strategy),
                all_benchmarks=benchmarks
            )
            
        except Exception as e:
            log_with_timestamp(f"  {strategy} evaluation failed: {e}", 'WARNING')
            traceback.print_exc()
    
    split_results['metrics'] = all_metrics
    
    # ========================================================================
    # VIX Effectiveness Analysis
    # ========================================================================
    
    log_with_timestamp("Running VIX effectiveness analysis...")
    
    try:
        from visualizations.vix_analysis import analyze_vix_effectiveness
        
        # Get VIX data from macro features
        vix_col = [c for c in split_macro.columns if 'vix' in c.lower()]
        if vix_col and len(all_portfolio_results) > 0:
            vix_data = split_macro[vix_col[0]]
            
            # Get best performing strategy based on total return
            best_strategy = max(all_metrics.keys(), 
                              key=lambda k: all_metrics[k]['primary'].get('total_return', 0)
                              if isinstance(all_metrics[k], dict) and 'primary' in all_metrics[k] 
                              else all_metrics[k].get('total_return', 0))
            
            backtest = all_portfolio_results[best_strategy]
            
            # Build dict of all strategy returns for VIX analysis
            all_strategy_returns = {
                k: v['portfolio_returns'] 
                for k, v in all_portfolio_results.items()
                if 'portfolio_returns' in v
            }
            
            vix_results = analyze_vix_effectiveness(
                portfolio_returns=backtest['portfolio_returns'],
                benchmark_returns=benchmark_returns,
                vix_data=vix_data,
                weights_df=backtest['portfolio_weights'],
                regimes_df=regimes_df,
                output_dir=str(figures_dir / 'vix_analysis'),
                strategy_name=f"{best_strategy.upper()} (JM-XGB)",
                all_strategy_returns=all_strategy_returns
            )
            
            split_results['vix_analysis'] = vix_results
            log_with_timestamp("VIX analysis complete")
        else:
            log_with_timestamp("VIX data not available", 'WARNING')
    except Exception as e:
        log_with_timestamp(f"VIX analysis failed: {e}", 'WARNING')
    
    # ========================================================================
    # XGBoost Diagnostics (SHAP, Feature Importance, Baselines)
    # ========================================================================
    
    diag_cfg = config.get('regimes', {}).get('diagnostics', {})
    if diag_cfg.get('enabled', False) and hasattr(regime_engine, 'classifiers'):
        log_with_timestamp("Running XGBoost diagnostics...")
        
        try:
            from core.diagnostics import (
                run_full_diagnostics, save_diagnostics_summary, 
                plot_feature_importance_comparison
            )
            
            diag_dir = figures_dir / 'xgb_diagnostics'
            diag_dir.mkdir(parents=True, exist_ok=True)
            
            all_diag_results = {}
            
            # Run diagnostics for each asset
            for asset_name in split_asset_features.keys():
                if asset_name not in regime_engine.classifiers:
                    continue
                
                try:
                    asset_feat = split_asset_features[asset_name]
                    common_idx = asset_feat.index.intersection(split_macro.index)
                    
                    # Build feature matrix
                    X_full = pd.DataFrame(index=common_idx)
                    for col in asset_feat.columns:
                        X_full[col] = asset_feat.loc[common_idx, col]
                    for col in split_macro.columns:
                        X_full[f'macro_{col}'] = split_macro.loc[common_idx, col]
                    
                    X_full = X_full.dropna()
                    
                    if len(X_full) < 100:
                        continue
                    
                    # Get regimes - defensive handling for assets with incomplete data
                    if asset_name in regimes_df.columns:
                        regime_col = regimes_df[asset_name]
                        # Ensure we have a Series, not DataFrame (can happen with duplicate columns)
                        if isinstance(regime_col, pd.DataFrame):
                            regime_col = regime_col.iloc[:, 0]
                        y_full = regime_col.reindex(X_full.index).dropna()
                        # Ensure y_full is 1D
                        if hasattr(y_full, 'ndim') and y_full.ndim > 1:
                            y_full = y_full.iloc[:, 0] if isinstance(y_full, pd.DataFrame) else pd.Series(y_full.ravel())
                        X_full = X_full.loc[y_full.index]
                    else:
                        continue
                    
                    # Skip if insufficient data after regime alignment
                    if len(y_full) < 100:
                        log_with_timestamp(f"  Skipping {asset_name}: insufficient regime data ({len(y_full)} rows)", 'WARNING')
                        continue
                    
                    # Split
                    split_point = int(len(X_full) * 0.8)
                    X_train = X_full.iloc[:split_point]
                    X_test = X_full.iloc[split_point:]
                    y_train = y_full.iloc[:split_point]
                    y_test = y_full.iloc[split_point:]
                    
                    # Get returns for conditional analysis
                    if asset_name in split_returns.columns:
                        asset_returns = split_returns[asset_name]
                    else:
                        asset_returns = pd.Series()
                    
                    diag_results = run_full_diagnostics(
                        regime_engine=regime_engine,
                        asset_name=asset_name,
                        X_train=X_train,
                        X_test=X_test,
                        y_train=y_train,
                        y_test=y_test,
                        returns=asset_returns,
                        output_dir=diag_dir,
                        config=config
                    )
                    all_diag_results[asset_name] = diag_results
                    
                except Exception as e:
                    log_with_timestamp(f"  Diagnostics for {asset_name} failed: {e}", 'WARNING')
            
            # Save aggregate results
            if all_diag_results:
                save_diagnostics_summary(all_diag_results, output_dir, split_name)
                plot_feature_importance_comparison(all_diag_results, diag_dir)
                split_results['xgb_diagnostics'] = all_diag_results
                log_with_timestamp(f"  Diagnostics complete for {len(all_diag_results)} assets")
            
        except Exception as e:
            log_with_timestamp(f"XGBoost diagnostics failed: {e}", 'WARNING')
            traceback.print_exc()
    
    # ========================================================================
    # Advanced Analytics (Fat Tails, Correlation Regimes)
    # ========================================================================
    
    if config.get('regimes', {}).get('diagnostics', {}).get('enabled', False):
        log_with_timestamp("Running advanced analytics...")
        
        try:
            from visualizations.advanced_analytics import (
                generate_fat_tail_analysis,
                generate_correlation_regime_analysis,
                generate_statistical_tests
            )
            
            # Use best strategy for analysis
            if all_metrics and all_portfolio_results:
                best_strategy = max(all_metrics.keys(), 
                                  key=lambda k: all_metrics[k].get('sharpe_ratio', 0) 
                                  if isinstance(all_metrics[k], dict) else 0)
                backtest = all_portfolio_results[best_strategy]
                
                analytics_dir = figures_dir / 'advanced_analytics'
                analytics_dir.mkdir(parents=True, exist_ok=True)
                
                # Fat tail analysis
                fat_tail_results = generate_fat_tail_analysis(
                    returns=backtest['portfolio_returns'],
                    regimes=regimes_df.iloc[:, 0] if len(regimes_df.columns) > 0 else None,
                    output_dir=str(analytics_dir),
                    strategy_name=f"{best_strategy.upper()}"
                )
                split_results['fat_tail_analysis'] = fat_tail_results
                
                # Statistical tests vs benchmark
                stat_tests = generate_statistical_tests(
                    portfolio_returns=backtest['portfolio_returns'],
                    benchmark_returns=benchmark_returns,
                    output_dir=str(analytics_dir)
                )
                split_results['statistical_tests'] = stat_tests
                
                log_with_timestamp("Advanced analytics complete")
        except Exception as e:
            log_with_timestamp(f"Advanced analytics failed: {e}", 'WARNING')
            traceback.print_exc()
    
    # ========================================================================
    # Tail Hedge Analysis
    # ========================================================================
    
    tail_hedge_cfg = config.get('portfolio', {}).get('tail_hedges', {})
    if tail_hedge_cfg.get('enabled', False):
        log_with_timestamp("Running tail hedge analysis...")
        
        try:
            from visualizations.tail_hedge_analysis import analyze_tail_hedges
            
            if all_portfolio_results:
                best_strategy = max(all_metrics.keys(), 
                                  key=lambda k: all_metrics[k].get('sharpe_ratio', 0)
                                  if isinstance(all_metrics[k], dict) else 0)
                backtest = all_portfolio_results[best_strategy]
                
                tail_dir = figures_dir / 'tail_hedge'
                tail_dir.mkdir(parents=True, exist_ok=True)
                
                tail_results = analyze_tail_hedges(
                    portfolio_returns=backtest['portfolio_returns'],
                    portfolio_weights=backtest['portfolio_weights'],
                    asset_returns=split_returns,
                    regime_series=regimes_df.iloc[:, 0] if len(regimes_df.columns) > 0 else None,
                    config=config,
                    output_dir=tail_dir,
                    split_name=split_name
                )
                split_results['tail_hedge_analysis'] = tail_results
                log_with_timestamp("Tail hedge analysis complete")
        except Exception as e:
            log_with_timestamp(f"Tail hedge analysis failed: {e}", 'WARNING')
            traceback.print_exc()
    
    # ========================================================================
    # Robustness Grid (if enabled)
    # ========================================================================
    
    robustness_cfg = config.get('portfolio', {}).get('robustness_grid', {})
    if robustness_cfg.get('enabled', False):
        log_with_timestamp("Running robustness grid analysis...")
        
        try:
            from visualizations.robustness_grid import evaluate_gamma_grid
            
            robustness_dir = figures_dir / 'robustness'
            robustness_dir.mkdir(parents=True, exist_ok=True)
            
            robustness_results = evaluate_gamma_grid(
                config=config,
                returns_df=split_returns,
                regime_forecasts_df=regimes_df,
                macro_features=split_macro,
                regimes_df=regimes_df,
                split_name=split_name,
                output_dir=robustness_dir,
                risk_free_rate=split_rf
            )
            split_results['robustness_grid'] = robustness_results.to_dict() if robustness_results is not None else {}
            log_with_timestamp("Robustness grid complete")
        except Exception as e:
            log_with_timestamp(f"Robustness grid failed: {e}", 'WARNING')
            traceback.print_exc()
    
    # Save summary
    with open(results_dir / 'strategy_comparison.json', 'w') as f:
        json.dump(all_metrics, f, indent=2, default=str)
    
    # ========================================================================
    # Period-Specific Analysis (Supply Shock and Financial Crisis)
    # ========================================================================
    
    if all_portfolio_results and split_name == 'test':
        log_with_timestamp("Running period-specific analysis...")
        
        try:
            from visualizations.period_analysis import (
                generate_supply_shock_analysis,
                generate_financial_crisis_analysis
            )
            
            best_strategy = max(all_metrics.keys(), 
                              key=lambda k: all_metrics[k]['primary'].get('sharpe_ratio', 0)
                              if isinstance(all_metrics[k], dict) and 'primary' in all_metrics[k] else 0)
            backtest = all_portfolio_results[best_strategy]
            
            # Supply shock analysis (2018-2022)
            if pd.Timestamp('2018-01-01') >= split_returns.index.min():
                supply_results = generate_supply_shock_analysis(
                    portfolio_returns=backtest['portfolio_returns'],
                    portfolio_weights=backtest['portfolio_weights'],
                    benchmarks=benchmarks,  # Pass all benchmarks
                    strategy_name=f"{best_strategy.upper()} (JM-XGB)",
                    output_dir=figures_dir
                )
                split_results['supply_shock_analysis'] = supply_results
                log_with_timestamp("Supply shock analysis complete")
            
            # Financial crisis analysis (2006-2010)
            if pd.Timestamp('2006-01-01') >= split_returns.index.min():
                crisis_results = generate_financial_crisis_analysis(
                    portfolio_returns=backtest['portfolio_returns'],
                    portfolio_weights=backtest['portfolio_weights'],
                    benchmarks=benchmarks,  # Pass all benchmarks
                    strategy_name=f"{best_strategy.upper()} (JM-XGB)",
                    output_dir=figures_dir
                )
                split_results['financial_crisis_analysis'] = crisis_results
                log_with_timestamp("Financial crisis analysis complete")
                
        except Exception as e:
            log_with_timestamp(f"Period analysis failed: {e}", 'WARNING')
            traceback.print_exc()
    
    return split_results


def generate_summary(results: Dict, output_dir: Path) -> Dict:
    """Generate pipeline summary."""
    summary = {
        'timestamp': datetime.now().isoformat(),
        'data_shape': results.get('data_shape'),
        'date_range': results.get('date_range'),
        'n_assets': results.get('n_assets'),
        'splits': {}
    }
    
    for split_name in SPLITS:
        if split_name in results and isinstance(results[split_name], dict):
            split_data = results[split_name]
            summary['splits'][split_name] = {
                'optimal_lambda': split_data.get('optimal_lambda'),
                'metrics': split_data.get('metrics', {})
            }
    
    with open(output_dir / 'pipeline_summary.json', 'w') as f:
        json.dump(summary, f, indent=2, default=str)
    
    return summary


def main():
    """Main entry point."""
    # Setup logging
    logger = setup_logging(level='INFO' if VERBOSE else 'WARNING')
    
    # Load config
    config = load_config(CONFIG_PATH)
    
    # Create output directory
    output_dir = Path(OUTPUT_DIR)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Clean output directory before new run
    cleanup_output_directory(output_dir)
    
    # Run pipeline
    results = run_pipeline(config, output_dir)
    
    return results


if __name__ == '__main__':
    main()
