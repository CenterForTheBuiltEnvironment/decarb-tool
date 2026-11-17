import datetime
import re

import numpy as np
import pandas as pd

from src.equipment import EquipmentLibrary
from src.metadata import Metadata
from utils.display_registry import format_emission_scenario_id_short
from utils.units import (
    COLUMN_DISPLAY_NAMES,
    UNIT_MAP,
    convert_dataframe,
    get_category,
    get_column_label,
)

# Columns that identify a case (equipment x emission scenario); first in every results CSV
EXPORT_ID_COLUMNS = [
    "eq_scen_slot",
    "eq_scen_name",
    "em_scen_letter",
    "em_scen_name",
    "em_year",
    "em_grid_scenario",
    "em_elec_source",
    "em_emission_type",
    "eq_scen_id",
    "em_scen_id",
]

# Hourly results column order after the identifiers; columns not listed here are appended
_HOURLY_COLUMN_ORDER = [
    # conditions
    "t_out_C",
    "heating_W",
    "cooling_W",
    # totals
    "elec_Wh",
    "gas_Wh",
    "elec_emissions",
    "gas_emissions",
    "total_refrig_emissions",
    "total_emissions",
    # grid emission rates
    "elec_emissions_rate_gCO2e_per_kWh",
    "lrmer_co2e_c",
    "lrmer_co2e_p",
    "lrmer_co2e",
    "srmer_co2e_c",
    "srmer_co2e_p",
    "srmer_co2e",
    "aer_load_co2e_c",
    "aer_load_co2e_p",
    "aer_load_co2e",
    "shortrun_weighting",
    # equipment operation, heating then cooling
    "hhw_W",
    "chw_W",
    "hr_hhw_W",
    "hr_chw_W",
    "hr_cop_h",
    "simult_h_hr_W",
    "elec_hr_Wh",
    "awhp_hhw_W",
    "awhp_cap_h_W",
    "awhp_cop_h",
    "elec_awhp_h_Wh",
    "boiler_hhw_W",
    "gas_boiler_Wh",
    "res_hhw_W",
    "elec_res_Wh",
    "awhp_chw_W",
    "awhp_num_c",
    "awhp_cap_c_W",
    "awhp_cop_c",
    "elec_awhp_c_Wh",
    "chiller_chw_W",
    "chiller_cop",
    "elec_chiller_Wh",
    # equipment properties, constant per equipment scenario
    "max_cap_h_hr_W",
    "min_cap_h_hr_W",
    "awhp_num",
    "awhp_num_redundant",
    "boiler_num",
    "boiler_cap_W",
    "boiler_eff",
    "hr_wwhp_refrigerant",
    "hr_wwhp_refrigerant_weight_kg",
    "hr_wwhp_refrigerant_gwp_kgCO2e_per_kgRefrig",
    "awhp_refrigerant",
    "total_awhp_refrigerant_weight_kg",
    "total_awhp_refrigerant_gwp_kgCO2e_per_kgRefrig",
    "chiller_refrigerant",
    "chiller_refrigerant_weight_kg",
    "chiller_refrigerant_gwp_kgCO2e_per_kgRefrig",
    "total_refrig_gwp_kg",
]

# Load year of the timestamp; dropped so it is not mistaken for the emission year
_HOURLY_DROP_COLUMNS = ["year"]

# Hourly columns summed into the annual summary (hourly data, so W sums to Wh)
_ANNUAL_SUM_COLUMNS = {
    "heating_W": "annual_heating_Wh",
    "cooling_W": "annual_cooling_Wh",
    "elec_Wh": "elec_Wh",
    "gas_Wh": "gas_Wh",
    "elec_hr_Wh": "elec_hr_Wh",
    "elec_awhp_h_Wh": "elec_awhp_h_Wh",
    "elec_res_Wh": "elec_res_Wh",
    "elec_awhp_c_Wh": "elec_awhp_c_Wh",
    "elec_chiller_Wh": "elec_chiller_Wh",
    "gas_boiler_Wh": "gas_boiler_Wh",
    "elec_emissions": "elec_emissions",
    "gas_emissions": "gas_emissions",
    "total_refrig_emissions": "total_refrig_emissions",
    "total_emissions": "total_emissions",
}


