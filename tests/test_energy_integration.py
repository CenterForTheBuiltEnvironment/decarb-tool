"""Integration tier: full 8760-hour runs on real load and Cambium data.

Runs the same call chain as the Results page (get_load_data -> loads_to_site_energy
-> site_to_source) and checks:
  1. Hour-level invariants (no NaN, loads fully served, non-negative energy,
     component sums, emissions sums) on simulated buildings.
  2. Annual electricity, gas and emissions totals against committed golden
     values (tests/snapshots/integration_annual_totals.json), within ±0.1 %.
  3. A measured-data smoke case (real data with gaps, spans two calendar years).

Golden values are regression anchors, not independent truth (that is the job
of the verification tier). Regenerate deliberately after a change that should
alter results, then review the JSON diff before committing:
    pytest -m integration --generate-golden
"""

import json
from pathlib import Path

import numpy as np
import pytest

from src import paths
from src.config import Columns as Col
from src.energy import loads_to_site_energy, site_to_source
from src.equipment import load_library
from src.loads import get_load_data
from src.metadata import LoadData, Metadata

pytestmark = pytest.mark.integration

GOLDEN_FILE = Path(__file__).parent / "snapshots" / "integration_annual_totals.json"
TOLERANCE = 0.001  # ±0.1 %

# Library buildings: 83 = Hospital, New York (cold); 35 = Large office, San Francisco (mild).
BUILDINGS = {"83": "NYISO", "35": "CAISO"}
SCENARIOS = [
    "eq_scenario_1",  # gas boiler + chiller baseline
    "eq_scenario_3",  # 20 % AWHP (H+C) + gas backup
    "eq_scenario_4",  # 100 % AWHP (H+C) + electric backup
    "eq_scenario_5",  # HR-WWHP + 100 % AWHP + electric backup
    "eq_scenario_10",  # HR-WWHP + gas boiler + chiller
    "eq_scenario_18",  # 100 % AWHP + fuel switching
]
SIMULATED_CASES = [(b, s) for b in BUILDINGS for s in SCENARIOS]
MEASURED_CASE = ("182", "NorthernGrid_West", "eq_scenario_3")  # gaps, leap year, 2 calendar years


def _metadata(building_id: str, load_type: str, region: str) -> Metadata:
    """App defaults: Cambium MidCase long-run marginal, 2025/2035/2045, 5 % leakage."""
    metadata = Metadata.create(building_id=building_id, load_data=LoadData(load_type=load_type))
    metadata.set_gea_grid_region_for_all(region)
    return metadata


def _key(building_id: str, scenario_id: str, load_type: str = "simulated") -> str:
    return f"building_{building_id}_{scenario_id}_{load_type}"


def _run(building_id, scenario_id, load_type, region, library):
    metadata = _metadata(building_id, load_type, region)
    site = loads_to_site_energy(get_load_data(metadata), library, [scenario_id], detail=True)
    return site, site_to_source(site, metadata=metadata)


@pytest.fixture(scope="module")
def results():
    """Run every case once per module: {key: (site_df, source_df)}."""
    library = load_library(paths.EQUIPMENT_JSON)
    out = {_key(b, s): _run(b, s, "simulated", BUILDINGS[b], library) for b, s in SIMULATED_CASES}
    b, region, s = MEASURED_CASE
    out[_key(b, s, "measured")] = _run(b, s, "measured", region, library)
    return out


# ---------------------------------------------------------------------------
# Hour-level invariants (simulated buildings)
# ---------------------------------------------------------------------------

case_params = pytest.mark.parametrize(
    "building_id, scenario_id", SIMULATED_CASES, ids=[_key(b, s) for b, s in SIMULATED_CASES]
)


@case_params
def test_no_nans_in_core_columns(building_id, scenario_id, results):
    site, source = results[_key(building_id, scenario_id)]
    for col in (Col.ELEC_WH, Col.GAS_WH, Col.HHW_W, Col.CHW_W):
        assert not site[col.value].isna().any(), f"NaN in site '{col.value}'"
    for col in (Col.ELEC_EMISSIONS_RATE_G_PER_KWH, Col.TOTAL_EMISSIONS_KG_CO2E):
        assert not source[col.value].isna().any(), f"NaN in source '{col.value}'"


@case_params
def test_heating_and_cooling_fully_served(building_id, scenario_id, results):
    """Checked after fuel switching (source frame), where dispatch is final."""
    _, df = results[_key(building_id, scenario_id)]
    heat = sum(
        df[c.value].fillna(0)
        for c in (Col.HR_HHW_W, Col.AWHP_HHW_W, Col.BOILER_HHW_W, Col.RES_HHW_W)
    )
    cool = sum(df[c.value].fillna(0) for c in (Col.HR_CHW_W, Col.AWHP_CHW_W, Col.CHILLER_CHW_W))
    assert np.allclose(heat, df[Col.HHW_W.value], atol=1.0), "unserved heating"
    assert np.allclose(cool, df[Col.CHW_W.value], atol=1.0), "unserved cooling"


