"""Tests for equipment models and library."""

import pytest

from src import paths
from src.equipment import (
    EquipmentLibrary,
    load_library,
)


@pytest.mark.unit
class TestEquipmentLibrary:
    """Tests for equipment library loading and manipulation."""

    def test_load_library_succeeds(self):
        """Test that equipment library loads successfully from JSON."""
        lib = load_library(paths.EQUIPMENT_JSON)
        assert isinstance(lib, EquipmentLibrary)
        assert len(lib.equipment) > 0
        assert len(lib.equipment_scenarios) > 0

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


@pytest.mark.unit
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


@pytest.mark.unit
class TestEquipment:
    """Tests for individual equipment models."""

    def test_equipment_has_required_fields(self, equipment_library):
        """Test that equipment items have all required fields."""
        for equipment in equipment_library.equipment:
            assert equipment.eq_id is not None
            assert equipment.eq_type is not None
            assert equipment.model is not None
            assert equipment.fuel is not None
