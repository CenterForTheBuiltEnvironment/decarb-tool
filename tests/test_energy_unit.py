"""Tier 1 unit tests for pure helper functions in src/energy.py.

No file I/O, no real equipment JSON or parquet data. All inputs are
small synthetic numpy arrays built inline.
"""

import numpy as np
import pytest

from src.energy import (
    _capacity_constraints,
    _constant_heating_efficiency,
    _heat_recovery_plr_curve,
    _per_unit_cooling_capacity_W,
    _per_unit_cooling_cop,
    _per_unit_heating_capacity_W,
    _per_unit_heating_cop,
)
from src.equipment import Equipment, Performance, PerformanceCurves

# ---------------------------------------------------------------------------
# Shared minimal fixtures (inline, no conftest dependency)
# ---------------------------------------------------------------------------

T_OUT_BREAKPOINTS = [-10.0, 0.0, 10.0]
COP_AT_BREAKPOINTS = [3.0, 3.5, 4.0]
CAP_AT_BREAKPOINTS = [10_000.0, 12_000.0, 14_000.0]


def _make_awhp_heating(
    t_out_C=None,
    cap_W=None,
    efficiency=None,
) -> Equipment:
    t_out_C = t_out_C or T_OUT_BREAKPOINTS
    return Equipment(
        eq_id="test_awhp",
        eq_type="heat_pump",
        model="TestAWHP",
        fuel="electricity",
        performance={
            "heating": Performance(t_out_C=t_out_C, capacity_W=cap_W, efficiency=efficiency)
        },
    )


def _make_awhp_cooling(t_out_C=None, fixed_capacity_W=None) -> Equipment:
    t_out_C = t_out_C or [20.0, 30.0, 40.0]
    return Equipment(
        eq_id="test_awhp_c",
        eq_type="heat_pump",
        model="TestAWHPCooling",
        fuel="electricity",
        capacity_W=fixed_capacity_W,
        performance={"cooling": Performance(t_out_C=t_out_C)},
    )


def _perf_fixed(cop_values=None, cap_values=None, min_t=-20.0, max_t=40.0) -> PerformanceCurves:
    """PerformanceCurves as produced by _heating_supply_temp_performance for a fixed supply temp."""
    cop_values = cop_values or COP_AT_BREAKPOINTS
    cap_values = cap_values or CAP_AT_BREAKPOINTS
    perf = PerformanceCurves()
    perf.cop = np.array([cop_values])  # shape (1, n_t_out)
    perf.capacity_W = np.array([cap_values])  # shape (1, n_t_out)
    perf.constraints = {"min_temp_C": min_t, "max_temp_C": max_t}
    return perf


# ---------------------------------------------------------------------------
# _capacity_constraints
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestCapacityConstraints:
    def test_below_min_zeroed(self):
        t_out = np.array([-20.0, -5.0])
        cap = np.array([8_000.0, 9_000.0])
        perf = PerformanceCurves()
        perf.constraints = {"min_temp_C": 0.0, "max_temp_C": 35.0}
        result = _capacity_constraints(t_out, cap.copy(), perf, "heating")
        assert result[0] == 0.0
        assert result[1] == 0.0

    def test_above_max_zeroed(self):
        t_out = np.array([36.0, 45.0])
        cap = np.array([8_000.0, 5_000.0])
        perf = PerformanceCurves()
        perf.constraints = {"min_temp_C": 0.0, "max_temp_C": 35.0}
        result = _capacity_constraints(t_out, cap.copy(), perf, "heating")
        assert result[0] == 0.0
        assert result[1] == 0.0

    def test_in_range_unchanged(self):
        t_out = np.array([0.0, 10.0, 25.0])
        cap = np.array([10_000.0, 12_000.0, 9_000.0])
        perf = PerformanceCurves()
        perf.constraints = {"min_temp_C": -5.0, "max_temp_C": 30.0}
        result = _capacity_constraints(t_out, cap.copy(), perf, "heating")
        assert np.allclose(result, cap)

    def test_mixed_in_and_out_of_range(self):
        t_out = np.array([-5.0, 5.0, 40.0])
        cap = np.array([8_000.0, 10_000.0, 6_000.0])
        perf = PerformanceCurves()
        perf.constraints = {"min_temp_C": 0.0, "max_temp_C": 35.0}
        result = _capacity_constraints(t_out, cap.copy(), perf, "heating")
        assert result[0] == 0.0  # below min
        assert result[1] == 10_000.0  # in range
        assert result[2] == 0.0  # above max


