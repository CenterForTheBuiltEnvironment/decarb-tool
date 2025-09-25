import dash
from dash import dcc, html, Input, Output, State, callback, ctx, no_update
import dash_bootstrap_components as dbc

from src.config import URLS

from utils.units import unit_map

from src.metadata import Metadata, EmissionScenario

from layout.input import (
    scenario_saving_buttons,
    select_grid_scenario,
    set_emission_type,
    set_grid_year,
    set_shortrun_weighting,
    set_static_emissions,
)

from layout.output import summary_emissions_selection

dash.register_page(__name__, name="Emissions", path=URLS.EMISSIONS.value, order=2)


def layout():
    return dbc.Container(
        children=[
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
                        width=4,
                    ),
                    dbc.Col(
                        [
                            html.Hr(),
                            set_static_emissions(),
                            html.Hr(),
                            html.Hr(),
                            scenario_saving_buttons(),
                        ],
                        width=3,
                    ),
                    dbc.Col(
                        [
                            html.H5("Summary"),
                            html.Hr(),
                            html.Div(
                                id="summary-emissions-info",
                            ),
                        ],
                        width=5,
                    ),
                ]
            )
        ]
    )


@callback(Output("summary-emissions-info", "children"), Input("metadata-store", "data"))
def show_metadata(data):
    if not data:
        return "No metadata yet"

    return summary_emissions_selection(data)


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
    State("natural-gas-leakage-input", "value"),
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
    ng_leakage,
    metadata_data,
):
    trigger = ctx.triggered_id
    if not trigger:
        return metadata_data

    metadata = Metadata(**metadata_data)

    # Map button IDs to scenario IDs
    mapping = {
        "update-scen-A": "em_scenario_a",
        "update-scen-B": "em_scenario_b",
        "update-scen-C": "em_scenario_c",
    }

    scen_id = mapping.get(trigger)
    if not scen_id:
        return metadata_data

    try:
        scenario = metadata.get_emission_scenario(scen_id)
    except KeyError:
        # If it doesn't exist yet, create one
        scenario = EmissionScenario(
            em_scen_id=scen_id,
            grid_scenario="MidCase",
            gea_grid_region="CAISO",
            time_zone="America/Los_Angeles",
            emission_type="Combustion only",
            shortrun_weighting=1.0,
            annual_refrig_leakage=0.01,
            annual_ng_leakage=0.005,
            year=2025,
        )

    # Update with new values if provided
    if selected_grid_year is not None:
        scenario.year = selected_grid_year
    if selected_grid_scenario:
        scenario.grid_scenario = selected_grid_scenario
    if selected_emission_type:
        scenario.emission_type = selected_emission_type
    if selected_shortrun_weighting is not None:
        scenario.shortrun_weighting = selected_shortrun_weighting
    if ref_leakage is not None:
        scenario.annual_refrig_leakage = ref_leakage
    if ng_leakage is not None:
        scenario.annual_ng_leakage = ng_leakage

    # Save back into metadata
    metadata.add_emission_scenario(scenario, overwrite=True)

    return metadata.model_dump()


@callback(
    [
        Output("refrigerant-leakage-unit", "children"),
        Output("natural-gas-leakage-unit", "children"),
        Output("refrigerant-leakage-input", "placeholder"),
        Output("natural-gas-leakage-input", "placeholder"),
        Output("refrigerant-leakage-input", "value"),
        Output("natural-gas-leakage-input", "value"),
    ],
    [
        Input("unit-toggle", "value"),  # "SI" or "IP"
        State("refrigerant-leakage-input", "value"),
        State("natural-gas-leakage-input", "value"),
    ],
)
def update_static_emission_fields(unit_mode, ref_value, gas_value):
    conversion = unit_map["static_emission_intensity"][unit_mode]

    unit = conversion["label"]
    refrig_placeholder = conversion["refrig_default"]
    ng_placeholder = conversion["ng_default"]

    # Convert existing user inputs to SI if they exist
    ref_value_si = conversion["func"](ref_value) if ref_value is not None else None
    gas_value_si = conversion["func"](gas_value) if gas_value is not None else None

    return unit, unit, refrig_placeholder, ng_placeholder, ref_value_si, gas_value_si
