import contextlib
import json
from pathlib import Path

import dash
import dash_mantine_components as dmc
import pandas as pd
from dash import (
    ALL,
    Input,
    Output,
    State,
    callback,
    callback_context,
    dcc,
    html,
    no_update,
)
from dash_iconify import DashIconify

from layout.input import add_emission_modal, build_emissions_table, edit_emission_modal
from src.config import URLS, EmissionScenarioDefaults
from src.energy import loads_to_site_energy, site_to_source
from src.equipment import EquipmentLibrary
from src.loads import get_load_data
from src.metadata import Metadata
from utils.error_handling import (
    create_error_notification,
    create_success_notification,
    create_warning_notification,
)
from utils.logging_config import get_logger
from utils.tooltips import with_icon

logger = get_logger(__name__)


dash.register_page(__name__, name="Emissions", path=URLS.EMISSIONS.value, order=2)


def layout():
    return dmc.Container(
        [
            dcc.Store(id="active-emissions-tab"),
            dcc.Store(id="site-energy-store"),
            html.Div(id="source-energy-store"),
            html.Div(id="calc-status-toast"),
            dmc.Group(
                [
                    dmc.Stack(
                        [
                            with_icon(
                                text="Emissions",
                                order=5,
                                icon="basil:book-open-outline",
                                href="https://github.com/CenterForTheBuiltEnvironment/decarb-tool",
                            ),
                            dmc.Text(
                                "Specify and select emission scenarios to include in the analysis.",
                                size="sm",
                                c="dimmed",
                            ),
                        ],
                        gap=3,
                    ),
                    dmc.Group(
                        [
                            dmc.Button(
                                "Add",
                                id="button-add-emission",
                                variant="outline",
                            ),
                            dmc.Button(
                                "Reset",
                                id="button-reset-emission",
                                variant="outline",
                                color="gray",
                                disabled=True,  # <- disabled for now
                            ),
                        ],
                    ),
                ],
                justify="space-between",
                mt="md",
                mb="sm",
            ),
            dmc.Paper(
                [
                    dmc.Group(
                        [
                            dmc.Group(
                                [
                                    dmc.Text("Scenario Group:", size="sm", fw=500),
                                    dmc.Select(
                                        id="emission-scenario-group-select",
                                        data=[
                                            {"label": "Year (2025, 2035, 2045)", "value": "year"},
                                            {
                                                "label": "Refrigerant leakage (1%, 5%, 10%)",
                                                "value": "refrigerant_leakage",
                                            },
                                            {
                                                "label": "Combustion vs pre-combustion",
                                                "value": "emission_types",
                                            },
                                        ],
                                        value=None,
                                        placeholder="Select a scenario group",
                                        size="sm",
                                        style={"width": "280px"},
                                        clearable=True,
                                        comboboxProps={"withinPortal": True, "zIndex": 1000},
                                    ),
                                ],
                                gap="sm",
                            ),
                            dmc.Group(
                                [
                                    dmc.Text("View:", size="sm", fw=500),
                                    dmc.SegmentedControl(
                                        id="emissions-view-mode",
                                        data=[
                                            {"label": "Simple", "value": "simple"},
                                            {"label": "Advanced", "value": "advanced"},
                                            {"label": "Differences", "value": "differences"},
                                        ],
                                        value="simple",
                                        size="sm",
                                    ),
                                ],
                                gap="sm",
                            ),
                        ],
                        justify="space-between",
                        mb="md",
                    ),
                    html.Div(
                        id="emissions-table",
                        style={
                            "marginTop": "16px",
                        },
                    ),
                ],
                withBorder=False,
                shadow="xs",
                radius="md",
                p="md",
            ),
            dmc.Group(
                [
                    dmc.Button(
                        [
                            "Calculate Source Emissions",
                            DashIconify(
                                icon="ic:baseline-autorenew",
                                width=20,
                                style={"marginLeft": 8},
                            ),
                        ],
                        id="button-calculate",
                        variant="filled",
                        color="blue",
                    ),
                ],
                justify="flex-end",
                mt="md",
                mb="md",
            ),
            add_emission_modal(),
            edit_emission_modal(),
        ],
        fluid=True,
    )


