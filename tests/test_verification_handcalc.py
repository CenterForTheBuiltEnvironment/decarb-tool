"""Verification tier, part 1: hand-calculated closed-form cases.

Every expected value below is written as plain arithmetic a reviewer can check by
hand, using the round-number equipment in tests/verification/equipment.py
(not the production library). These tests fail only if the engine's physics or
bookkeeping changes, never because the equipment library was edited.

Eight-hour load profile (kW thermal); each hour isolates one mechanism:

    hr  OAT   heat  cool   what it exercises
    0     0    120     0   AWHP at a catalogue point (COP 2.5, 60 kW/unit); sets the sizing peak
    1   -10    100     0   AWHP at the lower catalogue point (COP 2.0, 50 kW/unit)
    2   -20    110     0   below AWHP operating limit -> backup serves 100 %
    3     5     80     0   linear interpolation between catalogue points (COP 2.75)
    4    -5    120     0   load above AWHP capacity (2 x 55 kW) -> backup serves the rest
    5    25      0    60   AWHP cooling, interpolated (COP 4.5, 95 kW/unit)
    6    20     40   100   simultaneous: one of four compressors heats, three cool
    7    35      0   300   above AWHP heating limit; cooling capacity exceeded -> chiller

AWHP sizing (integer, 100 % of peak heating, N+1):
    units = ceil(120 kW / 60 kW at the 0 °C reference) = 2, plus 1 redundant = 3
"""

import math

import numpy as np
import pandas as pd
import pytest

from src.config import Columns as Col
from src.emissions import EmissionScenario
from src.energy import loads_to_site_energy, site_to_source
from src.loads import StandardLoad
from src.metadata import Metadata
from tests.verification import equipment as V

pytestmark = pytest.mark.verification

kW = 1000.0
OAT = [0.0, -10.0, -20.0, 5.0, -5.0, 25.0, 20.0, 35.0]
HEAT_kW = [120.0, 100.0, 110.0, 80.0, 120.0, 0.0, 40.0, 0.0]
COOL_kW = [0.0, 0.0, 0.0, 0.0, 0.0, 60.0, 100.0, 300.0]
N_HOURS = len(OAT)

AWHP_UNITS = math.ceil(max(HEAT_kW) / 60.0)  # 2
AWHP_UNITS_TOTAL = AWHP_UNITS + 1  # N+1 redundancy

REL = 1e-6  # engine rounds hourly Wh to 4 decimals


@pytest.fixture(scope="module")
def library():
    return V.verification_library()


@pytest.fixture(scope="module")
def load():
    return StandardLoad(
        pd.DataFrame(
            {
                "timestamp": pd.date_range("2025-01-01", periods=N_HOURS, freq="h"),
                "t_out_C": OAT,
                "heating_W": np.array(HEAT_kW) * kW,
                "cooling_W": np.array(COOL_kW) * kW,
            }
        )
    )


def _site(library, load, scenario_id):
    return loads_to_site_energy(load, library, [scenario_id], detail=True)


def _source(site_df, elec_rate, ng_rate=200.0, leakage=0.10):
    metadata = Metadata.create(
        emission_settings=[
            EmissionScenario(
                em_scen_id="em_const",
                em_scen_name="constant",
                elec_emission_source="Constant (User-provided)",
                elec_avg_emission_rate_gCO2e_per_kWh=elec_rate,
                emission_type="Includes pre-combustion",
                annual_refrig_leakage_percent=leakage,
                ng_emission_rate_gCO2e_per_kWh=ng_rate,
                year=2025,
            )
        ]
    )
    return site_to_source(site_df, metadata=metadata)


def _kWh(series):
    return float(series.fillna(0).sum()) / 1000.0


# ---------------------------------------------------------------------------
# Baseline: gas boiler + chiller (fixed efficiencies)
# ---------------------------------------------------------------------------


def test_baseline_gas_equals_heat_over_boiler_efficiency(library, load):
    df = _site(library, load, "v_baseline")
    assert _kWh(df[Col.GAS_WH.value]) == pytest.approx(sum(HEAT_kW) / V.BOILER_EFF, rel=REL)


def test_baseline_electricity_equals_cooling_over_chiller_cop(library, load):
    df = _site(library, load, "v_baseline")
    assert _kWh(df[Col.ELEC_WH.value]) == pytest.approx(sum(COOL_kW) / V.CHILLER_COP, rel=REL)


# ---------------------------------------------------------------------------
# AWHP heating + gas backup: catalogue lookup, interpolation, limits, sizing
# ---------------------------------------------------------------------------


