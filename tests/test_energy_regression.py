"""Tier 2 regression tests for src/energy.py.

Runs loads_to_site_energy() with real equipment library data and a small
synthetic load (24 hours), covering four distinct equipment configurations.
Two layers:
  2a — Physics invariant checks: energy balance holds regardless of inputs.
  2b — Snapshot regression: full output must match the committed CSV snapshot.

To seed or update snapshots after a deliberate change:
    pytest -m regression --snapshot-update
Then review the diff with: git diff tests/__snapshots__/
"""

import numpy as np
import pandas as pd
import pytest

from src import paths
from src.config import Columns as Col
from src.energy import loads_to_site_energy
from src.equipment import load_library
from src.loads import StandardLoad

# ---------------------------------------------------------------------------
# Scenario IDs — one per distinct equipment configuration
# ---------------------------------------------------------------------------
SCENARIOS = [
    "eq_scenario_3",  # AWHP + boiler backup + cooling
    "eq_scenario_4",  # AWHP + electric resistance backup + cooling
    "eq_scenario_5",  # HR-WWHP + AWHP + cooling + electric resistance backup
    "eq_scenario_10",  # HR-WWHP only (no AWHP) + boiler backup, no AWHP cooling
]

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def library():
    return load_library(paths.EQUIPMENT_JSON)


@pytest.fixture(scope="module")
def synthetic_load():
    """24-hour synthetic load covering cold, mild, warm, and hot OAT conditions.

    Deliberately spans the AWHP operating limits (-15°C to +35°C heating,
    +5°C to +45°C cooling) so that capacity-constraint zeroing is exercised.
    """
    t_out = np.array(
        [
            -20.0,
            -15.0,
            -10.0,
            -5.0,  # below and at AWHP heating min
            0.0,
            4.4,
            10.0,
            15.0,  # normal AWHP heating range
            20.0,
            25.0,
            28.0,
            30.0,  # mild — simultaneous H+C possible
            35.0,
            36.0,
            40.0,
            45.0,  # warm — above AWHP heating max
            -10.0,
            -5.0,
            0.0,
            5.0,  # repeat cold block
            10.0,
            15.0,
            20.0,
            25.0,  # repeat mild block
        ]
    )

    # Heating load: peaks when cold, tapers to zero above ~25°C
    heating_W = np.clip((-t_out + 25) * 10_000, 0, None).astype(float)
    # Cooling load: zero when cold, builds above 15°C
    cooling_W = np.clip((t_out - 15) * 8_000, 0, None).astype(float)

    df = pd.DataFrame(
        {
            "timestamp": pd.date_range("2025-01-01", periods=24, freq="h"),
            "t_out_C": t_out,
            "heating_W": heating_W,
            "cooling_W": cooling_W,
        }
    )
    return StandardLoad(df)


# ---------------------------------------------------------------------------
# Layer 2a — Physics invariant checks
# ---------------------------------------------------------------------------


@pytest.mark.regression
@pytest.mark.parametrize("scenario_id", SCENARIOS)
def test_all_heating_load_served(scenario_id, library, synthetic_load):
    df = loads_to_site_energy(load=synthetic_load, library=library, scenario_ids=[scenario_id])

    heating_served = (
        df[Col.HR_HHW_W.value].fillna(0)
        + df[Col.AWHP_HHW_W.value].fillna(0)
        + df[Col.BOILER_HHW_W.value].fillna(0)
        + df[Col.RES_HHW_W.value].fillna(0)
    )
    assert np.allclose(heating_served, df[Col.HHW_W.value], atol=1.0), (
        f"[{scenario_id}] Heating load not fully served. "
        f"Max gap: {abs(heating_served - df[Col.HHW_W.value]).max():.2f} W"
    )


@pytest.mark.regression
@pytest.mark.parametrize("scenario_id", SCENARIOS)
def test_all_cooling_load_served(scenario_id, library, synthetic_load):
    df = loads_to_site_energy(load=synthetic_load, library=library, scenario_ids=[scenario_id])

    cooling_served = (
        df[Col.HR_CHW_W.value].fillna(0)
        + df[Col.AWHP_CHW_W.value].fillna(0)
        + df[Col.CHILLER_CHW_W.value].fillna(0)
    )
    assert np.allclose(cooling_served, df[Col.CHW_W.value], atol=1.0), (
        f"[{scenario_id}] Cooling load not fully served. "
        f"Max gap: {abs(cooling_served - df[Col.CHW_W.value]).max():.2f} W"
    )


@pytest.mark.regression
@pytest.mark.parametrize("scenario_id", SCENARIOS)
def test_electricity_components_sum_to_total(scenario_id, library, synthetic_load):
    df = loads_to_site_energy(load=synthetic_load, library=library, scenario_ids=[scenario_id])

    elec_sum = (
        df[Col.ELEC_HR_WH.value].fillna(0)
        + df[Col.ELEC_AWHP_H_WH.value].fillna(0)
        + df[Col.ELEC_RES_WH.value].fillna(0)
        + df[Col.ELEC_AWHP_C_WH.value].fillna(0)
        + df[Col.ELEC_CHILLER_WH.value].fillna(0)
    )
    assert np.allclose(elec_sum, df[Col.ELEC_WH.value], atol=1.0), (
        f"[{scenario_id}] Component electricity does not sum to total. "
        f"Max gap: {abs(elec_sum - df[Col.ELEC_WH.value]).max():.4f} Wh"
    )


@pytest.mark.regression
@pytest.mark.parametrize("scenario_id", SCENARIOS)
def test_no_negative_energy(scenario_id, library, synthetic_load):
    df = loads_to_site_energy(load=synthetic_load, library=library, scenario_ids=[scenario_id])

    assert (df[Col.ELEC_WH.value] >= -1e-9).all(), f"[{scenario_id}] Negative electricity detected"
    assert (
        df[Col.GAS_WH.value] >= -1e-9
    ).all(), f"[{scenario_id}] Negative gas consumption detected"


# ---------------------------------------------------------------------------
# Layer 2b — Snapshot regression
# ---------------------------------------------------------------------------


@pytest.mark.regression
@pytest.mark.parametrize("scenario_id", SCENARIOS)
def test_scenario_output_snapshot(snapshot, scenario_id, library, synthetic_load):
    """Full output DataFrame must match committed snapshot.

    On first run this creates the snapshot. On subsequent runs it compares.
    To update after a deliberate change: pytest -m regression --snapshot-update
    """
    df = loads_to_site_energy(load=synthetic_load, library=library, scenario_ids=[scenario_id])
    assert snapshot == df.to_csv()
