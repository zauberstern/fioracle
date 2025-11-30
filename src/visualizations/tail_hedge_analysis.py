"""
Tail-hedge scenario analysis and drawdown decomposition.

Analyzes asset group performance (CHF, Gold, Gov, Credit) by regime
and decomposes drawdowns vs benchmark.
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from pathlib import Path
from typing import Dict, Optional, List
import json
import yaml

# Colors
COLORS = {
    'calm': '#38a169',
    'inflationary': '#d69e2e',
    'crisis': '#e53e3e',
    'chf': '#2b6cb0',
    'gold': '#d69e2e',
    'gov': '#38a169',
    'credit': '#e53e3e',
    'neutral': '#718096'
}


def load_config() -> dict:
    """Load configuration from config.yaml."""
    config_path = Path(__file__).parent.parent.parent / 'config' / 'config.yaml'
    if config_path.exists():
        with open(config_path, 'r') as f:
            return yaml.safe_load(f)
    return {}


def analyze_tail_hedges(
    portfolio_returns: pd.Series,
    portfolio_weights: pd.DataFrame,
    asset_returns: pd.DataFrame,
    regime_series: Optional[pd.Series],
    config: dict,
    output_dir: Path,
    split_name: str
) -> Dict:
    """
    Run tail-hedge scenario analysis.
    
    Analyzes performance of different asset groups (CHF, Gold, Gov, Credit)
    across regimes (calm, inflationary, crisis).
    """
    results = {}
    
    tail_cfg = config.get('portfolio', {}).get('tail_hedges', {})
    if not tail_cfg.get('enabled', False):
        return results
    
    output_path = output_dir / 'tail_hedge_analysis' / split_name
    output_path.mkdir(parents=True, exist_ok=True)
    
    # Handle None regime_series
    if regime_series is None or len(regime_series) == 0:
        # Create a default regime based on returns volatility
        if len(portfolio_returns) > 0:
            rolling_vol = portfolio_returns.rolling(21).std()
            regime_series = pd.Series(0, index=portfolio_returns.index)
            vol_75 = rolling_vol.quantile(0.75)
            vol_90 = rolling_vol.quantile(0.90)
            regime_series[rolling_vol > vol_75] = 1
            regime_series[rolling_vol > vol_90] = 2
        else:
            regime_series = pd.Series(dtype=int)
    
    # Get asset group definitions
    chf_assets = tail_cfg.get('chf_assets', ['CHF_TOTAL_RETURN', 'CHF'])
    gold_assets = tail_cfg.get('gold_assets', ['GOLD_TOTAL_RETURN', 'GOLD'])
    gov_assets = tail_cfg.get('gov_safe_assets', ['US_10Y_GOV_BOND_RETURN', 'US_10Y_GOV_BOND', 
                                                   'IBOXX_USD_TREASURY_TOTAL_RETURN', 'IBOXX_USD_TREASURY'])
    credit_assets = tail_cfg.get('credit_assets', ['IBOXX_USD_CORPORATE_TOTAL_RETURN', 'IBOXX_USD_CORPORATE',
                                                    'US_BAA_CORP_BOND_TOTAL_RETURN', 'US_BAA_CORP_BOND'])
    
    # Map asset names to columns (more flexible matching)
    def find_matching_cols(asset_list, columns):
        matches = []
        for asset in asset_list:
            asset_upper = asset.upper().replace('_TOTAL_RETURN', '').replace('_RETURN', '')
            for col in columns:
                col_clean = col.upper().replace('_TOTAL_RETURN', '').replace('_RETURN', '')
                # Try direct match or partial match
                if asset_upper == col_clean or asset_upper in col_clean or col_clean in asset_upper:
                    if col not in matches:
                        matches.append(col)
                        break
        return matches
    
    chf_cols = find_matching_cols(chf_assets, asset_returns.columns)
    gold_cols = find_matching_cols(gold_assets, asset_returns.columns)
    gov_cols = find_matching_cols(gov_assets, asset_returns.columns)
    credit_cols = find_matching_cols(credit_assets, asset_returns.columns)
    
    # Compute group returns
    groups = {
        'CHF/Safe Haven': chf_cols,
        'Gold': gold_cols,
        'Government Bonds': gov_cols,
        'Credit': credit_cols
    }
    
    # Filter to groups with data
    groups = {k: v for k, v in groups.items() if len(v) > 0}
    
    if len(groups) == 0:
        # Save empty results
        results['error'] = 'No matching asset groups found'
        with open(output_path / 'tail_hedge_results.json', 'w') as f:
            json.dump(results, f, indent=2, default=str)
        return results
    
    # Align regime series
    common_idx = portfolio_returns.index.intersection(regime_series.index)
    if len(common_idx) < 50:
        results['error'] = f'Insufficient overlapping data ({len(common_idx)} days)'
        with open(output_path / 'tail_hedge_results.json', 'w') as f:
            json.dump(results, f, indent=2, default=str)
        return results
    
    regime_aligned = regime_series.loc[common_idx]
    
    # Compute mean returns by regime for each group
    regime_performance = {}
    
    for group_name, cols in groups.items():
        if len(cols) == 0:
            continue
        
        # Equal weight within group
        group_returns = asset_returns[cols].mean(axis=1).reindex(common_idx)
        group_returns = group_returns.dropna()
        
        if len(group_returns) < 30:
            continue
        
        regime_performance[group_name] = {}
        for regime_val in sorted(regime_aligned.unique()):
            mask = regime_aligned.reindex(group_returns.index) == regime_val
            mask = mask.fillna(False)
            
            if mask.sum() < 10:
                continue
            
            regime_name = {0: 'calm', 1: 'inflationary', 2: 'crisis'}.get(int(regime_val), str(regime_val))
            regime_rets = group_returns[mask]
            
            if len(regime_rets) > 0 and regime_rets.std() > 0:
                regime_performance[group_name][regime_name] = {
                    'n_days': int(mask.sum()),
                    'mean_return_ann': float(regime_rets.mean() * 252),
                    'vol_ann': float(regime_rets.std() * np.sqrt(252)),
                    'sharpe': float(regime_rets.mean() / (regime_rets.std() + 1e-10) * np.sqrt(252))
                }
    
    results['regime_performance'] = regime_performance
    
    # Plot regime performance bar chart
    if len(regime_performance) > 0:
        _plot_regime_performance(regime_performance, output_path)
    
    # Plot regime boxplots
    if len(groups) > 0:
        _plot_regime_boxplots(asset_returns, regime_aligned, groups, output_path)
    
    # Drawdown decomposition
    dd_results = _compute_drawdown_decomposition(
        portfolio_returns.loc[common_idx],
        portfolio_weights.reindex(common_idx),
        asset_returns.reindex(common_idx),
        groups
    )
    results['drawdown_decomposition'] = dd_results
    
    # Save results
    with open(output_path / 'tail_hedge_results.json', 'w') as f:
        json.dump(results, f, indent=2, default=str)
    
    return results


def _plot_regime_performance(regime_performance: Dict, output_path: Path):
    """Plot asset group performance by regime - bar chart."""
    fig, ax = plt.subplots(figsize=(12, 6))
    
    groups = list(regime_performance.keys())
    regimes = ['calm', 'inflationary', 'crisis']
    
    if len(groups) == 0:
        ax.text(0.5, 0.5, 'No data available for regime performance', 
               ha='center', va='center', fontsize=14)
        plt.savefig(output_path / 'regime_performance_by_group.png', dpi=150, bbox_inches='tight')
        plt.close()
        return
    
    x = np.arange(len(groups))
    width = 0.25
    
    has_data = False
    for i, regime in enumerate(regimes):
        returns = []
        for group in groups:
            if regime in regime_performance.get(group, {}):
                ret_val = regime_performance[group][regime].get('mean_return_ann', 0) * 100
                returns.append(ret_val)
                if ret_val != 0:
                    has_data = True
            else:
                returns.append(0)
        
        offset = (i - 1) * width
        color = COLORS.get(regime, COLORS['neutral'])
        ax.bar(x + offset, returns, width, label=regime.capitalize(), color=color, alpha=0.8)
    
    if not has_data:
        ax.text(0.5, 0.5, 'Insufficient data for regime analysis', 
               ha='center', va='center', fontsize=14, transform=ax.transAxes)
    
    ax.set_xlabel('Asset Group', fontsize=11)
    ax.set_ylabel('Annualized Return (%)', fontsize=11)
    ax.set_title('Asset Group Performance by Regime', fontsize=13, fontweight='bold')
    ax.set_xticks(x)
    ax.set_xticklabels(groups, rotation=15, ha='right')
    ax.legend()
    ax.axhline(0, color='black', linestyle='-', alpha=0.3)
    ax.grid(axis='y', alpha=0.3)
    
    plt.tight_layout()
    plt.savefig(output_path / 'regime_performance_by_group.png', dpi=150, bbox_inches='tight')
    plt.close()


def _plot_regime_boxplots(
    asset_returns: pd.DataFrame,
    regime_series: pd.Series,
    groups: Dict[str, List[str]],
    output_path: Path
):
    """
    Plot box plots of returns distribution by regime and asset group.
    
    Shows the full distribution of returns for each group conditional on regime.
    """
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    axes = axes.flatten()
    
    regime_names = {0: 'Calm', 1: 'Inflationary', 2: 'Crisis'}
    regime_colors = {
        'Calm': COLORS['calm'],
        'Inflationary': COLORS['inflationary'],
        'Crisis': COLORS['crisis']
    }
    
    for ax_idx, (group_name, cols) in enumerate(groups.items()):
        if ax_idx >= 4:
            break
        
        ax = axes[ax_idx]
        
        if len(cols) == 0:
            ax.text(0.5, 0.5, f'No data for {group_name}', 
                   ha='center', va='center', fontsize=12)
            ax.set_title(group_name, fontsize=12, fontweight='bold')
            continue
        
        # Equal-weight group returns
        valid_cols = [c for c in cols if c in asset_returns.columns]
        if len(valid_cols) == 0:
            ax.text(0.5, 0.5, f'No columns found for {group_name}', 
                   ha='center', va='center', fontsize=12)
            ax.set_title(group_name, fontsize=12, fontweight='bold')
            continue
        
        group_returns = asset_returns[valid_cols].mean(axis=1)
        
        # Collect data for box plot
        box_data = []
        box_labels = []
        box_colors = []
        
        for regime_val, regime_label in regime_names.items():
            mask = regime_series.reindex(group_returns.index) == regime_val
            mask = mask.fillna(False)
            
            if mask.sum() >= 10:
                regime_rets = group_returns[mask].dropna() * 100  # Convert to %
                if len(regime_rets) > 0:
                    box_data.append(regime_rets.values)
                    box_labels.append(f'{regime_label}\n(n={mask.sum()})')
                    box_colors.append(regime_colors[regime_label])
        
        if len(box_data) == 0:
            ax.text(0.5, 0.5, f'Insufficient data for {group_name}', 
                   ha='center', va='center', fontsize=12)
            ax.set_title(group_name, fontsize=12, fontweight='bold')
            continue
        
        # Create box plot
        bp = ax.boxplot(box_data, labels=box_labels, patch_artist=True, widths=0.6)
        
        # Color the boxes
        for patch, color in zip(bp['boxes'], box_colors):
            patch.set_facecolor(color)
            patch.set_alpha(0.7)
        
        # Style
        ax.axhline(0, color='black', linestyle='--', alpha=0.5)
        ax.set_ylabel('Daily Return (%)', fontsize=10)
        ax.set_title(group_name, fontsize=12, fontweight='bold')
        ax.grid(axis='y', alpha=0.3)
        
        # Add mean markers
        means = [np.mean(d) for d in box_data]
        ax.scatter(range(1, len(means) + 1), means, color='darkred', 
                  marker='D', s=50, zorder=5, label='Mean')
    
    # Hide unused axes
    for ax_idx in range(len(groups), 4):
        axes[ax_idx].axis('off')
    
    plt.suptitle('Return Distributions by Regime and Asset Group', fontsize=14, fontweight='bold')
    plt.tight_layout()
    plt.savefig(output_path / 'regime_boxplots.png', dpi=150, bbox_inches='tight')
    plt.close()


def _compute_drawdown_decomposition(
    portfolio_returns: pd.Series,
    portfolio_weights: pd.DataFrame,
    asset_returns: pd.DataFrame,
    groups: Dict[str, List[str]]
) -> Dict:
    """Decompose drawdown by asset group contribution."""
    results = {}
    
    if len(portfolio_returns) == 0:
        return results
    
    # Portfolio cumulative wealth
    portfolio_wealth = (1 + portfolio_returns).cumprod()
    portfolio_running_max = portfolio_wealth.cummax()
    portfolio_drawdown = (portfolio_wealth - portfolio_running_max) / portfolio_running_max
    
    max_dd = portfolio_drawdown.min()
    max_dd_date = portfolio_drawdown.idxmin()
    
    results['max_drawdown'] = float(max_dd)
    results['max_drawdown_date'] = str(max_dd_date)
    
    # Find drawdown period
    try:
        peak_date = portfolio_running_max[:max_dd_date].idxmax()
    except:
        return results
    
    # Contribution from each group during drawdown
    group_contributions = {}
    
    for group_name, cols in groups.items():
        if len(cols) == 0:
            continue
        
        # Get weights for these assets
        matching_weight_cols = [c for c in portfolio_weights.columns 
                               if any(ac.upper() in c.upper() for ac in cols)]
        
        if len(matching_weight_cols) == 0:
            continue
        
        try:
            # Weight * return contribution during drawdown
            dd_period = portfolio_weights.loc[peak_date:max_dd_date, matching_weight_cols]
            
            # Find matching return columns
            matching_return_cols = [c for c in asset_returns.columns 
                                   if any(ac.upper() in c.upper() for ac in cols)]
            
            if len(matching_return_cols) == 0:
                continue
            
            ret_period = asset_returns.loc[peak_date:max_dd_date, matching_return_cols]
            
            if len(dd_period) > 0 and len(ret_period) > 0:
                avg_weight = dd_period.mean().sum()
                avg_return = ret_period.mean().mean()
                group_contributions[group_name] = {
                    'avg_weight': float(avg_weight),
                    'contribution': float(avg_weight * avg_return * len(dd_period))
                }
        except Exception as e:
            continue
    
    results['group_contributions'] = group_contributions
    
    return results


def analyze_regime_coherence(
    regime_forecasts: Dict[str, pd.Series],
    output_dir: Path,
    split_name: str
) -> Dict:
    """Analyze cross-asset regime coherence."""
    output_path = output_dir / 'tail_hedge_analysis' / split_name
    output_path.mkdir(parents=True, exist_ok=True)
    
    # Create DataFrame of regime forecasts
    regime_df = pd.DataFrame(regime_forecasts)
    
    if regime_df.empty or len(regime_df.columns) < 2:
        return {}
    
    # Crisis indicator (regime == 2)
    crisis_indicators = (regime_df == 2).astype(float)
    
    # Correlation matrix
    corr = crisis_indicators.corr()
    
    # Plot heatmap
    fig, ax = plt.subplots(figsize=(10, 8))
    
    im = ax.imshow(corr.values, cmap='RdYlGn_r', vmin=0, vmax=1, aspect='auto')
    
    plt.colorbar(im, ax=ax, shrink=0.8, label='Correlation')
    
    ax.set_xticks(range(len(corr.columns)))
    ax.set_yticks(range(len(corr.index)))
    ax.set_xticklabels([c[:15] for c in corr.columns], rotation=45, ha='right', fontsize=8)
    ax.set_yticklabels([c[:15] for c in corr.index], fontsize=8)
    
    ax.set_title('Crisis Regime Coherence Matrix', fontsize=13, fontweight='bold')
    
    plt.tight_layout()
    plt.savefig(output_path / 'regime_coherence_matrix.png', dpi=150, bbox_inches='tight')
    plt.close()
    
    return {'crisis_correlation_matrix': corr.to_dict()}
