import datetime

from src.equipment import EquipmentLibrary
from src.metadata import Metadata
from utils.units import UNIT_MAP


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


def _section(title: str) -> str:
    bar = "━" * 50
    return f"\n{bar}\n  {title}\n{bar}\n"


def build_metadata_summary(
    metadata: Metadata,
    equipment_library: EquipmentLibrary,
    selected_eq_ids: list[str],
    selected_em_ids: list[str],
    unit_mode: str = "SI",
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

    # ── Equipment Scenarios ────────────────────────────────
    lines.append(_section("EQUIPMENT SCENARIOS"))

    selected_eq_ids = list(selected_eq_ids) if selected_eq_ids else []
    selected_scenarios = [
        s for s in equipment_library.equipment_scenarios if s.eq_scen_id in selected_eq_ids
    ]

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
            lines.append(
                f"      SR/LR Weighting:   {scen.shortrun_weighting * 100:.0f} % short-run"
            )
            lines.append(
                f"      Refrig. Leakage:   {scen.annual_refrig_leakage_percent:.2f} % / year"
            )
            lines.append(
                f"      NG Emission Rate:  {scen.ng_emission_rate_gCO2e_per_kWh:.1f} g CO₂e / kWh"
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
