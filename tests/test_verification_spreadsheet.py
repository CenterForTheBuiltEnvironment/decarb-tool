"""Verification tier, part 3: legacy hand calculations (tests/testing_cases.xlsx).

The spreadsheet was prepared by hand, independently of the code: 7 equipment
scenarios x 3 characteristic hours (heating-dominant, cooling-dominant,
balanced) on 3 buildings. Its inputs and expected values are frozen in
tests/fixtures/spreadsheet_cases.json (see tests/verification/extract_spreadsheet.py
for provenance and for the values tagged "superseded").

Each case runs the tool on the three spreadsheet hours plus two synthetic hours
that reproduce the spreadsheet's annual peaks, so AWHP and chiller sizing see
the same peak loads the hand calculation assumed. Sizing-only hours sit outside
every operating envelope (-40 °C, +60 °C), so they do not interact with the
checked hours.
"""

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.config import Columns as Col
from src.emissions import EmissionScenario
from src.energy import loads_to_site_energy, site_to_source
from src.equipment import EquipmentLibrary
from src.loads import StandardLoad
from src.metadata import Metadata

pytestmark = pytest.mark.verification

FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "spreadsheet_cases.json").read_text())
CASES = {c["id"]: c for c in FIXTURE["cases"]}
REL = 2e-3  # spreadsheet rounds COPs to 2 decimals (up to ~0.2 % on derived energy)
ABS = 1e-3
PEAK_HEAT_TS = pd.Timestamp("2000-01-01 00:00")
PEAK_COOL_TS = pd.Timestamp("2000-01-01 01:00")


def _library(case):
    return EquipmentLibrary(equipment=FIXTURE["equipment"], equipment_scenarios=[case["scenario"]])


def _load(case):
    hours = case["hours"]
    peak_heat = case["peak_heating_kW"] or max(h["heating_kW"] for h in hours)
    df = pd.DataFrame(
        {
            "timestamp": [PEAK_HEAT_TS, PEAK_COOL_TS]
            + [pd.Timestamp(h["timestamp"]) for h in hours],
            "t_out_C": [-40.0, 60.0] + [h["t_out_C"] for h in hours],
            "heating_W": np.array([peak_heat, 0.0] + [h["heating_kW"] for h in hours]) * 1000,
            "cooling_W": np.array([0.0, case["peak_chiller_kW"]] + [h["cooling_kW"] for h in hours])
            * 1000,
        }
    )
    return StandardLoad(df)


_site_cache: dict[str, pd.DataFrame] = {}


def _site(case_id):
    if case_id not in _site_cache:
        case = CASES[case_id]
        _site_cache[case_id] = loads_to_site_energy(
            _load(case), _library(case), [case_id], detail=True
        )
    return _site_cache[case_id]


def _energy_params():
    for case in FIXTURE["cases"]:
        for hour in case["hours"]:
            for check in hour["checks"]:
                yield pytest.param(
                    case["id"],
                    hour["timestamp"],
                    check,
                    id=f"{case['id']}-{hour['timestamp'][:13]}-{check['column']}",
                )


@pytest.mark.parametrize("case_id, timestamp, check", list(_energy_params()))
def test_hourly_energy_matches_hand_calculation(case_id, timestamp, check):
    row = _site(case_id).loc[pd.Timestamp(timestamp)]
    tool = row[check["column"]]
    tool = 0.0 if pd.isna(tool) else tool / check["divisor"]
    assert tool == pytest.approx(check["value"], rel=REL, abs=ABS), check["label"]


def _known_difference_params():
    for case in FIXTURE["cases"]:
        for hour in case["hours"]:
            for check in hour["known_differences"]:
                yield pytest.param(
                    case["id"],
                    hour["timestamp"],
                    check,
                    id=f"{case['id']}-{hour['timestamp'][:13]}-{check['column']}",
                    marks=pytest.mark.xfail(strict=True, reason=check["reason"]),
                )


@pytest.mark.parametrize("case_id, timestamp, check", list(_known_difference_params()))
def test_known_method_differences(case_id, timestamp, check):
    """Documented open differences; strict xfail flags it if the tool's behaviour changes."""
    test_hourly_energy_matches_hand_calculation(case_id, timestamp, check)


# ---------------------------------------------------------------------------
# Emissions — only cases using pure long-run marginal rates. The spreadsheet's
# other cases blend short- and long-run rates with a weighting input the tool
# no longer offers.
# ---------------------------------------------------------------------------

LRMER_CASES = [c["id"] for c in FIXTURE["cases"] if c["emissions"]["shortrun_weighting"] == 0]


def _source(case_id):
    em = CASES[case_id]["emissions"]
    metadata = Metadata.create(
        emission_settings=[
            EmissionScenario(
                em_scen_id="em_sheet",
                em_scen_name=case_id,
                elec_emission_source="Marginal (Cambium, Long-run)",
                grid_scenario=em["grid_scenario"],
                gea_grid_region=em["gea_grid_region"],
                emission_type=em["emission_type"],
                annual_refrig_leakage_percent=em["annual_refrig_leakage"],
                ng_emission_rate_gCO2e_per_kWh=em["ng_rate_g_per_kWh"],
                year=em["year"],
            )
        ]
    )
    return site_to_source(_site(case_id), metadata=metadata)


@pytest.mark.parametrize("case_id", LRMER_CASES)
def test_hourly_grid_rate_and_emissions(case_id):
    out = _source(case_id)
    for hour in CASES[case_id]["hours"]:
        row = out.loc[pd.Timestamp(hour["timestamp"])]
        assert row[Col.ELEC_EMISSIONS_RATE_G_PER_KWH.value] == pytest.approx(
            hour["elec_rate_g_per_kWh"], rel=REL
        ), f"Cambium month-hour rate at {hour['timestamp']}"
        assert row[Col.GAS_EMISSIONS_KG_CO2E.value] == pytest.approx(
            hour["gas_emissions_kg"], rel=REL, abs=ABS
        )
        if not any(s["column"] == "elec_Wh" for s in hour["superseded"]):
            assert row[Col.ELEC_EMISSIONS_KG_CO2E.value] == pytest.approx(
                hour["elec_emissions_kg"], rel=REL, abs=ABS
            )


@pytest.mark.parametrize("case_id", [c["id"] for c in FIXTURE["cases"]])
def test_annual_refrigerant_emissions(case_id):
    """Refrigerant inventory (unit counts x charge x GWP x leakage) for the year.

    The spreadsheet spreads the annual figure over 8760 h; the tool spreads it
    over the rows supplied, so annual totals are compared.
    """
    em = CASES[case_id]["emissions"]
    metadata = Metadata.create(
        emission_settings=[
            EmissionScenario(
                em_scen_id="em_const",
                em_scen_name="constant",
                elec_emission_source="Constant (User-provided)",
                elec_avg_emission_rate_gCO2e_per_kWh=0.0,
                emission_type="Includes pre-combustion",
                annual_refrig_leakage_percent=em["annual_refrig_leakage"],
                ng_emission_rate_gCO2e_per_kWh=0.0,
                year=2025,
            )
        ]
    )
    out = site_to_source(_site(case_id), metadata=metadata)
    assert out[Col.TOTAL_REFRIG_EMISSIONS_KG_CO2E.value].sum() == pytest.approx(
        em["refrig_emissions_kg_per_hour"] * 8760, rel=REL
    )