# ---------------------------------------------------------------------------
# _per_unit_heating_cop
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestHeatingCOP:
    def test_exact_breakpoint_returns_exact_value(self):
        e = _make_awhp_heating()
        perf = _perf_fixed()
        result = _per_unit_heating_cop(e, np.array([-10.0]), perf, "interpolate_HHWST_fixed")
        assert np.allclose(result, [3.0])

    def test_midpoint_interpolated(self):
        e = _make_awhp_heating()
        perf = _perf_fixed()
        result = _per_unit_heating_cop(e, np.array([-5.0]), perf, "interpolate_HHWST_fixed")
        assert np.allclose(result, [3.25])  # linear midpoint of 3.0 and 3.5

    def test_upper_breakpoint(self):
        e = _make_awhp_heating()
        perf = _perf_fixed()
        result = _per_unit_heating_cop(e, np.array([10.0]), perf, "interpolate_HHWST_fixed")
        assert np.allclose(result, [4.0])

    def test_vector_input(self):
        e = _make_awhp_heating()
        perf = _perf_fixed()
        result = _per_unit_heating_cop(
            e, np.array([-10.0, 0.0, 10.0]), perf, "interpolate_HHWST_fixed"
        )
        assert np.allclose(result, [3.0, 3.5, 4.0])


# ---------------------------------------------------------------------------
# _per_unit_heating_capacity_W
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestHeatingCapacity:
    def test_ndarray_path_exact_breakpoint(self):
        e = _make_awhp_heating()
        perf = _perf_fixed()
        result = _per_unit_heating_capacity_W(e, np.array([0.0]), perf, "interpolate_HHWST_fixed")
        assert np.allclose(result, [12_000.0])

    def test_ndarray_path_interpolated(self):
        e = _make_awhp_heating()
        perf = _perf_fixed()
        result = _per_unit_heating_capacity_W(e, np.array([-5.0]), perf, "interpolate_HHWST_fixed")
        assert np.allclose(result, [11_000.0])  # midpoint of 10k and 12k

    def test_fixed_scalar_capacity_broadcasts(self):
        e = _make_awhp_heating()
        perf = PerformanceCurves()
        perf.capacity_W = 20_000.0  # scalar float, not ndarray → fixed-capacity fallback
        perf.constraints = {"min_temp_C": -20.0, "max_temp_C": 40.0}
        t_out = np.array([-5.0, 5.0, 15.0])
        result = _per_unit_heating_capacity_W(e, t_out, perf, "interpolate_HHWST_fixed")
        assert np.allclose(result, [20_000.0, 20_000.0, 20_000.0])

    def test_capacity_zeroed_outside_constraints(self):
        e = _make_awhp_heating()
        perf = _perf_fixed(min_t=0.0, max_t=20.0)
        t_out = np.array([-5.0, 5.0, 25.0])
        result = _per_unit_heating_capacity_W(e, t_out, perf, "interpolate_HHWST_fixed")
        assert result[0] == 0.0  # below min
        assert result[2] == 0.0  # above max


