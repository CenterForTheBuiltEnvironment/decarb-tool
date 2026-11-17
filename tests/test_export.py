"""Tier 1 unit tests for the results download in src/export.py.

Synthetic results frames only: names, column order, annual summary, and that the
SI/IP switch converts and labels every exported value.
"""

import datetime

import numpy as np
import pandas as pd
import pytest

from src.emissions import EmissionScenario
from src.equipment import EquipmentLibrary
from src.export import (
    _HOURLY_COLUMN_ORDER,
    EXPORT_ID_COLUMNS,
    _round_for_csv,
    build_annual_summary,
    build_export_basename,
    build_hourly_export,
    build_metadata_summary,
    format_for_csv,
)
from src.metadata import LoadData, Metadata
from utils.units import (
    COLUMN_REGISTRY,
    UNIT_MAP,
    W_to_BTUh,
    get_category,
    get_column_label,
)

NOW = datetime.datetime(2026, 11, 2, 14, 30)
HOURS = 3
EQ_IDS = ["eq_scenario_1", "eq_scenario_2"]
EM_IDS = ["em_scenario_a", "em_scenario_b"]
TEXT_COLUMNS = {"hr_wwhp_refrigerant", "awhp_refrigerant", "chiller_refrigerant"}

# Numeric export columns without a unit; every other numeric column must have a unit category
UNITLESS_COLUMNS = {
    "eq_scen_slot",
    "em_year",
    "hr_cop_h",
    "awhp_cop_h",
    "awhp_cop_c",
    "chiller_cop",
    "boiler_eff",
    "awhp_num",
    "awhp_num_redundant",
    "awhp_num_c",
    "boiler_num",
    "shortrun_weighting",
}


def _emission_scenarios():
    common = dict(
        elec_emission_source="Marginal (Cambium, Long-run)",
        grid_scenario="MidCase",
        emission_type="Includes pre-combustion",
        annual_refrig_leakage_percent=1.0,
        ng_emission_rate_gCO2e_per_kWh=239.2,
    )
    return [
        EmissionScenario(em_scen_id="em_scenario_a", em_scen_name="Mid 2030", year=2030, **common),
        EmissionScenario(em_scen_id="em_scenario_b", em_scen_name="Mid 2045", year=2045, **common),
    ]


def _metadata(**overrides):
    fields = dict(
        building_id="3",
        location="Los Angeles",
        ashrae_climate_zone="3C",
        load_data=LoadData(load_type="simulated"),
        emission_settings=_emission_scenarios(),
    )
    return Metadata.create(**{**fields, **overrides})


def _results_frame() -> pd.DataFrame:
    """Engine-shaped results: em scenarios outermost, as site_to_source returns them."""
    rng = np.random.default_rng(0)
    index = pd.date_range("2001-01-01 01:00", periods=HOURS, freq="h", name="timestamp")
    blocks = []
    for em_id in EM_IDS:
        for eq_id in EQ_IDS:
            block = pd.DataFrame(index=index)
            for col in _HOURLY_COLUMN_ORDER:
                block[col] = "R-32" if col in TEXT_COLUMNS else rng.uniform(1, 5000, HOURS)
            block["eq_scen_id"] = eq_id
            block["eq_scen_name"] = f"Name {eq_id}"
            block["em_scen_id"] = em_id
            block["year"] = 2001
            blocks.append(block)
    return pd.concat(blocks)


# ---------------------------------------------------------------------------
# File names
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_basename_library_building():
    name = build_export_basename(_metadata(), "SI", now=NOW)
    assert name == "decarb_B3_Los-Angeles_CZ3C_SI_20261102-1430"


@pytest.mark.unit
def test_basename_scaled_with_base_load_ip():
    scale = {"heating_factor": 1.25, "cooling_factor": 0.8}
    base = {"heating": {"method": "floor", "value_W": 5000.0}, "cooling": None}
    name = build_export_basename(_metadata(), "IP", scale, base, now=NOW)
    assert name == "decarb_B3_Los-Angeles_CZ3C_scaled-h1.25-c0.80_baseload_IP_20261102-1430"


