"""Tests for equipment models and library."""

import pandas as pd
import pytest

from layout.shell import _get_initial_equipment_scenario_ids
from src import paths
from src.equipment import (
    HEAT_PUMP_TYPES,
    Equipment,
    EquipmentLibrary,
    apply_curve_table,
    curve_table,
    delete_custom_equipment,
    duplicate_equipment,
    find_refrigerant,
    keep_custom_equipment,
    load_library,
    load_refrigerants,
    save_custom_equipment,
    scale_performance,
    scenarios_using,
    validate_equipment,
)

pytestmark = pytest.mark.unit


class TestEquipmentLibrary:
    """Tests for equipment library loading and manipulation."""

    def test_load_library_succeeds(self):
        """Test that equipment library loads successfully from JSON."""
        lib = load_library(paths.EQUIPMENT_JSON)
        assert isinstance(lib, EquipmentLibrary)
        assert len(lib.equipment) > 0
        assert len(lib.equipment_scenarios) > 0

    def test_initial_equipment_scenario_order_matches_default_group(self, equipment_library):
        """Initial table order must match the JSON's 'default' scenario group order."""
        equipment_data = equipment_library.model_dump()
        default_group = next(
            g for g in equipment_data["scenario_groups"] if g["group_id"] == "default"
        )
        assert _get_initial_equipment_scenario_ids(equipment_data) == default_group["scenario_ids"]

    def test_get_equipment_by_id(self, equipment_library):
        """Test equipment retrieval by ID."""
        # Get first equipment ID from library
        eq_id = equipment_library.equipment[0].eq_id
        equipment = equipment_library.get_equipment(eq_id)
        assert equipment.eq_id == eq_id

    def test_get_scenario_by_id(self, equipment_library):
        """Test scenario retrieval by ID."""
        scen_id = equipment_library.equipment_scenarios[0].eq_scen_id
        scenario = equipment_library.get_scenario(scen_id)
        assert scenario.eq_scen_id == scen_id

    def test_get_nonexistent_equipment_raises(self, equipment_library):
        """Test that getting nonexistent equipment raises KeyError."""
        with pytest.raises(KeyError):
            equipment_library.get_equipment("nonexistent_id")

    def test_get_nonexistent_scenario_raises(self, equipment_library):
        """Test that getting nonexistent scenario raises KeyError."""
        with pytest.raises(KeyError):
            equipment_library.get_scenario("nonexistent_id")


class TestEquipmentScenario:
    """Tests for equipment scenario model."""

    def test_get_value_simple_field(self, equipment_library):
        """Test simple field access via get_value mixin."""
        scenario = equipment_library.equipment_scenarios[0]
        assert scenario.get_value("eq_scen_id") == scenario.eq_scen_id
        assert scenario.get_value("eq_scen_name") == scenario.eq_scen_name

    def test_get_value_returns_none_for_missing(self, equipment_library):
        """Test that get_value returns None for nonexistent fields."""
        scenario = equipment_library.equipment_scenarios[0]
        assert scenario.get_value("nonexistent_field") is None

    def test_scenario_has_required_fields(self, equipment_library):
        """Test that scenarios have all required fields."""
        for scenario in equipment_library.equipment_scenarios:
            assert scenario.eq_scen_id is not None
            assert scenario.eq_scen_name is not None
            # At least one heating source should be defined (awhp, hr_wwhp, or backup_heating)
            has_heating = (
                scenario.awhp is not None
                or scenario.hr_wwhp is not None
                or scenario.backup_heating is not None
            )
            assert has_heating, f"Scenario {scenario.eq_scen_id} has no heating source"


class TestEquipment:
    """Tests for individual equipment models."""

    def test_equipment_has_required_fields(self, equipment_library):
        """Test that equipment items have all required fields."""
        for equipment in equipment_library.equipment:
            assert equipment.eq_id is not None
            assert equipment.eq_type is not None
            assert equipment.model is not None
            assert equipment.fuel is not None


# ---------------------------------------------------------------------------
# validate_equipment
# ---------------------------------------------------------------------------


