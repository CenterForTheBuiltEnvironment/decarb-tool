import json

import dash
from dash import (
    dcc,
    html,
    Input,
    Output,
    State,
    callback,
    callback_context,
    no_update,
    ALL,
)
import dash_mantine_components as dmc

import pandas as pd
from pathlib import Path

from dash_iconify import DashIconify

from src.config import URLS

from utils.units import unit_map

from src.metadata import Metadata

from src.equipment import EquipmentLibrary

from src.loads import get_load_data

from src.energy import loads_to_site_energy, site_to_source

from layout.input import build_emissions_table, add_emission_modal, edit_emission_modal


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
                    dmc.Text("Specify Emission Scenarios", fw=500, size="lg"),
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
                    ),
                ],
                justify="space-between",
                mt="md",
                mb="sm",
            ),
            dmc.Divider(),
            html.Div(
                id="emissions-table",
                style={
                    "minHeight": "500px",
                    "marginTop": "16px",
                },
            ),
            dmc.Divider(mt="md"),
            add_emission_modal(),
            edit_emission_modal(),
            # We’ll reintroduce “calculate” controls and toasts later;
            # for now we keep the page focused on the table.
        ],
        fluid=True,
    )


@callback(
    Output("emissions-table", "children"),
    Input("metadata-store", "data"),
    Input("selected-emissions-store", "data"),
)
def update_emissions_table(metadata_data, selected_emissions):
    if not metadata_data:
        return dmc.Text("No emission scenarios defined yet.")

    metadata = Metadata(**metadata_data)

    if not metadata.emission_settings:
        return dmc.Text("No emission scenarios defined yet.")

    scenarios = [s.model_dump() for s in metadata.emission_settings]
    active_ids = selected_emissions or []

    return build_emissions_table(scenarios, active_ids=active_ids)


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
            try:
                nums.append(int(sid.split("_")[-1]))
            except ValueError:
                pass
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
    Input("add-em-scenario-save-btn", "n_clicks"),
    State("metadata-store", "data"),
    State("add-em-base-scenario-select", "value"),
    State("add-em-scenario-id-input", "value"),
    prevent_initial_call=True,
)
def add_emission_scenario_to_metadata(
    save_clicks,
    metadata_data,
    base_id,
    new_id,
):
    if not save_clicks:
        return no_update

    if not metadata_data or "emission_settings" not in metadata_data:
        return no_update

    scenarios = metadata_data.get("emission_settings", [])
    if not base_id:
        # could also push error into add-em-scenario-error
        return no_update

    if not new_id or not new_id.strip():
        new_id = _next_emission_scen_id(metadata_data)
    new_id = new_id.strip()

    existing_ids = {s.get("em_scen_id") for s in scenarios}
    if new_id in existing_ids:
        # ID already exists; might set error text instead
        return no_update

    base_scen = next(
        (s for s in scenarios if s.get("em_scen_id") == base_id),
        None,
    )
    if base_scen is None:
        return no_update

    new_scenario = {**base_scen, "em_scen_id": new_id}
    new_scenarios = scenarios + [new_scenario]

    updated_metadata = {
        **metadata_data,
        "emission_settings": new_scenarios,
    }

    return updated_metadata


