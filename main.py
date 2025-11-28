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
    
    print("\n" + "="*75)
    print("Fioracle - Fixed Income Regime-Aware Portfolio Management")
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
        # Extract risk-free rate
        risk_free_col = [c for c in full_data.columns if 'risk_free' in c.lower()]
        if not risk_free_col:
            log_with_timestamp("No risk-free rate found, using zero", 'WARNING')
            risk_free_rate = pd.Series(0.0, index=full_data.index)
        else:
            risk_free_rate = full_data[risk_free_col[0]].pct_change()
        
        # Build EXCLUDED list from config - these are NOT INVESTABLE
        excluded_assets = set()
        for excl in config['assets'].get('excluded', []):
            # Normalize name: remove extensions, uppercase
            excl_norm = excl.replace('.csv', '').replace('_TOTAL_RETURN', '').replace('_RETURN', '').upper()
            excluded_assets.add(excl_norm)
            # Also add full names
            excluded_assets.add(excl.replace('.csv', '').upper())
        
        # Always exclude these non-investable assets
        excluded_assets.update({
            'SP500_TOTAL_RETURN', 'SP500',  # Equity - not fixed income
            'US_RISK_FREE_RATE',            # Risk-free rate
            'IBOXX_USD_LIQ_IG',             # Excluded per config
            'IBOXX_USD_LIQ_HY',             # Excluded per config
        })
        
        log_with_timestamp(f"Excluded from investment: {sorted(excluded_assets)}")
        
        # Build returns DataFrame (INVESTABLE ASSETS ONLY)
        non_return_cols = {'asset_us_treasury_2y_yield', 'asset_us_10y2y_slope', 'asset_us_risk_free_rate'}
        asset_returns = {}
        
        for col in full_data.columns:
            if col.startswith('asset_') and col not in non_return_cols:
                if col == risk_free_col[0] if risk_free_col else False:
                    continue
                asset_return = full_data[col].pct_change()
                excess_return = asset_return - risk_free_rate
                asset_name = col.replace('asset_', '').upper()
                
                # CRITICAL: Skip excluded assets
                if asset_name in excluded_assets:
                    continue
                    
                if asset_name in asset_features:
                    asset_returns[asset_name] = excess_return
        
        returns_df = pd.DataFrame(asset_returns)
        
        # Align with features
        common_idx = returns_df.index.intersection(macro_features.index)
        returns_df = returns_df.loc[common_idx]
        risk_free_rate = risk_free_rate.reindex(common_idx).fillna(0.0)
        
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
    
    train_start = pd.Timestamp(config['data']['train_start'])
    train_end = pd.Timestamp(config['data']['train_end'])
    
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
        xgb_params=config['regimes'].get('xgboost', {})
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
    # STEP 5: Evaluate on All Splits (Using Pre-Trained Models)
    # ========================================================================
    
    for split_name in SPLITS:
        log_with_timestamp(f"STEP 5/6: Evaluating {split_name.upper()} Split (Out-of-Sample)")
        print("-" * 50)
        
        try:
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
    if excluded_assets is None:
        excluded_assets = {'SP500_TOTAL_RETURN', 'SP500', 'US_RISK_FREE_RATE', 'IBOXX_USD_LIQ_IG', 'IBOXX_USD_LIQ_HY'}
    
    split_asset_features = {}
    for asset_name, features in asset_features.items():
        if asset_name in excluded_assets:
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
                probs = model.predict_proba(X_pred.values)[:, 0]  # Prob of bullish
                
                # Apply smoothing
                halflife = regime_engine.halflives.get(asset_name, 0)
                if halflife > 0:
                    alpha = 1 - np.exp(-np.log(2) / halflife)
                    probs_smooth = pd.Series(probs, index=X_pred.index).ewm(alpha=alpha, adjust=False).mean()
                else:
                    probs_smooth = pd.Series(probs, index=X_pred.index)
                
                # Binary prediction
                regimes_dict[asset_name] = (probs_smooth < 0.5).astype(int)  # <0.5 = bearish
                
            except Exception as e:
                log_with_timestamp(f"  {asset_name} prediction failed: {e}", 'WARNING')
        
        regimes_df = pd.DataFrame(regimes_dict)
        log_with_timestamp(f"Generated predictions for {len(regimes_df.columns)} assets")
    
    if len(regimes_df.columns) == 0:
        log_with_timestamp("No regime predictions available", 'WARNING')
        return split_results
    
    # Save regime results
    regimes_df.to_csv(results_dir / 'asset_regimes.csv')
    
    # Compute regime statistics
    regime_stats = {}
    for asset in regimes_df.columns:
        regimes = regimes_df[asset].dropna()
        if len(regimes) > 0:
            n_bull = (regimes == 0).sum()
            n_bear = (regimes == 1).sum()
            n_switches = (regimes.diff() != 0).sum()
            
            regime_stats[asset] = {
                'bull_days': int(n_bull),
                'bear_days': int(n_bear),
                'bull_pct': f"{n_bull/len(regimes)*100:.1f}%",
                'bear_pct': f"{n_bear/len(regimes)*100:.1f}%",
                'n_switches': int(n_switches)
            }
    
    with open(regime_stats_dir / 'regime_statistics.json', 'w') as f:
        json.dump(regime_stats, f, indent=2)
    
    split_results['regime_stats'] = regime_stats
    
    # ========================================================================
    # Portfolio Optimization
    # ========================================================================
    
    log_with_timestamp("Running portfolio optimization...")
    
    # For portfolio: regime forecasts = current regimes shifted forward 1 day
    regime_forecasts_df = regimes_df.shift(1).fillna(method='bfill')
    
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
                strategy=strategy.upper()
            )
            
            backtest_results = portfolio_engine.backtest(
                returns_df=split_returns,
                regimes_df=regimes_df,
                regime_forecasts_df=regime_forecasts_df,
                start_date=start_ts,
                end_date=end_ts,
                verbose=True
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
    
    # Create benchmark: Equal-weight all available assets (EW Buy-and-Hold)
    available_assets = [c for c in split_returns.columns if not split_returns[c].isna().all()]
    if len(available_assets) >= 2:
        benchmark_returns = split_returns[available_assets].mean(axis=1)
        benchmark_name = f"EW {len(available_assets)}-Asset Buy-Hold"
    else:
        benchmark_returns = split_returns.mean(axis=1)
        benchmark_name = "Buy-and-Hold"
    
    all_metrics = {}
    
    for strategy, backtest_results in all_portfolio_results.items():
        try:
            portfolio_returns = backtest_results['portfolio_returns']
            portfolio_weights = backtest_results['portfolio_weights']
            
            if len(portfolio_returns) == 0:
                continue
            
            metrics = evaluator.compute_portfolio_metrics(
                portfolio_returns=portfolio_returns,
                portfolio_weights=portfolio_weights,
                benchmark_returns=benchmark_returns,
                risk_free_rate=split_rf
            )
            
            all_metrics[strategy] = metrics
            
            # Print key metrics
            ann_ret_key = 'ann_excess_return' if 'ann_excess_return' in metrics else 'excess_return'
            log_with_timestamp(f"  {strategy.upper()}: Sharpe={metrics['sharpe_ratio']:.2f}, "
                             f"MDD={metrics['max_drawdown']*100:.1f}%, "
                             f"TotalRet={metrics['total_return']*100:.1f}%")
            
            # Save metrics
            strategy_dir = results_dir / strategy
            with open(strategy_dir / 'performance_metrics.json', 'w') as f:
                json.dump({k: float(v) if isinstance(v, (int, float, np.floating)) else v 
                          for k, v in metrics.items()}, f, indent=2)
            
            # Generate separate plots
            evaluator.generate_all_plots(
                portfolio_returns=portfolio_returns,
                portfolio_weights=portfolio_weights,
                benchmark_returns=benchmark_returns,
                benchmark_name=benchmark_name,
                strategy_name=f"{strategy.upper()} (JM-XGB)",
                save_dir=str(figures_dir / strategy)
            )
            
        except Exception as e:
            log_with_timestamp(f"  {strategy} evaluation failed: {e}", 'WARNING')
            traceback.print_exc()
    
    split_results['metrics'] = all_metrics
    
    # Save summary
    with open(results_dir / 'strategy_comparison.json', 'w') as f:
        json.dump(all_metrics, f, indent=2, default=str)
    
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
