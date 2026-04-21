# Unit Conventions Reference

This document provides a comprehensive overview of all variable types used in the Berkeley Decarb Tool, their internal storage units, and display units for SI and IP systems.

**Ground Rule**: All calculations use base SI units internally. Unit conversion is applied only for display purposes.

---

## Implementation Overview

The centralized unit conversion system is implemented in `utils/units.py` with:

1. **`UNIT_MAP`**: Category-based unit definitions with `base`, `SI`, and `IP` configurations
2. **`COLUMN_CONFIG`**: Unified registry mapping column names to `(category, display_name)` tuples
3. **`AUTO_SCALE_CONFIG`**: Automatic scaling for large values (e.g., kWh → MWh → GWh)
4. **Helper Functions**: `convert_dataframe()`, `convert_value()`, `get_auto_scale()`, etc.

```
┌──────────────────────────────────────────────────────────────────────┐
│                         utils/units.py                               │
│  ┌─────────────────┐  ┌─────────────────┐  ┌──────────────────────┐  │
│  │   UNIT_MAP      │  │  COLUMN_CONFIG  │  │  AUTO_SCALE_CONFIG   │  │
│  │  (categories)   │  │ (col → category │  │  (large value        │  │
│  │                 │  │  + display name)│  │   scaling)           │  │
│  │ energy:         │  │                 │  │                      │  │
│  │   base: Wh      │  │ elec_Wh:        │  │ energy:              │  │
│  │   SI: kWh       │  │  (energy,       │  │   SI: kWh→MWh→GWh    │  │
│  │   IP: BTU       │  │   "Total Elec") │  │   IP: kBTU→MMBTU     │  │
│  └─────────────────┘  └─────────────────┘  └──────────────────────┘  │
│                                                                      │
│  Derived views (backward compat): COLUMN_REGISTRY, COLUMN_DISPLAY_NAMES
└──────────────────────────────────────────────────────────────────────┘
```

---

## Summary: Unit Toggle Implementation Status

| Status | Description |
|--------|-------------|
| ✅ | Implemented in `UNIT_MAP` and `COLUMN_REGISTRY` |
| ⚠️ | Partially implemented or inconsistent |
| ❌ | Not implemented |
| N/A | No conversion needed (dimensionless) |

---

## 1. Energy Variables

| Variable | Column/Field | Internal Unit | SI Display | IP Display | Status |
|----------|--------------|---------------|------------|------------|--------|
| Total electricity | `elec_Wh` | Wh | kWh | BTU | ✅ |
| Total gas | `gas_Wh` | Wh | kWh | BTU | ✅ |
| HR-WWHP electricity | `elec_hr_Wh` | Wh | kWh | BTU | ✅ |
| AWHP heating elec | `elec_awhp_h_Wh` | Wh | kWh | BTU | ✅ |
| AWHP cooling elec | `elec_awhp_c_Wh` | Wh | kWh | BTU | ✅ |
| Resistance heater elec | `elec_res_Wh` | Wh | kWh | BTU | ✅ |
| Chiller electricity | `elec_chiller_Wh` | Wh | kWh | BTU | ✅ |
| Boiler gas | `gas_boiler_Wh` | Wh | kWh | BTU | ✅ |

---

## 2. Power / Load Variables

**Note**: Heating power uses BTU/h in IP mode. Cooling power uses TR (tons of refrigeration) in IP mode.

