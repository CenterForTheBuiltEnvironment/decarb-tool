# any constants used in the analysis
# unit conversions
# all are multiplied, right to left
ton_to_W = 12000 * 0.293  # refrigerant-ton to W
W_to_ton = 1 / ton_to_W
BTUh_to_W = 0.293  # BTU/hr to W
W_to_BTUh = 1 / BTUh_to_W
Wh_to_BTU = 3.412
BTU_to_Wh = 1 / Wh_to_BTU
lbs_to_ton = 0.454 / 1000  # lbs (e.g. of CO2) to metric tons
ton_to_lbs = 1 / lbs_to_ton
lb_to_kg = 0.454  # lbs (e.g. of CO2) to metric tons
kg_to_lb = 1 / lb_to_kg
lb_to_g = 454  # lbs (e.g. of CO2) to metric tons
g_to_lb = 1 / lb_to_g
dC_to_dF = 1.8  # conversion of temperature differences (i.e. delta Ts)
dF_to_dC = 1 / dC_to_dF
cfm_to_lps = 0.47194745  # cfm to l/s
lps_to_cfm = 1 / cfm_to_lps

# fixed emissions conversions factors
# ng_combustion_to_co2e = 5.3*1000/29.3 # 5.3kg/therm to g/kWh (same unit as cambium emissions data, kg/MWh)
# from EPA: https://www.epa.gov/energy/greenhouse-gas-equivalencies-calculator-calculations-and-references
# if including pre-combustion emissions to end use that match Cambium assumptions, increase by 29% (31% reported in paper adjusted to account for newer IPCC AR6 values)
ng_combustion_to_co2e = (
    1.29 * 5.3 * 1000 / 29.3
)  # 5.3kg/therm to g/kWh (same unit as cambium emissions data, kg/MWh)


### CONVERSIONS ###
def C_to_F(c_val):
    return c_val * 1.8 + 32


def F_to_C(f_val):
    return (f_val - 32) / 1.8


def Wh_to_kWh(Wh):
    return Wh / 1000


def Wh_to_BTUh(Wh):
    return Wh * 3.412


def kg_to_lbs(kg):
    return kg * 2.20462


def lbs_to_ton(lbs):
    return lbs / 2000


def kg_to_ton(kg):  # imperial tons
    return kg / 907.185


### COP CONVERSIONS ###


def cop_c_to_cop_h(cop_c_val):
    return cop_c_val + 1


def cop_h_to_cop_c(cop_h_val):
    return cop_h_val - 1


def cop_h_to_cop_hc(cop_h_val):
    return (cop_h_val * 2) - 1


def cop_c_to_cop_hc(cop_c_val):
    return (cop_c_val * 2) + 1


def cop_hc_to_cop_c(cop_hc):
    return (cop_hc - 1) / 2


def cop_hc_to_cop_h(cop_hc):
    return ((cop_hc - 1) / 2) + 1


### UNIT CONVERSIONS FOR DISPLAY ###
def W_to_kW(W):
    return W / 1000


def W_to_tons(W):
    """Convert Watts to refrigeration tons."""
    return W * W_to_ton


def kW_to_tons(kW):
    """Convert kilowatts to refrigeration tons."""
    return kW * W_to_ton * 1000


def sqm_to_sqft(sqm):
    """Convert square meters to square feet."""
    return sqm * 10.7639


def sqft_to_sqm(sqft):
    """Convert square feet to square meters."""
    return sqft / 10.7639


### CENTRALIZED UNIT CONVERSION SYSTEM ###
# This is the single source of truth for all unit conversions in the app.
# See docs/unit-conventions.md for full documentation.

# =============================================================================
# UNIT_MAP: Category-based unit definitions with base/SI/IP
# =============================================================================
# Structure: category -> {base, SI: {unit, func}, IP: {unit, func}}
# - base: internal storage unit (used in calculations)
# - SI: {unit: display label, func: base→SI conversion}
# - IP: {unit: display label, func: base→IP conversion}

