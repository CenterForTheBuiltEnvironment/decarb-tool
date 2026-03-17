import json

import dash
from dash import (
    ALL,
    callback,
    html,
    dcc,
    Input,
    Output,
    State,
    callback_context,
    no_update,
)
import dash_mantine_components as dmc

from dash_iconify import DashIconify

from src.config import URLS

from layout.input import (
    add_equipment_modal,
    build_equipment_table,
    edit_equipment_modal,
)

from utils.logging_config import get_logger
from utils.tooltips import with_tooltip, with_icon

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
                        rightSection=DashIconify(
                            icon="tabler:arrow-narrow-right-dashed"
                        ),
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
    Input("scenario-group-select", "value"),
    State("equipment-store", "data"),
    prevent_initial_call=True,
)
def handle_group_selection(group_id, equipment_data):
    """
    When a scenario group is selected, update displayed and selected scenarios.
    """
    if not group_id or not equipment_data:
        return no_update, no_update, no_update

    groups = equipment_data.get("scenario_groups", [])
    selected_group = next((g for g in groups if g.get("group_id") == group_id), None)

    if not selected_group:
        return no_update, no_update, no_update

    scenario_ids = selected_group.get("scenario_ids", [])

    # Update displayed, selected, and checkbox group with the group's scenarios
    return scenario_ids, scenario_ids, scenario_ids


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
            try:
                nums.append(int(sid.split("_")[-1]))
            except ValueError:
                pass
    n = max(nums) + 1 if nums else 1
    return f"eq_scenario_{n}"


@callback(
    Output("equipment-add-modal", "opened"),
    Output("add-base-scenario-select", "data"),
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

    # Initial page load
    if not ctx.triggered:
        return False, base_options, "", "", ""

    trigger_id = ctx.triggered[0]["prop_id"].split(".")[0]

    # --- Open modal ---
    if trigger_id == "button-add-equipment":
        auto_id = _next_scenario_id(equipment_data)
        return True, base_options, auto_id, "", ""

    # --- Cancel -> close modal ---
    if trigger_id == "add-scenario-cancel-btn":
        return False, base_options, "", "", ""

    # --- Save -> close modal as well ---
    if trigger_id == "add-scenario-save-btn":
        # store update happens in callback B
        return False, base_options, "", "", ""

    # Fallback
    return no_update, no_update, no_update, no_update, no_update


# 3. Update equipment-store when adding new scenario


@callback(
    Output("equipment-store", "data"),
    Input("add-scenario-save-btn", "n_clicks"),
    State("equipment-store", "data"),
    State("add-base-scenario-select", "value"),
    State("add-scenario-id-input", "value"),
    State("add-scenario-name-input", "value"),
    prevent_initial_call=True,
)
def add_scenario_to_store(save_clicks, equipment_data, base_id, new_id, new_name):
    if not save_clicks:
        # should never hit with prevent_initial_call, but extra guard is cheap
        return no_update

    if not equipment_data:
        return no_update

    scenarios = equipment_data.get("equipment_scenarios", [])
    if not base_id:
        #! potentially highlight error in UI
        return no_update

    if not new_id or not new_id.strip():
        new_id = _next_scenario_id(equipment_data)
    new_id = new_id.strip()
    new_name = (new_name or "").strip() or new_id

    existing_ids = {s.get("eq_scen_id") for s in scenarios}
    if new_id in existing_ids:
        #! potentially highlight error in UI
        return no_update

    base_scenario = next((s for s in scenarios if s.get("eq_scen_id") == base_id), None)
    if base_scenario is None:
        return no_update

    new_scenario = {**base_scenario, "eq_scen_id": new_id, "eq_scen_name": new_name}
    updated_equipment = {
        **equipment_data,
        "equipment_scenarios": scenarios + [new_scenario],
    }

    return updated_equipment


@callback(
    Output("selected-equipment-store", "data"),
    Output("equipment-checkbox-group", "value"),
    Input("equipment-checkbox-group", "value"),
    prevent_initial_call=True,
)
def sync_active_equipment(selected_values):
    """
    Keep selected-equipment-store in sync with the checkbox group.
    Enforce the 'max 5 scenarios' rule by capping and reflecting
    that back in the CheckboxGroup.
    """
    raw_selected = selected_values or []
    capped_selected = raw_selected[:5]

    # If user picked <= 5, just mirror as-is
    if len(raw_selected) <= 5:
        return capped_selected, capped_selected

    # If user tried to pick more than 5:
    # - store only the first 5
    # - set the CheckboxGroup value back to those 5, auto-unchecking extras
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
def handle_column_dropdown_change(
    dropdown_values, displayed_ids, equipment_data, selected_ids
):
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
        base_scenario = next(
            (s for s in scenarios if s.get("eq_scen_id") == new_scen_id), None
        )

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
            "equipment_scenarios": scenarios + [new_scenario],
        }

        # Use the copy's ID in the displayed list
        new_displayed[column_idx] = copy_id
    else:
        # No duplicate - just update the displayed list
        new_displayed[column_idx] = new_scen_id

    # Update selected-equipment-store: swap old scenario for new one
    new_selected = list(selected_ids) if selected_ids else []
    old_scen_id = displayed_ids[
        column_idx
    ]  # The scenario that was in this column before

    if old_scen_id in new_selected:
        # Replace old with new in selection
        old_index = new_selected.index(old_scen_id)
        new_selected[old_index] = new_displayed[column_idx]

    return new_displayed, updated_equipment, new_selected, new_selected


