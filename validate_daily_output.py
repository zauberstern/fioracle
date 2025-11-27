#!/usr/bin/env python
"""
Validate the daily CSV outputs from the disaggregation pipeline.
"""

import pandas as pd
from pathlib import Path
import sys

def validate_csv(filepath):
    """Validate a single CSV file."""
    errors = []
    warnings = []
    
    try:
        # Read CSV
        df = pd.read_csv(filepath, parse_dates=['Date'])
        
        # Check shape
        if len(df) == 0:
            errors.append("Empty file")
            return errors, warnings
        
        if len(df.columns) != 2:
            errors.append(f"Expected 2 columns, found {len(df.columns)}")
        
        # Check column names
        if df.columns[0] != 'Date':
            errors.append(f"First column should be 'Date', found '{df.columns[0]}'")
        
        metric_name = filepath.stem
        if df.columns[1] != metric_name:
            warnings.append(f"Second column is '{df.columns[1]}', expected '{metric_name}'")
        
        # Check date column
        if not pd.api.types.is_datetime64_any_dtype(df['Date']):
            errors.append("Date column is not datetime")
        
        # Check for missing dates
        if df['Date'].isna().any():
            errors.append(f"{df['Date'].isna().sum()} missing dates")
        
        # Check date range
        date_range = f"{df['Date'].min().date()} to {df['Date'].max().date()}"
        
        # Check if dates are business days (approximately - weekends should be rare)
        weekend_dates = df[df['Date'].dt.dayofweek >= 5]
        if len(weekend_dates) > 0:
            warnings.append(f"{len(weekend_dates)} weekend dates found")
        
        # Check for missing values
        value_col = df.columns[1]
        na_count = df[value_col].isna().sum()
        if na_count > 0:
            warnings.append(f"{na_count} missing values")
        
        # Check for duplicates
        dup_count = df['Date'].duplicated().sum()
        if dup_count > 0:
            errors.append(f"{dup_count} duplicate dates")
        
        # Check sorting
        if not df['Date'].is_monotonic_increasing:
            errors.append("Dates not sorted")
        
        return errors, warnings, {
            'rows': len(df),
            'date_range': date_range,
            'na_count': na_count
        }
        
    except Exception as e:
        errors.append(f"Failed to read: {e}")
        return errors, warnings, None


def main():
    """Validate all CSV files in data_daily/."""
    data_dir = Path("data_daily")
    
    if not data_dir.exists():
        print(f"❌ Directory {data_dir} not found")
        return 1
    
    csv_files = sorted(data_dir.glob("*.csv"))
    
    if len(csv_files) == 0:
        print(f"❌ No CSV files found in {data_dir}")
        return 1
    
    print("="*80)
    print(f"VALIDATION REPORT: {len(csv_files)} CSV files")
    print("="*80)
    
    all_valid = True
    
    for filepath in csv_files:
        result = validate_csv(filepath)
        
        if len(result) == 2:
            # Error during read
            errors, warnings = result
            info = None
        else:
            errors, warnings, info = result
        
        status = "✓" if len(errors) == 0 else "✗"
        
        print(f"\n{status} {filepath.name}")
        
        if info:
            print(f"  Rows: {info['rows']:,}")
            print(f"  Date range: {info['date_range']}")
            if info['na_count'] > 0:
                print(f"  Missing values: {info['na_count']}")
        
        if errors:
            all_valid = False
            for error in errors:
                print(f"  ❌ {error}")
        
        if warnings:
            for warning in warnings:
                print(f"  ⚠️  {warning}")
    
    print("\n" + "="*80)
    if all_valid:
        print("✓ ALL FILES VALID")
        print("="*80)
        return 0
    else:
        print("✗ SOME FILES HAVE ERRORS")
        print("="*80)
        return 1


if __name__ == "__main__":
    sys.exit(main())