UNIT_MAP = {
    # --- Energy (heating & general) ---
    "energy": {
        "base": "Wh",
        "SI": {"unit": "kWh", "func": Wh_to_kWh},
        "IP": {"unit": "BTU", "func": Wh_to_BTUh},
    },
    # --- Power (heating & general) ---
    "power": {
        "base": "W",
        "SI": {"unit": "kW", "func": W_to_kW},
        "IP": {"unit": "BTU/h", "func": lambda x: x * W_to_BTUh},
    },
    # --- Power for cooling (uses tons of refrigeration in IP) ---
    "power_cooling": {
        "base": "W",
        "SI": {"unit": "kW", "func": W_to_kW},
        "IP": {"unit": "TR", "func": W_to_tons},
    },
    # --- Capacity (same as power, for equipment ratings) ---
    "capacity": {
        "base": "W",
        "SI": {"unit": "kW", "func": W_to_kW},
        "IP": {"unit": "BTU/h", "func": lambda x: x * W_to_BTUh},
    },
    # --- Capacity for cooling equipment ---
    "capacity_cooling": {
        "base": "W",
        "SI": {"unit": "kW", "func": W_to_kW},
        "IP": {"unit": "TR", "func": W_to_tons},
    },
    # --- Power already in kW (for pre-converted data) ---
    "power_kw": {
        "base": "kW",
        "SI": {"unit": "kW", "func": lambda x: x},
        "IP": {"unit": "TR", "func": kW_to_tons},
    },
    # --- Temperature ---
    "temperature": {
        "base": "°C",
        "SI": {"unit": "°C", "func": lambda x: x},
        "IP": {"unit": "°F", "func": C_to_F},
    },
    # --- Area ---
    "area": {
        "base": "m²",
        "SI": {"unit": "m²", "func": lambda x: x},
        "IP": {"unit": "ft²", "func": sqm_to_sqft},
    },
    # --- Emissions (mass of CO2e) ---
    "emissions": {
        "base": "kg CO₂e",
        "SI": {"unit": "kg CO₂e", "func": lambda x: x},
        "IP": {"unit": "lb CO₂e", "func": kg_to_lbs},
    },
    # --- Emission rate (grid emissions) ---
    "emissions_rate": {
        "base": "g CO₂e/kWh",
        "SI": {"unit": "g CO₂e/kWh", "func": lambda x: x},
        "IP": {"unit": "lb CO₂e/kBTU", "func": lambda x: x * g_to_lb / Wh_to_BTU},
    },
    # --- Gas emission factor ---
    "gas_emission_factor": {
        "base": "g CO₂e/kWh",
        "SI": {"unit": "g CO₂e/kWh", "func": lambda x: x},
        "IP": {"unit": "lb CO₂e/kBTU", "func": lambda x: x * g_to_lb / Wh_to_BTU},
    },
    # --- NG leakage rate ---
    "ng_leakage_rate": {
        "base": "g/kWh",
        "SI": {"unit": "g/kWh", "func": lambda x: x},
        "IP": {"unit": "lb/kBTU", "func": lambda x: x * g_to_lb / Wh_to_BTU},
    },
    # --- Mass (refrigerant weight, etc.) ---
    "mass": {
        "base": "kg",
        "SI": {"unit": "kg", "func": lambda x: x},
        "IP": {"unit": "lb", "func": kg_to_lbs},
    },
    # --- Mass stored in grams ---
    "mass_g": {
        "base": "g",
        "SI": {"unit": "kg", "func": lambda x: x / 1000},
        "IP": {"unit": "lb", "func": lambda x: x * g_to_lb},
    },
    # --- Load intensity ---
    "load_intensity": {
        "base": "W/m²",
        "SI": {"unit": "W/m²", "func": lambda x: x},
        "IP": {"unit": "BTU/h·ft²", "func": lambda x: x * W_to_BTUh / 10.7639},
    },
    # --- GWP (global warming potential per kg refrigerant) ---
    "gwp": {
        "base": "kg CO₂e/kg",
        "SI": {"unit": "kg CO₂e/kg", "func": lambda x: x},
        "IP": {"unit": "lb CO₂e/lb", "func": lambda x: x},  # dimensionless ratio
    },
}