@callback(
    Output("emissions-table", "children"),
    Input("metadata-store", "data"),
    Input("selected-emissions-store", "data"),
    Input("emissions-view-mode", "value"),
    Input("unit-toggle", "value"),
)
def update_emissions_table(metadata_data, selected_emissions, view_mode, unit_mode):
    if not metadata_data:
        return dmc.Text("No emission scenarios defined yet.")

    metadata = Metadata(**metadata_data)

    if not metadata.emission_settings:
        return dmc.Text("No emission scenarios defined yet.")

    scenarios = [s.model_dump() for s in metadata.emission_settings]
    active_ids = selected_emissions or []

    return build_emissions_table(
        scenarios,
        active_ids=active_ids,
        view_mode=view_mode or "simple",
        unit_mode=unit_mode or "SI",
    )


@callback(
    Output("selected-emissions-store", "data"),
    Output("emissions-checkbox-group", "value"),
    Input("emissions-checkbox-group", "value"),
    prevent_initial_call=True,
)
def sync_active_emissions(selected_values):
    """
    Keep selected-emissions-store in sync with the CheckboxGroup.
    For now, no cap on number of active emission scenarios.
    """
    selected = selected_values or []
    return selected, selected


@callback(
    Output("metadata-store", "data", allow_duplicate=True),
    Output("selected-emissions-store", "data", allow_duplicate=True),
    Output("emission-scenario-group-store", "data", allow_duplicate=True),
    Input("emission-scenario-group-select", "value"),
    State("metadata-store", "data"),
    State("selected-emissions-store", "data"),
    State("emission-scenario-group-store", "data"),
    prevent_initial_call=True,
)
def handle_emission_group_selection(group_id, metadata_data, selected_ids, stored_group):
    """
    When an emission scenario group is selected, modify the displayed scenarios.
    Also persists the selection to the store for restoration on page navigation.
    Skips reapplying settings if this is just a restore (group unchanged).

    The selected group parameter varies across scenarios, while all other
    parameters are reset to their defaults.

    Groups:
    - year: Varies years (2025, 2035, 2045), others reset to defaults
    - refrigerant_leakage: Varies leakage (0.01, 0.05, 0.1), others reset to defaults
    - emission_types: Varies emission type ("Includes pre-combustion" vs "Combustion only"), others reset to defaults
    """
    # When dropdown is cleared, clear the stored group to allow re-selecting
    if not group_id:
        if stored_group is not None:
            return no_update, no_update, None
        return no_update, no_update, no_update

    if not metadata_data:
        return no_update, no_update, no_update

    # Skip if this is just restoring the same group (don't overwrite manual edits)
    if group_id == stored_group:
        return no_update, no_update, no_update

    if "emission_settings" not in metadata_data:
        return no_update, no_update, no_update

    existing_scenarios = list(metadata_data["emission_settings"])

    default_ids = ["em_scenario_a", "em_scenario_b"]
    if group_id != "emission_types": # only two scenarios for comparing emission types
        default_ids.append("em_scenario_c")

    # Get defaults
    default_year = EmissionScenarioDefaults.YEAR.value
    default_leakage = EmissionScenarioDefaults.REFRIGERANT_LEAKAGE.value
    default_emission_type = EmissionScenarioDefaults.EMISSION_TYPE.value
    default_ng_leakage = EmissionScenarioDefaults.NG_LEAKAGE_G_KWH.value

    # Define the variation values and default IDs
    year_values = [2025, 2035, 2045]
    leakage_values = [0.01, 0.05, 0.1]
    emission_types = ["Combustion only", "Includes pre-combustion"]
    ng_leakage_values = [EmissionScenarioDefaults.NG_LEAKAGE_G_KWH_COMBUSTION.value, default_ng_leakage]

    # Create base scenario template from first existing scenario or defaults
    base_scenario = (
        existing_scenarios[0].copy()
        if existing_scenarios
        else {
            "grid_scenario": "MidCase",
            "gea_grid_region": None,
            "time_zone": "America/Los_Angeles",
            "emission_type": default_emission_type,
            "shortrun_weighting": 0,
            "annual_refrig_leakage_percent": default_leakage,
            "annual_ng_leakage_g_per_kWh": default_ng_leakage,
            "year": default_year,
        }
    )

    # Reset to default 2/3 scenarios (a, b, optionally c) with group-specific values
    updated_scenarios = []
    for idx, scen_id in enumerate(default_ids):
        scen = {**base_scenario, "em_scen_id": scen_id}

        if group_id == "year":
            # Vary year, reset others to defaults
            scen["year"] = year_values[idx % len(year_values)]
            scen["annual_refrig_leakage_percent"] = default_leakage
            scen["emission_type"] = default_emission_type
            scen["annual_ng_leakage_g_per_kWh"] = default_ng_leakage
        elif group_id == "refrigerant_leakage":
            # Vary leakage, reset others to defaults
            scen["annual_refrig_leakage_percent"] = leakage_values[idx % len(leakage_values)]
            scen["year"] = default_year
            scen["emission_type"] = default_emission_type
            scen["annual_ng_leakage_g_per_kWh"] = default_ng_leakage
        elif group_id == "emission_types":
            # Set emission type, reset others to defaults
            scen["emission_type"] = emission_types[idx % len(emission_types)]
            scen["annual_ng_leakage_g_per_kWh"] = ng_leakage_values[idx % len(ng_leakage_values)]
            scen["year"] = default_year
            scen["annual_refrig_leakage_percent"] = default_leakage
        
        updated_scenarios.append(scen)

    logger.info(
        "Reset emission scenarios to defaults for group '%s': %s",
        group_id,
        default_ids,
    )

    # Update metadata
    updated_metadata = metadata_data.copy()
    updated_metadata["emission_settings"] = updated_scenarios

    # Update selected_ids to the default scenario IDs
    return updated_metadata, default_ids, group_id