# ---------------------------------------------------------------------------
# _per_unit_cooling_cop
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestCoolingCOP:
    def test_exact_breakpoint(self):
        e = _make_awhp_cooling(t_out_C=[20.0, 30.0, 40.0])
        perf = PerformanceCurves()
        perf.cop = [5.0, 4.5, 4.0]
        perf.constraints = {"min_temp_C": 15.0, "max_temp_C": 45.0}
        result = _per_unit_cooling_cop(e, np.array([30.0]), perf)
        assert np.allclose(result, [4.5])

    def test_midpoint_interpolated(self):
        e = _make_awhp_cooling(t_out_C=[20.0, 30.0, 40.0])
        perf = PerformanceCurves()
        perf.cop = [5.0, 4.5, 4.0]
        perf.constraints = {"min_temp_C": 15.0, "max_temp_C": 45.0}
        result = _per_unit_cooling_cop(e, np.array([25.0]), perf)
        assert np.allclose(result, [4.75])  # midpoint of 5.0 and 4.5


# ---------------------------------------------------------------------------
# _per_unit_cooling_capacity_W
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestCoolingCapacity:
    def test_list_path_exact_breakpoint(self):
        e = _make_awhp_cooling(t_out_C=[20.0, 30.0, 40.0])
        perf = PerformanceCurves()
        perf.capacity_W = [50_000.0, 45_000.0, 40_000.0]  # list → uses interp
        perf.constraints = {"min_temp_C": 15.0, "max_temp_C": 45.0}
        result = _per_unit_cooling_capacity_W(e, np.array([30.0]), perf)
        assert np.allclose(result, [45_000.0])

    def test_list_path_interpolated(self):
        e = _make_awhp_cooling(t_out_C=[20.0, 30.0, 40.0])
        perf = PerformanceCurves()
        perf.capacity_W = [50_000.0, 45_000.0, 40_000.0]
        perf.constraints = {"min_temp_C": 15.0, "max_temp_C": 45.0}
        result = _per_unit_cooling_capacity_W(e, np.array([25.0]), perf)
        assert np.allclose(result, [47_500.0])

    def test_fixed_capacity_fallback(self):
        e = _make_awhp_cooling(t_out_C=[20.0, 30.0, 40.0], fixed_capacity_W=48_000.0)
        perf = PerformanceCurves()
        perf.capacity_W = None  # not a list → fallback to e.capacity_W
        perf.constraints = {"min_temp_C": 15.0, "max_temp_C": 45.0}
        result = _per_unit_cooling_capacity_W(e, np.array([25.0, 35.0]), perf)
        assert np.allclose(result, [48_000.0, 48_000.0])

    def test_capacity_zeroed_outside_constraints(self):
        e = _make_awhp_cooling(t_out_C=[20.0, 30.0, 40.0])
        perf = PerformanceCurves()
        perf.capacity_W = [50_000.0, 45_000.0, 40_000.0]
        perf.constraints = {"min_temp_C": 22.0, "max_temp_C": 38.0}
        result = _per_unit_cooling_capacity_W(e, np.array([20.0, 30.0, 40.0]), perf)
        assert result[0] == 0.0  # 20 < 22
        assert result[1] == 45_000.0  # 30 in range
        assert result[2] == 0.0  # 40 > 38


# ---------------------------------------------------------------------------
# _heat_recovery_plr_curve
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestHeatRecoveryPLRCurve:
    def test_returns_correct_columns(self):
        e = Equipment(
            eq_id="test_wwhp",
            eq_type="heat_pump",
            model="TestWWHP",
            fuel="electricity",
            performance={"heating": Performance(capacity_W=[100_000.0, 150_000.0, 200_000.0])},
        )
        perf = PerformanceCurves()
        perf.cop = np.array([[4.0, 4.5, 5.0]])
        result = _heat_recovery_plr_curve(e, perf)
        assert set(result.columns) == {"cap", "cop"}

    def test_values_match_inputs(self):
        caps = [100_000.0, 150_000.0, 200_000.0]
        cops = [4.0, 4.5, 5.0]
        e = Equipment(
            eq_id="test_wwhp",
            eq_type="heat_pump",
            model="TestWWHP",
            fuel="electricity",
            performance={"heating": Performance(capacity_W=caps)},
        )
        perf = PerformanceCurves()
        perf.cop = np.array([cops])
        result = _heat_recovery_plr_curve(e, perf)
        assert np.allclose(result["cap"].to_numpy(), caps)
        assert np.allclose(result["cop"].to_numpy(), cops)