# =============================================================================
# COLUMN_CONFIG: Unified registry for column metadata (SINGLE SOURCE OF TRUTH)
# =============================================================================
# Each entry: column_name -> (category, display_name)
# - category: Unit category from UNIT_MAP (or None for dimensionless)
# - display_name: Human-readable label for exports/display
#
# Add new columns here when they're added to calculations.

COLUMN_CONFIG = {
    # === Area ===
    "area_sqm": ("area", "Area"),
    # === Energy (Wh) ===
    "elec_Wh": ("energy", "Total Electricity"),
    "gas_Wh": ("energy", "Total Gas"),
    "elec_hr_Wh": ("energy", "HR-WWHP Electricity"),
    "elec_awhp_h_Wh": ("energy", "AWHP Heating Electricity"),
    "elec_awhp_c_Wh": ("energy", "AWHP Cooling Electricity"),
    "elec_res_Wh": ("energy", "Resistance Heater Electricity"),
    "elec_chiller_Wh": ("energy", "Chiller Electricity"),
    "gas_boiler_Wh": ("energy", "Boiler Gas"),
    # === Power - Heating (W) ===
    "heating_W": ("power", "Heating Load"),
    "hhw_W": ("power", "HHW Load"),
    "hhw_rem_W": ("power", "HHW Remaining"),
    "hr_hhw_W": ("power", "HR HHW Output"),
    "awhp_hhw_W": ("power", "AWHP HHW Output"),
    "boiler_hhw_W": ("power", "Boiler HHW Output"),
    "res_hhw_W": ("power", "Resistance HHW Output"),
    "hhw_max_load": ("power", "Peak HHW Load"),
    "hhw_mean_load": ("power", "Mean HHW Load"),
    "hhw_median_load": ("power", "Median HHW Load"),
    "hhw_min_load": ("power", "Min HHW Load"),
    "hhw_q25_load": ("power", "Q25 HHW Load"),
    "hhw_q75_load": ("power", "Q75 HHW Load"),
    # === Power - Cooling (W) ===
    "cooling_W": ("power_cooling", "Cooling Load"),
    "chw_W": ("power_cooling", "CHW Load"),
    "chw_rem_W": ("power_cooling", "CHW Remaining"),
    "hr_chw_W": ("power_cooling", "HR CHW Output"),
    "awhp_chw_W": ("power_cooling", "AWHP CHW Output"),
    "chiller_chw_W": ("power_cooling", "Chiller CHW Output"),
    "chw_max_load": ("power_cooling", "Peak CHW Load"),
    "chw_mean_load": ("power_cooling", "Mean CHW Load"),
    "chw_median_load": ("power_cooling", "Median CHW Load"),
    "chw_min_load": ("power_cooling", "Min CHW Load"),
    "chw_q25_load": ("power_cooling", "Q25 CHW Load"),
    "chw_q75_load": ("power_cooling", "Q75 CHW Load"),
    # === Capacity - Heating (W) ===
    "max_cap_h_hr_W": ("capacity", "HR Max Heating Cap"),
    "min_cap_h_hr_W": ("capacity", "HR Min Heating Cap"),
    "simult_h_hr_W": ("capacity", "HR Simultaneous Cap"),
    "awhp_cap_h_W": ("capacity", "AWHP Heating Cap"),
    "capacity_W": ("capacity", "Rated Capacity"),
    # === Capacity - Cooling (W) ===
    "awhp_cap_c_W": ("capacity_cooling", "AWHP Cooling Cap"),
    # === Temperature (°C) ===
    "t_out_C": ("temperature", "Outdoor Temp"),
    "max_temp": ("temperature", "Max Temp"),
    "min_temp": ("temperature", "Min Temp"),
    "median_temp": ("temperature", "Median Temp"),
    # === Load Intensity (W/m²) ===
    "hhw_max_load_per_area": ("load_intensity", "Peak HHW Load/Area"),
    "chw_max_load_per_area": ("load_intensity", "Peak CHW Load/Area"),
    # === Emissions (kg CO₂e) ===
    "elec_emissions": ("emissions", "Electricity Emissions"),
    "gas_emissions": ("emissions", "Gas Emissions"),
    "total_refrig_emissions": ("emissions", "Refrigerant Emissions"),
    "total_emissions": ("emissions", "Total Emissions"),
    "total_refrig_gwp_kg": ("emissions", "Total Refrigerant GWP"),
    # === Emission Rates (g CO₂e/kWh) ===
    "elec_emissions_rate_gCO2e_per_kWh": ("emissions_rate", "Elec Emissions Rate"),
    "lrmer_co2e_c": ("emissions_rate", "LRMER Combustion"),
    "lrmer_co2e_p": ("emissions_rate", "LRMER Pre-combustion"),
    "srmer_co2e_c": ("emissions_rate", "SRMER Combustion"),
    "srmer_co2e_p": ("emissions_rate", "SRMER Pre-combustion"),
    # === NG Leakage ===
    "annual_ng_leakage_g_per_kWh": ("ng_leakage_rate", "Annual NG Leakage"),
    # === Refrigerant Mass (kg) ===
    "hr_wwhp_refrigerant_weight_kg": ("mass", "HR-WWHP Refrig Weight"),
    "total_awhp_refrigerant_weight_kg": ("mass", "AWHP Refrig Weight"),
    "chiller_refrigerant_weight_kg": ("mass", "Chiller Refrig Weight"),
    # === Refrigerant Mass (g) ===
    "refrigerant_weight_g": ("mass_g", "Refrigerant Charge"),
    # === Refrigerant GWP ===
    "hr_wwhp_refrigerant_gwp_kgCO2e_per_kgRefrig": ("gwp", "HR-WWHP Refrig GWP"),
    "total_awhp_refrigerant_gwp_kgCO2e_per_kgRefrig": ("gwp", "AWHP Refrig GWP"),
    "chiller_refrigerant_gwp_kgCO2e_per_kgRefrig": ("gwp", "Chiller Refrig GWP"),
    # === COP / Efficiency (dimensionless - no unit conversion needed) ===
    "hr_cop_h": (None, "HR Heating COP"),
    "awhp_cop_h": (None, "AWHP Heating COP"),
    "awhp_cop_c": (None, "AWHP Cooling COP"),
    "chiller_cop": (None, "Chiller COP"),
    "boiler_eff": (None, "Boiler Efficiency"),
    # === Equipment Counts (dimensionless) ===
    "awhp_num_h": (None, "AWHP Count (Heating)"),
    "awhp_num_h_redundant": (None, "AWHP Redundant (Heating)"),
    "awhp_num_c": (None, "AWHP Count (Cooling)"),
    # === Refrigerant Type (text - no conversion) ===
    "chiller_refrigerant": (None, "Chiller Refrigerant"),
    "hr_wwhp_refrigerant": (None, "HR-WWHP Refrigerant"),
    "awhp_refrigerant": (None, "AWHP Refrigerant"),
    # === Emission Scenario Parameters ===
    "lrmer_co2e": (None, "LRMER CO₂e"),
    "srmer_co2e": (None, "SRMER CO₂e"),
    "shortrun_weighting": (None, "Short-run Weighting"),
    "year": (None, "Year"),
    # === Scenario Identifiers ===
    "em_scen_id": (None, "Emission Scenario ID"),
    "eq_scen_id": (None, "Equipment Scenario ID"),
    "eq_scen_name": (None, "Equipment Scenario"),
}


