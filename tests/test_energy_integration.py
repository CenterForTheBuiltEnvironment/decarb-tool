"""Tier 3 integration / smoke tests for src/energy.py.

Simulation cases (full invariant suite):
  1. No NaNs in core output columns
  2. All heating and cooling load served (energy balance)
  3. Electricity and gas non-negative
  4. Component electricity sum matches total
  5. Annual totals match golden values within ±0.1%

Measured cases (smoke test only):
  Verifies the run completes without error and annual totals match golden
  values. Hour-level invariants are not checked because real-world data
  contains missing t_out_C values that propagate through AWHP calculations.

Golden values are stored in tests/snapshots/integration_annual_totals.json.
They are populated once (manually seeded) and updated deliberately after a
code or data change that legitimately alters results.

To generate golden values on first run:
    pytest -m integration --generate-golden
"""

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src import paths
from src.config import Columns as Col
from src.energy import loads_to_site_energy
from src.equipment import load_library
from src.loads import StandardLoad

GOLDEN_FILE = Path(__file__).parent / "snapshots" / "integration_annual_totals.json"
TOLERANCE = 0.001  # ±0.1%

# Simulation cases: clean inputs, full invariant suite applies.
SIMULATION_CASES = [
    ("5", "eq_scenario_3", "simulation"),  # Office, Port Angeles (mild): AWHP + boiler + cooling
    (
        "5",
        "eq_scenario_5",
        "simulation",
    ),  # Office, Port Angeles: HR-WWHP + AWHP + cooling + elec resistance
    ("1", "eq_scenario_3", "simulation"),  # Hospital, Denver (cold): AWHP + boiler + cooling
]

# Measured cases: real-world data with missing t_out_C hours; smoke test only.
MEASURED_CASES = [
    ("180", "eq_scenario_3", "measured"),  # Measured building: AWHP + boiler + cooling
]

ALL_CASES = SIMULATION_CASES + MEASURED_CASES


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_building(building_id: str, source: str) -> StandardLoad:
    df = pd.read_parquet(
        paths.LOAD_DATA_PARQUET,
        filters=[("building_id", "=", building_id), ("source", "=", source)],
    )
    return StandardLoad(df[["timestamp", "t_out_C", "heating_W", "cooling_W"]].copy())


def _case_key(building_id: str, scenario_id: str, source: str) -> str:
    return f"building_{building_id}_{scenario_id}_{source}"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def library_session():
    return load_library(paths.EQUIPMENT_JSON)


@pytest.fixture(scope="session")
def integration_results(library_session):
    """Run all integration cases once per session and cache results."""
    cache = {}
    for building_id, scenario_id, source in ALL_CASES:
        load = _load_building(building_id, source)
        df = loads_to_site_energy(load=load, library=library_session, scenario_ids=[scenario_id])
        cache[_case_key(building_id, scenario_id, source)] = df
    return cache


# ---------------------------------------------------------------------------
# Invariant tests — simulation cases only
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.parametrize("building_id,scenario_id,source", SIMULATION_CASES)
def test_no_nans_in_summary_columns(building_id, scenario_id, source, integration_results):
    """Core output columns must never be NaN.

    Detail columns (hr_hhw_W, boiler_eff, etc.) are intentionally NaN
    when the corresponding phase doesn't run for a given scenario — those
    are checked implicitly by the energy-balance invariants below.
    """
    df = integration_results[_case_key(building_id, scenario_id, source)]
    always_populated = [
        Col.T_OUT_C.value,
        Col.HEATING_W.value,
        Col.COOLING_W.value,
        Col.HHW_W.value,
        Col.CHW_W.value,
        Col.ELEC_WH.value,
        Col.GAS_WH.value,
    ]
    for col in always_populated:
        assert (
            not df[col].isna().any()
        ), f"[{building_id}/{scenario_id}] NaN found in column '{col}'"


@pytest.mark.integration
@pytest.mark.parametrize("building_id,scenario_id,source", SIMULATION_CASES)
def test_all_heating_served(building_id, scenario_id, source, integration_results):
    df = integration_results[_case_key(building_id, scenario_id, source)]
    heating_served = (
        df[Col.HR_HHW_W.value].fillna(0)
        + df[Col.AWHP_HHW_W.value].fillna(0)
        + df[Col.BOILER_HHW_W.value].fillna(0)
        + df[Col.RES_HHW_W.value].fillna(0)
    )
    assert np.allclose(heating_served, df[Col.HHW_W.value], atol=1.0), (
        f"[{building_id}/{scenario_id}] Unserved heating load. "
        f"Max gap: {abs(heating_served - df[Col.HHW_W.value]).max():.2f} W"
    )