# ---------------------------------------------------------------------------
# _constant_heating_efficiency
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestConstantHeatingEfficiency:
    def test_returns_correct_float(self):
        e = Equipment(
            eq_id="test_boiler",
            eq_type="boiler",
            model="TestBoiler",
            fuel="natural_gas",
            performance={"heating": Performance(efficiency=0.9)},
        )
        result = _constant_heating_efficiency(e)
        assert result == pytest.approx(0.9)

    def test_high_efficiency(self):
        e = Equipment(
            eq_id="test_boiler_condensing",
            eq_type="boiler",
            model="TestCondensingBoiler",
            fuel="natural_gas",
            performance={"heating": Performance(efficiency=0.97)},
        )
        result = _constant_heating_efficiency(e)
        assert result == pytest.approx(0.97)


# ---------------------------------------------------------------------------
# Emissions rate formula (mirrors inline logic in site_to_source)
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestEmissionsRateFormula:
    """Test the LRMER/SRMER blending formula used in site_to_source.

    These verify the math without calling the full function (which needs real
    emissions parquet data).
    """

    def _combustion_rate(self, lrmer, srmer, weighting):
        return lrmer * (1 - weighting) + srmer * weighting

    def _precombustion_rate(self, lrmer_c, lrmer_p, srmer_c, srmer_p, weighting):
        return (lrmer_c + lrmer_p) * (1 - weighting) + (srmer_c + srmer_p) * weighting

    def test_weighting_zero_returns_lrmer(self):
        assert self._combustion_rate(400.0, 600.0, 0.0) == pytest.approx(400.0)

    def test_weighting_one_returns_srmer(self):
        assert self._combustion_rate(400.0, 600.0, 1.0) == pytest.approx(600.0)

    def test_weighting_half_returns_average(self):
        assert self._combustion_rate(400.0, 600.0, 0.5) == pytest.approx(500.0)

    def test_includes_precombustion_weighting_zero(self):
        # weighting=0 → pure LRMER (combustion + pre-combustion)
        result = self._precombustion_rate(350.0, 50.0, 550.0, 50.0, 0.0)
        assert result == pytest.approx(400.0)

    def test_includes_precombustion_weighting_one(self):
        # weighting=1 → pure SRMER (combustion + pre-combustion)
        result = self._precombustion_rate(350.0, 50.0, 550.0, 50.0, 1.0)
        assert result == pytest.approx(600.0)


# ---------------------------------------------------------------------------
# Physics invariants
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestPhysicsInvariants:
    def test_elec_equals_thermal_divided_by_cop(self):
        """Electricity use = thermal output / COP at every hour."""
        thermal_W = np.array([10_000.0, 20_000.0, 15_000.0])
        cop = np.array([3.5, 4.0, 3.2])
        elec_Wh = thermal_W / cop
        assert np.allclose(elec_Wh, thermal_W / cop)
        assert np.all(elec_Wh > 0)

    def test_gas_equals_thermal_divided_by_efficiency(self):
        """Gas input = thermal output / boiler efficiency at every hour."""
        thermal_W = np.array([5_000.0, 10_000.0])
        efficiency = 0.9
        gas_Wh = thermal_W / efficiency
        assert np.allclose(gas_Wh, [5_000.0 / 0.9, 10_000.0 / 0.9])
        assert np.all(gas_Wh >= thermal_W)  # gas input always >= thermal output

    def test_cop_greater_than_one_implies_elec_less_than_thermal(self):
        """For COP > 1, electricity consumed < thermal delivered."""
        thermal_W = np.array([10_000.0])
        cop = np.array([3.5])
        elec_Wh = thermal_W / cop
        assert np.all(elec_Wh < thermal_W)
