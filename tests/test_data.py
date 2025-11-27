"""
Unit tests for src.core.data module.
"""

from pathlib import Path

import pandas as pd

from src.core.data import DataPipeline


def _write_asset_file(path: Path, dates, values):
    df = pd.DataFrame({'Date': dates, 'Total Return Index': values})
    df.to_csv(path, index=False)


def _write_macro_file(path: Path, dates, values, date_col: str = 'date', value_col: str = 'GPRD'):
    df = pd.DataFrame({date_col: dates, value_col: values})
    df.to_csv(path, index=False)


class TestDataPipelineLoading:
    def test_load_combines_asset_and_macro(self, tmp_path):
        asset_dir = tmp_path / "assets"
        macro_dir = tmp_path / "macro"
        asset_dir.mkdir()
        macro_dir.mkdir()

        asset_dates = pd.date_range('2000-01-01', periods=3, freq='D')
        macro_dates = ['2000-01-01', '2000-01-02', '2000-01-03']

        _write_asset_file(
            asset_dir / "US_10Y_GOV_BOND_RETURN.csv",
            asset_dates,
            [100.0, 101.0, 102.0],
        )
        _write_macro_file(
            macro_dir / "gpr_daily_1900_2025.csv",
            macro_dates,
            [90.0, 91.0, 92.0],
        )

        pipeline = DataPipeline(asset_dir=asset_dir, macro_dir=macro_dir)
        data = pipeline.load('2000-01-01', '2000-01-03')

        assert 'asset_us_10y_gov_bond' in data.columns
        assert 'macro_gpr' in data.columns
        assert len(data) == 3

    def test_load_respects_date_range(self, tmp_path):
        asset_dir = tmp_path / "assets"
        macro_dir = tmp_path / "macro"
        asset_dir.mkdir()
        macro_dir.mkdir()

        dates = pd.date_range('1999-12-30', periods=5, freq='D')
        _write_asset_file(
            asset_dir / "US_CASH_RETURN.csv",
            dates,
            [100, 101, 102, 103, 104],
        )

        pipeline = DataPipeline(asset_dir=asset_dir, macro_dir=macro_dir)
        data = pipeline.load('1999-12-31', '2000-01-01')

        assert data.index.min() == pd.Timestamp('1999-12-31')
        assert data.index.max() == pd.Timestamp('2000-01-01')

    def test_missing_directories_return_empty(self, tmp_path):
        pipeline = DataPipeline(
            asset_dir=tmp_path / "missing_assets",
            macro_dir=tmp_path / "missing_macro",
        )
        data = pipeline.load('2000-01-01', '2000-01-02')
        assert data.empty


class TestDataPipelineMetadata:
    def test_get_asset_list(self, tmp_path):
        asset_dir = tmp_path / "assets"
        macro_dir = tmp_path / "macro"
        asset_dir.mkdir()
        macro_dir.mkdir()

        dates = pd.date_range('2000-01-01', periods=2, freq='D')
        _write_asset_file(asset_dir / "US_10Y_GOV_BOND_RETURN.csv", dates, [100, 101])
        _write_asset_file(asset_dir / "US_TIPS_0_5_TOTAL_RETURN.csv", dates, [50, 51])

        pipeline = DataPipeline(asset_dir=asset_dir, macro_dir=macro_dir)
        assets = pipeline.get_asset_list()

        assert 'US_10Y_GOV_BOND' in assets
        assert 'US_TIPS_0_5' in assets
        assert len(assets) == 2
