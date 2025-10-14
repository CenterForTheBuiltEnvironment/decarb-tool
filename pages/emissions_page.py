import dash
from dash import dcc, html, Input, Output, State, callback, ctx, no_update
import dash_bootstrap_components as dbc

import pandas as pd

from io import StringIO

from dash_iconify import DashIconify

from src.config import URLS

from utils.units import unit_map

from src.metadata import Metadata
from src.emissions import EmissionScenario

from layout.input import (
    emission_scenario_saving_buttons,
    select_gea_grid_region,
    select_grid_scenario,
    set_emission_type,
    set_grid_year,
    set_shortrun_weighting,
    set_static_emissions,
)

from src.equipment import EquipmentLibrary

from src.loads import get_load_data
from src.emissions import get_emissions_data

from src.energy import loads_to_site_energy, site_to_source

from layout.output import summary_emissions_selection

dash.register_page(__name__, name="Emissions", path=URLS.EMISSIONS.value, order=2)


def layout():
    return dbc.Container(
        children=[
            dcc.Store(id="active-emissions-tab"),
            dbc.Row(
                [
                    dbc.Col(
                        [
                            html.H5("Emission Scenario"),
                            html.Hr(),
                            set_grid_year(),
                            html.Hr(),
                            select_grid_scenario(),
                            html.Hr(),
                            set_emission_type(),
                            html.Hr(),
                            set_shortrun_weighting(),
                            html.Hr(),
                        ],
                        width=3,
                    ),
                    dbc.Col(
                        [
                            html.Hr(),
                            set_static_emissions(),
                            html.Hr(),
                            select_gea_grid_region(),
                            html.Hr(),
                            emission_scenario_saving_buttons(),
                        ],
                        width=4,
                    ),
                    dbc.Col(
                        [
                            html.H5("Overview"),
                            html.Hr(),
                            html.Div(
                                id="summary-emissions-info",
                            ),
                            dbc.Button(
                                [
                                    "Calculate Source Emissions ",
                                    DashIconify(
                                        icon="ic:baseline-autorenew",
                                        width=20,
                                    ),
                                ],
                                id="button-calculate",
                                n_clicks=0,
                                color="primary",
                                style={"float": "right"},
                            ),
                            html.Div(
                                id="calc-status-toast"
                            ),  #! for debugging: remove later
                        ],
                        width=5,
                    ),
                ]
            ),
        ]
    )


# Overwrite EmissionScenario in metadata based on user inputs
@callback(
    Output("metadata-store", "data", allow_duplicate=True),
    Input("update-scen-A", "n_clicks"),
    Input("update-scen-B", "n_clicks"),
    Input("update-scen-C", "n_clicks"),
    State("grid-year-input", "value"),
    State("grid-scenario-input", "value"),
    State("emission-type-input", "value"),
    State("shortrun-weighting-input", "value"),
    State("refrigerant-leakage-input", "value"),
    State("gea-grid-region-input", "value"),
    State("metadata-store", "data"),
    prevent_initial_call=True,
)
def update_metadata(
    n_a,
    n_b,
    n_c,
    selected_grid_year,
    selected_grid_scenario,
    selected_emission_type,
    selected_shortrun_weighting,
    ref_leakage,
    gea_grid_region,
    metadata_data,
):
    trigger = ctx.triggered_id
    trigger_val = ctx.triggered[0]["value"] if ctx.triggered else None

    # prevent firing on first page load
    if not trigger or trigger_val in (None, 0):
        raise dash.exceptions.PreventUpdate

    metadata = Metadata(**metadata_data)

    # Map button IDs to scenario IDs
    mapping = {
        "update-scen-A": "em_scenario_a",
        "update-scen-B": "em_scenario_b",
        "update-scen-C": "em_scenario_c",
    }

    scen_id = mapping.get(trigger)

    scenario = metadata.get_emission_scenario(scen_id)

    # Update with new values if provided
    if selected_grid_year is not None:
        scenario.year = selected_grid_year
    if selected_grid_scenario is not None:
        scenario.grid_scenario = selected_grid_scenario
    if selected_emission_type is not None:
        scenario.emission_type = selected_emission_type
    if selected_shortrun_weighting is not None:
        scenario.shortrun_weighting = selected_shortrun_weighting
    if ref_leakage is not None:
        scenario.annual_refrig_leakage_percent = (
            ref_leakage / 100
        )  # convert % to fraction
    if gea_grid_region is not None:
        scenario.gea_grid_region = gea_grid_region

    # print(f"Updated scenario: {scenario}")
    # Save back into metadata
    if trigger in ["update-scen-A", "update-scen-B", "update-scen-C"]:
        metadata.add_emission_scenario(scenario, overwrite=True)

    return metadata.model_dump()