def _awhp_dict():
    """A minimal valid AWHP (heating + cooling) as a plain dict, easy to break per test."""
    return {
        "eq_id": "t_awhp",
        "eq_type": "heat_pump",
        "eq_calc_type": "specific",
        "model": "TestAWHP",
        "nominal_capacity_W": 100_000,
        "fuel": "electricity",
        "performance": {
            "heating": {
                "t_out_C": [-10.0, 0.0, 10.0],
                "leaving_supply_t": {
                    "40": {
                        "cop": [2.5, 3.0, 3.5],
                        "capacity_W": [80_000.0, 90_000.0, 100_000.0],
                        "constraints": {"min_temp_C": -15.0, "max_temp_C": 35.0},
                    },
                    "55": {
                        "cop": [2.0, 2.5, 3.0],
                        "capacity_W": [75_000.0, 85_000.0, 95_000.0],
                        "constraints": {"min_temp_C": -10.0, "max_temp_C": 35.0},
                    },
                },
                "constraints": {"min_temp_C": 40.0, "max_temp_C": 55.0},
            },
            "cooling": {
                "t_out_C": [25.0, 35.0],
                "leaving_supply_t": {
                    "7": {
                        "cop": [4.0, 3.0],
                        "capacity_W": [100_000.0, 90_000.0],
                        "constraints": {"min_temp_C": 5.0, "max_temp_C": 45.0},
                    }
                },
                "constraints": {"min_temp_C": 7.0, "max_temp_C": 7.0},
            },
        },
    }


def _errors(eq_dict, modes=None):
    issues = validate_equipment(Equipment(**eq_dict), modes)
    return [i for i in issues if i.severity == "error"]


def _warnings(eq_dict, modes=None):
    issues = validate_equipment(Equipment(**eq_dict), modes)
    return [i for i in issues if i.severity == "warning"]


class TestValidateEquipment:
    def test_library_has_no_errors(self, equipment_library):
        for eq_id, issues in equipment_library.validation_issues().items():
            errors = [i.message for i in issues if i.severity == "error"]
            assert not errors, f"{eq_id}: {errors}"

    def test_valid_awhp_has_no_issues(self):
        assert validate_equipment(Equipment(**_awhp_dict())) == []

    def test_cop_length_mismatch(self):
        d = _awhp_dict()
        d["performance"]["heating"]["leaving_supply_t"]["40"]["cop"] = [2.5, 3.0]
        errors = _errors(d)
        assert [e.field for e in errors] == ["performance.heating.leaving_supply_t.40.cop"]
        assert "different lengths" in errors[0].message

    def test_capacity_length_mismatch(self):
        d = _awhp_dict()
        d["performance"]["heating"]["leaving_supply_t"]["55"]["capacity_W"] = [1.0]
        assert [e.field for e in _errors(d)] == [
            "performance.heating.leaving_supply_t.55.capacity_W"
        ]

    def test_t_out_not_increasing(self):
        d = _awhp_dict()
        d["performance"]["heating"]["t_out_C"] = [-10.0, 10.0, 0.0]
        assert "strictly increasing" in _errors(d)[0].message

    def test_non_positive_cop(self):
        d = _awhp_dict()
        d["performance"]["heating"]["leaving_supply_t"]["40"]["cop"] = [2.5, 0.0, 3.5]
        assert "non-positive" in _errors(d)[0].message

    def test_non_numeric_supply_temperature(self):
        d = _awhp_dict()
        lst = d["performance"]["heating"]["leaving_supply_t"]
        lst["hot"] = lst.pop("55")
        assert any("not a number" in e.message for e in _errors(d))

    def test_missing_cop_value(self):
        d = _awhp_dict()
        d["performance"]["heating"]["leaving_supply_t"]["40"]["cop"] = [2.5, float("nan"), 3.5]
        assert "missing" in _errors(d)[0].message

    def test_missing_curve_point(self):
        d = _awhp_dict()
        d["performance"]["heating"]["t_out_C"] = [-10.0, float("nan"), 10.0]
        assert "missing" in _errors(d)[0].message

    def test_duplicate_supply_temperature(self):
        d = _awhp_dict()
        lst = d["performance"]["heating"]["leaving_supply_t"]
        lst["40.0"] = lst.pop("55")
        assert any("more than once" in e.message for e in _errors(d))

    def test_missing_oat_constraints(self):
        d = _awhp_dict()
        del d["performance"]["heating"]["leaving_supply_t"]["40"]["constraints"]
        assert [e.field for e in _errors(d)] == [
            "performance.heating.leaving_supply_t.40.constraints"
        ]

    def test_flipped_supply_temperature_constraints(self):
        d = _awhp_dict()
        d["performance"]["heating"]["constraints"] = {"min_temp_C": 55.0, "max_temp_C": 40.0}
        assert "min_temp_C above max_temp_C" in _errors(d)[0].message

    def test_missing_capacity_without_fixed_capacity(self):
        d = _awhp_dict()
        del d["performance"]["heating"]["leaving_supply_t"]["40"]["capacity_W"]
        assert "lacks heating capacity info" in _errors(d)[0].message

    def test_fixed_unit_capacity_replaces_capacity_curve(self):
        d = _awhp_dict()
        del d["performance"]["heating"]["leaving_supply_t"]["40"]["capacity_W"]
        d["capacity_W"] = 100_000.0
        assert _errors(d) == []

    def test_implausible_cop_is_warning_only(self):
        d = _awhp_dict()
        d["performance"]["heating"]["leaving_supply_t"]["40"]["cop"] = [2.5, 3.0, 12.0]
        assert _errors(d) == []
        assert "typical range" in _warnings(d)[0].message

    def test_constraints_not_matching_curves_is_warning(self):
        d = _awhp_dict()
        d["performance"]["heating"]["constraints"] = {"min_temp_C": 35.0, "max_temp_C": 55.0}
        assert _errors(d) == []
        assert [w.field for w in _warnings(d)] == ["performance.heating.constraints"]

    def test_modes_limits_checks(self):
        d = _awhp_dict()
        d["performance"]["cooling"]["leaving_supply_t"]["7"]["cop"] = [4.0]
        assert _errors(d, modes=("heating",)) == []
        assert _errors(d, modes=("heating", "cooling"))

    def test_missing_mode_is_error_when_requested(self):
        d = _awhp_dict()
        del d["performance"]["cooling"]
        assert "lacks cooling performance data" in _errors(d, modes=("cooling",))[0].message

    def test_boiler_requires_positive_efficiency(self):
        boiler = {
            "eq_id": "t_bo",
            "eq_type": "backup_heating",
            "model": "TestBoiler",
            "fuel": "natural_gas",
            "performance": {"heating": {"efficiency": 0.0}},
        }
        assert "positive 'efficiency'" in _errors(boiler)[0].message