| Variable | Column/Field | Internal Unit | SI Display | IP Display | Status |
|----------|--------------|---------------|------------|------------|--------|
| Heating load | `heating_W` | W | kW | BTU/h | ✅ |
| Cooling load | `cooling_W` | W | kW | TR | ✅ |
| HHW load | `hhw_W` | W | kW | BTU/h | ✅ |
| CHW load | `chw_W` | W | kW | TR | ✅ |
| Peak HHW load | `hhw_max_load` | W | kW | BTU/h | ✅ |
| Peak CHW load | `chw_max_load` | W | kW | TR | ✅ |
| Mean HHW load | `hhw_mean_load` | W | kW | BTU/h | ✅ |
| Mean CHW load | `chw_mean_load` | W | kW | TR | ✅ |
| Median HHW load | `hhw_median_load` | W | kW | BTU/h | ✅ |
| Median CHW load | `chw_median_load` | W | kW | TR | ✅ |
| Min HHW load | `hhw_min_load` | W | kW | BTU/h | ✅ |
| Min CHW load | `chw_min_load` | W | kW | TR | ✅ |
| Q25/Q75 HHW load | `hhw_q25_load`, `hhw_q75_load` | W | kW | BTU/h | ✅ |
| Q25/Q75 CHW load | `chw_q25_load`, `chw_q75_load` | W | kW | TR | ✅ |
| HR heating output | `hr_hhw_W` | W | kW | BTU/h | ✅ |
| HR cooling output | `hr_chw_W` | W | kW | TR | ✅ |
| AWHP heating output | `awhp_hhw_W` | W | kW | BTU/h | ✅ |
| AWHP cooling output | `awhp_chw_W` | W | kW | TR | ✅ |
| Boiler heating output | `boiler_hhw_W` | W | kW | BTU/h | ✅ |
| Chiller cooling output | `chiller_chw_W` | W | kW | TR | ✅ |
| Resistance heater output | `res_hhw_W` | W | kW | BTU/h | ✅ |
| HHW remaining | `hhw_rem_W` | W | kW | BTU/h | ✅ |
| CHW remaining | `chw_rem_W` | W | kW | TR | ✅ |

---

## 3. Capacity Variables

| Variable | Column/Field | Internal Unit | SI Display | IP Display | Status |
|----------|--------------|---------------|------------|------------|--------|
| HR max heating cap | `max_cap_h_hr_W` | W | kW | BTU/h | ✅ |
| HR min heating cap | `min_cap_h_hr_W` | W | kW | BTU/h | ✅ |
| Simultaneous HR cap | `simult_h_hr_W` | W | kW | BTU/h | ✅ |
| AWHP heating capacity | `awhp_cap_h_W` | W | kW | BTU/h | ✅ |
| AWHP cooling capacity | `awhp_cap_c_W` | W | kW | TR | ✅ |
| Equipment rated capacity | `capacity_W` | W | kW | BTU/h | ✅ |

---

## 4. Temperature Variables

| Variable | Column/Field | Internal Unit | SI Display | IP Display | Status |
|----------|--------------|---------------|------------|------------|--------|
| Outdoor air temp | `t_out_C` | °C | °C | °F | ✅ |
| Max outdoor temp | `max_temp` | °C | °C | °F | ✅ |
| Min outdoor temp | `min_temp` | °C | °C | °F | ✅ |
| Median outdoor temp | `median_temp` | °C | °C | °F | ✅ |

---

## 5. Area Variables

| Variable | Column/Field | Internal Unit | SI Display | IP Display | Status |
|----------|--------------|---------------|------------|------------|--------|
| Building floor area | `area_sqm` | m² | m² | ft² | ✅ |

---

## 6. Load Intensity Variables

| Variable | Column/Field | Internal Unit | SI Display | IP Display | Status |
|----------|--------------|---------------|------------|------------|--------|
| Peak HHW per area | `hhw_max_load_per_area` | W/m² | W/m² | BTU/h·ft² | ✅ |
| Peak CHW per area | `chw_max_load_per_area` | W/m² | W/m² | BTU/h·ft² | ✅ |

---

## 7. Emissions Variables

| Variable | Column/Field | Internal Unit | SI Display | IP Display | Status |
|----------|--------------|---------------|------------|------------|--------|
| Electricity emissions | `elec_emissions` | kg CO₂e | kg CO₂e | lb CO₂e | ✅ |
| Gas emissions | `gas_emissions` | kg CO₂e | kg CO₂e | lb CO₂e | ✅ |
| Refrigerant emissions | `total_refrig_emissions` | kg CO₂e | kg CO₂e | lb CO₂e | ✅ |
| Total emissions | `total_emissions` | kg CO₂e | kg CO₂e | lb CO₂e | ✅ |
| Total refrigerant GWP | `total_refrig_gwp_kg` | kg CO₂e | kg CO₂e | lb CO₂e | ✅ |

---

## 8. Emission Rate Variables