@callback(
    Output("equipment-store", "data", allow_duplicate=True),
    Output("selected-equipment-store", "data", allow_duplicate=True),
    Input({"type": "equipment-remove-btn", "eq_scen_id": ALL}, "n_clicks"),
    State("equipment-store", "data"),
    State("selected-equipment-store", "data"),
    prevent_initial_call=True,
)
def remove_scenario(remove_clicks, equipment_data, selected_equipment_ids):
    """
    Remove the scenario whose trash icon was clicked, and also
    prune it from selected-equipment-store if it was active.
    """
    if not any(remove_clicks or []):
        return no_update, no_update

    if not equipment_data or "equipment_scenarios" not in equipment_data:
        return no_update, no_update

    triggered = callback_context.triggered
    if not triggered:
        return no_update, no_update

    prop_id = triggered[0]["prop_id"]
    id_str = prop_id.split(".")[0]

    try:
        btn_id = json.loads(id_str)
    except json.JSONDecodeError:
        return no_update, no_update

    eq_scen_id = btn_id.get("eq_scen_id")
    if not eq_scen_id:
        return no_update, no_update

    # ----- 1) Update equipment-store -----
    scenarios = equipment_data["equipment_scenarios"]
    new_scenarios = [s for s in scenarios if s.get("eq_scen_id") != eq_scen_id]

    if len(new_scenarios) == len(scenarios):
        return no_update, no_update

    updated_equipment = equipment_data.copy()
    updated_equipment["equipment_scenarios"] = new_scenarios

    # ----- 2) Update selected-equipment-store (prune removed id) -----
    selected_equipment_ids = selected_equipment_ids or []
    new_selected = [sid for sid in selected_equipment_ids if sid != eq_scen_id]
    logger.info("Updated selected equipment IDs: %s", new_selected)

    return updated_equipment, new_selected


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
    # Output("edit-hr-wwhp-h-supply-t-select", "data"), # added for autofill callback, not implemented
    Output("edit-hr-wwhp-h-supply-t-select", "value"),
    Output("edit-awhp-select", "data"),
    Output("edit-awhp-select", "value"),
    # Output("edit-awhp-h-supply-t-select", "data"), # added for autofill callback, not implemented
    Output("edit-awhp-h-supply-t-select", "value"),
    Output("edit-awhp-sizing-mode", "value"),
    Output("edit-awhp-sizing-value", "value"),
    Output("edit-awhp-redundancy", "value"),
    Output("edit-awhp-use-cooling", "checked"),
    Output("edit-backup-heating-select", "data"),
    Output("edit-backup-heating-select", "value"),
    Output("edit-chiller-select", "data"),
    Output("edit-chiller-select", "value"),
    Output("edit-scenario-error", "children"),
    Input({"type": "equipment-edit-btn", "eq_scen_id": ALL}, "n_clicks"),
    State("equipment-store", "data"),
    prevent_initial_call=True,
)
def open_edit_modal(edit_clicks, equipment_data):
    """
    Open the edit modal for the scenario whose pencil icon was clicked,
    pre-filling all editable fields.
    """
    if not any(edit_clicks or []):
        return (no_update,) * 18

    if not equipment_data:
        return (
            False,
            "",
            "",
            [],
            None,
            None,
            [],
            None,
            None,
            None,
            None,
            None,
            False,
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
        return (no_update,) * 18

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
            [],
            None,
            None,
            None,
            None,
            None,
            False,
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
            [],
            None,
            None,
            None,
            None,
            None,
            False,
            [],
            None,
            [],
            None,
            f"Scenario {eq_scen_id!r} not found.",
        )

    # --- Build select options from equipment list ---
    hr_hp_options = _build_equipment_options(
        equipment_list, "hr_heat_pump", include_none=True
    )
    awhp_options = _build_equipment_options(
        equipment_list, "heat_pump", include_none=True
    )
    backup_heating_options = _build_equipment_options(
        equipment_list, "backup_heating", include_none=False
    )
    chiller_options = _build_equipment_options(
        equipment_list, "chiller", include_none=False
    )

    # --- Scenario current values ---
    scen_name = scenario.get("eq_scen_name", eq_scen_id)

    hr_wwhp_val = scenario.get("hr_wwhp")
    if hr_wwhp_val is None:
        hr_wwhp_val = "None"

    # added for autofill callback, not implemented
    # hr_hp_supply_t_options = _build_heating_supply_temp_options(
    #     equipment_list, hr_wwhp_val.get("eq_id")
    # )

    hr_wwhp_h_supply_t_val = scenario.get("hr_wwhp_h_supply_t")
    if hr_wwhp_h_supply_t_val is None:
        hr_wwhp_h_supply_t_val = "None"

    awhp_val = scenario.get("awhp")
    if awhp_val is None:
        awhp_val = "None"

    # added for autofill callback, not implemented
    # awhp_supply_t_options = _build_heating_supply_temp_options(
    #     equipment_list, awhp_val.get("eq_id")
    # )
        
    awhp_h_supply_t_val = scenario.get("awhp_h_supply_t")
    if awhp_h_supply_t_val is None:
        awhp_h_supply_t_val = "None"

    sizing_mode = scenario.get("awhp_sizing_mode") or "integer_sizing_peak_load"
    sizing_value = scenario.get("awhp_sizing_value", 1.0)
    redundancy = scenario.get("awhp_redundancy", 1)
    use_cooling = scenario.get("awhp_use_cooling", False)

    backup_heating_val = scenario.get("backup_heating")
    chiller_val = scenario.get("chiller")

    return (
        True,  # modal open
        eq_scen_id,  # id input
        scen_name,
        hr_hp_options,
        hr_wwhp_val,
        hr_wwhp_h_supply_t_val,
        awhp_options,
        awhp_val,
        awhp_h_supply_t_val,
        sizing_mode,
        sizing_value,
        redundancy,
        use_cooling,
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
    State("edit-hr-wwhp-h-supply-t-select", "value"),
    State("edit-awhp-select", "value"),
    State("edit-awhp-h-supply-t-select", "value"),
    State("edit-awhp-sizing-mode", "value"),
    State("edit-awhp-sizing-value", "value"),
    State("edit-awhp-redundancy", "value"),
    State("edit-awhp-use-cooling", "checked"),
    State("edit-backup-heating-select", "value"),
    State("edit-chiller-select", "value"),
    State("equipment-store", "data"),
    prevent_initial_call=True,
)
def save_edit_scenario(
    n_clicks,
    scen_id,
    new_name,
    hr_wwhp_val,
    hr_wwhp_h_supply_t_val,
    awhp_val,
    awhp_h_supply_t_val,
    sizing_mode,
    sizing_value,
    redundancy,
    use_cooling,
    backup_heating_val,
    chiller_val,
    equipment_data,
):
    if not n_clicks:
        return no_update, no_update, no_update

    if not equipment_data or "equipment_scenarios" not in equipment_data:
        return False, no_update, "No equipment data to edit."

    new_name = (new_name or "").strip()
    if not new_name:
        return True, no_update, "Scenario name cannot be empty."

    if hr_wwhp_val == "None":
        hr_wwhp_val = None
    if awhp_val == "None":
        awhp_val = None

    if hr_wwhp_h_supply_t_val == "None":
        hr_wwhp_h_supply_t_val = None
    if awhp_h_supply_t_val == "None":
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
            new_scen["hr_wwhp_h_supply_t"] = hr_wwhp_h_supply_t_val
            new_scen["awhp"] = awhp_val
            new_scen["awhp_h_supply_t"] = awhp_h_supply_t_val
            new_scen["awhp_sizing_mode"] = sizing_mode
            new_scen["awhp_sizing_value"] = sizing_value
            new_scen["awhp_redundancy"] = redundancy
            new_scen["awhp_use_cooling"] = use_cooling
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


