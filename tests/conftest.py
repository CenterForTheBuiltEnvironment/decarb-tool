import numpy as np
import pandas as pd
import pytest

from src import paths
from src.emissions import EmissionScenario
from src.equipment import load_library
from src.loads import StandardLoad
from src.metadata import Metadata

"""Shared pytest fixtures and hooks for Berkeley Decarb Tool tests."""


def pytest_addoption(parser):
    parser.addoption(
        "--generate-golden",
        action="store_true",
        default=False,
        help="Regenerate integration_annual_totals.json golden values (Tier 3)",
    )


@pytest.fixture
def sample_load_df():
    """Create a minimal valid load DataFrame with 8760 hours."""
    hours = 8760
    np.random.seed(42)  # Reproducible random data
    return pd.DataFrame(
        {
            "timestamp": pd.date_range("2025-01-01", periods=hours, freq="h"),
            "t_out_C": np.random.uniform(-5, 35, hours),
            "heating_W": np.abs(np.random.uniform(0, 500000, hours)),
            "cooling_W": np.abs(np.random.uniform(0, 300000, hours)),
        }
    )


@pytest.fixture
def standard_load(sample_load_df):
    """Create a StandardLoad instance from sample data."""
    return StandardLoad(sample_load_df)


@pytest.fixture
def equipment_library():
    """Load the actual equipment library from data files."""
    return load_library(paths.EQUIPMENT_JSON)


@pytest.fixture
def sample_metadata():
    """Create sample metadata for testing."""
    return Metadata.create(
        building_id="test_building",
        location="Berkeley",
        ashrae_climate_zone="3C",
        area_sqm=5000.0,
    )


@pytest.fixture
def emission_scenario():
    """Create a sample emission scenario for testing."""
    return EmissionScenario(
        em_scen_id="test_em_1",
        grid_scenario="MidCase",
        gea_grid_region="CAMX",
        time_zone="America/Los_Angeles",
        emission_type="Includes pre-combustion",
        shortrun_weighting=0.0,
        annual_refrig_leakage_percent=0.05,
        ng_emission_rate_gCO2e_per_kWh=239.2,
        year=2025,
    )