@callback(
    Output("metadata-store", "data", allow_duplicate=True),
    Output("selected-emissions-store", "data", allow_duplicate=True),
    Input({"type": "emission-remove-btn", "em_scen_id": ALL}, "n_clicks"),
    State("metadata-store", "data"),
    State("selected-emissions-store", "data"),
    prevent_initial_call=True,
)
def remove_emission_scenario(remove_clicks, metadata_data, selected_em_ids):
    if not any(remove_clicks or []):
        return no_update, no_update

    if not metadata_data or "emission_settings" not in metadata_data:
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

    em_scen_id = btn_id.get("em_scen_id")
    if not em_scen_id:
        return no_update, no_update

    scenarios = metadata_data.get("emission_settings", [])
    new_scenarios = [s for s in scenarios if s.get("em_scen_id") != em_scen_id]

    if len(new_scenarios) == len(scenarios):
        return no_update, no_update

    updated_metadata = metadata_data.copy()
    updated_metadata["emission_settings"] = new_scenarios

    selected_em_ids = selected_em_ids or []
    new_selected = [sid for sid in selected_em_ids if sid != em_scen_id]

    return updated_metadata, new_selected


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
    prevent_initial_call=True,
)
def open_edit_emission_modal(edit_clicks, metadata_data):
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

    return (
        True,
        scen.get("em_scen_id"),
        scen.get("grid_scenario", ""),
        scen.get("gea_grid_region", ""),
        scen.get("time_zone", ""),
        scen.get("emission_type", ""),
        scen.get("shortrun_weighting"),
        str(scen.get("year")) if scen.get("year") is not None else "",
        scen.get("annual_refrig_leakage_percent"),
        scen.get("annual_ng_leakage_g_per_kWh"),
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
):
    if not n_clicks:
        return no_update, no_update, no_update

    if not metadata_data or "emission_settings" not in metadata_data:
        return False, no_update, "No emission data to edit."

    if not scen_id:
        return True, no_update, "Scenario ID is missing."

    # basic type cleaning
    try:
        shortrun_weighting = (
            float(shortrun_weighting) if shortrun_weighting is not None else 0.0
        )
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
    Output("notification-container", "sendNotifications", allow_duplicate=True),
    Input("button-calculate", "n_clicks"),
    prevent_initial_call=True,
)
def show_loading_notification(n_clicks):
    if not n_clicks:
        return no_update

    return [
        dict(
            id="emission-calc",
            title="Calculating emissions",
            message="Running loads_to_site and site_to_source...",
            loading=True,
            color="blue",
            action="show",
            autoClose=False,
        )
    ]


@callback(
    Output("site-energy-store", "data"),
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
    if not n_clicks or not metadata_json or not equipment_json:
        raise dash.exceptions.PreventUpdate

    if not selected_scenarios:
        # no equipment scenarios selected -> nothing to compute
        raise dash.exceptions.PreventUpdate

    folder = Path(f"/tmp/{session_data['session_id']}")  # isolated, ephemeral
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
    print(f"Saving Site Energy to: {site_path}")

    return str(site_path)


@callback(
    Output("source-energy-store", "children"),
    Output("notification-container", "sendNotifications", allow_duplicate=True),
    Input("site-energy-store", "data"),
    State("metadata-store", "data"),
    State("selected-emissions-store", "data"),
    State("session-store", "data"),
    prevent_initial_call=True,
)
def run_site_to_source(
    site_energy_path, metadata_json, selected_emission_ids, session_data
):
    if not site_energy_path:
        raise dash.exceptions.PreventUpdate

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
    else:
        error_notif = [
            dict(
                id="emission-calc",
                title="No emission scenarios selected",
                message="Please select at least one emission scenario before calculating.",
                color="red",
                loading=False,
                action="update",  # update the loading notif into an error
                autoClose=4000,
            )
        ]
        return dash.no_update, error_notif

    # Now site_to_source will see ONLY the selected emission scenarios
    source_energy = site_to_source(site_energy, metadata=metadata)

    source_path = folder / "source_energy.pkl"
    source_energy.to_pickle(source_path)
    print(f"Saving Source Energy to: {source_path}")

    # Update the existing loading notification to 'success'
    notif = [
        dict(
            id="emission-calc",
            title="Emissions calculated",
            message="Source energy and emissions have been computed.",
            color="green",
            loading=False,
            action="update",
            autoClose=3000,
            icon=DashIconify(icon="akar-icons:circle-check"),
        )
    ]

    return dcc.Store(id="source-energy-store", data=str(source_path)), notif
