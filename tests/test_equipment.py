"""Tests for equipment models and library."""

import pytest

from layout.shell import _get_initial_equipment_scenario_ids
from src import paths
from src.equipment import (
    Equipment,
    EquipmentLibrary,
    curve_table,
    duplicate_equipment,
    load_library,
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
