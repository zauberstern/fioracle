
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import os

def transform_epu():
    print("Starting EPU transformation...")
    
    # Paths
    daily_path = 'dataset/EPU/US_EPU_Daily.csv'
    monthly_path = 'dataset/EPU/US EPU Monthly.xlsx'
    output_path = 'dataset/EPU/epu_daily_1900_2025.csv'
    
    # 1. Load Daily Data (1985-2025)
    print("Loading Daily Data...")
    df_daily = pd.read_csv(daily_path)
    df_daily['date'] = pd.to_datetime(df_daily[['year', 'month', 'day']])
    df_daily = df_daily.set_index('date').sort_index()
    
    # Check column name
    col_name = 'EPU'
    if 'daily_policy_index' in df_daily.columns:
        col_name = 'daily_policy_index'
    
    daily_series = df_daily[col_name]
    
    # Filter for 1985-01-01 onwards
    daily_series = daily_series[daily_series.index >= '1985-01-01']
    
    # Calculate rho
    rho = daily_series.autocorr(lag=1)
    print(f"Estimated rho from daily data: {rho:.4f}")
    
    # 2. Load Monthly Data (1900-1984)
    print("Loading Monthly Data...")
    df_monthly = pd.read_excel(monthly_path)
    
    # Create date column
    df_monthly['day'] = 1
    df_monthly['date'] = pd.to_datetime(df_monthly[['Year', 'Month', 'day']])
    df_monthly = df_monthly.set_index('date').sort_index()
    
    # Filter for 1900-1984
    monthly_series = df_monthly['EPU']
    monthly_series = monthly_series[(monthly_series.index >= '1900-01-01') & (monthly_series.index < '1985-01-01')]
    
    print(f"Monthly data range: {monthly_series.index.min()} to {monthly_series.index.max()}")
    print(f"Monthly data count: {len(monthly_series)}")
    
    # 3. Chow-Lin Disaggregation
    print("Performing Chow-Lin Disaggregation...")
    
    # Target daily range
    start_date = monthly_series.index.min()
    last_month = monthly_series.index.max()
    next_month = last_month + pd.DateOffset(months=1)
    end_date = next_month - pd.DateOffset(days=1)
    
    target_daily_index = pd.date_range(start=start_date, end=end_date, freq='D')
    
    # Create mapping from daily to monthly
    daily_df = pd.DataFrame(index=target_daily_index)
    daily_df['month_start'] = daily_df.index.to_period('M').to_timestamp()
    
    # Filter daily_df to match available months
    daily_df = daily_df[daily_df['month_start'].isin(monthly_series.index)]
    target_daily_index = daily_df.index
    
    n = len(target_daily_index)
    N = len(monthly_series)
    
    print(f"Disaggregating {N} months into {n} days.")
    
    # Precompute powers of rho
    max_dist = n 
    
    # Prepare V_agg (N x N)
    V_agg = np.zeros((N, N))
    
    # Prepare V_cross (n x N)
    V_cross = np.zeros((n, N))
    
    # Map months to day indices
    month_days = []
    current_idx = 0
    for m in monthly_series.index:
        days_in_month = daily_df[daily_df['month_start'] == m].index
        count = len(days_in_month)
        indices = list(range(current_idx, current_idx + count))
        month_days.append(indices)
        current_idx += count
        
    # Compute V_cross
    print("Computing Covariance Matrices...")
    
    for j in range(N):
        if j % 100 == 0:
            print(f"  Processing month {j}/{N}")
        
        m_indices = month_days[j]
        m_len = len(m_indices)
        
        start = m_indices[0]
        end = m_indices[-1]
        
        # Vectorized implementation
        t = np.arange(n)
        col = np.zeros(n)
        
        mask_before = t < start
        mask_after = t > end
        mask_inside = (t >= start) & (t <= end)
        
        if np.any(mask_before):
            t_b = t[mask_before]
            col[mask_before] = (np.power(rho, start - t_b) - np.power(rho, end - t_b + 1)) / (1 - rho)
            
        if np.any(mask_after):
            t_a = t[mask_after]
            col[mask_after] = np.power(rho, t_a - end) * (1 - np.power(rho, end - start + 1)) / (1 - rho)
            
        if np.any(mask_inside):
            t_i = t[mask_inside]
            left = (1 - np.power(rho, t_i - start + 1)) / (1 - rho)
            right = rho * (1 - np.power(rho, end - t_i)) / (1 - rho)
            col[mask_inside] = left + right
            
        V_cross[:, j] = col / m_len

    # Compute V_agg
    print("Computing V_agg...")
    for i in range(N):
        m_indices = month_days[i]
        V_agg[i, :] = np.mean(V_cross[m_indices, :], axis=0)
        
    # Solve GLS
    print("Solving GLS...")
    X_agg = np.ones((N, 1))
    Y_vec = monthly_series.values.reshape(-1, 1)
    
    try:
        V_agg_inv_X = np.linalg.solve(V_agg, X_agg)
        V_agg_inv_Y = np.linalg.solve(V_agg, Y_vec)
    except np.linalg.LinAlgError:
        V_agg += np.eye(N) * 1e-6
        V_agg_inv_X = np.linalg.solve(V_agg, X_agg)
        V_agg_inv_Y = np.linalg.solve(V_agg, Y_vec)
        
    numerator = X_agg.T @ V_agg_inv_Y
    denominator = X_agg.T @ V_agg_inv_X
    beta_hat = numerator / denominator
    
    print(f"Estimated Beta (Mean Level): {beta_hat[0][0]}")
    
    residuals_agg = Y_vec - X_agg @ beta_hat
    z = np.linalg.solve(V_agg, residuals_agg)
    distributed_residuals = V_cross @ z
    
    y_hat = np.ones((n, 1)) * beta_hat + distributed_residuals
    
    # Create DataFrame
    df_estimated = pd.DataFrame(y_hat, index=target_daily_index, columns=['EPU'])
    
    # 4. Combine and Save
    print("Combining Data...")
    df_actual = pd.DataFrame(daily_series).rename(columns={col_name: 'EPU'})
    
    df_final = pd.concat([df_estimated, df_actual])
    df_final = df_final.sort_index()
    df_final = df_final[~df_final.index.duplicated(keep='last')]
    
    print(f"Final dataset shape: {df_final.shape}")
    print(f"Saving to {output_path}...")
    
    df_final.to_csv(output_path)
    print("Done.")

if __name__ == "__main__":
    transform_epu()