# ---------------------------------------------------------------------------
# duplicate_equipment / curve_table
# ---------------------------------------------------------------------------


class TestDuplicateEquipment:
    def test_copy_gets_new_id_and_custom_source(self, equipment_library):
        hp01 = equipment_library.get_equipment("hp01")
        copy = duplicate_equipment(hp01, [e.eq_id for e in equipment_library.equipment])
        assert copy.eq_id == "custom_hp01_1"
        assert copy.source == "custom"
        assert copy.based_on == "hp01"
        assert copy.model == f"{hp01.model} (copy)"

    def test_id_skips_existing_copies(self, equipment_library):
        hp01 = equipment_library.get_equipment("hp01")
        assert duplicate_equipment(hp01, ["custom_hp01_1"]).eq_id == "custom_hp01_2"

    def test_copy_of_copy_refers_to_library_item(self, equipment_library):
        first = duplicate_equipment(equipment_library.get_equipment("hp01"), [])
        second = duplicate_equipment(first, [first.eq_id])
        assert second.eq_id == "custom_hp01_2"
        assert second.based_on == "hp01"

    def test_copy_is_deep(self, equipment_library):
        hp01 = equipment_library.get_equipment("hp01")
        original_cop = list(hp01.performance_heating.leaving_supply_t["38"].cop)
        copy = duplicate_equipment(hp01, [])
        copy.performance_heating.leaving_supply_t["38"].cop[0] = 99.0
        assert hp01.performance_heating.leaving_supply_t["38"].cop == original_cop