def _slug(text, max_len: int = 40) -> str:
    """Filename-safe part: letters, digits, '.' and '-' only."""
    slug = re.sub(r"[^A-Za-z0-9.]+", "-", str(text)).strip("-.")
    return slug[:max_len].rstrip("-.")


def _building_label(metadata: Metadata) -> str:
    building_id = _slug(metadata.building_id or "")
    if metadata.load_data.load_type == "custom":
        if not building_id and metadata.load_data.load_source_ref:
            building_id = _slug(metadata.load_data.load_source_ref.rsplit(".", 1)[0])
        return f"custom-{building_id}" if building_id else "custom"
    if building_id.isdigit():
        return f"B{building_id}"
    return building_id


def build_export_basename(
    metadata: Metadata,
    unit_mode: str = "SI",
    scale_info: dict | None = None,
    base_load_info: dict | None = None,
    now: datetime.datetime | None = None,
) -> str:
    """Descriptive name for the results download, e.g.
    decarb_B3_Denver_CZ5B_scaled-h1.25-c1.25_SI_20261102-1430
    """
    now = now or datetime.datetime.now()
    parts = ["decarb", _building_label(metadata)]
    if metadata.location:
        parts.append(_slug(metadata.location))
    if metadata.ashrae_climate_zone:
        parts.append(f"CZ{_slug(metadata.ashrae_climate_zone)}")
    if scale_info:
        heating = scale_info.get("heating_factor", 1.0)
        cooling = scale_info.get("cooling_factor", 1.0)
        parts.append(f"scaled-h{heating:.2f}-c{cooling:.2f}")
    if base_load_info and any(base_load_info.get(k) for k in ("heating", "cooling")):
        parts.append("baseload")
    parts.append(unit_mode or "SI")
    parts.append(now.strftime("%Y%m%d-%H%M"))
    return "_".join(p for p in parts if p)


def _slot_number(eq_scen_id: str, slot_map: dict) -> int | None:
    if eq_scen_id in slot_map:
        return slot_map[eq_scen_id]
    suffix = str(eq_scen_id).removeprefix("eq_scenario_")
    return int(suffix) if suffix.isdigit() else None


def build_hourly_export(
    df: pd.DataFrame, metadata: Metadata, slot_map: dict | None = None
) -> pd.DataFrame:
    """Hourly results in export layout (raw column names, base units).

    Adds readable case identifiers (equipment slot, emission letter, emission scenario
    settings) as the first columns, orders the remaining columns by topic and sorts the
    rows so that each equipment x emission combination is one contiguous block.

    slot_map maps eq_scen_id to its slot on the Equipment page, the number the Results
    page shows; without it the number in the scenario id is used.
    """
    slot_map = slot_map or {}
    em_by_id = {s.em_scen_id: s for s in metadata.emission_settings}

    out = df.drop(columns=[c for c in _HOURLY_DROP_COLUMNS if c in df.columns])
    eq_ids = out["eq_scen_id"]
    em_ids = out["em_scen_id"]

    slots = {i: _slot_number(i, slot_map) for i in eq_ids.unique()}
    out["eq_scen_slot"] = eq_ids.map(slots).astype("Int64")
    out["em_scen_letter"] = em_ids.map(format_emission_scenario_id_short)

    descriptors = {
        "em_scen_name": "em_scen_name",
        "em_year": "year",
        "em_grid_scenario": "grid_scenario",
        "em_elec_source": "elec_emission_source",
        "em_emission_type": "emission_type",
    }
    for col, field in descriptors.items():
        values = {i: getattr(s, field) for i, s in em_by_id.items()}
        out[col] = em_ids.map(values)
    out["em_year"] = out["em_year"].astype("Int64")

    ordered = [c for c in EXPORT_ID_COLUMNS + _HOURLY_COLUMN_ORDER if c in out.columns]
    ordered += [c for c in out.columns if c not in ordered]
    out = out[ordered]

    index_name = out.index.name or "timestamp"
    out = (
        out.rename_axis(index_name)
        .reset_index()
        .sort_values(["eq_scen_slot", "eq_scen_id", "em_scen_id", index_name], kind="stable")
        .set_index(index_name)
    )
    return out