def test_awhp_unit_count(library, load):
    df = _site(library, load, "v_awhp_gas")
    assert df[Col.AWHP_NUM.value].iloc[0] == AWHP_UNITS
    assert df[Col.AWHP_NUM_R.value].iloc[0] == AWHP_UNITS_TOTAL


@pytest.mark.parametrize(
    "hour, expected_cop, expected_served_kW",
    [
        (0, 2.5, 120.0),  # catalogue point, capacity 2 x 60 = 120 exactly meets load
        (1, 2.0, 100.0),  # catalogue point, capacity 2 x 50 = 100 exactly meets load
        (2, 2.0, 0.0),  # -20 °C is below the -10 °C limit: capacity forced to 0
        (3, 2.75, 80.0),  # halfway between 0 °C (2.5) and 10 °C (3.0)
        (4, 2.25, 110.0),  # halfway between -10 °C and 0 °C; capacity 2 x 55 = 110 < 120
    ],
)
def test_awhp_hourly_cop_and_served_load(library, load, hour, expected_cop, expected_served_kW):
    df = _site(library, load, "v_awhp_gas")
    row = df.iloc[hour]
    assert row[Col.AWHP_COP_H.value] == pytest.approx(expected_cop, rel=REL)
    assert row[Col.AWHP_HHW_W.value] / kW == pytest.approx(expected_served_kW, rel=REL)
    if expected_served_kW > 0:
        assert row[Col.ELEC_AWHP_H_WH.value] / kW == pytest.approx(
            expected_served_kW / expected_cop, rel=REL
        )


def test_awhp_gas_annual_totals(library, load):
    df = _site(library, load, "v_awhp_gas")
    awhp_elec_kWh = 120 / 2.5 + 100 / 2.0 + 80 / 2.75 + 110 / 2.25 + 40 / 4.0
    boiler_heat_kWh = 110 + (120 - 110)  # hour 2 (out of range) + hour 4 (capacity shortfall)
    assert _kWh(df[Col.GAS_WH.value]) == pytest.approx(boiler_heat_kWh / V.BOILER_EFF, rel=REL)
    assert _kWh(df[Col.ELEC_WH.value]) == pytest.approx(
        awhp_elec_kWh + sum(COOL_kW) / V.CHILLER_COP, rel=REL
    )


# ---------------------------------------------------------------------------
# AWHP heating + cooling + electric resistance backup
# ---------------------------------------------------------------------------


def test_electric_resistance_backup_is_one_to_one(library, load):
    df = _site(library, load, "v_awhp_hc_elec")
    assert _kWh(df[Col.GAS_WH.value]) == 0.0
    assert _kWh(df[Col.ELEC_RES_WH.value]) == pytest.approx(110 + 10, rel=REL)


@pytest.mark.parametrize(
    "hour, cooling_units, expected_cop, expected_awhp_kW",
    [
        # No heating: all 2 / 0.5 = 4 compressors cool -> 2 units x 95 kW (interp 25 °C)
        (5, 2.0, 4.5, 60.0),
        # Heating 40 of 160 kW needs ceil(4 x 40/160) = 1 compressor; 3 left = 1.5 units x 100 kW
        (6, 1.5, 5.0, 100.0),
        # 35 °C is above the heating limit (cap 0), so all 4 compressors cool: 2 x 85 = 170 kW
        (7, 2.0, 3.5, 170.0),
    ],
)
def test_awhp_cooling_compressor_split(
    library, load, hour, cooling_units, expected_cop, expected_awhp_kW
):
    df = _site(library, load, "v_awhp_hc_elec")
    row = df.iloc[hour]
    assert row[Col.AWHP_NUM_C.value] == pytest.approx(cooling_units)
    assert row[Col.AWHP_COP_C.value] == pytest.approx(expected_cop, rel=REL)
    assert row[Col.AWHP_CHW_W.value] / kW == pytest.approx(expected_awhp_kW, rel=REL)


def test_awhp_hc_elec_annual_electricity(library, load):
    df = _site(library, load, "v_awhp_hc_elec")
    awhp_heat_kWh = 120 / 2.5 + 100 / 2.0 + 80 / 2.75 + 110 / 2.25 + 40 / 4.0
    resistance_kWh = 110 + 10
    awhp_cool_kWh = 60 / 4.5 + 100 / 5.0 + 170 / 3.5
    chiller_kWh = (300 - 170) / V.CHILLER_COP
    assert _kWh(df[Col.ELEC_WH.value]) == pytest.approx(
        awhp_heat_kWh + resistance_kWh + awhp_cool_kWh + chiller_kWh, rel=REL
    )


# ---------------------------------------------------------------------------
# Emissions: constant grid rate, gas rate, refrigerant leakage
# ---------------------------------------------------------------------------