| Variable | Column/Field | Internal Unit | SI Display | IP Display | Status |
|----------|--------------|---------------|------------|------------|--------|
| Electricity emission rate | `elec_emissions_rate_gCO2e_per_kWh` | g CO₂e/kWh | g CO₂e/kWh | lb CO₂e/kBTU | ✅ |
| LRMER combustion | `lrmer_co2e_c` | g CO₂e/kWh | g CO₂e/kWh | lb CO₂e/kBTU | ✅ |
| LRMER pre-combustion | `lrmer_co2e_p` | g CO₂e/kWh | g CO₂e/kWh | lb CO₂e/kBTU | ✅ |
| SRMER combustion | `srmer_co2e_c` | g CO₂e/kWh | g CO₂e/kWh | lb CO₂e/kBTU | ✅ |
| SRMER pre-combustion | `srmer_co2e_p` | g CO₂e/kWh | g CO₂e/kWh | lb CO₂e/kBTU | ✅ |
| NG leakage rate | `annual_ng_leakage_g_per_kWh` | g/kWh | g/kWh | lb/kBTU | ✅ |

---

## 9. Refrigerant Variables

| Variable | Column/Field | Internal Unit | SI Display | IP Display | Status |
|----------|--------------|---------------|------------|------------|--------|
| HR-WWHP refrigerant weight | `hr_wwhp_refrigerant_weight_kg` | kg | kg | lb | ✅ |
| AWHP refrigerant weight | `total_awhp_refrigerant_weight_kg` | kg | kg | lb | ✅ |
| Chiller refrigerant weight | `chiller_refrigerant_weight_kg` | kg | kg | lb | ✅ |
| Equipment refrigerant charge | `refrigerant_weight_g` | g | kg | lb | ✅ |
| HR-WWHP refrigerant GWP | `hr_wwhp_refrigerant_gwp_kgCO2e_per_kgRefrig` | kg CO₂e/kg | kg CO₂e/kg | lb CO₂e/lb | ✅ |
| AWHP refrigerant GWP | `total_awhp_refrigerant_gwp_kgCO2e_per_kgRefrig` | kg CO₂e/kg | kg CO₂e/kg | lb CO₂e/lb | ✅ |
| Chiller refrigerant GWP | `chiller_refrigerant_gwp_kgCO2e_per_kgRefrig` | kg CO₂e/kg | kg CO₂e/kg | lb CO₂e/lb | ✅ |
| Refrigerant leakage rate | `annual_refrig_leakage_percent` | fraction | % | % | N/A |

---

## 10. Efficiency / COP Variables (No Conversion Needed)

| Variable | Column/Field | Internal Unit | Display | Status |
|----------|--------------|---------------|---------|--------|
| HR heating COP | `hr_cop_h` | dimensionless | COP | N/A |
| AWHP heating COP | `awhp_cop_h` | dimensionless | COP | N/A |
| AWHP cooling COP | `awhp_cop_c` | dimensionless | COP | N/A |
| Chiller COP | `chiller_cop` | dimensionless | COP | N/A |
| Boiler efficiency | `boiler_eff` | fraction | % | N/A |

---

## Current `UNIT_MAP` in `utils/units.py`

```python
UNIT_MAP = {
    "energy":          {"base": "Wh",  "SI": "kWh",       "IP": "BTU"},
    "power":           {"base": "W",   "SI": "kW",        "IP": "BTU/h"},
    "power_cooling":   {"base": "W",   "SI": "kW",        "IP": "TR"},
    "capacity":        {"base": "W",   "SI": "kW",        "IP": "BTU/h"},
    "capacity_cooling":{"base": "W",   "SI": "kW",        "IP": "TR"},
    "temperature":     {"base": "°C",  "SI": "°C",        "IP": "°F"},
    "area":            {"base": "m²",  "SI": "m²",        "IP": "ft²"},
    "emissions":       {"base": "kg",  "SI": "kg CO₂e",   "IP": "lb CO₂e"},
    "emissions_rate":  {"base": "g/kWh", "SI": "g CO₂e/kWh", "IP": "lb CO₂e/kBTU"},
    "ng_leakage_rate": {"base": "g/kWh", "SI": "g/kWh",   "IP": "lb/kBTU"},
    "gas_emission_factor": {"base": "g/kWh", "SI": "g CO₂e/kWh", "IP": "lb CO₂e/kBTU"},
    "mass":            {"base": "kg",  "SI": "kg",        "IP": "lb"},
    "mass_g":          {"base": "g",   "SI": "kg",        "IP": "lb"},
    "load_intensity":  {"base": "W/m²", "SI": "W/m²",     "IP": "BTU/h·ft²"},
    "gwp":             {"base": "kg/kg", "SI": "kg CO₂e/kg", "IP": "lb CO₂e/lb"},
}
```

## Current `AUTO_SCALE_CONFIG` in `utils/units.py`

