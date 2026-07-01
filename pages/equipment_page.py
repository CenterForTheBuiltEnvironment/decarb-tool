import contextlib
import json

import dash
import dash_mantine_components as dmc
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

from layout.input import (
    add_equipment_modal,
    build_equipment_table,
    edit_equipment_modal,
)
from src.config import URLS
from utils.logging_config import get_logger
from utils.tooltips import with_icon, with_tooltip

logger = get_logger(__name__)


dash.register_page(
    __name__,
    name="Equipment",
    path=URLS.EQUIPMENT.value,
    order=1,
)


def layout():
    return dmc.Container(
        [
            dcc.Store(id="active-equipment-tab"),
            dmc.Group(
                [
                    dmc.Stack(
                        [
                            with_icon(
                                text="Equipment",
                                order=5,
                                icon="basil:book-open-outline",
                                href="https://github.com/CenterForTheBuiltEnvironment/decarb-tool",
                            ),
                            dmc.Text(
                                "Specify and select equipment scenarios to include in the analysis.",
                                size="sm",
                                c="dimmed",
                            ),
                        ],
                        gap=3,
                    ),
                    dmc.Group(
                        [
                            with_tooltip(
                                dmc.Button(
                                    "Add",
                                    id="button-add-equipment",
                                    variant="outline",
                                ),
                                "equipment.add_eq_scenario",
                            ),
                            with_tooltip(
                                dmc.Button(
                                    "Reset",
                                    id="button-reset-equipment",
                                    variant="outline",
                                    color="gray",
                                ),
                                "equipment.reset_eq_scenario",
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
                                        id="scenario-group-select",
                                        data=[],  # Will be populated by callback
                                        value=None,
                                        placeholder="Select a scenario group",
                                        size="sm",
                                        style={"width": "250px"},
                                        allowDeselect=True,
                                        comboboxProps={"withinPortal": True, "zIndex": 1000},
                                    ),
                                ],
                                gap="sm",
                            ),
                            dmc.Group(
                                [
                                    dmc.Text("View:", size="sm", fw=500),
                                    dmc.SegmentedControl(
                                        id="equipment-view-mode",
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
                        id="equipment-table",
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
            dmc.Space(h=20),
            dcc.Link(
                [
                    dmc.Button(
                        "Specify Emissions ",
                        rightSection=DashIconify(icon="tabler:arrow-narrow-right-dashed"),
                        variant="filled",
                        color="blue",
                        id="button-specify-emissions",
                        n_clicks=0,
                        style={"float": "right"},
                    ),
                ],
                href="/emissions",
            ),
            add_equipment_modal(),
            edit_equipment_modal(),
        ],
        fluid=True,
    )


# ---------------------------------------- Callbacks ----------------------------------------

# 1. Populate equipment table from equipment-store


@callback(
    Output("equipment-table", "children"),
    Input("url", "pathname"),
    Input("equipment-store", "data"),
    Input("selected-equipment-store", "data"),
    Input("displayed-equipment-store", "data"),
    Input("equipment-view-mode", "value"),
    Input("unit-toggle", "value"),
)
def update_equipment_table(
    pathname,
    equipment_store_data,
    selected_equipment_data,
    displayed_equipment_data,
    view_mode,
    unit_mode,
):
    if pathname != URLS.EQUIPMENT.value:
        return no_update

    if not equipment_store_data:
        return dmc.Text("No equipment scenarios defined yet.")

    scenarios = equipment_store_data.get("equipment_scenarios", [])
    if not scenarios:
        return dmc.Text("No equipment scenarios defined yet.")

    selected_ids = selected_equipment_data or []
    displayed_ids = displayed_equipment_data or []

    return build_equipment_table(
        scenarios,
        displayed_ids=displayed_ids,
        active_ids=selected_ids,
        view_mode=view_mode or "simple",
        unit_mode=unit_mode or "SI",
    )


@callback(
    Output("scenario-group-select", "data"),
    Input("url", "pathname"),
    Input("equipment-store", "data"),
)
def populate_group_dropdown(pathname, equipment_data):
    """Populate the scenario group dropdown with available groups."""
    if pathname != URLS.EQUIPMENT.value:
        return no_update

    if not equipment_data:
        return []

    groups = equipment_data.get("scenario_groups", [])
    return [
        {"label": g.get("group_name", g.get("group_id")), "value": g.get("group_id")}
        for g in groups
    ]


@callback(
    Output("displayed-equipment-store", "data", allow_duplicate=True),
    Output("selected-equipment-store", "data", allow_duplicate=True),
    Output("equipment-checkbox-group", "value", allow_duplicate=True),
    Output("equipment-scenario-group-store", "data", allow_duplicate=True),
    Output("equipment-store", "data", allow_duplicate=True),
    Input("scenario-group-select", "value"),
    State("equipment-store", "data"),
    State("equipment-initial-store", "data"),
    State("equipment-scenario-group-store", "data"),
    prevent_initial_call=True,
)
def handle_group_selection(group_id, equipment_data, initial_data, stored_group):
    """
    When a scenario group is selected, update displayed and selected scenarios.
    Also persists the selection to the store for restoration on page navigation.
    Skips reapplying settings if this is just a restore (group unchanged).
    Resets all scenarios in the group to their initial/default values.
    """
    # When dropdown is cleared, clear the stored group to allow re-selecting
    if not group_id:
        if stored_group is not None:
            return no_update, no_update, no_update, None, no_update
        return no_update, no_update, no_update, no_update, no_update

    if not equipment_data:
        return no_update, no_update, no_update, no_update, no_update

    # Skip if this is just restoring the same group (don't overwrite manual edits)
    if group_id == stored_group:
        return no_update, no_update, no_update, no_update, no_update

    groups = equipment_data.get("scenario_groups", [])
    selected_group = next((g for g in groups if g.get("group_id") == group_id), None)

    if not selected_group:
        return no_update, no_update, no_update, no_update, no_update

    scenario_ids = selected_group.get("scenario_ids", [])
    scenario_ids_set = set(scenario_ids)

    # Reset scenarios in the group to their initial/default values
    current_scenarios = equipment_data.get("equipment_scenarios", [])
    initial_scenarios = initial_data.get("equipment_scenarios", []) if initial_data else []

    # Build a map of initial scenarios for quick lookup
    initial_map = {s.get("eq_scen_id"): s for s in initial_scenarios}

    # Keep scenarios not in the group as-is, reset group scenarios to initial values
    updated_scenarios = []
    restored_ids = []

    # First, keep all scenarios not in the group
    for scen in current_scenarios:
        if scen.get("eq_scen_id") not in scenario_ids_set:
            updated_scenarios.append(scen)

    # Then add/restore all scenarios from the group using initial values
    for scen_id in scenario_ids:
        if scen_id in initial_map:
            updated_scenarios.append(initial_map[scen_id])
            restored_ids.append(scen_id)

    if restored_ids:
        logger.info(
            "Reset %d scenarios to initial values for group '%s': %s",
            len(restored_ids),
            group_id,
            restored_ids,
        )

    updated_equipment = {
        **equipment_data,
        "equipment_scenarios": updated_scenarios,
    }

    # Update displayed, selected, checkbox group, persist group selection, and equipment store
    return scenario_ids, scenario_ids, scenario_ids, group_id, updated_equipment


@callback(
    Output("scenario-group-select", "value"),
    Input("url", "pathname"),
    State("equipment-scenario-group-store", "data"),
)
def restore_equipment_group_selection(pathname, stored_group):
    """Restore the scenario group selection when navigating back to the page."""
    if pathname != URLS.EQUIPMENT.value:
        return no_update
    return stored_group


# 2. Add equipment scenario modal + store update


# helpers to dynamically build options and next scenario id
def _build_base_options(equip_json):
    if not equip_json or "equipment_scenarios" not in equip_json:
        return []
    return [
        {
            "label": f"{s.get('eq_scen_name', s.get('eq_scen_id'))} ({s.get('eq_scen_id')})",
            "value": s.get("eq_scen_id"),
        }
        for s in equip_json["equipment_scenarios"]
        if s.get("eq_scen_id")
    ]


def _next_scenario_id(equip_json):
    if not equip_json or "equipment_scenarios" not in equip_json:
        return "eq_scenario_1"
    nums = []
    for scen in equip_json["equipment_scenarios"]:
        sid = scen.get("eq_scen_id", "")
        if isinstance(sid, str) and sid.startswith("eq_scenario_"):
            with contextlib.suppress(ValueError):
                nums.append(int(sid.split("_")[-1]))
    n = max(nums) + 1 if nums else 1
    return f"eq_scenario_{n}"


@callback(
    Output("equipment-add-modal", "opened"),
    Output("add-base-scenario-select", "data"),
    Output("add-base-scenario-select", "value"),
    Output("add-scenario-id-input", "value"),
    Output("add-scenario-name-input", "value"),
    Output("add-scenario-error", "children"),
    Input("button-add-equipment", "n_clicks"),
    Input("add-scenario-cancel-btn", "n_clicks"),
    Input("add-scenario-save-btn", "n_clicks"),
    State("equipment-store", "data"),
)
def equipment_add_modal(add_clicks, cancel_clicks, save_clicks, equipment_data):
    ctx = callback_context

    base_options = _build_base_options(equipment_data)
    # Set first scenario as default base selection
    default_base = base_options[0]["value"] if base_options else None

    # Initial page load
    if not ctx.triggered:
        return False, base_options, None, "", "", ""

    trigger_id = ctx.triggered[0]["prop_id"].split(".")[0]

    # --- Open modal ---
    if trigger_id == "button-add-equipment":
        auto_id = _next_scenario_id(equipment_data)
        return True, base_options, default_base, auto_id, "", ""

    # --- Cancel -> close modal ---
    if trigger_id == "add-scenario-cancel-btn":
        return False, base_options, None, "", "", ""

    # --- Save -> close modal as well ---
    if trigger_id == "add-scenario-save-btn":
        # store update happens in callback B
        return False, base_options, None, "", "", ""

    # Fallback
    return no_update, no_update, no_update, no_update, no_update, no_update


# 3. Update equipment-store when adding new scenario


@callback(
    Output("equipment-store", "data", allow_duplicate=True),
    Output("displayed-equipment-store", "data", allow_duplicate=True),
    Output("add-scenario-error", "children", allow_duplicate=True),
    Output("equipment-scenario-group-store", "data", allow_duplicate=True),
    Input("add-scenario-save-btn", "n_clicks"),
    State("equipment-store", "data"),
    State("displayed-equipment-store", "data"),
    State("add-base-scenario-select", "value"),
    State("add-scenario-id-input", "value"),
    State("add-scenario-name-input", "value"),
    prevent_initial_call=True,
)
def add_scenario_to_store(save_clicks, equipment_data, displayed_ids, base_id, new_id, new_name):
    logger.debug(
        "add_scenario_to_store called: clicks=%s, base_id=%s, new_id=%s",
        save_clicks,
        base_id,
        new_id,
    )

    if not save_clicks:
        # should never hit with prevent_initial_call, but extra guard is cheap
        return no_update, no_update, no_update, no_update

    if not equipment_data:
        logger.warning("No equipment data available")
        return no_update, no_update, "No equipment data available", no_update

    scenarios = equipment_data.get("equipment_scenarios", [])
    if not base_id:
        logger.warning("No base scenario selected")
        return no_update, no_update, "Please select a base scenario", no_update

    if not new_id or not new_id.strip():
        new_id = _next_scenario_id(equipment_data)
    new_id = new_id.strip()
    new_name = (new_name or "").strip() or new_id

    existing_ids = {s.get("eq_scen_id") for s in scenarios}
    if new_id in existing_ids:
        logger.warning("Scenario ID '%s' already exists", new_id)
        return no_update, no_update, f"Scenario ID '{new_id}' already exists", no_update

    base_scenario = next((s for s in scenarios if s.get("eq_scen_id") == base_id), None)
    if base_scenario is None:
        logger.warning("Base scenario '%s' not found", base_id)
        return no_update, no_update, "Base scenario not found", no_update

    new_scenario = {**base_scenario, "eq_scen_id": new_id, "eq_scen_name": new_name}
    updated_equipment = {
        **equipment_data,
        "equipment_scenarios": [*scenarios, new_scenario],
    }

    # Add the new scenario to displayed IDs so it appears in the table
    updated_displayed = [*(displayed_ids or []), new_id]

    logger.info("Added new equipment scenario: %s (based on %s)", new_id, base_id)

    # Clear scenario group store to allow re-selecting the same group
    return updated_equipment, updated_displayed, "", None


@callback(
    Output("selected-equipment-store", "data"),
    Output("equipment-checkbox-group", "value"),
    Input("equipment-checkbox-group", "value"),
    State("displayed-equipment-store", "data"),
    prevent_initial_call=True,
)
def sync_active_equipment(selected_values, displayed_ids):
    """
    Keep selected-equipment-store in sync with the checkbox group.
    Enforce the 'max 5 scenarios' rule by capping and reflecting
    that back in the CheckboxGroup.
    Preserves the displayed order (column order in the table) for chart consistency.
    """
    raw_selected = set(selected_values or [])

    # Reorder selected values to match the displayed order
    if displayed_ids:
        ordered_selected = [sid for sid in displayed_ids if sid in raw_selected]
    else:
        ordered_selected = list(raw_selected)

    # Enforce max 5 scenarios rule
    capped_selected = ordered_selected[:5]

    return capped_selected, capped_selected


@callback(
    Output("displayed-equipment-store", "data"),
    Output("equipment-store", "data", allow_duplicate=True),
    Output("selected-equipment-store", "data", allow_duplicate=True),
    Output("equipment-checkbox-group", "value", allow_duplicate=True),
    Input({"type": "equipment-column-dropdown", "column": ALL}, "value"),
    State("displayed-equipment-store", "data"),
    State("equipment-store", "data"),
    State("selected-equipment-store", "data"),
    prevent_initial_call=True,
)
def handle_column_dropdown_change(dropdown_values, displayed_ids, equipment_data, selected_ids):
    """
    Handle scenario selection from column dropdowns.
    If selected scenario is already displayed elsewhere, create a copy.
    """
    if not dropdown_values or not displayed_ids or not equipment_data:
        return no_update, no_update, no_update, no_update

    ctx = callback_context
    if not ctx.triggered:
        return no_update, no_update, no_update, no_update

    # Find which dropdown triggered the callback
    triggered = ctx.triggered[0]
    prop_id = triggered["prop_id"]

    # Parse the pattern-matching ID
    try:
        id_str = prop_id.split(".")[0]
        btn_id = json.loads(id_str)
        column_idx = btn_id.get("column")
    except (json.JSONDecodeError, AttributeError):
        return no_update, no_update, no_update, no_update

    if column_idx is None:
        return no_update, no_update, no_update, no_update

    # Get the newly selected scenario ID
    new_scen_id = dropdown_values[column_idx]

    if not new_scen_id:
        return no_update, no_update, no_update, no_update

    # Exit early if the selection hasn't actually changed
    old_scen_id = displayed_ids[column_idx] if column_idx < len(displayed_ids) else None
    if new_scen_id == old_scen_id:
        return no_update, no_update, no_update, no_update

    # Check if this scenario is already displayed in another column
    new_displayed = list(displayed_ids)
    updated_equipment = equipment_data

    other_columns = [i for i in range(len(new_displayed)) if i != column_idx]
    already_displayed = new_scen_id in [new_displayed[i] for i in other_columns]

    if already_displayed:
        # Create a copy of the scenario with a new ID
        scenarios = equipment_data.get("equipment_scenarios", [])
        base_scenario = next((s for s in scenarios if s.get("eq_scen_id") == new_scen_id), None)

        if base_scenario is None:
            return no_update, no_update, no_update, no_update

        # Generate new ID
        copy_id = _next_scenario_id(equipment_data)
        copy_name = f"{base_scenario.get('eq_scen_name', new_scen_id)} (copy)"

        # Create the copy
        new_scenario = {
            **base_scenario,
            "eq_scen_id": copy_id,
            "eq_scen_name": copy_name,
        }

        # Add to equipment store
        updated_equipment = {
            **equipment_data,
            "equipment_scenarios": [*scenarios, new_scenario],
        }

        # Use the copy's ID in the displayed list
        new_displayed[column_idx] = copy_id
    else:
        # No duplicate - just update the displayed list
        new_displayed[column_idx] = new_scen_id

    # Update selected-equipment-store: swap old scenario for new one
    new_selected = list(selected_ids) if selected_ids else []
    old_scen_id = displayed_ids[column_idx]  # The scenario that was in this column before

    if old_scen_id in new_selected:
        # Replace old with new in selection
        old_index = new_selected.index(old_scen_id)
        new_selected[old_index] = new_displayed[column_idx]

    return new_displayed, updated_equipment, new_selected, new_selected


@callback(
    Output("equipment-store", "data", allow_duplicate=True),
    Output("selected-equipment-store", "data", allow_duplicate=True),
    Output("displayed-equipment-store", "data", allow_duplicate=True),
    Output("equipment-scenario-group-store", "data", allow_duplicate=True),
    Input({"type": "equipment-remove-btn", "eq_scen_id": ALL}, "n_clicks"),
    State("equipment-store", "data"),
    State("selected-equipment-store", "data"),
    State("displayed-equipment-store", "data"),
    prevent_initial_call=True,
)
def remove_scenario(remove_clicks, equipment_data, selected_equipment_ids, displayed_ids):
    """
    Remove the scenario whose trash icon was clicked, and also
    prune it from selected-equipment-store and displayed-equipment-store.
    Clears scenario group store to allow re-selecting the same group.
    """
    if not any(remove_clicks or []):
        return no_update, no_update, no_update, no_update

    if not equipment_data or "equipment_scenarios" not in equipment_data:
        return no_update, no_update, no_update, no_update

    triggered = callback_context.triggered
    if not triggered:
        return no_update, no_update, no_update, no_update

    prop_id = triggered[0]["prop_id"]
    id_str = prop_id.split(".")[0]

    try:
        btn_id = json.loads(id_str)
    except json.JSONDecodeError:
        return no_update, no_update, no_update, no_update

    eq_scen_id = btn_id.get("eq_scen_id")
    if not eq_scen_id:
        return no_update, no_update, no_update, no_update

    # ----- 1) Update equipment-store -----
    scenarios = equipment_data["equipment_scenarios"]
    new_scenarios = [s for s in scenarios if s.get("eq_scen_id") != eq_scen_id]

    if len(new_scenarios) == len(scenarios):
        return no_update, no_update, no_update, no_update

    updated_equipment = equipment_data.copy()
    updated_equipment["equipment_scenarios"] = new_scenarios

    # ----- 2) Update selected-equipment-store (prune removed id) -----
    selected_equipment_ids = selected_equipment_ids or []
    new_selected = [sid for sid in selected_equipment_ids if sid != eq_scen_id]

    # ----- 3) Update displayed-equipment-store (prune removed id) -----
    displayed_ids = displayed_ids or []
    new_displayed = [sid for sid in displayed_ids if sid != eq_scen_id]

    logger.info("Removed scenario '%s'. Selected: %s", eq_scen_id, new_selected)

    # Clear scenario group store to allow re-selecting the same group
    return updated_equipment, new_selected, new_displayed, None


@callback(
    Output("equipment-store", "data", allow_duplicate=True),
    Output("selected-equipment-store", "data", allow_duplicate=True),
    Input("button-reset-equipment", "n_clicks"),
    State("equipment-initial-store", "data"),
    prevent_initial_call=True,
)
def reset_equipment(n_clicks, initial_data):
    """
    Reset the equipment configuration back to the initial library
    and clear any active selections.
    """
    if not n_clicks:
        return no_update, no_update

    if not initial_data:
        return no_update, no_update

    return initial_data, []


@callback(
    Output("equipment-edit-modal", "opened"),
    Output("edit-scenario-id-input", "value"),
    Output("edit-scenario-name-input", "value"),
    Output("edit-hr-wwhp-select", "data"),
    Output("edit-hr-wwhp-select", "value"),
    Output("edit-hr-wwhp-performance-model", "value"),
    Output("edit-hr-wwhp-h-supply-t-value", "value"),
    Output("edit-awhp-select", "data"),
    Output("edit-awhp-select", "value"),
    Output("edit-awhp-performance-model", "value"),
    Output("edit-awhp-h-supply-t-value", "value"),
    Output("edit-awhp-sizing-mode", "value"),
    Output("edit-awhp-sizing-value", "value"),
    Output("edit-awhp-redundancy", "value"),
    Output("edit-awhp-use-cooling", "checked"),
    Output("edit-awhp-sizing-priority", "value"),
    Output("edit-backup-heating-select", "data"),
    Output("edit-backup-heating-select", "value"),
    Output("edit-chiller-select", "data"),
    Output("edit-chiller-select", "value"),
    Output("edit-scenario-error", "children"),
    Input({"type": "equipment-edit-btn", "eq_scen_id": ALL}, "n_clicks"),
    State("equipment-store", "data"),
    State("unit-toggle", "value"),
    prevent_initial_call=True,
)
def open_edit_modal(edit_clicks, equipment_data, unit_mode):
    """
    Open the edit modal for the scenario whose pencil icon was clicked,
    pre-filling all editable fields.
    """
    if not any(edit_clicks or []):
        return (no_update,) * 21

    if not equipment_data:
        return (
            False,
            "",
            "",
            [],
            None,
            None,
            None,
            [],
            None,
            None,
            None,
            None,
            None,
            None,
            False,
            None,
            [],
            None,
            [],
            None,
            "No equipment data.",
        )

    equipment_list = equipment_data.get("equipment", [])
    scenarios = equipment_data.get("equipment_scenarios", [])

    triggered = callback_context.triggered
    if not triggered:
        return (no_update,) * 21

    prop_id = triggered[0]["prop_id"]
    id_str = prop_id.split(".")[0]

    try:
        btn_id = json.loads(id_str)
    except json.JSONDecodeError:
        return (
            False,
            "",
            "",
            [],
            None,
            None,
            None,
            [],
            None,
            None,
            None,
            None,
            None,
            None,
            False,
            None,
            [],
            None,
            [],
            None,
            "Failed to parse button id.",
        )

    eq_scen_id = btn_id.get("eq_scen_id")
    scenario = next(
        (s for s in scenarios if s.get("eq_scen_id") == eq_scen_id),
        None,
    )
    if scenario is None:
        return (
            False,
            "",
            "",
            [],
            None,
            None,
            None,
            [],
            None,
            None,
            None,
            None,
            None,
            None,
            False,
            None,
            [],
            None,
            [],
            None,
            f"Scenario {eq_scen_id!r} not found.",
        )

    # --- Build select options from equipment list ---
    hr_hp_options = _build_equipment_options(
        equipment_list, "hr_heat_pump", unit_mode, include_none=True
    )
    awhp_options = _build_equipment_options(
        equipment_list, "heat_pump", unit_mode, include_none=True
    )
    backup_heating_options = _build_equipment_options(
        equipment_list, "backup_heating", unit_mode, include_none=False
    )
    chiller_options = _build_equipment_options(
        equipment_list, "chiller", unit_mode, include_none=False
    )

    # --- Scenario current values ---
    scen_name = scenario.get("eq_scen_name", eq_scen_id)

    hr_wwhp_val = scenario.get("hr_wwhp")
    if hr_wwhp_val is None:
        hr_wwhp_val = "None"

    hr_wwhp_performance_model_val = scenario.get("hr_wwhp_performance_model") or "interpolate_HHWST"

    # Get temperature values and convert to display units
    from utils.units import C_to_F

    unit_mode = unit_mode or "SI"

    hr_wwhp_h_supply_t_val = scenario.get("hr_wwhp_h_supply_t")
    if hr_wwhp_h_supply_t_val is not None:
        try:
            hr_wwhp_h_supply_t_val = float(hr_wwhp_h_supply_t_val)
            if unit_mode == "IP":
                hr_wwhp_h_supply_t_val = C_to_F(hr_wwhp_h_supply_t_val)
        except (ValueError, TypeError):
            hr_wwhp_h_supply_t_val = None

    awhp_val = scenario.get("awhp")
    if awhp_val is None:
        awhp_val = "None"

    awhp_performance_model_val = scenario.get("awhp_performance_model") or "interpolate_HHWST_fixed"

    awhp_h_supply_t_val = scenario.get("awhp_h_supply_t")
    if awhp_h_supply_t_val is not None:
        try:
            awhp_h_supply_t_val = float(awhp_h_supply_t_val)
            if unit_mode == "IP":
                awhp_h_supply_t_val = C_to_F(awhp_h_supply_t_val)
        except (ValueError, TypeError):
            awhp_h_supply_t_val = None

    sizing_mode = scenario.get("awhp_sizing_mode") or "integer_sizing_peak_load"
    sizing_value = scenario.get("awhp_sizing_value", 1.0)
    redundancy = scenario.get("awhp_redundancy", 1)
    use_cooling = scenario.get("awhp_use_cooling", False)
    sizing_priority = scenario.get("awhp_sizing_priority") or "heating"

    backup_heating_val = scenario.get("backup_heating")
    chiller_val = scenario.get("chiller")

    return (
        True,  # modal open
        eq_scen_id,  # id input
        scen_name,
        hr_hp_options,
        hr_wwhp_val,
        hr_wwhp_performance_model_val,
        hr_wwhp_h_supply_t_val,
        awhp_options,
        awhp_val,
        awhp_performance_model_val,
        awhp_h_supply_t_val,
        sizing_mode,
        sizing_value,
        redundancy,
        use_cooling,
        sizing_priority,
        backup_heating_options,
        backup_heating_val,
        chiller_options,
        chiller_val,
        "",
    )


@callback(
    Output("equipment-edit-modal", "opened", allow_duplicate=True),
    Output("equipment-store", "data", allow_duplicate=True),
    Output("edit-scenario-error", "children", allow_duplicate=True),
    Input("edit-scenario-save-btn", "n_clicks"),
    State("edit-scenario-id-input", "value"),
    State("edit-scenario-name-input", "value"),
    State("edit-hr-wwhp-select", "value"),
    State("edit-hr-wwhp-performance-model", "value"),
    State("edit-hr-wwhp-h-supply-t-value", "value"),
    State("edit-awhp-select", "value"),
    State("edit-awhp-performance-model", "value"),
    State("edit-awhp-h-supply-t-value", "value"),
    State("edit-awhp-sizing-mode", "value"),
    State("edit-awhp-sizing-value", "value"),
    State("edit-awhp-redundancy", "value"),
    State("edit-awhp-use-cooling", "checked"),
    State("edit-awhp-sizing-priority", "value"),
    State("edit-backup-heating-select", "value"),
    State("edit-chiller-select", "value"),
    State("equipment-store", "data"),
    State("unit-toggle", "value"),
    prevent_initial_call=True,
)
def save_edit_scenario(
    n_clicks,
    scen_id,
    new_name,
    hr_wwhp_val,
    hr_wwhp_performance_model_val,
    hr_wwhp_h_supply_t_val,
    awhp_val,
    awhp_performance_model_val,
    awhp_h_supply_t_val,
    sizing_mode,
    sizing_value,
    redundancy,
    use_cooling,
    sizing_priority,
    backup_heating_val,
    chiller_val,
    equipment_data,
    unit_mode,
):
    if not n_clicks:
        return no_update, no_update, no_update

    if not equipment_data or "equipment_scenarios" not in equipment_data:
        return False, no_update, "No equipment data to edit."

    new_name = (new_name or "").strip()
    if not new_name:
        return True, no_update, "Scenario name cannot be empty."

    from utils.units import F_to_C

    unit_mode = unit_mode or "SI"

    if hr_wwhp_val == "None":
        hr_wwhp_val = None
    if awhp_val == "None":
        awhp_val = None

    # Convert temperature values from display units back to Celsius (base unit)
    if hr_wwhp_h_supply_t_val is not None:
        try:
            hr_wwhp_h_supply_t_val = float(hr_wwhp_h_supply_t_val)
            if unit_mode == "IP":
                hr_wwhp_h_supply_t_val = F_to_C(hr_wwhp_h_supply_t_val)
        except (ValueError, TypeError):
            hr_wwhp_h_supply_t_val = None

    if awhp_h_supply_t_val is not None:
        try:
            awhp_h_supply_t_val = float(awhp_h_supply_t_val)
            if unit_mode == "IP":
                awhp_h_supply_t_val = F_to_C(awhp_h_supply_t_val)
        except (ValueError, TypeError):
            awhp_h_supply_t_val = None

    try:
        sizing_value = float(sizing_value) if sizing_value is not None else 1.0
    except (TypeError, ValueError):
        sizing_value = 1.0

    try:
        redundancy = int(redundancy) if redundancy is not None else 1
    except (TypeError, ValueError):
        redundancy = 1

    use_cooling = bool(use_cooling)

    scenarios = equipment_data["equipment_scenarios"]
    updated = False
    new_scenarios = []

    for scen in scenarios:
        if scen.get("eq_scen_id") == scen_id:
            new_scen = scen.copy()
            new_scen["eq_scen_name"] = new_name
            new_scen["hr_wwhp"] = hr_wwhp_val
            new_scen["hr_wwhp_performance_model"] = hr_wwhp_performance_model_val
            new_scen["hr_wwhp_h_supply_t"] = hr_wwhp_h_supply_t_val
            new_scen["awhp"] = awhp_val
            new_scen["awhp_performance_model"] = awhp_performance_model_val
            new_scen["awhp_h_supply_t"] = awhp_h_supply_t_val
            new_scen["awhp_sizing_mode"] = sizing_mode
            new_scen["awhp_sizing_value"] = sizing_value
            new_scen["awhp_redundancy"] = redundancy
            new_scen["awhp_use_cooling"] = use_cooling
            new_scen["awhp_sizing_priority"] = sizing_priority
            new_scen["backup_heating"] = backup_heating_val
            new_scen["chiller"] = chiller_val
            new_scenarios.append(new_scen)
            updated = True
        else:
            new_scenarios.append(scen)

    if not updated:
        return True, no_update, f"Scenario {scen_id!r} not found."

    updated_equipment = equipment_data.copy()
    updated_equipment["equipment_scenarios"] = new_scenarios

    return False, updated_equipment, ""


# 9. Cancel edit modal


@callback(
    Output("equipment-edit-modal", "opened", allow_duplicate=True),
    Input("edit-scenario-cancel-btn", "n_clicks"),
    prevent_initial_call=True,
)
def cancel_edit_modal(n_clicks):
    if not n_clicks:
        return no_update
    return False


# 10. Update temperature labels, value, min/max, and disabled state based on unit mode, selected HP, and performance model
@callback(
    Output("edit-hr-wwhp-h-supply-t-label", "children"),
    Output("edit-hr-wwhp-h-supply-t-value", "min"),
    Output("edit-hr-wwhp-h-supply-t-value", "max"),
    Output("edit-hr-wwhp-h-supply-t-value", "value", allow_duplicate=True),
    Output("edit-hr-wwhp-h-supply-t-value", "disabled"),
    Output("edit-awhp-h-supply-t-label", "children"),
    Output("edit-awhp-h-supply-t-value", "min"),
    Output("edit-awhp-h-supply-t-value", "max"),
    Output("edit-awhp-h-supply-t-value", "value", allow_duplicate=True),
    Output("edit-awhp-h-supply-t-value", "disabled"),
    Input("edit-hr-wwhp-select", "value"),
    Input("edit-awhp-select", "value"),
    Input("edit-awhp-performance-model", "value"),
    State("edit-hr-wwhp-h-supply-t-value", "value"),
    State("edit-awhp-h-supply-t-value", "value"),
    State("unit-toggle", "value"),
    State("equipment-store", "data"),
    prevent_initial_call=True,
)
def update_temp_inputs_on_hp_change(
    hr_hp_id,
    awhp_id,
    awhp_perf_model,
    current_hr_temp,
    current_awhp_temp,
    unit_mode,
    equipment_data,
):
    """Update temperature constraints when HP selection changes.

    Preserves existing temperature values if they're within the new valid range.
    Only resets to minimum if the current value is invalid or None.
    """
    from utils.units import C_to_F, get_unit_label

    unit_mode = unit_mode or "SI"
    temp_unit = get_unit_label("temperature", unit_mode)

    hr_label = f"HR HP Heating supply temp ({temp_unit})"
    awhp_label = f"AWHP Heating supply temp ({temp_unit})"

    # Get equipment list
    equipment_list = equipment_data.get("equipment", []) if equipment_data else []

    # Get supply temp ranges from selected HPs
    hr_min_c, hr_max_c = _get_supply_temp_range(equipment_list, hr_hp_id)
    awhp_min_c, awhp_max_c = _get_supply_temp_range(equipment_list, awhp_id)

    # Check if HPs are selected
    hr_selected = hr_hp_id and hr_hp_id != "None" and hr_min_c is not None
    awhp_selected = awhp_id and awhp_id != "None" and awhp_min_c is not None

    # Check if AWHP performance model is 'reset'; disable temperature input in this case
    awhp_performance_reset = awhp_perf_model == "interpolate_HHWST_reset"

    awhp_supply_t_enabled = awhp_selected and not awhp_performance_reset

    # Use defaults for display if no HP selected (but will be disabled)
    if not hr_selected:
        hr_min_c, hr_max_c = 32.2, 73.9
    if not awhp_selected:
        awhp_min_c, awhp_max_c = 35, 60

    # Convert to display units if IP mode
    if unit_mode == "IP":
        hr_min = C_to_F(hr_min_c)
        hr_max = C_to_F(hr_max_c)
        awhp_min = C_to_F(awhp_min_c)
        awhp_max = C_to_F(awhp_max_c)
    else:
        hr_min, hr_max = hr_min_c, hr_max_c
        awhp_min, awhp_max = awhp_min_c, awhp_max_c

    # Preserve current value if valid, otherwise set to minimum
    if hr_selected:
        if current_hr_temp is not None and hr_min <= current_hr_temp <= hr_max:
            hr_value = current_hr_temp
        else:
            hr_value = hr_min
    else:
        hr_value = None

    if awhp_selected:
        if current_awhp_temp is not None and awhp_min <= current_awhp_temp <= awhp_max:
            awhp_value = current_awhp_temp
        else:
            awhp_value = awhp_min
    else:
        awhp_value = None

    return (
        hr_label,
        hr_min,
        hr_max,
        hr_value,
        not hr_selected,
        awhp_label,
        awhp_min,
        awhp_max,
        awhp_value,
        not awhp_supply_t_enabled,
    )


# 10b. Update temperature labels when unit mode changes (without resetting values)
@callback(
    Output("edit-hr-wwhp-h-supply-t-label", "children", allow_duplicate=True),
    Output("edit-awhp-h-supply-t-label", "children", allow_duplicate=True),
    Input("unit-toggle", "value"),
    prevent_initial_call=True,
)
def update_temp_labels_on_unit_change(unit_mode):
    """Update temperature labels when unit mode changes."""
    from utils.units import get_unit_label

    unit_mode = unit_mode or "SI"
    temp_unit = get_unit_label("temperature", unit_mode)

    hr_label = f"HR HP Heating supply temp ({temp_unit})"
    awhp_label = f"AWHP Heating supply temp ({temp_unit})"

    return hr_label, awhp_label


@callback(
    Output("edit-hr-wwhp-performance-model", "disabled"),
    Output("edit-awhp-performance-model", "disabled"),
    Input("edit-hr-wwhp-select", "value"),
    Input("edit-awhp-select", "value"),
    prevent_initial_call=True,
)
def update_perf_model_on_hp_change(hr_hp_id, awhp_id):
    """Enable/disable performance model input when HP selection changes."""

    # Check if HPs are selected
    hr_selected = hr_hp_id and hr_hp_id != "None"
    awhp_selected = awhp_id and awhp_id != "None"

    return (not hr_selected, not awhp_selected)


@callback(
    Output("edit-awhp-sizing-priority", "disabled"),
    Input("edit-awhp-use-cooling", "checked"),
    Input("edit-awhp-sizing-mode", "value"),
    prevent_initial_call=True,
)
def update_sizing_priority(use_cooling, sizing_mode):
    """Enable/disable AWHP sizing priority input when use-cooling or sizing mode changes."""

    # Disable input if AWHP is not used for cooling or if sizing is not based on peak load
    disabled = (not use_cooling) or (sizing_mode == "fixed_num_units")

    return disabled


# helper to build equipment options for Selects

def _build_equipment_options(
    equipment_list, eq_type, unit_mode, include_none=False, none_label="None"
):
    from utils.units import format_with_auto_scale

    unit_mode = unit_mode or "SI"
    decimals = 0 if unit_mode == "IP" else 1

    options = []
    for eq in equipment_list or []:
        if eq.get("eq_type") == eq_type:
            if eq.get("eq_manufacturer"):
                label = f"{eq.get('eq_manufacturer', '')} {eq.get('model', '')}"

            else:
                label = f"{eq.get('model', '')}"

            if eq_type == "backup_heating":
                eff = eq.get("performance", "")["heating"]["efficiency"]
                label += f" {eff * 100:.0f}% Eff"

            if eq.get("eq_calc_type") == "specific":
                if eq_type in ["hr_heat_pump", "heat_pump", "chiller"]:
                    capacity = "nominal_capacity_W"
                    category = "power_cooling"

                if eq_type == "backup_heating":
                    capacity = "capacity_W"
                    category = "power"

                label_cap = format_with_auto_scale(
                    eq.get(capacity, ""), category, unit_mode, decimals=decimals
                )

            else:
                label_cap = "Infinite cap."

            label += f" ({label_cap})"

            options.append(
                {
                    "label": label,
                    "value": eq.get("eq_id"),
                }
            )
    if include_none:
        options = [{"label": none_label, "value": "None"}, *options]
    return options


def _get_supply_temp_range(equipment_list, eq_id):
    """Extract min/max supply temperature from equipment's leaving_supply_t keys.

    Args:
        equipment_list: List of equipment dictionaries
        eq_id: Equipment ID to look up

    Returns:
        Tuple of (min_temp, max_temp) in Celsius, or (None, None) if not found
    """
    if not eq_id or eq_id == "None" or not equipment_list:
        return None, None

    eq = next((e for e in equipment_list if e.get("eq_id") == eq_id), None)
    if not eq:
        return None, None

    leaving_supply_t = eq.get("performance", {}).get("heating", {}).get("leaving_supply_t", {})
    if not leaving_supply_t:
        return None, None

    try:
        temps = [float(t) for t in leaving_supply_t]
        return min(temps), max(temps)
    except (ValueError, TypeError):
        return None, None


@callback(
    Output("edit-awhp-sizing-value", "step"),
    Output("edit-awhp-sizing-value", "precision"),
    Output("edit-awhp-sizing-value", "min"),
    Output("edit-awhp-sizing-value", "max"),
    Output("edit-awhp-sizing-value", "value", allow_duplicate=True),
    Input("edit-awhp-sizing-mode", "value"),
    State("edit-awhp-sizing-value", "value"),
    prevent_initial_call=True,
)
def update_sizing_value_constraints_and_snap(mode, current_value):
    """
    Adjust constraints for awhp sizing and snap the current value
    when the sizing mode changes.

    - fixed_num_units: integer-only, [1, 10]
    - other modes: decimal %, [0.0, 5.0], step 0.05
    """
    # Default if current_value is weird or None
    # (use your earlier "0.85" % default)
    DEFAULT_PERCENT = 0.85
    INT_MIN, INT_MAX = 1, 10
    PCT_MIN, PCT_MAX = 0.0, 5.0

    if mode == "fixed_num_units":
        # Integer-only config
        step = 1
        precision = 0
        min_val = INT_MIN
        max_val = INT_MAX

        # Snap to an integer within [1, 10]
        try:
            v = INT_MIN if current_value is None else float(current_value)
            v = round(v)
        except (TypeError, ValueError):
            v = INT_MIN

        v = max(min_val, min(v, max_val))

        return step, precision, min_val, max_val, v

    # Percentage-based modes (integer_sizing_peak_load / fractional_sizing_peak_load)
    step = 0.05
    precision = 2
    min_val = PCT_MIN
    max_val = PCT_MAX

    try:
        v = DEFAULT_PERCENT if current_value is None else float(current_value)
    except (TypeError, ValueError):
        v = DEFAULT_PERCENT

    # Snap into [0.0, 5.0]
    v = max(min_val, min(v, max_val))

    return step, precision, min_val, max_val, v