@callback(
    Output("emission-scenario-group-select", "value"),
    Input("url", "pathname"),
    State("emission-scenario-group-store", "data"),
)
def restore_emission_group_selection(pathname, stored_group):
    """Restore the scenario group selection when navigating back to the page."""
    if pathname != URLS.EMISSIONS.value:
        return no_update
    return stored_group


def _build_emission_base_options(metadata_json):
    """
    Build options for 'Base scenario' select in Add modal.
    """
    if not metadata_json or "emission_settings" not in metadata_json:
        return []

    return [
        {
            "label": s.get("em_scen_id", f"scenario_{i}"),
            "value": s.get("em_scen_id"),
        }
        for i, s in enumerate(metadata_json["emission_settings"])
        if s.get("em_scen_id")
    ]


def _next_emission_scen_id(metadata_json):
    """
    Generate next em_scen_id like em_scenario_4, em_scenario_5, ...
    """
    if not metadata_json or "emission_settings" not in metadata_json:
        return "em_scenario_1"

    nums = []
    for scen in metadata_json["emission_settings"]:
        sid = scen.get("em_scen_id", "")
        if isinstance(sid, str) and sid.startswith("em_scenario_"):
            with contextlib.suppress(ValueError):
                nums.append(int(sid.split("_")[-1]))
    n = max(nums) + 1 if nums else 1
    return f"em_scenario_{n}"


@callback(
    Output("emissions-add-modal", "opened"),
    Output("add-em-base-scenario-select", "data"),
    Output("add-em-scenario-id-input", "value"),
    Output("add-em-scenario-error", "children"),
    Input("button-add-emission", "n_clicks"),
    Input("add-em-scenario-cancel-btn", "n_clicks"),
    Input("add-em-scenario-save-btn", "n_clicks"),
    State("metadata-store", "data"),
)
def emissions_add_modal(add_clicks, cancel_clicks, save_clicks, metadata_data):
    ctx = callback_context

    base_options = _build_emission_base_options(metadata_data)

    # initial load
    if not ctx.triggered:
        return False, base_options, "", ""

    trigger_id = ctx.triggered[0]["prop_id"].split(".")[0]

    # Open modal
    if trigger_id == "button-add-emission":
        auto_id = _next_emission_scen_id(metadata_data)
        return True, base_options, auto_id, ""

    # Cancel -> close
    if trigger_id == "add-em-scenario-cancel-btn":
        return False, base_options, "", ""

    # Save -> close (store update in separate callback)
    if trigger_id == "add-em-scenario-save-btn":
        return False, base_options, "", ""

    return no_update, no_update, no_update, no_update