@callback(
    Output("summary-emissions-info", "children"),
    Input("metadata-store", "data"),
    State("active-emissions-tab", "data"),
)
def show_emissions_scenarios(data, active_tab):
    if not data or data is None:
        raise dash.exceptions.PreventUpdate

    return summary_emissions_selection(data, active_tab)


@callback(
    [
        Output("ng-emission-factor-unit", "children"),
        Output("ng-emission-factor-unit", "placeholder"),
        Output("ng-emission-factor-input", "value"),
    ],
    [
        Input("unit-toggle", "value"),  # "SI" or "IP"
        State("ng-emission-factor-input", "value"),
    ],
)
def update_static_emission_fields(unit_mode, ref_value):
    conversion = unit_map["gas_emission_factor"][unit_mode]

    unit = conversion["label"]
    gas_emission_factor_placeholder = conversion["default_value"]

    # Convert existing user inputs to SI if they exist
    gas_value_si = conversion["func"](ref_value) if ref_value is not None else None

    return unit, gas_emission_factor_placeholder, gas_value_si


@callback(
    Output("active-emissions-tab", "data"),
    Input("emission-scenario-tabs", "active_tab"),
    prevent_initial_call=True,
)
def store_active_emissions_tab(active_tab):
    return active_tab


@callback(
    Output("site-energy-store", "data"),
    Input("button-calculate", "n_clicks"),
    State("metadata-store", "data"),
    State("equipment-store", "data"),
    prevent_initial_call=True,
)
def run_loads_to_site(n_clicks, metadata_json, equipment_json):
    if not n_clicks or n_clicks < 1:
        return no_update  # do nothing until button clicked at least once

    if not metadata_json or not equipment_json:
        return no_update

    metadata = Metadata(**metadata_json) if metadata_json else None
    equipment = EquipmentLibrary(**equipment_json) if equipment_json else None

    load_data = get_load_data(metadata)

    site_energy = loads_to_site_energy(
        load_data, equipment, metadata.equipment_scenarios, detail=True
    )

    # site_energy.to_csv("site_energy_debug.csv")  # for debugging

    return site_energy.to_json(date_format="iso", orient="split")


@callback(
    Output("source-energy-store", "data"),
    Output("calc-status-toast", "children"),
    Input("site-energy-store", "data"),
    State("metadata-store", "data"),
    prevent_initial_call=True,
)
def run_site_to_source(site_energy_json, metadata_json):
    site_energy = pd.read_json(StringIO(site_energy_json), orient="split")
    metadata = Metadata(**metadata_json) if metadata_json else None

    # print(metadata.emission_settings)

    source_energy = site_to_source(site_energy, metadata=metadata)

    return (
        source_energy.to_json(date_format="iso", orient="split"),
        dbc.Toast(
            "Calculation finished!",
            duration=3000,
            is_open=True,
            style={
                "position": "fixed",
                "top": 66,
                "right": 50,
                "width": 250,
                "zIndex": 9999,
            },
            header=[
                DashIconify(
                    icon="ei:check",
                    width=20,
                ),
                "Success",
            ],
        ),
    )
