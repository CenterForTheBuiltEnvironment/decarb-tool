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
                            html.H5("Equipment"),
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
            dmc.Paper(
                html.Div(
                    id="equipment-table",
                    style={
                        "marginTop": "16px",
                    },
                ),
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

    return build_equipment_table(scenarios, active_ids=selected_ids)


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
    Output("edit-awhp-select", "data"),
    Output("edit-awhp-select", "value"),
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
        return (no_update,) * 16

    if not equipment_data:
        return (
            False,
            "",
            "",
            [],
            None,
            [],
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
        return (no_update,) * 16

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
            [],
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
            [],
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

    awhp_val = scenario.get("awhp")
    if awhp_val is None:
        awhp_val = "None"

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
        awhp_options,
        awhp_val,
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
    State("edit-awhp-select", "value"),
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
    awhp_val,
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
            new_scen["awhp"] = awhp_val
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
