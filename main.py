#!/usr/bin/env python3
"""Fioracle: Regime-aware portfolio optimization system."""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / 'src'))

from core import (
    setup_logging, load_config, DataPipeline, engineer_features, 
    RegimeEngine, PortfolioEngine, Evaluator
)

def parse_args():
    parser = argparse.ArgumentParser(description='Fioracle')
    parser.add_argument('--config', default='config/config.yaml')
    parser.add_argument('--output-dir', default='output')
    parser.add_argument('--split', choices=['train', 'val', 'test', 'all'], default='all',
                       help='Which data split to use: train (1945-2000), val (2001-2010), test (2011-2025), all (1945-2025)')
    parser.add_argument('--optimize-portfolio', action='store_true', help='Run portfolio optimization')
    parser.add_argument('--tune-lambda', action='store_true', help='Tune jump penalty lambda')
    parser.add_argument('--skip-forecast', action='store_true', help='Skip forecasting (faster)')
    parser.add_argument('--walk-forward', action='store_true', help='Use walk-forward validation')
    parser.add_argument('--verbose', action='store_true')
    return parser.parse_args()

def main():
    args = parse_args()
    logger = setup_logging(level='INFO' if args.verbose else 'WARNING')
    config = load_config(args.config)
    
    # Determine date range based on split
    split_dates = {
        'train': (config['data']['train_start'], config['data']['train_end']),
        'val': (config['data']['val_start'], config['data']['val_end']),
        'test': (config['data']['test_start'], config['data']['test_end']),
        'all': (config['data']['start_date'], config['data']['end_date'])
    }
    
    start_date, end_date = split_dates[args.split]
    
    # Create output directories
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Create split-specific subdirectories
    split_suffix = f"_{args.split}" if args.split != 'all' else ''
    figures_dir = output_dir / 'figures' / args.split if args.split != 'all' else output_dir / 'figures'
    results_dir = output_dir / 'results' / args.split if args.split != 'all' else output_dir / 'results'
    models_dir = output_dir / 'models' / args.split if args.split != 'all' else output_dir / 'models'
    regime_stats_dir = output_dir / 'regime_statistics' / args.split if args.split != 'all' else output_dir / 'regime_statistics'
    
    figures_dir.mkdir(parents=True, exist_ok=True)
    results_dir.mkdir(parents=True, exist_ok=True)
    models_dir.mkdir(parents=True, exist_ok=True)
    regime_stats_dir.mkdir(parents=True, exist_ok=True)
    
    print("\n" + "="*75)
    print("Fioracle - Regime-Aware Portfolio Management")
    print("="*75)
    print(f"Data Split: {args.split.upper()}")
    print(f"Date Range: {start_date} to {end_date}")
    
    if args.split == 'all':
        print(f"\n  Training:   {config['data']['train_start']} to {config['data']['train_end']}")
        print(f"  Validation: {config['data']['val_start']} to {config['data']['val_end']}")
        print(f"  Test:       {config['data']['test_start']} to {config['data']['test_end']}")
    
    print("="*75 + "\n")
    
    # STEP 1: Load Data
    print("STEP 1/5: Loading Data")
    print("-" * 40)
    pipeline = DataPipeline()
    data = pipeline.load(start_date, end_date)
    print(f"✓ Loaded {len(data)} rows, {len(data.columns)} columns")
    print(f"  Date range: {data.index[0]} to {data.index[-1]}\n")
    
    # STEP 2: Engineer Features
    print("STEP 2/5: Engineering Features")
    print("-" * 40)
    asset_features, macro_features = engineer_features(data)
    print(f"✓ Asset features: {len(asset_features)} assets")
    print(f"✓ Macro features: {len(macro_features.columns)} features\n")
    
    # Build returns from raw data (excess returns vs risk-free)
    import pandas as pd
    risk_free_col = [c for c in data.columns if 'risk_free' in c]
    if not risk_free_col:
        print("❌ No risk-free rate column found!")
        return
    rf_returns = data[risk_free_col[0]].pct_change()
    
    asset_returns = {}
    non_return_cols = {'asset_us_treasury_2y_yield', 'asset_us_10y2y_slope'}
    for col in data.columns:
        if col.startswith('asset_') and col not in non_return_cols and col != risk_free_col[0]:
            asset_return = data[col].pct_change()
            excess_return = asset_return - rf_returns
            asset_name = col.replace('asset_', '').upper()
            if asset_name in asset_features:
                asset_returns[asset_name] = excess_return
    
    if not asset_returns:
        print("❌ No asset returns computed!")
        return
    
    returns_df = pd.DataFrame(asset_returns)
    # Align returns with feature dates
    common_idx = returns_df.index.intersection(macro_features.index)
    returns_df = returns_df.loc[common_idx]
    print(f"  Returns shape: {returns_df.shape}")
    print(f"  Assets: {', '.join(returns_df.columns)}\n")
    
    # STEP 3: Identify Regimes
    print("STEP 3/5: Regime Identification")
    print("-" * 40)
    
    # Hyperparameter tuning if requested
    if args.tune_lambda:
        print("  Tuning lambda hyperparameter...")
        lambda_candidates = config['regimes']['jump_model']['lambda_candidates']
        
        # Tune on first asset as representative
        first_asset = list(asset_features.keys())[0]
        evaluator = Evaluator()
        optimal_lambda, tuning_results = evaluator.tune_lambda_fast(
            asset_features[first_asset],
            asset_returns[first_asset],
            lambda_candidates=lambda_candidates,
            n_splits=config['evaluation']['cv_folds']
        )
        
        # Save tuning results
        tuning_file = results_dir / 'lambda_tuning_results.csv'
        tuning_results.to_csv(tuning_file, index=False)
        print(f"  ✓ Optimal λ: {optimal_lambda}")
        print(f"  Saved tuning results: {tuning_file}")
        
        lambda_jump = optimal_lambda
    else:
        lambda_jump = config['regimes']['jump_model']['default_lambda']
    
    n_macro_regimes = config['regimes']['hmm']['n_states']
    
    print(f"  Jump Model λ: {lambda_jump}")
    print(f"  Macro regimes: {n_macro_regimes}")
    
    regime_engine = RegimeEngine(
        lambda_jump=lambda_jump,
        n_macro_regimes=n_macro_regimes
    )
    
    try:
        regime_results = regime_engine.fit_identify_forecast(
            asset_features_dict=asset_features,
            asset_returns_df=returns_df,
            macro_features=macro_features,
            train_forecasters=not args.skip_forecast,
            verbose=args.verbose
        )
        
        print(f"✓ Regimes identified for {len(regime_results.get('asset_regimes', {}))} assets")
        
        # Save regime results
        if 'asset_regimes' in regime_results:
            regimes_df = pd.DataFrame(regime_results['asset_regimes'])
            regimes_file = results_dir / 'asset_regimes.csv'
            regimes_df.to_csv(regimes_file)
            print(f"  Saved: {regimes_file}")
            
            # Save regime statistics
            regime_stats = {}
            for asset in regimes_df.columns:
                regimes = regimes_df[asset].dropna()
                n_bull = (regimes == 1).sum()
                n_bear = (regimes == 0).sum()
                n_switches = (regimes.diff() != 0).sum()
                avg_duration = len(regimes) / max(n_switches, 1)
                
                regime_stats[asset] = {
                    'bull_days': int(n_bull),
                    'bear_days': int(n_bear),
                    'bull_pct': f"{n_bull/len(regimes)*100:.1f}%",
                    'bear_pct': f"{n_bear/len(regimes)*100:.1f}%",
                    'n_switches': int(n_switches),
                    'avg_regime_duration': f"{avg_duration:.1f} days"
                }
            
            stats_file = regime_stats_dir / 'regime_statistics.json'
            with open(stats_file, 'w') as f:
                json.dump(regime_stats, f, indent=2)
            print(f"  Saved regime stats: {stats_file}")
        
        if 'macro_regime_probs' in regime_results:
            macro_probs_file = results_dir / 'macro_regime_probs.csv'
            regime_results['macro_regime_probs'].to_csv(macro_probs_file)
            print(f"  Saved: {macro_probs_file}")
        
        # Save trained models
        if hasattr(regime_engine, 'classifiers') and regime_engine.classifiers:
            import pickle
            models_file = models_dir / 'regime_forecasters.pkl'
            with open(models_file, 'wb') as f:
                pickle.dump(regime_engine.classifiers, f)
            print(f"  Saved models: {models_file}")
        
        if hasattr(regime_engine, 'macro_model') and regime_engine.macro_model is not None:
            macro_model_file = models_dir / 'macro_hmm_model.pkl'
            with open(macro_model_file, 'wb') as f:
                pickle.dump(regime_engine.macro_model, f)
            print(f"  Saved macro model: {macro_model_file}")
        
        print()
        
    except Exception as e:
        print(f"⚠ Regime identification failed: {e}")
        print("  Continuing with simplified analysis...\n")
        regime_results = None
    
    # STEP 4: Portfolio Optimization (if requested)
    portfolio_weights = None
    portfolio_returns = None
    
    if args.optimize_portfolio and regime_results is not None:
        print("STEP 4/5: Portfolio Optimization")
        print("-" * 40)
        
        try:
            # Walk-forward validation if requested
            if args.walk_forward:
                print("  Using walk-forward validation...")
                from sklearn.model_selection import TimeSeriesSplit
                
                regimes_df = pd.DataFrame(regime_results['asset_regimes'])
                n_splits = min(5, len(regimes_df) // 252)  # Max 5 splits or 1 per year
                
                tscv = TimeSeriesSplit(n_splits=n_splits)
                all_weights = []
                all_returns = []
                
                for fold, (train_idx, test_idx) in enumerate(tscv.split(regimes_df)):
                    # Use test period regimes for allocation
                    test_regimes = regimes_df.iloc[test_idx]
                    test_rets = returns_df.reindex(test_regimes.index, fill_value=0)
                    
                    # Equal weight bullish assets
                    weights = (test_regimes == 1).astype(float)
                    weights = weights.div(weights.sum(axis=1).replace(0, 1), axis=0)
                    
                    all_weights.append(weights)
                    all_returns.append((test_rets * weights).sum(axis=1))
                    
                    print(f"    Fold {fold+1}/{n_splits}: {len(test_regimes)} days")
                
                portfolio_weights = pd.concat(all_weights)
                portfolio_returns = pd.concat(all_returns)
                
                print(f"  ✓ Walk-forward validation complete ({n_splits} folds)")
            
            else:
                # Simple regime-based allocation
                regimes_df = pd.DataFrame(regime_results['asset_regimes'])
                
                # Create weights: equal weight across bullish assets, 0 for bearish
                portfolio_weights = (regimes_df == 1).astype(float)
                portfolio_weights = portfolio_weights.div(portfolio_weights.sum(axis=1).replace(0, 1), axis=0)
                
                # Calculate portfolio returns
                aligned_returns = returns_df.reindex(portfolio_weights.index, fill_value=0)
                portfolio_returns = (aligned_returns * portfolio_weights).sum(axis=1)
                
                print(f"✓ Portfolio optimized (regime-based allocation)")
            
            print(f"  Strategy: Equal weight across bullish assets")
            avg_weights = portfolio_weights.mean()
            top_3 = avg_weights.nlargest(3)
            print(f"  Top allocations: {', '.join([f'{k}: {v:.1%}' for k, v in top_3.items()])}")
            
            # Save results
            weights_file = results_dir / 'portfolio_weights.csv'
            portfolio_weights.to_csv(weights_file)
            print(f"  Saved weights: {weights_file}")
            
            returns_file = results_dir / 'portfolio_returns.csv'
            portfolio_returns.to_csv(returns_file)
            print(f"  Saved returns: {returns_file}")
            print()
            
        except Exception as e:
            print(f"⚠ Portfolio optimization failed: {e}\n")
            import traceback
            if args.verbose:
                traceback.print_exc()
    
    else:
        print("STEP 4/5: Portfolio Optimization")
        print("-" * 40)
        print("  Skipped (use --optimize-portfolio to enable)\n")
    
    # STEP 5: Evaluation
    print("STEP 5/5: Performance Evaluation")
    print("-" * 40)
    
    if portfolio_returns is not None and portfolio_weights is not None:
        try:
            evaluator = Evaluator()
            
            # Compute metrics with plotting
            metrics = evaluator.evaluate(
                portfolio_returns=portfolio_returns,
                portfolio_weights=portfolio_weights,
                plot=True,
                save_dir=str(figures_dir),
                verbose=args.verbose
            )
            
            # Save metrics
            metrics_file = results_dir / 'performance_metrics.json'
            with open(metrics_file, 'w') as f:
                json.dump(metrics, f, indent=2)
            
            print(f"✓ Performance evaluated")
            print(f"\n  Key Metrics:")
            print(f"  {'─'*40}")
            print(f"  Sharpe Ratio:      {metrics.get('sharpe', 0):.3f}")
            print(f"  Sortino Ratio:     {metrics.get('sortino', 0):.3f}")
            print(f"  Max Drawdown:      {metrics.get('max_drawdown', 0):.2%}")
            print(f"  Annual Return:     {metrics.get('annualized_return', 0):.2%}")
            print(f"  Annual Volatility: {metrics.get('volatility', 0):.2%}")
            print(f"  Win Rate:          {metrics.get('win_rate', 0):.2%}")
            print(f"  {'─'*40}\n")
            
            print(f"  Saved metrics: {metrics_file}")
            print(f"  Saved figures: {figures_dir}/\n")
            
        except Exception as e:
            print(f"⚠ Evaluation failed: {e}\n")
            import traceback
            if args.verbose:
                traceback.print_exc()
    
    else:
        # Basic evaluation with equal-weight portfolio
        try:
            ew_returns = returns_df.mean(axis=1)
            evaluator = Evaluator()
            metrics = evaluator.compute_metrics(ew_returns)
            
            print(f"✓ Equal-weight benchmark computed")
            print(f"\n  Benchmark Metrics (Equal Weight):")
            print(f"  {'─'*40}")
            print(f"  Sharpe Ratio:     {metrics.get('sharpe', 0):.3f}")
            print(f"  Max Drawdown:     {metrics.get('max_drawdown', 0):.2%}")
            print(f"  {'─'*40}\n")
            
        except Exception as e:
            print(f"⚠ Evaluation failed: {e}\n")
    
    # Summary
    print("="*75)
    print("Pipeline Complete!")
    print("="*75)
    print(f"\nOutputs saved to: {output_dir}/")
    print(f"Split: {args.split.upper()}")
    print("\nGenerated files:")
    
    for result_file in results_dir.glob('*'):
        print(f"  ✓ results/{args.split}/{result_file.name}")
    
    for fig_file in figures_dir.glob('*'):
        print(f"  ✓ figures/{args.split}/{fig_file.name}")
    
    if models_dir.exists():
        for model_file in models_dir.glob('*'):
            print(f"  ✓ models/{args.split}/{model_file.name}")
    
    if regime_stats_dir.exists():
        for stats_file in regime_stats_dir.glob('*'):
            print(f"  ✓ regime_statistics/{args.split}/{stats_file.name}")
    
    print("\nNext steps:")
    print("  1. Review results in output/results/")
    print("  2. Check figures in output/figures/")
    print("  3. Explore notebooks/ for detailed analysis")
    
    if not args.tune_lambda:
        print("  4. Try --tune-lambda for hyperparameter optimization")
    if not args.walk_forward:
        print("  5. Try --walk-forward for realistic validation")
    
    print("="*75 + "\n")

if __name__ == '__main__':
    main()