@callback(
    Output("metadata-store", "data", allow_duplicate=True),
    Output("selected-emissions-store", "data", allow_duplicate=True),
    Output("emission-scenario-group-store", "data", allow_duplicate=True),
    Input("add-em-scenario-save-btn", "n_clicks"),
    State("metadata-store", "data"),
    State("selected-emissions-store", "data"),
    State("add-em-base-scenario-select", "value"),
    State("add-em-scenario-id-input", "value"),
    prevent_initial_call=True,
)
def add_emission_scenario_to_metadata(
    save_clicks,
    metadata_data,
    selected_ids,
    base_id,
    new_id,
):
    if not save_clicks:
        return no_update, no_update, no_update

    if not metadata_data or "emission_settings" not in metadata_data:
        return no_update, no_update, no_update

    scenarios = metadata_data.get("emission_settings", [])
    if not base_id:
        # could also push error into add-em-scenario-error
        return no_update, no_update, no_update

    if not new_id or not new_id.strip():
        new_id = _next_emission_scen_id(metadata_data)
    new_id = new_id.strip()

    existing_ids = {s.get("em_scen_id") for s in scenarios}
    if new_id in existing_ids:
        # ID already exists; might set error text instead
        return no_update, no_update, no_update

    base_scen = next(
        (s for s in scenarios if s.get("em_scen_id") == base_id),
        None,
    )
    if base_scen is None:
        return no_update, no_update, no_update

    new_scenario = {**base_scen, "em_scen_id": new_id}
    new_scenarios = [*scenarios, new_scenario]

    updated_metadata = {
        **metadata_data,
        "emission_settings": new_scenarios,
    }

    # Add the new scenario to selected IDs so it appears in the table
    updated_selected = [*(selected_ids or []), new_id]

    logger.info("Added new emission scenario: %s (based on %s)", new_id, base_id)

    # Clear scenario group store to allow re-selecting the same group
    return updated_metadata, updated_selected, None


@callback(
    Output("metadata-store", "data", allow_duplicate=True),
    Output("selected-emissions-store", "data", allow_duplicate=True),
    Output("emission-scenario-group-store", "data", allow_duplicate=True),
    Input({"type": "emission-remove-btn", "em_scen_id": ALL}, "n_clicks"),
    State("metadata-store", "data"),
    State("selected-emissions-store", "data"),
    prevent_initial_call=True,
)
def remove_emission_scenario(remove_clicks, metadata_data, selected_em_ids):
    """
    Remove emission scenario and clear group store to allow re-selecting same group.
    """
    if not any(remove_clicks or []):
        return no_update, no_update, no_update

    if not metadata_data or "emission_settings" not in metadata_data:
        return no_update, no_update, no_update

    triggered = callback_context.triggered
    if not triggered:
        return no_update, no_update, no_update

    prop_id = triggered[0]["prop_id"]
    id_str = prop_id.split(".")[0]

    try:
        btn_id = json.loads(id_str)
    except json.JSONDecodeError:
        return no_update, no_update, no_update

    em_scen_id = btn_id.get("em_scen_id")
    if not em_scen_id:
        return no_update, no_update, no_update

    scenarios = metadata_data.get("emission_settings", [])
    new_scenarios = [s for s in scenarios if s.get("em_scen_id") != em_scen_id]

    if len(new_scenarios) == len(scenarios):
        return no_update, no_update, no_update

    updated_metadata = metadata_data.copy()
    updated_metadata["emission_settings"] = new_scenarios

    selected_em_ids = selected_em_ids or []
    new_selected = [sid for sid in selected_em_ids if sid != em_scen_id]

    logger.info("Removed emission scenario '%s'", em_scen_id)

    # Clear scenario group store to allow re-selecting the same group
    return updated_metadata, new_selected, None


