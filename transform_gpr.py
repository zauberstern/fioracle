
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import os

def transform_gpr():
    print("Starting GPR transformation...")
    
    # Paths
    daily_path = 'dataset/GPRI/GPRI_Daily.xls'
    monthly_path = 'dataset/GPRI/GPRI_Monthly.xls'
    output_path = 'dataset/GPRI/gpr_daily_1900_2025.csv'
    
    # 1. Load Daily Data (1985-2025)
    print("Loading Daily Data...")
    df_daily = pd.read_excel(daily_path)
    df_daily['date'] = pd.to_datetime(df_daily['DAY'].astype(str), format='%Y%m%d')
    df_daily = df_daily.set_index('date').sort_index()
    daily_series = df_daily['GPRD']
    
    # Filter for 1985-01-01 onwards (just to be safe)
    daily_series = daily_series[daily_series.index >= '1985-01-01']
    
    # Calculate rho
    rho = daily_series.autocorr(lag=1)
    print(f"Estimated rho from daily data: {rho:.4f}")
    
    # 2. Load Monthly Data (1900-1984)
    print("Loading Monthly Data...")
    df_monthly = pd.read_excel(monthly_path)
    
    # Fix date parsing for 1900-1999
    # The format is MM/DD/YY. Pandas might interpret 00-68 as 2000-2068.
    # We know the range is 1900-1984.
    def parse_date(date_val):
        if isinstance(date_val, datetime):
            return date_val
        # If it's a string
        try:
            dt = pd.to_datetime(date_val)
            if dt.year > 2020: # Correction for 2-digit year
                dt = dt.replace(year=dt.year - 100)
            return dt
        except:
            return pd.NaT

    df_monthly['date'] = df_monthly['month'].apply(parse_date)
    df_monthly = df_monthly.set_index('date').sort_index()
    
    # Filter for 1900-1984
    monthly_series = df_monthly['GPRH']
    monthly_series = monthly_series[(monthly_series.index >= '1900-01-01') & (monthly_series.index < '1985-01-01')]
    
    print(f"Monthly data range: {monthly_series.index.min()} to {monthly_series.index.max()}")
    print(f"Monthly data count: {len(monthly_series)}")
    
    # 3. Chow-Lin Disaggregation
    print("Performing Chow-Lin Disaggregation...")
    
    # Target daily range
    start_date = monthly_series.index.min()
    # End date should be the end of the last month
    last_month = monthly_series.index.max()
    # Get the last day of that month
    next_month = last_month + pd.DateOffset(months=1)
    end_date = next_month - pd.DateOffset(days=1)
    
    target_daily_index = pd.date_range(start=start_date, end=end_date, freq='D')
    
    # Create mapping from daily to monthly
    # We need to know which month each day belongs to
    day_to_month_idx = []
    month_starts = monthly_series.index
    
    # Create a Series for the daily index to map to months
    daily_df = pd.DataFrame(index=target_daily_index)
    daily_df['month_start'] = daily_df.index.to_period('M').to_timestamp()
    
    # Check if all months in daily_df exist in monthly_series
    unique_months = daily_df['month_start'].unique()
    missing_months = [m for m in unique_months if m not in monthly_series.index]
    if missing_months:
        print(f"Warning: Missing months in monthly series: {missing_months}")
        # We might need to trim the daily index or handle missing data
    
    # Filter daily_df to match available months
    daily_df = daily_df[daily_df['month_start'].isin(monthly_series.index)]
    target_daily_index = daily_df.index
    
    n = len(target_daily_index)
    N = len(monthly_series)
    
    print(f"Disaggregating {N} months into {n} days.")
    
    # Construct Aggregation Matrix C (implicitly)
    # C is N x n. C[i, t] = 1/m_i if day t is in month i.
    
    # We need V_agg = C V C' (N x N)
    # and V_cross = V C' (n x N)
    
    # Since constructing full matrices is slow, we use the property of AR(1) covariance.
    # Cov(day_t, day_s) = rho^|t-s|
    
    # Let's compute V_agg and V_cross efficiently.
    # Actually, for N=1020, N^2 is 1M. We can compute V_agg element by element or using vectorization.
    # But calculating the sum of rho^|t-s| for all pairs of days in two months is heavy.
    # Approximation: Use the midpoint of the month? No, Chow-Lin should be exact.
    
    # Optimization:
    # Cov(Month_I, Month_J) = (1/(m_I * m_J)) * Sum_{t in I} Sum_{s in J} rho^|t-s|
    # This sum can be computed closed-form or efficiently.
    # Sum_{t=1..m} Sum_{s=1..k} rho^|t-s+d| where d is distance between months.
    
    # Let's try a slightly less efficient but simpler approach first.
    # If it's too slow, we optimize.
    # We can construct V_cross column by column.
    # Column j of V_cross corresponds to Month j.
    # Element t of Column j is Cov(day_t, Month_j) = (1/m_j) * Sum_{s in Month_j} rho^|t-s|
    
    # This is a convolution!
    # We can compute rho^|k| for k = -n to n.
    # Then for each month, we sum the appropriate window.
    
    # Let's do this:
    # 1. Create a vector of rho^|k| for k = 0 to n.
    # Actually, we need rho^|t-s|.
    
    # Let's use a helper function to compute Cov(day_t, Month_J).
    # It depends on the distance between day t and the days in Month J.
    
    # Precompute powers of rho
    max_dist = n # Upper bound
    rho_powers = np.power(rho, np.arange(max_dist))
    
    # Prepare V_agg (N x N)
    V_agg = np.zeros((N, N))
    
    # Prepare V_cross (n x N)
    # We can't store 31000 x 1000 easily? 31M floats is ~250MB. That's fine.
    V_cross = np.zeros((n, N))
    
    # Map months to day indices
    # month_days[i] = [list of day indices (0 to n-1) for month i]
    month_days = []
    current_idx = 0
    for m in monthly_series.index:
        # Find days in this month
        days_in_month = daily_df[daily_df['month_start'] == m].index
        count = len(days_in_month)
        indices = list(range(current_idx, current_idx + count))
        month_days.append(indices)
        current_idx += count
        
    # Compute V_cross
    # For each month J, compute column J of V_cross
    # V_cross[t, J] = Average_{s in J} rho^|t-s|
    print("Computing Covariance Matrices...")
    
    # This loop might be slow in pure Python. Let's vectorize.
    # Create a grid of indices? No, too big.
    
    # Iterate over months (columns of V_cross)
    for j in range(N):
        if j % 100 == 0:
            print(f"  Processing month {j}/{N}")
        
        m_indices = month_days[j] # indices of days in month j
        m_len = len(m_indices)
        
        # We need to compute sum(rho^|t-s|) for s in m_indices, for all t.
        # This is sum(rho^|t - s|) / m_len
        
        # Let's define a function for a single month
        # The month spans indices [start, end]
        start = m_indices[0]
        end = m_indices[-1]
        
        # For t < start: sum is rho^(start-t) + ... + rho^(end-t) = rho^(start-t) * (1 + rho + ... + rho^(end-start))
        # Geometric series sum: (1 - rho^k) / (1 - rho)
        
        # For t > end: similar
        
        # For start <= t <= end: split into left and right sums
        
        # Let's use the geometric series formula to be fast.
        # Sum_{k=0 to K} rho^k = (1 - rho^(K+1)) / (1 - rho)
        
        # Case 1: t < start
        # Sum = Sum_{k=start}^{end} rho^(k-t) = rho^(-t) * Sum_{k=start}^{end} rho^k
        # = rho^(-t) * (rho^start - rho^(end+1)) / (1-rho)
        # = (rho^(start-t) - rho^(end-t+1)) / (1-rho)
        
        # Case 2: t > end
        # Sum = Sum_{k=start}^{end} rho^(t-k) = rho^t * Sum_{k=start}^{end} rho^(-k) ... wait
        # Sum = rho^(t-end) + ... + rho^(t-start)
        # = rho^(t-end) * (1 + ... + rho^(end-start))
        # = rho^(t-end) * (1 - rho^(end-start+1)) / (1-rho)
        
        # Case 3: start <= t <= end
        # Sum = Sum_{s=start}^{t} rho^(t-s) + Sum_{s=t+1}^{end} rho^(s-t)
        # Left part: s goes start to t. let k = t-s. k goes 0 to t-start.
        # Sum = (1 - rho^(t-start+1)) / (1-rho)
        # Right part: s goes t+1 to end. let k = s-t. k goes 1 to end-t.
        # Sum = rho * (1 - rho^(end-t)) / (1-rho)
        
        # Vectorized implementation
        t = np.arange(n)
        col = np.zeros(n)
        
        # Masking
        mask_before = t < start
        mask_after = t > end
        mask_inside = (t >= start) & (t <= end)
        
        # Before
        if np.any(mask_before):
            t_b = t[mask_before]
            col[mask_before] = (np.power(rho, start - t_b) - np.power(rho, end - t_b + 1)) / (1 - rho)
            
        # After
        if np.any(mask_after):
            t_a = t[mask_after]
            col[mask_after] = np.power(rho, t_a - end) * (1 - np.power(rho, end - start + 1)) / (1 - rho)
            
        # Inside
        if np.any(mask_inside):
            t_i = t[mask_inside]
            left = (1 - np.power(rho, t_i - start + 1)) / (1 - rho)
            right = rho * (1 - np.power(rho, end - t_i)) / (1 - rho)
            col[mask_inside] = left + right
            
        V_cross[:, j] = col / m_len

    # Compute V_agg = C * V_cross
    # V_agg[i, j] = Average of V_cross[t, j] for t in Month i
    print("Computing V_agg...")
    for i in range(N):
        m_indices = month_days[i]
        # Average the rows corresponding to month i
        V_agg[i, :] = np.mean(V_cross[m_indices, :], axis=0)
        
    # Solve GLS
    print("Solving GLS...")
    # X is a column of 1s (n x 1)
    # X_agg is C X = column of 1s (N x 1)
    X_agg = np.ones((N, 1))
    Y_vec = monthly_series.values.reshape(-1, 1)
    
    # beta_hat = (X_agg' V_agg^-1 X_agg)^-1 X_agg' V_agg^-1 Y
    # Use solve instead of inverse for stability
    # V_agg_inv_X = solve(V_agg, X_agg)
    try:
        V_agg_inv_X = np.linalg.solve(V_agg, X_agg)
        V_agg_inv_Y = np.linalg.solve(V_agg, Y_vec)
    except np.linalg.LinAlgError:
        # Add small jitter if singular
        V_agg += np.eye(N) * 1e-6
        V_agg_inv_X = np.linalg.solve(V_agg, X_agg)
        V_agg_inv_Y = np.linalg.solve(V_agg, Y_vec)
        
    numerator = X_agg.T @ V_agg_inv_Y
    denominator = X_agg.T @ V_agg_inv_X
    beta_hat = numerator / denominator
    
    print(f"Estimated Beta (Mean Level): {beta_hat[0][0]}")
    
    # Estimate y
    # y_hat = X beta + V_cross V_agg^-1 (Y - X_agg beta)
    # residuals_agg = Y - X_agg beta
    residuals_agg = Y_vec - X_agg @ beta_hat
    
    # distributed_residuals = V_cross @ (V_agg^-1 residuals_agg)
    # Let z = V_agg^-1 residuals_agg
    z = np.linalg.solve(V_agg, residuals_agg)
    
    distributed_residuals = V_cross @ z
    
    y_hat = np.ones((n, 1)) * beta_hat + distributed_residuals
    
    # Create DataFrame
    df_estimated = pd.DataFrame(y_hat, index=target_daily_index, columns=['GPRD'])
    
    # 4. Combine and Save
    print("Combining Data...")
    # Combine estimated (1900-1984) and actual (1985-2025)
    # Ensure no overlap or gaps
    
    # Actual daily data
    df_actual = df_daily[['GPRD']]
    
    # Concatenate
    df_final = pd.concat([df_estimated, df_actual])
    df_final = df_final.sort_index()
    
    # Remove duplicates if any (priority to actual)
    df_final = df_final[~df_final.index.duplicated(keep='last')]
    
    print(f"Final dataset shape: {df_final.shape}")
    print(f"Saving to {output_path}...")
    
    df_final.to_csv(output_path)
    print("Done.")

if __name__ == "__main__":
    transform_gpr()