@pytest.mark.unit
def test_basename_empty_base_load_is_not_flagged():
    base = {"heating": None, "cooling": None}
    assert "baseload" not in build_export_basename(_metadata(), "SI", None, base, now=NOW)


@pytest.mark.unit
def test_basename_custom_upload_and_missing_location():
    md = _metadata(
        building_id="My Bldg #2",
        location=None,
        ashrae_climate_zone=None,
        load_data=LoadData(load_type="custom", load_source_ref="upload.csv"),
    )
    assert build_export_basename(md, "SI", now=NOW) == "decarb_custom-My-Bldg-2_SI_20261102-1430"


# ---------------------------------------------------------------------------
# Hourly layout and annual summary
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_hourly_identifiers_first_and_no_column_lost():
    df = _results_frame()
    out = build_hourly_export(df, _metadata())

    assert list(out.columns[: len(EXPORT_ID_COLUMNS)]) == EXPORT_ID_COLUMNS
    assert set(df.columns) - {"year"} <= set(out.columns)
    assert "year" not in out.columns
    assert len(out) == len(df)


@pytest.mark.unit
def test_hourly_appends_unknown_columns():
    df = _results_frame()
    df["new_engine_col"] = 1.0
    assert build_hourly_export(df, _metadata()).columns[-1] == "new_engine_col"


@pytest.mark.unit
def test_hourly_rows_grouped_per_case_and_slot_map_applied():
    # eq_scenario_2 occupies slot 1 on the Equipment page
    slot_map = {"eq_scenario_2": 1, "eq_scenario_1": 2}
    out = build_hourly_export(_results_frame(), _metadata(), slot_map)

    cases = list(zip(out["eq_scen_slot"], out["em_scen_letter"], strict=True))
    expected = [(s, e) for s in (1, 2) for e in ("A", "B") for _ in range(HOURS)]
    assert cases == expected
    assert out["eq_scen_id"].iloc[0] == "eq_scenario_2"
    assert out.index[:HOURS].is_monotonic_increasing


@pytest.mark.unit
def test_hourly_emission_descriptors():
    out = build_hourly_export(_results_frame(), _metadata())
    by_em = out.groupby("em_scen_id")[["em_scen_name", "em_year", "em_grid_scenario"]].first()
    assert by_em.loc["em_scenario_a"].tolist() == ["Mid 2030", 2030, "MidCase"]
    assert by_em.loc["em_scenario_b"].tolist() == ["Mid 2045", 2045, "MidCase"]


@pytest.mark.unit
def test_annual_summary_sums_each_case():
    hourly = build_hourly_export(_results_frame(), _metadata())
    annual = build_annual_summary(hourly)

    assert len(annual) == len(EQ_IDS) * len(EM_IDS)
    assert list(annual.columns[: len(EXPORT_ID_COLUMNS)]) == EXPORT_ID_COLUMNS
    expected = hourly.groupby(["eq_scen_id", "em_scen_id"])[["total_emissions", "heating_W"]].sum()
    got = annual.set_index(["eq_scen_id", "em_scen_id"])
    pd.testing.assert_series_equal(
        got["total_emissions"], expected["total_emissions"], check_names=False
    )
    pd.testing.assert_series_equal(
        got["annual_heating_Wh"], expected["heating_W"], check_names=False
    )


# ---------------------------------------------------------------------------
# SI / IP
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_every_numeric_export_column_has_a_unit_or_is_unitless():
    hourly = build_hourly_export(_results_frame(), _metadata())
    annual = build_annual_summary(hourly)
    for frame in (hourly, annual):
        numeric = frame.select_dtypes("number").columns
        missing = [c for c in numeric if c not in COLUMN_REGISTRY and c not in UNITLESS_COLUMNS]
        assert not missing, f"no unit category for {missing}"