```python
AUTO_SCALE_CONFIG = {
    "energy": {
        "SI": [(1e9, "GWh"), (1e6, "MWh"), (1e3, "kWh")],
        "IP": [(1e3/3.412, "kBTU")],
    },
    "power": {
        "SI": [(1e6, "MW"), (1e3, "kW")],
        "IP": [(1e3/3.412, "kBTU/h")],
    },
    "power_cooling": {
        "SI": [(1e6, "MW"), (1e3, "kW")],
        "IP": [(3517, "TR")],  # No kTR - stays in TR
    },
    "emissions": {
        "SI": [(1e6, "kt CO₂e"), (1e3, "t CO₂e")],
        "IP": [(1e3, "t CO₂e")],  # EPA convention: metric tons
    },
}
# Thresholds are in BASE units (W, Wh, kg)
# Format: (threshold, unit_label)
```

---

## Key Helper Functions

```python
# Get category for a column
category = get_category("elec_Wh")  # Returns "energy"

# Get display unit for category and mode
unit = get_display_unit("energy", "IP")  # Returns "BTU"

# Convert a single value
converted = convert_value(1000, "elec_Wh", "SI")  # Returns 1.0 (kWh)

# Convert entire DataFrame
df_converted = convert_dataframe(df, "IP")

# Get column label with unit
label = get_column_label("elec_Wh", "SI")  # Returns "Total Electricity [kWh]"
```

---

## Usage in Components

### Charts (`src/visuals.py`)
```python
# Convert DataFrame before plotting
df = convert_dataframe(df, unit_mode)

# Get hover units
hover_unit = get_display_unit("energy", unit_mode)
```

### Tables (`layout/input.py`)
```python
def build_building_table(buildings_data, selected_id=None, unit_mode="SI"):
    # Convert values and get unit labels dynamically
    unit = get_display_unit(category, unit_mode)
    value = convert_value(raw_value, column_name, unit_mode)
```

### Download (`pages/results_page.py`)
```python
# Convert DataFrame before export
df = convert_dataframe(df, unit_mode)
# Rename columns to include units
df = df.rename(columns={col: get_column_label(col, unit_mode) for col in df.columns})
```

---

## Auto-Scaling for Large Values

The `AUTO_SCALE_CONFIG` automatically scales large accumulated values to appropriate display units:

| Category | SI Scaling | IP Scaling |
|----------|------------|------------|
| Energy | Wh → kWh → MWh → GWh | Wh → kBTU → MMBTU |
| Power (heating) | W → kW → MW | W → kBTU/h → MMBTU/h |
| Power (cooling) | W → kW → MW | W → TR (no kTR) |
| Emissions | kg → t CO₂e → kt CO₂e | kg → t CO₂e (metric tons, EPA convention) |

### Usage

```python
from utils.units import get_auto_scale, format_with_auto_scale

# Get scale factor and unit for a set of values
scale, unit = get_auto_scale([1500000, 800000], "power", "SI")
# Returns: (1000, "kW") - values are in the kW range

# Format a single value with auto-scaling
formatted = format_with_auto_scale(4500000, "power", "SI")
# Returns: "4,500.0 kW"

# For charts: scale values consistently
power_scale, power_unit = get_auto_scale(all_values, "power", unit_mode)
scaled_values = [v / power_scale for v in all_values]
```

### Load Selection Sliders (IP Mode)

The load selection modal uses appropriate units for IP mode:
- **Heating (HHW)**: MMBTU/h (avoids extremely large BTU/h values)
- **Cooling (CHW)**: TR (tons of refrigeration)

---

## Download Export

When exporting data via CSV download:
- Values are converted to the selected unit mode (SI/IP)
- Smart rounding is applied: 2 decimal places normally, 3 for values < 1
- Column headers include units: e.g., "Total Electricity [kWh]"

---

## Notes

- **COP and efficiency** are dimensionless and don't require unit conversion
- **Percentages and fractions** are unitless (display as % or 0-1 based on context)
- **Counts** (number of units, years, etc.) don't require conversion
- Internal storage always uses **base SI units** (W, Wh, °C, m², kg, g)
- Display may use derived SI units (kW, kWh) for readability
- **Cooling power** uses TR (tons of refrigeration) in IP mode
- **Heating power** uses BTU/h (or MMBTU/h for large values) in IP mode
- **IP emissions** use metric tons (t CO₂e) per EPA convention, not pounds for large values
- **IP energy** uses MMBTU (not MBTU) as the standard convention

---

*Last updated: 2026-03-13*