ELEC_RATE = 400.0  # gCO2e/kWh
NG_RATE = 200.0  # gCO2e/kWh
LEAKAGE = 0.10  # 10 % of charge per year


def test_baseline_emissions(library, load):
    out = _source(_site(library, load, "v_baseline"), ELEC_RATE, NG_RATE, LEAKAGE)
    elec_kWh = sum(COOL_kW) / V.CHILLER_COP
    gas_kWh = sum(HEAT_kW) / V.BOILER_EFF
    chiller_units = math.ceil(max(COOL_kW) * kW / V.CHILLER_CAP_W)  # 1
    refrig_kg = V.CHILLER_REFRIG_KG * chiller_units * V.CHILLER_GWP * LEAKAGE

    assert out[Col.ELEC_EMISSIONS_KG_CO2E.value].sum() == pytest.approx(
        elec_kWh * ELEC_RATE / 1000, rel=REL
    )
    assert out[Col.GAS_EMISSIONS_KG_CO2E.value].sum() == pytest.approx(
        gas_kWh * NG_RATE / 1000, rel=REL
    )
    assert out[Col.TOTAL_REFRIG_EMISSIONS_KG_CO2E.value].sum() == pytest.approx(refrig_kg, rel=REL)
    assert out[Col.TOTAL_EMISSIONS_KG_CO2E.value].sum() == pytest.approx(
        elec_kWh * ELEC_RATE / 1000 + gas_kWh * NG_RATE / 1000 + refrig_kg, rel=REL
    )


def test_refrigerant_leakage_counts_all_awhp_units_and_chiller(library, load):
    """AWHP leakage uses the N+1 unit count; annual total is independent of profile length."""
    out = _source(_site(library, load, "v_awhp_hc_elec"), ELEC_RATE, NG_RATE, LEAKAGE)
    awhp_kg = V.AWHP_REFRIG_KG * AWHP_UNITS_TOTAL * V.AWHP_GWP * LEAKAGE
    chiller_kg = V.CHILLER_REFRIG_KG * 1 * V.CHILLER_GWP * LEAKAGE
    assert out[Col.TOTAL_REFRIG_EMISSIONS_KG_CO2E.value].sum() == pytest.approx(
        awhp_kg + chiller_kg, rel=REL
    )


# ---------------------------------------------------------------------------
# Fuel switching: AWHP hours move to gas when R/COP > NG/eff
# ---------------------------------------------------------------------------


def test_fuel_switching_moves_dirty_hours_to_gas(library, load):
    # Gas heat intensity = 200 / 0.8 = 250 g/kWh_th. Electric: 600 / COP.
    #   hr0 COP 2.5 -> 240 stays electric     hr1 COP 2.0  -> 300 switches to gas
    #   hr3 COP 2.75 -> 218 stays electric    hr4 COP 2.25 -> 267 switches to gas
    #   hr6 COP 4.0 -> 150 stays electric     (hr2 already all-gas: AWHP out of range)
    out = _source(_site(library, load, "v_awhp_fuel_switching"), elec_rate=600.0, ng_rate=200.0)

    awhp_elec_kWh = 120 / 2.5 + 80 / 2.75 + 40 / 4.0
    gas_heat_kWh = 110 + 100 + 120
    assert _kWh(out[Col.ELEC_AWHP_H_WH.value]) == pytest.approx(awhp_elec_kWh, rel=REL)
    assert _kWh(out[Col.GAS_WH.value]) == pytest.approx(gas_heat_kWh / V.BOILER_EFF, rel=REL)
    assert _kWh(out[Col.ELEC_WH.value]) == pytest.approx(
        awhp_elec_kWh + sum(COOL_kW) / V.CHILLER_COP, rel=REL
    )
    # Boiler count is re-sized after switching: peak boiler load 120 kW / 100 kW per unit
    assert out[Col.BOILER_NUM.value].iloc[0] == math.ceil(120 * kW / V.BOILER_CAP_W)


def test_fuel_switching_inactive_when_grid_is_clean(library, load):
    """At 100 g/kWh no hour is dirtier than gas, so results match the non-switching scenario."""
    switching = _source(_site(library, load, "v_awhp_fuel_switching"), elec_rate=100.0)
    plain = _source(_site(library, load, "v_awhp_gas"), elec_rate=100.0)
    assert _kWh(switching[Col.GAS_WH.value]) == pytest.approx(_kWh(plain[Col.GAS_WH.value]))
    assert _kWh(switching[Col.ELEC_WH.value]) == pytest.approx(_kWh(plain[Col.ELEC_WH.value]))