@callback(
    Output("emissions-edit-modal", "opened"),
    Output("edit-em-scenario-id-input", "value"),
    Output("edit-em-grid-scenario", "value"),
    Output("edit-em-gea-grid-region", "value"),
    Output("edit-em-time-zone", "value"),
    Output("edit-em-emission-type", "value"),
    Output("edit-em-shortrun-weighting", "value"),
    Output("edit-em-year", "value"),
    Output("edit-em-refrig-leakage", "value"),
    Output("edit-em-ng-leakage", "value"),
    Output("edit-em-scenario-error", "children"),
    Input({"type": "emission-edit-btn", "em_scen_id": ALL}, "n_clicks"),
    State("metadata-store", "data"),
    State("unit-toggle", "value"),
    prevent_initial_call=True,
)
def open_edit_emission_modal(edit_clicks, metadata_data, unit_mode):
    if not any(edit_clicks or []):
        return (no_update,) * 11

    if not metadata_data or "emission_settings" not in metadata_data:
        return (
            False,
            "",
            "",
            "",
            "",
            "",
            None,
            None,
            None,
            None,
            "No emission data.",
        )

    scenarios = metadata_data.get("emission_settings", [])

    triggered = callback_context.triggered
    if not triggered:
        return (no_update,) * 11

    prop_id = triggered[0]["prop_id"]
    id_str = prop_id.split(".")[0]

    try:
        btn_id = json.loads(id_str)
    except json.JSONDecodeError:
        return (
            False,
            "",
            "",
            "",
            "",
            "",
            None,
            None,
            None,
            None,
            "Failed to parse button id.",
        )

    em_scen_id = btn_id.get("em_scen_id")
    scen = next((s for s in scenarios if s.get("em_scen_id") == em_scen_id), None)

    if scen is None:
        return (
            False,
            "",
            "",
            "",
            "",
            "",
            None,
            None,
            None,
            None,
            f"Scenario {em_scen_id!r} not found.",
        )

    # Convert NG leakage for display based on unit mode
    ng_leakage_base = scen.get("annual_ng_leakage_g_per_kWh")
    if ng_leakage_base is not None and unit_mode == "IP":
        from utils.units import get_unit_converter

        ng_converter = get_unit_converter("ng_leakage_rate", "IP")
        ng_leakage_display = ng_converter(float(ng_leakage_base))
    else:
        ng_leakage_display = ng_leakage_base

    # Round refrigerant leakage to 2 decimal places for display
    refrig_leakage = scen.get("annual_refrig_leakage_percent")
    if refrig_leakage is not None:
        refrig_leakage = round(float(refrig_leakage), 2)

    # Round NG leakage display to 2 decimal places
    if ng_leakage_display is not None:
        ng_leakage_display = round(float(ng_leakage_display), 2)

    return (
        True,
        scen.get("em_scen_id"),
        scen.get("grid_scenario", ""),
        scen.get("gea_grid_region", ""),
        scen.get("time_zone", ""),
        scen.get("emission_type", ""),
        scen.get("shortrun_weighting"),
        str(scen.get("year")) if scen.get("year") is not None else "",
        refrig_leakage,
        ng_leakage_display,
        "",
    )