# 10. Update temperature labels and select options based on unit mode
@callback(
    Output("edit-hr-wwhp-h-supply-t-label", "children"),
    Output("edit-hr-wwhp-h-supply-t-select", "data"),
    Output("edit-awhp-h-supply-t-label", "children"),
    Output("edit-awhp-h-supply-t-select", "data"),
    Input("unit-toggle", "value"),
)
def update_temp_labels_and_options(unit_mode):
    """Update temperature labels and select options based on unit mode."""
    from utils.units import get_unit_label, C_to_F

    unit_mode = unit_mode or "SI"
    temp_unit = get_unit_label("temperature", unit_mode)

    hr_label = f"HR HP Heating supply temp ({temp_unit})"
    awhp_label = f"AWHP Heating supply temp ({temp_unit})"

    # Base temperatures in Celsius
    hr_temps_c = [32.2, 48.9, 60, 73.9]
    awhp_temps_c = [35, 38, 38.9, 43.3, 45, 48.9, 50, 52, 54.4, 60]

    if unit_mode == "IP":
        # Convert to Fahrenheit for display
        hr_options = [
            {"label": f"{C_to_F(t):.1f}", "value": str(t)} for t in hr_temps_c
        ]
        awhp_options = [
            {"label": f"{C_to_F(t):.1f}", "value": str(t)} for t in awhp_temps_c
        ]
    else:
        # Use Celsius values directly
        hr_options = [{"label": str(t), "value": str(t)} for t in hr_temps_c]
        awhp_options = [{"label": str(t), "value": str(t)} for t in awhp_temps_c]

    return hr_label, hr_options, awhp_label, awhp_options