def build_annual_summary(df_hourly: pd.DataFrame) -> pd.DataFrame:
    """Annual totals, one row per equipment x emission combination (base units).

    Takes the output of build_hourly_export. Hourly loads in W sum to annual Wh.
    """
    id_cols = [c for c in EXPORT_ID_COLUMNS if c in df_hourly.columns]
    sum_cols = [c for c in _ANNUAL_SUM_COLUMNS if c in df_hourly.columns]
    annual = (
        df_hourly.groupby(id_cols, dropna=False, sort=False)[sum_cols]
        .sum()
        .reset_index()
        .rename(columns=_ANNUAL_SUM_COLUMNS)
    )
    return annual


def _perf_model_label(model: str | None) -> str:
    labels = {
        "fixed_COP": "Fixed COP",
        "interpolate_HHWST": "Interpolate HHWST",
        "interpolate_HHWST_fixed": "Interpolate HHWST (fixed)",
        "interpolate_HHWST_reset": "Interpolate HHWST (reset)",
        "performance_curves": "Performance curves",
    }
    return labels.get(model, model or "N/A")


def _sizing_label(mode: str | None) -> str:
    labels = {
        "integer_sizing_peak_load": "Integer sizing (peak load)",
        "fractional_sizing_peak_load": "Fractional sizing (peak load)",
        "fixed_num_units": "Fixed number of units",
    }
    return labels.get(mode, mode or "N/A")


def _eq_display(eq_id: str | None, library: EquipmentLibrary) -> str:
    if not eq_id:
        return "None"
    try:
        eq = library.get_equipment(eq_id)
        mfr = f"{eq.eq_manufacturer} " if eq.eq_manufacturer else ""
        return f"{mfr}{eq.model}"
    except (KeyError, AttributeError):
        return eq_id


def _eq_capacity(eq_id: str | None, library: EquipmentLibrary, unit_mode: str) -> str:
    if not eq_id:
        return "N/A"
    try:
        eq = library.get_equipment(eq_id)
        cap = eq.nominal_capacity_W or eq.capacity_W
        if cap is None:
            return "N/A"
        func = UNIT_MAP["capacity"][unit_mode]["func"]
        unit = UNIT_MAP["capacity"][unit_mode]["unit"]
        return f"{func(cap):,.0f} {unit}"
    except (KeyError, AttributeError):
        return "N/A"


def _round_like_python(values, decimals):
    """Vectorised round() with the same result as Python's built-in round().

    Series.round() can differ from round() on values that look like exact
    halves in decimal (e.g. 6.825); those few values are rounded one by one.
    Masks and assignments are positional, as the hourly index repeats per case.
    """
    rounded = values.round(decimals)
    scaled = values * 10**decimals
    near_half = (((scaled - np.trunc(scaled)).abs() - 0.5).abs() < 1e-6).to_numpy()
    if near_half.any():
        rounded.iloc[near_half] = [round(v, decimals) for v in values.iloc[near_half]]
    return rounded


def _round_for_csv(values):
    """2 decimals for |x| >= 1, 4 significant figures below (at most 8 decimals).

    Significant figures keep small values such as lb CO2e/kWh rates or hourly
    emissions from rounding to zero.
    """
    rounded = _round_like_python(values, 2)
    magnitude = values.abs().to_numpy()
    small = (magnitude < 1) & (magnitude > 0)
    if small.any():
        decimals = np.zeros(len(values), dtype=int)
        decimals[small] = np.minimum(3 - np.floor(np.log10(magnitude[small])), 8)
        for d in np.unique(decimals[small]):
            mask = small & (decimals == d)
            rounded.iloc[mask] = _round_like_python(values.iloc[mask], int(d)).to_numpy()
    return rounded