@case_params
def test_energy_non_negative_and_components_sum(building_id, scenario_id, results):
    _, df = results[_key(building_id, scenario_id)]
    assert (df[Col.ELEC_WH.value] >= -1e-6).all()
    assert (df[Col.GAS_WH.value] >= -1e-6).all()
    components = sum(
        df[c.value].fillna(0)
        for c in (
            Col.ELEC_HR_WH,
            Col.ELEC_AWHP_H_WH,
            Col.ELEC_RES_WH,
            Col.ELEC_AWHP_C_WH,
            Col.ELEC_CHILLER_WH,
        )
    )
    assert np.allclose(components, df[Col.ELEC_WH.value], atol=1.0)
    assert np.allclose(df[Col.GAS_BOILER_WH.value].fillna(0), df[Col.GAS_WH.value], atol=1.0)


@case_params
def test_emissions_components_sum(building_id, scenario_id, results):
    _, df = results[_key(building_id, scenario_id)]
    parts = (
        df[Col.ELEC_EMISSIONS_KG_CO2E.value]
        + df[Col.GAS_EMISSIONS_KG_CO2E.value]
        + df[Col.TOTAL_REFRIG_EMISSIONS_KG_CO2E.value]
    )
    assert np.allclose(parts, df[Col.TOTAL_EMISSIONS_KG_CO2E.value], atol=1e-6)


# ---------------------------------------------------------------------------
# Annual golden values
# ---------------------------------------------------------------------------


def _annual_totals(site, source) -> dict:
    totals = {
        "elec_kWh": round(site[Col.ELEC_WH.value].sum() / 1000, 2),
        "gas_kWh": round(site[Col.GAS_WH.value].sum() / 1000, 2),
    }
    for em_id, em in source.groupby(Col.EM_SCEN_ID.value):
        totals[em_id] = {
            "elec_kWh": round(em[Col.ELEC_WH.value].sum() / 1000, 2),  # after fuel switching
            "gas_kWh": round(em[Col.GAS_WH.value].sum() / 1000, 2),
            "total_kgCO2e": round(em[Col.TOTAL_EMISSIONS_KG_CO2E.value].sum(), 2),
            "refrig_kgCO2e": round(em[Col.TOTAL_REFRIG_EMISSIONS_KG_CO2E.value].sum(), 2),
        }
    return totals


def _flatten(d, prefix=""):
    for k, v in d.items():
        if isinstance(v, dict):
            yield from _flatten(v, f"{prefix}{k}.")
        else:
            yield f"{prefix}{k}", v


@pytest.fixture(scope="module")
def golden(request, results):
    if request.config.getoption("--generate-golden"):
        data = {key: _annual_totals(*frames) for key, frames in results.items()}
        GOLDEN_FILE.parent.mkdir(parents=True, exist_ok=True)
        GOLDEN_FILE.write_text(json.dumps(data, indent=2) + "\n")
        print(f"\nGolden values written to {GOLDEN_FILE}; review `git diff` before committing.")
    if not GOLDEN_FILE.exists():
        pytest.fail(
            f"{GOLDEN_FILE} missing. Generate it with: pytest -m integration --generate-golden"
        )
    return json.loads(GOLDEN_FILE.read_text())


ALL_KEYS = [_key(b, s) for b, s in SIMULATED_CASES] + [
    _key(MEASURED_CASE[0], MEASURED_CASE[2], "measured")
]


@pytest.mark.parametrize("key", ALL_KEYS)
def test_annual_totals_match_golden(key, results, golden):
    assert key in golden, f"No golden entry for {key}. Regenerate with --generate-golden."
    actual = dict(_flatten(_annual_totals(*results[key])))
    expected = dict(_flatten(golden[key]))
    assert actual.keys() == expected.keys()
    drift = {
        metric: (expected[metric], actual[metric])
        for metric in expected
        if actual[metric] != pytest.approx(expected[metric], rel=TOLERANCE, abs=0.01)
    }
    assert not drift, f"[{key}] golden (expected, actual) beyond ±{TOLERANCE:.1%}: {drift}"


# ---------------------------------------------------------------------------
# Measured data
# ---------------------------------------------------------------------------


def test_measured_building_runs_end_to_end(results):
    b, _, s = MEASURED_CASE
    site, source = results[_key(b, s, "measured")]
    assert len(site) in (8760, 8784)
    assert source[Col.TOTAL_EMISSIONS_KG_CO2E.value].sum() > 0


@pytest.mark.xfail(
    strict=True,
    reason=(
        "Known issue: hours with missing outdoor temperature become NaN for AWHP scenarios but "
        "not for boiler/chiller scenarios, so annual totals of different scenarios cover "
        "different hours on measured data (building 182: 16 vs 648 NaN hours). Remove this "
        "xfail once missing hours are handled consistently."
    ),
)
def test_measured_scenarios_cover_the_same_hours():
    b, region, _ = MEASURED_CASE
    library = load_library(paths.EQUIPMENT_JSON)
    nan_hours = {
        s: int(_run(b, s, "measured", region, library)[0][Col.ELEC_WH.value].isna().sum())
        for s in ("eq_scenario_1", "eq_scenario_4")
    }
    assert len(set(nan_hours.values())) == 1, nan_hours