# =============================================================================
# DERIVED VIEWS (for backward compatibility)
# =============================================================================
# These are derived from COLUMN_CONFIG to maintain backward compatibility.
# New code should use COLUMN_CONFIG or the helper functions.

COLUMN_REGISTRY = {
    col: config[0]
    for col, config in COLUMN_CONFIG.items()
    if config[0] is not None
}

COLUMN_DISPLAY_NAMES = {
    col: config[1]
    for col, config in COLUMN_CONFIG.items()
}


# =============================================================================
# AUTO-SCALING: Higher-order unit configuration for large values
# =============================================================================
# Defines scaling thresholds and higher-order units for categories.
# Used when accumulated values become too large to display readably.

AUTO_SCALE_CONFIG = {
    # Thresholds are in BASE units (W, Wh, kg, etc.)
    # Scale factors convert directly from base to the target display unit.
    # Format: (threshold_in_base, scale_factor, unit_label)
    "energy": {
        "SI": [
            (1e9, 1e9, "GWh"),   # >= 1 GWh (in Wh) → GWh
            (1e6, 1e6, "MWh"),   # >= 1 MWh (in Wh) → MWh
            (1e3, 1e3, "kWh"),   # >= 1 kWh (in Wh) → kWh
        ],
        "IP": [
            # 1 Wh = 3.412 BTU; MMBTU = 1e6 BTU
            # Threshold: 1 MMBTU = 1e6 BTU = 1e6/3.412 Wh ≈ 293,083 Wh
            # Scale: divide Wh by (1e6/3.412) to get MMBTU
            (1e6 / 3.412, 1e6 / 3.412, "MMBTU"),
            (1e3 / 3.412, 1e3 / 3.412, "kBTU"),
        ],
    },
    "power": {
        "SI": [
            (1e6, 1e6, "MW"),    # >= 1 MW (in W) → MW
            (1e3, 1e3, "kW"),    # >= 1 kW (in W) → kW
        ],
        "IP": [
            # 1 W = 3.412 BTU/h; MMBTU/h = 1e6 BTU/h
            # Threshold: 1 MMBTU/h = 1e6/3.412 W ≈ 293,083 W
            (1e6 / 3.412, 1e6 / 3.412, "MMBTU/h"),
            (1e3 / 3.412, 1e3 / 3.412, "kBTU/h"),
        ],
    },
    "power_cooling": {
        "SI": [
            (1e6, 1e6, "MW"),
            (1e3, 1e3, "kW"),
        ],
        "IP": [
            # 1 TR = 3517 W - keep in TR only (no kTR)
            (3517, 3517, "TR"),
        ],
    },
    "emissions": {
        "SI": [
            (1e6, 1e6, "kt CO₂e"),  # >= 1 kilotonne (in kg) → kt
            (1e3, 1e3, "t CO₂e"),   # >= 1 tonne (in kg) → t
        ],
        "IP": [
            # EPA convention: use metric tons
            (1e3, 1e3, "t CO₂e"),  # >= 1 metric ton (in kg) → t
        ],
    },
    "area": {
        # Area: base unit is m², no auto-scaling but need conversion for IP
        # Scale factor for IP: divide by (1/10.7639) = multiply by 10.7639
        "SI": [
            (1, 1, "m²"),  # Always show in m²
        ],
        "IP": [
            # 1 m² = 10.7639 ft²
            # scale = 1/10.7639 so that value/scale = value*10.7639 = sqft
            (1, 1 / 10.7639, "ft²"),
        ],
    },
}


