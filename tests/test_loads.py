"""Tests for load data validation and processing."""

import pandas as pd
import pytest

from src.loads import STANDARD_COLUMNS, StandardLoad


class TestStandardLoad:
    """Tests for StandardLoad validation and processing."""

    def test_valid_load_creation(self, sample_load_df):
        """Test creation with valid data succeeds."""
        load = StandardLoad(sample_load_df)
        assert load.num_hours == len(sample_load_df)

    def test_missing_columns_raises_error(self):
        """Test that missing required columns raise ValueError."""
        df = pd.DataFrame(
            {
                "timestamp": pd.date_range("2025-01-01", periods=100, freq="h"),
                "t_out_C": [20] * 100,
                # Missing heating_W and cooling_W
            }
        )
        with pytest.raises(ValueError, match="Missing required columns"):
            StandardLoad(df)

    def test_standard_columns_defined(self):
        """Test that STANDARD_COLUMNS constant is properly defined."""
        assert "t_out_C" in STANDARD_COLUMNS
        assert "heating_W" in STANDARD_COLUMNS
        assert "cooling_W" in STANDARD_COLUMNS

    def test_load_dataframe_accessible(self, standard_load):
        """Test that underlying DataFrame is accessible."""
        assert hasattr(standard_load, "df")
        assert isinstance(standard_load.df, pd.DataFrame)

    def test_load_has_timestamp_index(self, standard_load):
        """Test that load data has timestamp as index."""
        assert standard_load.df.index.name == "timestamp"

    def test_compute_load_stats(self, standard_load):
        """Test load statistics computation."""
        stats = standard_load.compute_load_stats()
        assert "hhw_max_load" in stats
        assert "chw_max_load" in stats
        assert stats["hhw_max_load"] >= 0
        assert stats["chw_max_load"] >= 0

    def test_leap_year_detection(self):
        """Test leap day detection for leap years."""
        # 2024 is a leap year (8784 hours)
        df = pd.DataFrame(
            {
                "timestamp": pd.date_range("2024-01-01", periods=8784, freq="h"),
                "t_out_C": [20] * 8784,
                "heating_W": [1000] * 8784,
                "cooling_W": [500] * 8784,
            }
        )
        load = StandardLoad(df)
        assert load.has_leap_day  # Use truthy check instead of 'is True'

    def test_non_leap_year_detection(self, sample_load_df):
        """Test leap day detection for non-leap years."""
        # 2025 is not a leap year (sample_load_df uses 2025)
        load = StandardLoad(sample_load_df)
        assert not load.has_leap_day  # Use falsy check instead of 'is False'


class TestLoadDataValidation:
    """Tests for edge cases in load data validation."""

    def test_negative_loads_allowed(self):
        """Test that negative load values are allowed (heat recovery scenarios)."""
        df = pd.DataFrame(
            {
                "timestamp": pd.date_range("2025-01-01", periods=100, freq="h"),
                "t_out_C": [20] * 100,
                "heating_W": [-1000] * 100,  # Negative heating (unusual but valid)
                "cooling_W": [500] * 100,
            }
        )
        # Should not raise an error
        load = StandardLoad(df)
        assert load is not None

    def test_zero_loads_allowed(self):
        """Test that zero load values are allowed."""
        df = pd.DataFrame(
            {
                "timestamp": pd.date_range("2025-01-01", periods=100, freq="h"),
                "t_out_C": [20] * 100,
                "heating_W": [0] * 100,
                "cooling_W": [0] * 100,
            }
        )
        load = StandardLoad(df)
        assert load is not None