def format_for_csv(df, unit_mode):
    """Convert to the unit system, round, and label columns with display name and unit."""
    df = convert_dataframe(df, unit_mode)

    for col in df.columns:
        if df[col].dtype in [np.float64, np.float32, float]:
            df[col] = _round_for_csv(df[col])

    # Columns with a unit category get "Name [unit]"; others just their display name
    column_renames = {}
    for col in df.columns:
        if get_category(col) is not None:
            column_renames[col] = get_column_label(col, unit_mode)
        elif col in COLUMN_DISPLAY_NAMES:
            column_renames[col] = COLUMN_DISPLAY_NAMES[col]
    return df.rename(columns=column_renames)


def _format_rate(value: float) -> str:
    """1 decimal for g/kWh-sized values, 4 significant figures for lb-sized ones."""
    return f"{value:.1f}" if abs(value) >= 10 else f"{value:.4g}"


def _load_modification_lines(scale_info, base_load_info, unit_mode, row) -> list[str]:
    area_func = UNIT_MAP["area"][unit_mode]["func"]
    area_unit = UNIT_MAP["area"][unit_mode]["unit"]
    power_func = UNIT_MAP["power"][unit_mode]["func"]
    power_unit = UNIT_MAP["power"][unit_mode]["unit"]

    lines = []
    if scale_info:
        lines.append(row("Scaled By:", scale_info.get("method") or "N/A"))
        lines.append(row("Heating Scale Factor:", f"{scale_info.get('heating_factor', 1.0):.3f}"))
        lines.append(row("Cooling Scale Factor:", f"{scale_info.get('cooling_factor', 1.0):.3f}"))
        if scale_info.get("orig_area_sqm") is not None:
            lines.append(
                row(
                    f"Original Floor Area [{area_unit}]:",
                    f"{area_func(scale_info['orig_area_sqm']):,.0f}",
                )
            )
        if scale_info.get("target_area_sqm") is not None:
            lines.append(
                row(
                    f"Target Floor Area [{area_unit}]:",
                    f"{area_func(scale_info['target_area_sqm']):,.0f}",
                )
            )
    else:
        lines.append(row("Scaling:", "None (original load profile)"))

    base_load_info = base_load_info or {}
    methods = {"floor": "Floor (minimum)", "offset": "Constant offset"}
    for load_type in ("heating", "cooling"):
        entry = base_load_info.get(load_type)
        label = f"{load_type.capitalize()} Base Load:"
        if not entry:
            lines.append(row(label, "None"))
            continue
        # Shown in the export's unit mode, not the one active when it was entered
        value = power_func(entry["value_W"])
        lines.append(
            row(
                label,
                f"{methods.get(entry.get('method'), entry.get('method'))}, "
                f"{value:,.1f} {power_unit}",
            )
        )
    return lines


def _section(title: str) -> str:
    bar = "━" * 50
    return f"\n{bar}\n  {title}\n{bar}\n"