# =============================================================================
# BACKWARD COMPATIBILITY: Legacy unit_map format
# =============================================================================
# This maintains compatibility with existing code that uses the old format.
# New code should use UNIT_MAP and the new helper functions.

def _build_legacy_unit_map():
    """Build backward-compatible unit_map from new UNIT_MAP structure."""
    legacy = {}
    for category, config in UNIT_MAP.items():
        legacy[category] = {}
        for mode in ["SI", "IP"]:
            mode_config = config[mode]
            base_unit = config["base"]
            display_unit = mode_config["unit"]

            legacy[category][mode] = {
                "func": mode_config["func"],
                "label": f'{category.replace("_", " ").title()} <span style="font-weight:200">| {display_unit}</span>',
                "hover_unit": display_unit,
                "short": display_unit,
            }
    return legacy

unit_map = _build_legacy_unit_map()


# =============================================================================
# NEW HELPER FUNCTIONS (recommended for new code)
# =============================================================================


def get_category(column_name: str) -> str | None:
    """Look up the unit category for a column name.

    Args:
        column_name: The column/field name (e.g., "elec_Wh", "t_out_C")

    Returns:
        Category string (e.g., "energy", "temperature") or None if not registered
    """
    return COLUMN_REGISTRY.get(column_name)


def get_converter(category: str, unit_mode: str):
    """Get conversion function for category and mode.

    Args:
        category: Unit category (e.g., "energy", "power", "temperature")
        unit_mode: "SI" or "IP"

    Returns:
        Conversion function that takes a value and returns converted value
    """
    return UNIT_MAP[category][unit_mode]["func"]