@callback(
    Output("emissions-edit-modal", "opened", allow_duplicate=True),
    Output("metadata-store", "data", allow_duplicate=True),
    Output("edit-em-scenario-error", "children", allow_duplicate=True),
    Input("edit-em-scenario-save-btn", "n_clicks"),
    State("edit-em-scenario-id-input", "value"),
    State("edit-em-grid-scenario", "value"),
    State("edit-em-gea-grid-region", "value"),
    State("edit-em-time-zone", "value"),
    State("edit-em-emission-type", "value"),
    State("edit-em-shortrun-weighting", "value"),
    State("edit-em-year", "value"),
    State("edit-em-refrig-leakage", "value"),
    State("edit-em-ng-leakage", "value"),
    State("metadata-store", "data"),
    State("unit-toggle", "value"),
    prevent_initial_call=True,
)
def save_edit_emission(
    n_clicks,
    scen_id,
    grid_scenario,
    gea_grid_region,
    time_zone,
    emission_type,
    shortrun_weighting,
    year,
    refrig_leakage,
    ng_leakage,
    metadata_data,
    unit_mode,
):
    if not n_clicks:
        return no_update, no_update, no_update

    if not metadata_data or "emission_settings" not in metadata_data:
        return False, no_update, "No emission data to edit."

    if not scen_id:
        return True, no_update, "Scenario ID is missing."

    # basic type cleaning
    try:
        shortrun_weighting = float(shortrun_weighting) if shortrun_weighting is not None else 0.0
    except (TypeError, ValueError):
        shortrun_weighting = 0.0

    try:
        year = int(year) if year is not None and year != "" else 2025
    except (TypeError, ValueError):
        year = 2025

    try:
        refrig_leakage = float(refrig_leakage) if refrig_leakage is not None else 0.0
    except (TypeError, ValueError):
        refrig_leakage = 0.0

    try:
        ng_leakage = float(ng_leakage) if ng_leakage is not None else 0.0
    except (TypeError, ValueError):
        ng_leakage = 0.0

    # Convert NG leakage back to base units (g/kWh) if in IP mode
    unit_mode = unit_mode or "SI"
    if unit_mode == "IP" and ng_leakage > 0:
        from utils.units import Wh_to_BTU, g_to_lb

        # IP unit is lb/kBTU, convert back to g/kWh
        # g/kWh = (lb/kBTU) / (g_to_lb / Wh_to_BTU)
        ng_leakage = ng_leakage / (g_to_lb / Wh_to_BTU)

    scenarios = metadata_data.get("emission_settings", [])
    updated = False
    new_scenarios = []

    for scen in scenarios:
        if scen.get("em_scen_id") == scen_id:
            new_scen = scen.copy()
            new_scen["grid_scenario"] = grid_scenario
            new_scen["gea_grid_region"] = gea_grid_region
            new_scen["time_zone"] = time_zone
            new_scen["emission_type"] = emission_type
            new_scen["shortrun_weighting"] = shortrun_weighting
            new_scen["year"] = year
            new_scen["annual_refrig_leakage_percent"] = refrig_leakage
            new_scen["annual_ng_leakage_g_per_kWh"] = ng_leakage
            new_scenarios.append(new_scen)
            updated = True
        else:
            new_scenarios.append(scen)

    if not updated:
        return True, no_update, f"Scenario {scen_id!r} not found."

    updated_metadata = metadata_data.copy()
    updated_metadata["emission_settings"] = new_scenarios

    return False, updated_metadata, ""


@callback(
    Output("emissions-edit-modal", "opened", allow_duplicate=True),
    Input("edit-em-scenario-cancel-btn", "n_clicks"),
    prevent_initial_call=True,
)
def cancel_edit_emission_modal(n_clicks):
    if not n_clicks:
        return no_update
    return False


@callback(
    Output("edit-em-ng-leakage-label", "children"),
    Input("unit-toggle", "value"),
)
def update_ng_leakage_label(unit_mode):
    """Update NG leakage label based on unit mode."""
    from utils.units import get_unit_label

    unit_mode = unit_mode or "SI"
    ng_unit = get_unit_label("ng_leakage_rate", unit_mode)
    return f"Annual NG leakage ({ng_unit})"


@callback(
    Output("site-energy-store", "data"),
    Output("notification-container", "sendNotifications", allow_duplicate=True),
    Input("button-calculate", "n_clicks"),
    State("metadata-store", "data"),
    State("equipment-store", "data"),
    State("selected-equipment-store", "data"),
    State("session-store", "data"),
    prevent_initial_call=True,
)
def run_loads_to_site(
    n_clicks,
    metadata_json,
    equipment_json,
    selected_scenarios,
    session_data,
):
    # --- Guard clauses (no notification needed, just prevent update) ---
    if not n_clicks:
        raise dash.exceptions.PreventUpdate

    # --- Validation with user feedback ---
    if not metadata_json:
        logger.warning("Calculation attempted without load selection")
        notification = create_warning_notification(
            "Missing Selection", "Please select a load dataset on the Loads page first."
        )
        return no_update, [notification]

    if not equipment_json:
        logger.warning("Calculation attempted without equipment data")
        notification = create_error_notification(
            "Missing Data",
            "No equipment library data available. Please refresh the page.",
        )
        return no_update, [notification]

    if not selected_scenarios:
        logger.warning("Calculation attempted without equipment scenarios")
        notification = create_warning_notification(
            "No Scenarios Selected", "Please select at least one equipment scenario."
        )
        return no_update, [notification]

    # --- Main calculation with error handling ---
    try:
        logger.info(
            f"Starting site energy calculation for following eq scenarios {selected_scenarios}"
        )

        folder = Path(f"/tmp/{session_data['session_id']}")
        folder.mkdir(parents=True, exist_ok=True)

        metadata = Metadata(**metadata_json)
        equipment = EquipmentLibrary(**equipment_json)

        load_data = get_load_data(metadata)

        site_energy = loads_to_site_energy(
            load_data,
            equipment,
            scenario_ids=selected_scenarios,
            detail=True,
        )

        site_path = folder / "site_energy.pkl"
        site_energy.to_pickle(site_path)
        logger.info(f"Saved site energy to: {site_path}")

        return str(site_path), no_update

    except ValueError as e:
        logger.error(f"Calculation validation error: {e}")
        notification = create_error_notification(
            "Calculation Error",
            str(e),  # ValueError messages from energy.py
        )
        return no_update, [notification]

    except FileNotFoundError as e:
        logger.error(f"Load data file not found: {e}")
        notification = create_error_notification(
            "Data Not Found",
            "Could not find load data for this building. Please re-select on Loads page.",
        )
        return no_update, [notification]

    except Exception as e:
        logger.exception(f"Unexpected calculation error: {e}")
        notification = create_error_notification(
            "Unexpected Error",
            "Calculation failed. Please make sure have a selected a load dataset and at least one equipment and emission scenario.",
        )
        return no_update, [notification]