def build_metadata_summary(
    metadata: Metadata,
    equipment_library: EquipmentLibrary,
    selected_eq_ids: list[str],
    selected_em_ids: list[str],
    unit_mode: str = "SI",
    scale_info: dict | None = None,
    base_load_info: dict | None = None,
) -> str:
    unit_mode = unit_mode or "SI"
    energy_func = UNIT_MAP["energy"][unit_mode]["func"]
    energy_unit = UNIT_MAP["energy"][unit_mode]["unit"]
    power_func = UNIT_MAP["power"][unit_mode]["func"]
    power_unit = UNIT_MAP["power"][unit_mode]["unit"]
    area_func = UNIT_MAP["area"][unit_mode]["func"]
    area_unit = UNIT_MAP["area"][unit_mode]["unit"]
    temp_func = UNIT_MAP["temperature"][unit_mode]["func"]
    temp_unit = UNIT_MAP["temperature"][unit_mode]["unit"]
    rate_func = UNIT_MAP["emissions_rate"][unit_mode]["func"]
    rate_unit = UNIT_MAP["emissions_rate"][unit_mode]["unit"]
    ng_rate_func = UNIT_MAP["gas_emission_factor"][unit_mode]["func"]
    ng_rate_unit = UNIT_MAP["gas_emission_factor"][unit_mode]["unit"]
    unit_label = "SI (metric)" if unit_mode == "SI" else "IP (imperial)"

    now = datetime.datetime.now().strftime("%Y-%m-%d  %H:%M:%S")
    lines = [
        "=== DECARB TOOL — ANALYSIS SETTINGS SUMMARY ===",
        f"Exported:    {now}",
        f"Units:       {unit_label}",
    ]

    def row(label, value):
        return f"  {label:<32}{value}"

    # ── Building & Load ────────────────────────────────────
    lines.append(_section("BUILDING & LOAD PROFILE"))
    ld = metadata.load_data

    lines.append(row("Building ID:", metadata.building_id or "N/A"))
    lines.append(row("Location:", metadata.location or "N/A"))
    lines.append(row("Building Type:", metadata.building_type or "N/A"))
    lines.append(row("Vintage:", str(metadata.vintage) if metadata.vintage else "N/A"))
    lines.append(row("Climate Zone (ASHRAE):", metadata.ashrae_climate_zone or "N/A"))

    if metadata.area_sqm is not None:
        lines.append(row(f"Floor Area [{area_unit}]:", f"{area_func(metadata.area_sqm):,.0f}"))
    else:
        lines.append(row("Floor Area:", "N/A"))

    lines.append(row("Load Source:", ld.load_type or "N/A"))
    lines.append(row("Load Reference:", ld.load_source_ref or "N/A"))
    lines.append("")

    if ld.hhw_annual_load is not None:
        lines.append(
            row(f"Annual Heating Load [{energy_unit}]:", f"{energy_func(ld.hhw_annual_load):,.0f}")
        )
    if ld.hhw_max_load is not None:
        lines.append(
            row(f"Peak Heating Load [{power_unit}]:", f"{power_func(ld.hhw_max_load):,.1f}")
        )
    if ld.chw_annual_load is not None:
        lines.append(
            row(f"Annual Cooling Load [{energy_unit}]:", f"{energy_func(ld.chw_annual_load):,.0f}")
        )
    if ld.chw_max_load is not None:
        lines.append(
            row(f"Peak Cooling Load [{power_unit}]:", f"{power_func(ld.chw_max_load):,.1f}")
        )
    if ld.heat_recovery_heating_fraction is not None:
        lines.append(row("Heat Recovery Fraction:", f"{ld.heat_recovery_heating_fraction:.2f}"))

    # ── Load Modifications ─────────────────────────────────
    lines.append(_section("LOAD MODIFICATIONS"))
    lines.extend(_load_modification_lines(scale_info, base_load_info, unit_mode, row))

    # ── Equipment Scenarios ────────────────────────────────
    lines.append(_section("EQUIPMENT SCENARIOS"))

    selected_eq_ids = list(selected_eq_ids) if selected_eq_ids else []
    # Order by selected_eq_ids (tracks Equipment-page column position), not
    # equipment_library.equipment_scenarios storage order - a scenario
    # copied by the column-dropdown swap is appended to the end of storage
    # order but belongs wherever its slot puts it in selected_eq_ids.
    eq_scen_by_id = {s.eq_scen_id: s for s in equipment_library.equipment_scenarios}
    selected_scenarios = [eq_scen_by_id[sid] for sid in selected_eq_ids if sid in eq_scen_by_id]

    if not selected_scenarios:
        lines.append("  No equipment scenarios selected.")
    else:
        for i, scen in enumerate(selected_scenarios, 1):
            lines.append(f"  [{i}] {scen.eq_scen_name}")

            if scen.hr_wwhp:
                lines.append("      Heat Recovery (WWHP):")
                lines.append(
                    f"        Model:         {_eq_display(scen.hr_wwhp, equipment_library)}"
                )
                lines.append(
                    f"        Capacity:      {_eq_capacity(scen.hr_wwhp, equipment_library, unit_mode)}"
                )
                lines.append(
                    f"        Performance:   {_perf_model_label(scen.hr_wwhp_performance_model)}"
                )
                if scen.hr_wwhp_h_supply_t is not None:
                    lines.append(
                        f"        Supply Temp:   {temp_func(scen.hr_wwhp_h_supply_t):.1f} {temp_unit}"
                    )

            if scen.awhp:
                lines.append("      Air-to-Water HP (AWHP):")
                lines.append(f"        Model:         {_eq_display(scen.awhp, equipment_library)}")
                lines.append(
                    f"        Capacity:      {_eq_capacity(scen.awhp, equipment_library, unit_mode)}"
                )
                lines.append(
                    f"        Performance:   {_perf_model_label(scen.awhp_performance_model)}"
                )
                if scen.awhp_h_supply_t is not None:
                    lines.append(
                        f"        Supply Temp:   {temp_func(scen.awhp_h_supply_t):.1f} {temp_unit}"
                    )
                lines.append(f"        Sizing Mode:   {_sizing_label(scen.awhp_sizing_mode)}")
                lines.append(
                    f"        Cooling:       {'Enabled' if scen.awhp_use_cooling else 'Disabled'}"
                )

            backup = (
                _eq_display(scen.backup_heating, equipment_library)
                if scen.backup_heating
                else "None"
            )
            chiller = _eq_display(scen.chiller, equipment_library) if scen.chiller else "None"
            lines.append(f"      Backup Heating:    {backup}")
            lines.append(f"      Chiller:           {chiller}")

            if i < len(selected_scenarios):
                lines.append("")

    # ── Emission Scenarios ─────────────────────────────────
    lines.append(_section("EMISSION SCENARIOS"))

    selected_em_ids = list(selected_em_ids) if selected_em_ids else []
    selected_em = [s for s in metadata.emission_settings if s.em_scen_id in selected_em_ids]

    if not selected_em:
        lines.append("  No emission scenarios selected.")
    else:
        for i, scen in enumerate(selected_em, 1):
            lines.append(f"  [{i}] {scen.em_scen_name}")
            lines.append(f"      Grid Scenario:     {scen.grid_scenario}")
            lines.append(f"      Grid Region:       {scen.gea_grid_region or 'N/A'}")
            lines.append(f"      Year:              {scen.year}")
            lines.append(f"      Emission Type:     {scen.emission_type}")
            lines.append(f"      Emission Source:   {scen.elec_emission_source}")
            if (
                scen.elec_emission_source == "Constant (User-provided)"
                and scen.elec_avg_emission_rate_gCO2e_per_kWh is not None
            ):
                lines.append(
                    "      Elec. Emission Rate: "
                    f"{_format_rate(rate_func(scen.elec_avg_emission_rate_gCO2e_per_kWh))}"
                    f" {rate_unit}"
                )
            lines.append(
                f"      Refrig. Leakage:   {scen.annual_refrig_leakage_percent:.2f} % / year"
            )
            lines.append(
                "      NG Emission Rate:  "
                f"{_format_rate(ng_rate_func(scen.ng_emission_rate_gCO2e_per_kWh))} {ng_rate_unit}"
            )

            if i < len(selected_em):
                lines.append("")

    lines.append("")
    return "\n".join(lines)


def build_settings_bundle(
    metadata: Metadata,
    equipment_library: EquipmentLibrary,
    selected_eq_ids: list[str],
    selected_em_ids: list[str],
) -> dict:
    return {
        "format_version": "1.0",
        "tool": "decarb-tool",
        "exported_at": datetime.datetime.now().isoformat(),
        "metadata": metadata.model_dump(),
        "equipment_library": equipment_library.model_dump(),
        "selected_equipment_scenario_ids": list(selected_eq_ids) if selected_eq_ids else [],
        "selected_emission_scenario_ids": list(selected_em_ids) if selected_em_ids else [],
    }
