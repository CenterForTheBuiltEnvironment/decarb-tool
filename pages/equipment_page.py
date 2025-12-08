import json

import dash
from dash import (
    MATCH,
    ALL,
    callback,
    ctx,
    html,
    dcc,
    dash_table,
    Input,
    Output,
    State,
    callback_context,
    no_update,
)
import dash_mantine_components as dmc

from dash_iconify import DashIconify

from layout.output import summary_equipment_selection
from src.config import URLS

from layout.input import (
    build_equipment_table,
    select_equipment,
    equipment_scenario_saving_buttons,
)
from src.equipment import EquipmentLibrary, EquipmentScenario

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
                    dmc.Text("Specify Equipment", fw=500, size="lg"),
                    dmc.Group(
                        [
                            dmc.Button(
                                "Add",
                                id="button-add-equipment",
                                variant="outline",
                            ),
                            dmc.Button(
                                "Reset",
                                id="button-reset-equipment",
                                variant="outline",
                                color="gray",
                            ),
                        ],
                    ),
                ],
                justify="space-between",
                mt="md",
                mb="sm",
            ),
            dmc.Divider(),
            html.Div(
                id="equipment-table",
                style={
                    "minHeight": "300px",  # just to make the area visible while empty
                    "marginTop": "16px",
                },
            ),
            # Use Mantine spacing prop instead of marginTop
            dmc.Divider(mt="md"),
            dmc.Group(
                [
                    dmc.Button(
                        "Confirm",
                        id="button-confirm-equipment",
                        variant="filled",
                    )
                ],
                justify="flex-end",
                mt="md",
                mb="md",
            ),
            # ? This could potentially be used to confirm selection before moving on
            dmc.Modal(
                id="equipment-confirm-modal",
                opened=False,  # controlled via callback
                title="Confirm selected scenarios",
                children=[
                    dmc.Text(
                        id="equipment-modal-content",
                        size="sm",
                    ),
                    dmc.Group(
                        [
                            dmc.Button(
                                "OK",
                                id="equipment-modal-ok-btn",
                            )
                        ],
                        justify="flex-end",
                        mt="md",
                    ),
                ],
            ),
            dmc.Modal(
                id="equipment-add-modal",
                opened=False,  # controlled via callback
                title="Add equipment scenario",
                children=dmc.Stack(
                    [
                        dmc.Select(
                            id="add-base-scenario-select",
                            label="Base scenario",
                            placeholder="Choose scenario to copy",
                            data=[],  # filled from equipment-store
                            searchable=True,
                            nothingFoundMessage="No scenarios",
                            withScrollArea=True,
                        ),
                        dmc.TextInput(
                            id="add-scenario-id-input",
                            label="New scenario ID",
                            placeholder="e.g. eq_scenario_6",
                        ),
                        dmc.TextInput(
                            id="add-scenario-name-input",
                            label="New scenario name",
                            placeholder="Descriptive name",
                        ),
                        dmc.Text(
                            id="add-scenario-error",
                            size="xs",
                            c="red",
                        ),
                        dmc.Group(
                            [
                                dmc.Button(
                                    "Cancel",
                                    id="add-scenario-cancel-btn",
                                    variant="outline",
                                ),
                                dmc.Button(
                                    "Save",
                                    id="add-scenario-save-btn",
                                ),
                            ],
                            justify="flex-end",
                            mt="sm",
                        ),
                    ]
                ),
            ),
            dmc.Modal(
                id="equipment-edit-modal",
                opened=False,
                title="Edit equipment scenario",
                children=dmc.Stack(
                    [
                        dmc.TextInput(
                            id="edit-scenario-id-input",
                            label="Scenario ID",
                            disabled=True,  # we keep ID immutable
                        ),
                        dmc.TextInput(
                            id="edit-scenario-name-input",
                            label="Scenario name",
                        ),
                        dmc.Text(
                            id="edit-scenario-error",
                            size="xs",
                            c="red",
                        ),
                        dmc.Group(
                            [
                                dmc.Button(
                                    "Cancel",
                                    id="edit-scenario-cancel-btn",
                                    variant="outline",
                                ),
                                dmc.Button(
                                    "Save",
                                    id="edit-scenario-save-btn",
                                ),
                            ],
                            justify="flex-end",
                            mt="sm",
                        ),
                    ]
                ),
            ),
        ],
        fluid=True,
    )


# 1. Populate equipment table from equipment-store
@callback(
    Output("equipment-table", "children"),
    Input("url", "pathname"),
    Input("equipment-store", "data"),
    Input("selected-equipment-store", "data"),
)
def update_equipment_table(pathname, equipment_store_data, selected_equipment_data):
    if pathname != URLS.EQUIPMENT.value:
        return no_update

    if not equipment_store_data:
        return dmc.Text("No equipment scenarios defined yet.")

    scenarios = equipment_store_data.get("equipment_scenarios", [])
    if not scenarios:
        return dmc.Text("No equipment scenarios defined yet.")

    selected_ids = selected_equipment_data or []

    # This will both:
    # - check the corresponding checkboxes
    # - highlight those rows
    return build_equipment_table(scenarios, active_ids=selected_ids)


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
        # you may want to surface this error in the UI instead via another Output
        return no_update

    # normalize new_id / new_name
    if not new_id or not new_id.strip():
        new_id = _next_scenario_id(equipment_data)
    new_id = new_id.strip()
    new_name = (new_name or "").strip() or new_id

    existing_ids = {s.get("eq_scen_id") for s in scenarios}
    if new_id in existing_ids:
        # again: real UX would push this to an error Text, but data-wise we do nothing
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

    # If user tried to pick more than 5, we:
    # - store only the first 5
    # - set the CheckboxGroup value back to those 5, auto-unchecking extras
    return capped_selected, capped_selected


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

    # Which button fired?
    triggered = callback_context.triggered
    if not triggered:
        return no_update, no_update

    prop_id = triggered[0][
        "prop_id"
    ]  # e.g. '{"type":"equipment-remove-btn","eq_scen_id":"eq_1"}.n_clicks'
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
        # nothing actually removed
        return no_update, no_update

    updated_equipment = equipment_data.copy()
    updated_equipment["equipment_scenarios"] = new_scenarios

    # ----- 2) Update selected-equipment-store (prune removed id) -----
    selected_equipment_ids = selected_equipment_ids or []
    new_selected = [sid for sid in selected_equipment_ids if sid != eq_scen_id]
    print("Updated selected equipment IDs:", new_selected)

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