def get_display_unit(category: str, unit_mode: str) -> str:
    """Get display unit label for category and mode.

    Args:
        category: Unit category (e.g., "energy", "power")
        unit_mode: "SI" or "IP"

    Returns:
        Unit string (e.g., "kWh", "BTU", "°F")
    """
    return UNIT_MAP[category][unit_mode]["unit"]


def get_base_unit(category: str) -> str:
    """Get the base (internal storage) unit for a category.

    Args:
        category: Unit category (e.g., "energy", "power")

    Returns:
        Base unit string (e.g., "Wh", "W", "°C")
    """
    return UNIT_MAP[category]["base"]


def convert_value(value, column_name: str, unit_mode: str):
    """Convert a single value based on column name and unit mode.

    Args:
        value: Raw value in base units
        column_name: Column/field name to look up category
        unit_mode: "SI" or "IP"

    Returns:
        Converted value, or original value if column not registered
    """
    if value is None:
        return None

    category = get_category(column_name)
    if category is None:
        return value

    converter = get_converter(category, unit_mode)
    return converter(value)


def convert_dataframe(df, unit_mode: str):
    """Convert all registered columns in a DataFrame.

    Args:
        df: pandas DataFrame with columns to convert
        unit_mode: "SI" or "IP"

    Returns:
        New DataFrame with converted values (original is not modified)
    """
    import pandas as pd

    df = df.copy()
    for col in df.columns:
        category = get_category(col)
        if category is not None:
            converter = get_converter(category, unit_mode)
            # Handle potential NaN values
            df[col] = df[col].apply(lambda x: converter(x) if pd.notna(x) else x)
    return df


def get_column_display_name(column_name: str) -> str:
    """Get human-readable display name for a column.

    Args:
        column_name: Column/field name

    Returns:
        Human-readable name, or original if not found
    """
    return COLUMN_DISPLAY_NAMES.get(column_name, column_name)


def get_column_label(column_name: str, unit_mode: str) -> str:
    """Get display label for column including unit.

    Args:
        column_name: Column/field name
        unit_mode: "SI" or "IP"

    Returns:
        Label with unit, e.g., "Peak HHW Load [kW]"
    """
    display_name = get_column_display_name(column_name)
    category = get_category(column_name)

    if category is None:
        return display_name

    unit = get_display_unit(category, unit_mode)
    return f"{display_name} [{unit}]"


def format_value(value, column_name: str, unit_mode: str, decimals: int = 1) -> str:
    """Format a value with conversion and appropriate decimal places.

    Args:
        value: Raw value in base units
        column_name: Column/field name
        unit_mode: "SI" or "IP"
        decimals: Number of decimal places

    Returns:
        Formatted string (e.g., "1,234.5")
    """
    if value is None:
        return "—"

    converted = convert_value(value, column_name, unit_mode)
    if converted is None:
        return "—"

    try:
        return f"{converted:,.{decimals}f}"
    except (TypeError, ValueError):
        return str(converted)


# =============================================================================
# AUTO-SCALING FUNCTIONS (for large accumulated values)
# =============================================================================