@pytest.mark.unit
@pytest.mark.parametrize("unit_mode", ["SI", "IP"])
def test_values_and_headers_follow_unit_mode(unit_mode):
    hourly = build_hourly_export(_results_frame(), _metadata())
    annual = build_annual_summary(hourly)

    for raw in (hourly, annual):
        formatted = format_for_csv(raw, unit_mode)
        for col in raw.columns:
            category = get_category(col)
            if category is None:
                continue
            label = get_column_label(col, unit_mode)
            assert label.endswith(f"[{UNIT_MAP[category][unit_mode]['unit']}]")
            expected = UNIT_MAP[category][unit_mode]["func"](raw[col]).to_numpy()
            np.testing.assert_allclose(formatted[label].to_numpy(), expected, rtol=1e-3, atol=0.01)


@pytest.mark.unit
def test_combined_marginal_rates_convert_in_ip():
    raw = build_hourly_export(_results_frame(), _metadata())
    formatted = format_for_csv(raw, "IP")
    for col in ("lrmer_co2e", "srmer_co2e"):
        assert f"{col.upper()[:5]} CO₂e [lb CO₂e/kWh]" in formatted.columns


@pytest.mark.unit
def test_annual_ip_totals_equal_converted_base_sums():
    hourly = build_hourly_export(_results_frame(), _metadata())
    annual_ip = format_for_csv(build_annual_summary(hourly), "IP")
    base = hourly.groupby(["eq_scen_id", "em_scen_id"], sort=False)["total_emissions"].sum()
    expected = UNIT_MAP["emissions"]["IP"]["func"](base).to_numpy()
    np.testing.assert_allclose(annual_ip["Total Emissions [lb CO₂e]"], expected, rtol=1e-6)


@pytest.mark.unit
def test_rounding_keeps_small_values_and_positions():
    # Repeated index labels, as in the hourly export
    values = pd.Series(
        [1234.5678, 0.123456, 0.000123456, -0.0456789, 0.0, 1e-12, 6.825],
        index=[0, 0, 1, 1, 2, 2, 3],
    )
    rounded = _round_for_csv(values).tolist()
    assert rounded == [1234.57, 0.1235, 0.0001235, -0.04568, 0.0, 0.0, round(6.825, 2)]


# ---------------------------------------------------------------------------
# Settings summary
# ---------------------------------------------------------------------------


def _summary(unit_mode, scale_info=None, base_load_info=None):
    library = EquipmentLibrary(equipment=[], equipment_scenarios=[])
    return build_metadata_summary(
        _metadata(), library, [], EM_IDS, unit_mode, scale_info, base_load_info
    )


@pytest.mark.unit
def test_summary_rates_follow_unit_mode():
    assert "239.2 g CO₂e/kWh" in _summary("SI")
    ip = _summary("IP")
    assert "lb CO₂e/kBTU" in ip
    assert "g CO₂e" not in ip


@pytest.mark.unit
def test_summary_load_modifications_in_export_units():
    scale = {
        "method": "building area",
        "heating_factor": 1.25,
        "cooling_factor": 1.25,
        "orig_area_sqm": 1000.0,
        "target_area_sqm": 1250.0,
    }
    base = {"heating": {"method": "floor", "value_W": 10_000.0, "value_display": "10.0 kW"}}

    si = _summary("SI", scale, base)
    assert "Heating Scale Factor:" in si and "1.250" in si
    assert "Floor (minimum), 10.0 kW" in si
    assert "1,250" in si

    ip = _summary("IP", scale, base)
    # from value_W, not the value_display stored in the unit it was entered in
    assert f"{10_000.0 * W_to_BTUh:,.1f} BTU/h" in ip
    assert "13,455" in ip  # 1250 m² in ft²
    assert "Cooling Base Load:" in ip


@pytest.mark.unit
def test_summary_without_modifications():
    assert "None (original load profile)" in _summary("SI")