@callback(
    Output("source-energy-store", "children"),
    Output("notification-container", "sendNotifications", allow_duplicate=True),
    Input("site-energy-store", "data"),
    State("metadata-store", "data"),
    State("selected-emissions-store", "data"),
    State("session-store", "data"),
    prevent_initial_call=True,
)
def run_site_to_source(site_energy_path, metadata_json, selected_emission_ids, session_data):
    if not site_energy_path:
        raise dash.exceptions.PreventUpdate

    if not selected_emission_ids:
        notification = create_warning_notification(
            "No Emission Scenarios", "Please select at least one emission scenario."
        )
        return no_update, [notification]

    try:
        logger.info(
            f"Converting from site energy to source emissions for following em_scenarios: {selected_emission_ids}"
        )

        folder = Path(f"/tmp/{session_data['session_id']}")
        folder.mkdir(parents=True, exist_ok=True)

        site_energy = pd.read_pickle(site_energy_path)
        metadata = Metadata(**metadata_json)

        # filter emission scenarios
        selected_emission_ids = selected_emission_ids or []
        if selected_emission_ids:
            metadata.emission_settings = [
                scen
                for scen in metadata.emission_settings
                if scen.em_scen_id in selected_emission_ids
            ]

        source_energy = site_to_source(site_energy, metadata=metadata)

        source_path = folder / "source_energy.pkl"
        source_energy.to_pickle(source_path)

        logger.info(f"Saved source energy to: {source_path}")

        success = create_success_notification(
            "Calculation Complete",
            "Source emissions calculation finished successfully.",
        )

        return dcc.Store(id="source-energy-store", data=str(source_path)), [success]

    except ValueError as e:
        logger.error(f"Emissions calculation error: {e}")
        notification = create_error_notification("Calculation Error", str(e))
        return no_update, [notification]

    except Exception as e:
        logger.exception(f"Unexpected emissions error: {e}")
        notification = create_error_notification(
            "Unexpected Error", "Emissions calculation failed."
        )
        return no_update, [notification]

@callback(
    Output("edit-em-ng-leakage", "value", allow_duplicate=True),
    Input("edit-em-emission-type", "value"),
    State("unit-toggle", "value"),
    prevent_initial_call=True,
)
def update_ng_leakage_on_emission_type_change(emission_type, unit_mode):
    """Update NG leakage when emission type changes."""
    from utils.units import format_value
    unit_mode = unit_mode or "SI"

    if emission_type == "Combustion only":
        ng_leakage = EmissionScenarioDefaults.NG_LEAKAGE_G_KWH_COMBUSTION.value
    elif emission_type == "Includes pre-combustion":
        ng_leakage = EmissionScenarioDefaults.NG_LEAKAGE_G_KWH.value

    if unit_mode == "IP":
        ng_leakage = format_value(ng_leakage, "annual_ng_leakage_g_per_kWh", unit_mode, decimals=2)

    return ng_leakage