def get_auto_scale(values, category: str, unit_mode: str):
    """Determine the appropriate scale for a series of values in BASE units.

    Analyzes the maximum value and selects an appropriate display unit,
    returning the scale factor to convert from base to that unit.

    Args:
        values: Iterable of numeric values in BASE units (W, Wh, kg, etc.)
        category: Unit category (e.g., "energy", "power", "emissions")
        unit_mode: "SI" or "IP"

    Returns:
        Tuple of (scale_factor, unit_label) where:
        - scale_factor: Divide base unit values by this to get display values
        - unit_label: The unit string to display (e.g., "MW", "kBTU/h")

    Example:
        >>> values = [1200000, 800000, 1500000]  # Values in W
        >>> scale, unit = get_auto_scale(values, "power", "SI")
        >>> print(scale, unit)  # 1000, "kW" (or 1000000, "MW" if larger)
        >>> display_values = [v / scale for v in values]
    """
    if category not in AUTO_SCALE_CONFIG:
        # No auto-scaling configured - use standard conversion
        return 1, get_display_unit(category, unit_mode)

    mode_config = AUTO_SCALE_CONFIG[category].get(unit_mode, [])
    if not mode_config:
        return 1, get_display_unit(category, unit_mode)

    # Find the maximum absolute value
    try:
        max_val = max(abs(v) for v in values if v is not None and v == v)  # v == v filters NaN
    except (ValueError, TypeError):
        # Empty or invalid values
        return 1, get_display_unit(category, unit_mode)

    # Find the appropriate scale based on thresholds (in base units)
    for threshold, scale_factor, unit in mode_config:
        if max_val >= threshold:
            return scale_factor, unit

    # If no threshold matched, use the last (smallest) entry as default
    # This ensures proper unit conversion even for small values
    if mode_config:
        _, scale_factor, unit = mode_config[-1]
        return scale_factor, unit

    # Fallback if no config at all
    return 1, get_display_unit(category, unit_mode)


def auto_scale_series(values, category: str, unit_mode: str):
    """Auto-scale a series of values from base units to appropriate display units.

    Takes values in base units (W, Wh, kg) and returns scaled values with
    the appropriate display unit label.

    Args:
        values: Iterable of values in BASE units (W, Wh, kg, etc.)
        category: Unit category
        unit_mode: "SI" or "IP"

    Returns:
        Tuple of (scaled_values, unit_label) where:
        - scaled_values: List of scaled values ready for display
        - unit_label: Unit string to use in axis labels/legends

    Example:
        >>> values = [1500000, 800000, 1200000]  # W
        >>> scaled, unit = auto_scale_series(values, "power", "SI")
        >>> print(scaled, unit)  # [1500, 800, 1200], "kW"
    """
    # Determine scale directly from base unit values
    scale_factor, unit = get_auto_scale(values, category, unit_mode)

    # Apply scaling
    scaled = [v / scale_factor if v is not None else None for v in values]
    return scaled, unit


def get_scaled_axis_label(category: str, unit_mode: str, max_value: float = None) -> str:
    """Get an axis label with auto-scaled unit based on data range.

    Args:
        category: Unit category (e.g., "energy", "power")
        unit_mode: "SI" or "IP"
        max_value: Maximum value in the data (in display units, after base conversion)
                   If None, returns the standard unit label.

    Returns:
        Axis label with appropriate unit (e.g., "Energy [MWh]", "Power [kW]")
    """
    if max_value is None:
        unit = get_display_unit(category, unit_mode)
    else:
        # Use the max value to determine scale
        _, unit = get_auto_scale([max_value], category, unit_mode)

    # Create a nice category label
    category_label = category.replace("_", " ").title()
    if category == "power_cooling":
        category_label = "Power"
    elif category == "capacity_cooling":
        category_label = "Capacity"

    return f"{category_label} [{unit}]"


def format_large_number(n: float, decimals: int = 1) -> str:
    """Format a large number with appropriate suffix (k, M, G).

    Args:
        n: Number to format
        decimals: Decimal places for the formatted number

    Returns:
        Formatted string (e.g., "1.2M", "345k", "789")
    """
    if n is None:
        return "—"

    abs_n = abs(n)
    if abs_n >= 1e9:
        return f"{n / 1e9:.{decimals}f}G"
    elif abs_n >= 1e6:
        return f"{n / 1e6:.{decimals}f}M"
    elif abs_n >= 1e3:
        return f"{n / 1e3:.{decimals}f}k"
    else:
        return f"{n:.{decimals}f}"