@pytest.mark.integration
@pytest.mark.parametrize("building_id,scenario_id,source", SIMULATION_CASES)
def test_all_cooling_served(building_id, scenario_id, source, integration_results):
    df = integration_results[_case_key(building_id, scenario_id, source)]
    cooling_served = (
        df[Col.HR_CHW_W.value].fillna(0)
        + df[Col.AWHP_CHW_W.value].fillna(0)
        + df[Col.CHILLER_CHW_W.value].fillna(0)
    )
    assert np.allclose(cooling_served, df[Col.CHW_W.value], atol=1.0), (
        f"[{building_id}/{scenario_id}] Unserved cooling load. "
        f"Max gap: {abs(cooling_served - df[Col.CHW_W.value]).max():.2f} W"
    )


@pytest.mark.integration
@pytest.mark.parametrize("building_id,scenario_id,source", SIMULATION_CASES)
def test_energy_positivity(building_id, scenario_id, source, integration_results):
    df = integration_results[_case_key(building_id, scenario_id, source)]
    assert (
        df[Col.ELEC_WH.value] >= -1e-6
    ).all(), f"[{building_id}/{scenario_id}] Negative electricity found"
    assert (
        df[Col.GAS_WH.value] >= -1e-6
    ).all(), f"[{building_id}/{scenario_id}] Negative gas consumption found"


@pytest.mark.integration
@pytest.mark.parametrize("building_id,scenario_id,source", SIMULATION_CASES)
def test_component_electricity_sum(building_id, scenario_id, source, integration_results):
    df = integration_results[_case_key(building_id, scenario_id, source)]
    elec_sum = (
        df[Col.ELEC_HR_WH.value].fillna(0)
        + df[Col.ELEC_AWHP_H_WH.value].fillna(0)
        + df[Col.ELEC_RES_WH.value].fillna(0)
        + df[Col.ELEC_AWHP_C_WH.value].fillna(0)
        + df[Col.ELEC_CHILLER_WH.value].fillna(0)
    )
    assert np.allclose(elec_sum, df[Col.ELEC_WH.value], atol=1.0), (
        f"[{building_id}/{scenario_id}] Component electricity sum mismatch. "
        f"Max gap: {abs(elec_sum - df[Col.ELEC_WH.value]).max():.4f} Wh"
    )


# ---------------------------------------------------------------------------
# Annual golden values — all cases
# ---------------------------------------------------------------------------


def _compute_annual_totals(df: pd.DataFrame) -> dict:
    return {
        "total_elec_kWh": round(df[Col.ELEC_WH.value].sum() / 1000, 2),
        "total_gas_kWh": round(df[Col.GAS_WH.value].sum() / 1000, 2),
    }


@pytest.mark.integration
@pytest.mark.parametrize("building_id,scenario_id,source", ALL_CASES)
def test_annual_totals_match_golden(building_id, scenario_id, source, integration_results):
    """Annual electricity and gas must be within ±0.1% of the committed golden values.

    If GOLDEN_FILE does not exist, this test is skipped with a message explaining
    how to generate it. Run once with --generate-golden to create the file.
    """
    if not GOLDEN_FILE.exists():
        pytest.skip(
            f"Golden file not found at {GOLDEN_FILE}. "
            "Run once with: pytest -m integration --generate-golden"
        )

    golden = json.loads(GOLDEN_FILE.read_text())
    key = _case_key(building_id, scenario_id, source)

    if key not in golden:
        pytest.skip(f"No golden entry for key '{key}'. Re-run with --generate-golden.")

    df = integration_results[key]
    actual = _compute_annual_totals(df)
    expected = golden[key]

    for metric in ["total_elec_kWh", "total_gas_kWh"]:
        exp_val = expected[metric]
        act_val = actual[metric]
        if exp_val == 0:
            assert act_val == 0, f"[{key}] {metric}: expected 0, got {act_val}"
        else:
            rel_err = abs(act_val - exp_val) / abs(exp_val)
            assert rel_err <= TOLERANCE, (
                f"[{key}] {metric}: expected {exp_val:.2f}, got {act_val:.2f} "
                f"(relative error {rel_err:.4%} > {TOLERANCE:.1%})"
            )


# ---------------------------------------------------------------------------
# Golden file generation (opt-in via --generate-golden flag, defined in conftest.py)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session", autouse=True)
def maybe_generate_golden(request, integration_results):
    """Write golden file if --generate-golden flag is set."""
    if not request.config.getoption("--generate-golden", default=False):
        return

    golden = {}
    for building_id, scenario_id, source in ALL_CASES:
        key = _case_key(building_id, scenario_id, source)
        df = integration_results[key]
        golden[key] = _compute_annual_totals(df)

    GOLDEN_FILE.parent.mkdir(parents=True, exist_ok=True)
    GOLDEN_FILE.write_text(json.dumps(golden, indent=2))
    print(f"\nGolden values written to {GOLDEN_FILE}")