# helper to build equipment options for Selects


def _build_equipment_options(
    equipment_list, eq_type, include_none=False, none_label="None"
):
    options = [
        {
            "label": f"{eq.get('model', '')} ({eq.get('eq_subtype', '')})",
            "value": eq.get("eq_id"),
        }
        for eq in (equipment_list or [])
        if eq.get("eq_type") == eq_type
    ]
    if include_none:
        options = [{"label": none_label, "value": "None"}] + options
    return options

# added for autofill callback, not implemented
# def _build_heating_supply_temp_options(
#         equipment_list, eq_id, include_none=True, none_label="None"
# ):
#     eq = equipment_list.get(eq_id)
#     perf = eq.get("performance")
#     heating = perf.get("heating")
#     temps_perf = heating.get("leaving_supply_t")
#     options = [{"label": f"{i}°C", "value": i} for i in list(temps_perf.keys())]
#     if include_none:
#         options = [{"label": none_label, "value": "None"}] + options
#     return options

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
            if current_value is None:
                v = INT_MIN
            else:
                v = float(current_value)
            v = int(round(v))
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
        if current_value is None:
            v = DEFAULT_PERCENT
        else:
            v = float(current_value)
    except (TypeError, ValueError):
        v = DEFAULT_PERCENT

    # Snap into [0.0, 5.0]
    v = max(min_val, min(v, max_val))

    return step, precision, min_val, max_val, v
