"""Central registry for mapping raw IDs to user-friendly display names."""

from src.equipment import load_library


class DisplayRegistry:
    """Central registry for mapping raw IDs to display names."""

    _equipment_lookup: dict = None

    @classmethod
    def get_equipment_name(cls, eq_id: str) -> str:
        """Map equipment ID to model name.

        Args:
            eq_id: The equipment ID (e.g., "hr01", "awhp_1", "b01")

        Returns:
            The equipment model name, or the original ID if not found
        """
        if eq_id is None:
            return None
        if cls._equipment_lookup is None:
            cls._build_equipment_lookup()
        return cls._equipment_lookup.get(eq_id, eq_id)

    @classmethod
    def _build_equipment_lookup(cls):
        """Build the equipment ID to model name lookup dictionary."""
        library = load_library("data/input/equipment_data.JSON")
        cls._equipment_lookup = {eq.eq_id: eq.model for eq in library.equipment}

    @classmethod
    def clear_cache(cls):
        """Clear the cached lookup dictionary (useful for testing)."""
        cls._equipment_lookup = None


# Convenience function for use in table formatting
def get_equipment_display_name(eq_id: str) -> str:
    """Get the display name for an equipment ID.

    Args:
        eq_id: The equipment ID (e.g., "hr01", "awhp_1", "b01")

    Returns:
        The equipment model name, or the original ID if not found
    """
    return DisplayRegistry.get_equipment_name(eq_id)


# Fields that contain equipment IDs and should be mapped to model names
EQUIPMENT_ID_FIELDS = frozenset({"hr_wwhp", "awhp", "backup_heating", "chiller"})

# AWHP sizing mode value mappings
AWHP_SIZING_MODE_DISPLAY = {
    "integer_sizing_peak_load": "Integer sizing (peak load)",
    "fractional_sizing_peak_load": "Fractional sizing (peak load)",
    "fixed_num_units": "Fixed number of units",
}

# AWHP performance model value mappings
AWHP_PERFORMANCE_MODEL_DISPLAY = {
    "interpolate_HHWST_fixed": "Interpolated table (HHWST fixed)",
    "interpolate_HHWST_reset": "Interpolated table (HHWST reset)",
    "fixed_COP": "Fixed COP",
    "performance_curves": "Performance curves",
}

# HR performance model value mappings
HR_WWHP_PERFORMANCE_MODEL_DISPLAY = {
    "interpolate_HHWST": "Interpolated table (HHWST fixed)",
    "fixed_COP": "Fixed COP",
    "performance_curves": "Performance curves",
}

# Fields that have enumerated values needing display mapping
ENUM_VALUE_FIELDS = frozenset({"awhp_sizing_mode", "awhp_performance_model", "hr_wwhp_performance_model"})


def format_enum_value(value: str, field_name: str) -> str:
    """Format enumerated field values for display.

    Args:
        value: The raw enum value
        field_name: The field name to determine which mapping to use

    Returns:
        User-friendly display name
    """
    if value is None:
        return None

    if field_name == "awhp_sizing_mode":
        return AWHP_SIZING_MODE_DISPLAY.get(value, value)

    if field_name == "awhp_performance_model":
        return AWHP_PERFORMANCE_MODEL_DISPLAY.get(value, value)

    if field_name == "hr_wwhp_performance_model":
        return HR_WWHP_PERFORMANCE_MODEL_DISPLAY.get(value, value)

    return value


def format_equipment_scenario_id(eq_scen_id: str) -> str:
    """Format equipment scenario ID for display.

    Args:
        eq_scen_id: The scenario ID (e.g., "eq_scenario_1", "eq_scenario_2")

    Returns:
        Formatted display name (e.g., "Equipment Scen. 1")
    """
    if eq_scen_id is None:
        return None
    # Expected format: "eq_scenario_X" where X is a number
    if eq_scen_id.startswith("eq_scenario_"):
        suffix = eq_scen_id[len("eq_scenario_") :]
        return f"Equipment Scen. {suffix}"
    return eq_scen_id


def format_emission_scenario_id(em_scen_id: str) -> str:
    """Format emission scenario ID for display.

    Args:
        em_scen_id: The scenario ID (e.g., "em_scenario_a", "em_scenario_b")

    Returns:
        Formatted display name (e.g., "Emission Scen. A")
    """
    if em_scen_id is None:
        return None
    # Expected format: "em_scenario_X" where X is a letter
    if em_scen_id.startswith("em_scenario_"):
        suffix = em_scen_id[len("em_scenario_") :]
        return f"Emission Scen. {suffix.upper()}"
    return em_scen_id


# Mapping of meter/variable column names to user-friendly display names
METER_DISPLAY_NAMES = {
    # Electricity meters
    "elec_hr_Wh": "HR-WWHP Elec.",
    "elec_awhp_h_Wh": "AWHP Heating Elec.",
    "elec_awhp_c_Wh": "AWHP Cooling Elec.",
    "elec_chiller_Wh": "Chiller Elec.",
    "elec_res_Wh": "Resistance Heater Elec.",
    # Gas meters
    "gas_boiler_Wh": "Boiler Gas",
}


def format_meter_name(meter_col: str) -> str:
    """Format a meter column name for display.

    Args:
        meter_col: The column name (e.g., "elec_hr_Wh", "gas_boiler_Wh")

    Returns:
        User-friendly display name (e.g., "HR-WWHP Elec.", "Boiler Gas")
    """
    return METER_DISPLAY_NAMES.get(meter_col, meter_col)