# =============================================================================
# LEGACY HELPER FUNCTIONS (backward compatibility)
# =============================================================================
# These functions work with the old unit_map format.
# New code should use the functions above.


def get_unit_converter(var_type: str, unit_mode: str):
    """Return the converter function (legacy interface).

    DEPRECATED: Use get_converter() with UNIT_MAP instead.
    """
    return unit_map[var_type][unit_mode]["func"]


def get_hover_unit(var_type: str, unit_mode: str) -> str:
    """Return the short unit string for hovers (legacy interface).

    DEPRECATED: Use get_display_unit() with UNIT_MAP instead.
    """
    return unit_map[var_type][unit_mode]["hover_unit"]


def get_unit_label(var_type: str, unit_mode: str) -> str:
    """Return the short unit label (legacy interface).

    DEPRECATED: Use get_display_unit() with UNIT_MAP instead.
    """
    config = unit_map[var_type][unit_mode]
    return config.get("short", config.get("hover_unit", ""))


def format_with_units(
    value, var_type: str, unit_mode: str, decimals: int = 1, include_unit: bool = True
) -> str:
    """Format a value with appropriate unit conversion and label (legacy interface).

    DEPRECATED: Use format_value() + get_display_unit() instead.

    Args:
        value: The raw value to format (in base units)
        var_type: Type of variable (e.g., "power", "area", "temperature")
        unit_mode: "SI" or "IP"
        decimals: Number of decimal places (default: 1)
        include_unit: Whether to append the unit label (default: True)

    Returns:
        Formatted string with converted value and optional unit label
    """
    if value is None:
        return "—"

    try:
        converter = get_unit_converter(var_type, unit_mode)
        converted = converter(value)
        formatted = f"{converted:,.{decimals}f}"

        if include_unit:
            unit_label = get_unit_label(var_type, unit_mode)
            return f"{formatted} {unit_label}"
        return formatted
    except (KeyError, TypeError):
        # Fallback if var_type not in unit_map or conversion fails
        return str(value)


def format_with_auto_scale(
    value,
    category: str,
    unit_mode: str,
    decimals: int = 1,
    include_unit: bool = True,
) -> str:
    """Format a single value with automatic unit scaling.

    Takes a value in base units and auto-scales to an appropriate display unit.

    Args:
        value: The raw value in BASE units (e.g., W, Wh, kg)
        category: Unit category (e.g., "power", "energy", "emissions")
        unit_mode: "SI" or "IP"
        decimals: Number of decimal places (default: 1)
        include_unit: Whether to append the unit label (default: True)

    Returns:
        Formatted string with auto-scaled value and optional unit label

    Example:
        >>> format_with_auto_scale(4500000, "power", "SI")
        '4,500.0 kW'  # 4.5 MW shown as kW
        >>> format_with_auto_scale(4500000, "power", "IP")
        '15,356.3 kBTU/h'
    """
    if value is None:
        return "—"

    try:
        # Determine auto-scaling directly from base unit value
        scale, unit = get_auto_scale([value], category, unit_mode)
        scaled = value / scale

        formatted = f"{scaled:,.{decimals}f}"

        if include_unit:
            return f"{formatted} {unit}"
        return formatted
    except (KeyError, TypeError):
        return str(value)


def get_auto_scale_for_values(values, category: str, unit_mode: str):
    """Pre-calculate auto-scale for a set of values in base units.

    Useful when you need to apply consistent scaling across multiple values
    (e.g., in a chart or table column).

    Args:
        values: Iterable of values in BASE units (W, Wh, kg, etc.)
        category: Unit category
        unit_mode: "SI" or "IP"

    Returns:
        Tuple of (scale_factor, unit_label) where:
        - scale_factor: Divide base unit values by this to get display values
        - unit_label: The unit string to display

    Example:
        >>> scale, unit = get_auto_scale_for_values([1500000, 800000], "power", "SI")
        >>> print(scale, unit)  # 1000, "kW"
        >>> display_values = [v / scale for v in values]  # [1500, 800]
    """
    scale, unit = get_auto_scale(values, category, unit_mode)
    return scale, unit