class TestCurveTable:
    def test_awhp_rows_and_columns(self, equipment_library):
        hp01 = equipment_library.get_equipment("hp01")
        df = curve_table(hp01, "heating")
        n_lwt = len(hp01.performance_heating.leaving_supply_t)
        assert len(df) == n_lwt * len(hp01.performance_heating.t_out_C)
        assert set(df["x_kind"]) == {"t_out_C"}
        assert df["capacity_W"].notna().all()

    def test_hr_wwhp_uses_capacity_axis(self, equipment_library):
        hr01 = equipment_library.get_equipment("hr01")
        df = curve_table(hr01, "heating")
        assert len(df) == 2 * len(hr01.performance_heating.capacity_W)
        assert set(df["x_kind"]) == {"capacity_W"}
        assert (df["x"] == df["capacity_W"]).all()

    def test_supply_temperatures_sorted_numerically(self, equipment_library):
        # hp04 stores its supply temperatures as "50", "45", "35"
        df = curve_table(equipment_library.get_equipment("hp04"), "heating")
        assert list(df["lwt_C"].unique()) == [35.0, 45.0, 50.0]

    def test_fixed_capacity_gives_nan_capacity(self, equipment_library):
        df = curve_table(equipment_library.get_equipment("hp02"), "heating")
        assert df["capacity_W"].isna().all()

    def test_non_heat_pump_is_empty(self, equipment_library):
        assert curve_table(equipment_library.get_equipment("bo01"), "heating").empty


class TestApplyCurveTable:
    def test_round_trip_is_identity_for_library_heat_pumps(self, equipment_library):
        for eq in equipment_library.equipment:
            for mode in eq.performance if eq.eq_type in HEAT_PUMP_TYPES else ():
                back = apply_curve_table(eq, mode, curve_table(eq, mode))
                assert back.performance[mode] == eq.performance[mode], f"{eq.eq_id} {mode}"

    def test_edited_value_and_new_supply_temperature(self, equipment_library):
        hp01 = equipment_library.get_equipment("hp01")
        df = curve_table(hp01, "heating")
        df.loc[0, "cop"] = 9.9
        new = df[df["lwt_C"] == 52.0].assign(lwt_C=60.0)
        eq = apply_curve_table(hp01, "heating", pd.concat([df, new]))
        perf = eq.performance_heating
        assert perf.leaving_supply_t["38"].cop[0] == 9.9
        assert list(perf.leaving_supply_t) == ["38", "52", "60"]
        assert perf.constraints["max_temp_C"] == 60.0  # limits follow the curves
        assert hp01.performance_heating.leaving_supply_t["38"].cop[0] != 9.9  # original untouched

    def test_points_must_match_across_supply_temperatures(self, equipment_library):
        hp01 = equipment_library.get_equipment("hp01")
        df = curve_table(hp01, "heating")
        with pytest.raises(ValueError, match="same curve points"):
            apply_curve_table(hp01, "heating", df.drop(index=0))


class TestScalePerformance:
    def test_awhp_cop_and_capacity_scaled(self, equipment_library):
        hp01 = equipment_library.get_equipment("hp01")
        eq = scale_performance(hp01, "heating", cop_factor=0.9, capacity_factor=1.1)
        for key, curves in eq.performance_heating.leaving_supply_t.items():
            orig = hp01.performance_heating.leaving_supply_t[key]
            assert curves.cop == pytest.approx([0.9 * v for v in orig.cop])
            assert curves.capacity_W == pytest.approx([1.1 * v for v in orig.capacity_W])
        assert eq.nominal_capacity_W == round(1.1 * hp01.nominal_capacity_W)
        assert eq.performance_heating.t_out_C == hp01.performance_heating.t_out_C
        assert eq.scaling == {"heating": {"cop": 0.9, "capacity": 1.1}}

    def test_fixed_unit_capacity_scaled(self, equipment_library):
        hp02 = equipment_library.get_equipment("hp02")
        eq = scale_performance(hp02, "heating", capacity_factor=1.2)
        assert eq.capacity_W == pytest.approx(1.2 * hp02.capacity_W)

    def test_hr_wwhp_capacity_points_scaled(self, equipment_library):
        hr01 = equipment_library.get_equipment("hr01")
        eq = scale_performance(hr01, "heating", capacity_factor=0.5)
        assert eq.performance_heating.capacity_W == pytest.approx(
            [0.5 * v for v in hr01.performance_heating.capacity_W]
        )

    def test_reapplying_does_not_compound(self, equipment_library):
        hp01 = equipment_library.get_equipment("hp01")
        once = scale_performance(hp01, "heating", 1.1, 1.1)
        twice = scale_performance(once, "heating", 1.1, 1.1)
        assert twice.performance_heating == once.performance_heating
        back = scale_performance(twice, "heating", 1.0, 1.0)
        assert back.performance_heating.leaving_supply_t["38"].cop == pytest.approx(
            hp01.performance_heating.leaving_supply_t["38"].cop
        )
        assert back.scaling is None

    def test_rejects_non_positive_factor(self, equipment_library):
        with pytest.raises(ValueError):
            scale_performance(equipment_library.get_equipment("hp01"), "heating", 0)


class TestCustomEquipmentStore:
    def _data(self, equipment_library):
        return equipment_library.model_dump()

    def test_save_adds_then_replaces_custom_item(self, equipment_library):
        data = self._data(equipment_library)
        library_ids = [e["eq_id"] for e in data["equipment"]]
        copy = duplicate_equipment(equipment_library.get_equipment("hp01"), library_ids)
        added = save_custom_equipment(data, copy, library_ids)
        assert len(added["equipment"]) == len(data["equipment"]) + 1
        renamed = copy.model_copy(update={"model": "Renamed"})
        replaced = save_custom_equipment(added, renamed, library_ids)
        assert len(replaced["equipment"]) == len(added["equipment"])
        assert replaced["equipment"][-1]["model"] == "Renamed"
        assert data["equipment"] == self._data(equipment_library)["equipment"]  # input untouched

    def test_save_refuses_to_overwrite_library_items(self, equipment_library):
        data = self._data(equipment_library)
        library_ids = [e["eq_id"] for e in data["equipment"]]
        hp01 = equipment_library.get_equipment("hp01")
        with pytest.raises(ValueError, match="library equipment"):
            save_custom_equipment(data, hp01.model_copy(update={"model": "x"}), library_ids)
        # even when marked custom, a library id is refused
        with pytest.raises(ValueError, match="library equipment"):
            save_custom_equipment(data, hp01.model_copy(update={"source": "custom"}), library_ids)

    def test_delete_refuses_library_items_and_items_in_use(self, equipment_library):
        data = self._data(equipment_library)
        library_ids = [e["eq_id"] for e in data["equipment"]]
        with pytest.raises(ValueError, match="not custom"):
            delete_custom_equipment(data, "hp01")
        copy = duplicate_equipment(equipment_library.get_equipment("hp01"), library_ids)
        data = save_custom_equipment(data, copy, library_ids)
        scenario = {**data["equipment_scenarios"][0], "awhp": copy.eq_id}
        in_use = {**data, "equipment_scenarios": [*data["equipment_scenarios"], scenario]}
        assert scenarios_using(in_use, copy.eq_id) == [scenario["eq_scen_name"]]
        with pytest.raises(ValueError, match="used by"):
            delete_custom_equipment(in_use, copy.eq_id)
        assert copy.eq_id not in [
            e["eq_id"] for e in delete_custom_equipment(data, copy.eq_id)["equipment"]
        ]

    def test_reset_keeps_custom_items(self, equipment_library):
        initial = self._data(equipment_library)
        library_ids = [e["eq_id"] for e in initial["equipment"]]
        copy = duplicate_equipment(equipment_library.get_equipment("hp01"), library_ids)
        current = save_custom_equipment(initial, copy, library_ids)
        reset = keep_custom_equipment(initial, current)
        assert [e["eq_id"] for e in reset["equipment"]] == [*library_ids, copy.eq_id]
        assert keep_custom_equipment(initial, initial) is initial


class TestRefrigerants:
    def test_database_loads_with_unique_names(self):
        refrigerants = load_refrigerants()
        names = [r.name for r in refrigerants]
        assert len(names) == len(set(names)) >= 15
        assert all(r.gwp >= 0 for r in refrigerants)

    def test_library_gwps_match_database(self, equipment_library):
        for eq in equipment_library.equipment:
            if eq.refrigerant:
                match = find_refrigerant(eq.refrigerant)
                assert match is not None, f"{eq.eq_id}: {eq.refrigerant} not in database"
                assert match.gwp == eq.refrigerant_gwp, eq.eq_id

    def test_lookup_ignores_case_punctuation_and_uses_aliases(self):
        assert find_refrigerant("r134A").name == "R-134a"
        assert find_refrigerant("R-1234ze").name == "R-1234ze(E)"
        assert find_refrigerant("CO2").gwp == 1
        assert find_refrigerant("R-999") is None
        assert find_refrigerant(None) is None
