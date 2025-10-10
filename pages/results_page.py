import json

import dash
from dash import html, dcc, Input, Output, State, callback
import dash_bootstrap_components as dbc

import pandas as pd
import plotly.express as px

from io import StringIO

from src.config import URLS

from layout.input import (
    emission_rate_dropdown,
    emission_period_slider,
    results_utility_bar,
    filter_sidebar,
    settings_sidebar,
)

from layout.output import summary_project_info, summary_scenario_results

from layout.charts import chart_tabs

from src.metadata import Metadata
from src.visuals import (
    plot_meter_timeseries,
    plot_energy_and_emissions,
    plot_emission_scenarios_grouped,
    plot_emissions_heatmap,
)

dash.register_page(__name__, name="Results", path=URLS.RESULTS.value, order=3)


def layout():
    return dbc.Container(
        children=[
            dbc.Row(
                [
                    dbc.Col(
                        [
                            html.Div(id="building-info-results"),
                            html.Hr(),
                            summary_scenario_results(),
                            html.Hr(),
                            dbc.Button(
                                "Download Results",
                                color="primary",
                                id="download-button",
                                n_clicks=0,
                                active=False,
                            ),
                        ],
                        width=3,
                    ),
                    dbc.Col(
                        [
                            # results_utility_bar(),
                            chart_tabs(),
                            html.Hr(),
                        ],
                        width=9,
                    ),
                ]
            ),
            dcc.Download(id="download-data"),
            # filter_sidebar(),
            # settings_sidebar(),
        ],
        fluid=True,
    )


@callback(
    Output("building-info-results", "children"),
    Input("metadata-store", "data"),
)
def show_metadata(data):
    if not data:
        return "No metadata yet"

    return summary_project_info(data)


@callback(
    Output("meter-timeseries-plot", "figure"),
    Input("equipment-scen-dropdown", "value"),
    Input("emission-scen-dropdown", "value"),
    Input("stacked-toggle", "value"),
    Input("gas-toggle", "value"),
    Input("frequency-dropdown", "value"),
    Input("source-energy-store", "data"),
    Input("unit-toggle", "value"),
    # prevent_initial_call=True
)
def update_meter_plot(
    equipment_scenarios,
    emission_scenarios,
    stacked_value,
    gas_value,
    frequency_value,
    source_json,
    unit_mode,
):
    if not source_json:
        return px.line(x=[0, 1], y=[0, 0], title="Waiting for data...")

    df = pd.read_json(StringIO(source_json), orient="split")

    # flags from toggles
    stacked = "stacked" in stacked_value
    include_gas = "gas" in gas_value
    frequency_value = frequency_value if frequency_value else "D"

    fig = plot_meter_timeseries(
        df,
        equipment_scenarios,
        emission_scenarios,
        stacked=stacked,
        include_gas=include_gas,
        freq=frequency_value,
        unit_mode=unit_mode,
    )
    return fig


@callback(
    Output("energy-and-emissions-plot", "figure"),
    Input("source-energy-store", "data"),
    Input("total-equipment-scen-dropdown", "value"),
    Input("total-emission-scen-dropdown", "value"),
    Input("unit-toggle", "value"),
    # prevent_initial_call=True
)
def update_total_emissions_plot(
    source_json, equipment_scenarios, emission_scenario, unit_mode
):
    if not source_json:
        return px.line(x=[0, 1], y=[0, 0], title="Waiting for data...")

    df = pd.read_json(StringIO(source_json), orient="split")

    # Ensure equipment_scenarios and emission_scenario are lists
    # if isinstance(equipment_scenarios, str):
    #     equipment_scenarios = [equipment_scenarios]
    if isinstance(emission_scenario, str):
        emission_scenario = [emission_scenario]

    fig = plot_energy_and_emissions(
        df, equipment_scenarios, emission_scenario, unit_mode=unit_mode
    )
    return fig


@callback(
    Output("emissions-bar-plot", "figure"),
    Input("source-energy-store", "data"),
    Input("emission-em-scen-dropdown", "value"),
    Input("unit-toggle", "value"),
    # prevent_initial_call=True
)
def update_emissions_bar_plot(source_json, emission_scenarios, unit_mode):
    if not source_json:
        return px.line(x=[0, 1], y=[0, 0], title="Waiting for data...")

    df = pd.read_json(StringIO(source_json), orient="split")

    equipment_scenarios = df["scenario_id"].unique().tolist()

    # Ensure emission_scenarios is a list
    if isinstance(emission_scenarios, str):
        emission_scenarios = [emission_scenarios]

    fig = plot_emission_scenarios_grouped(
        df, equipment_scenarios, emission_scenarios, unit_mode=unit_mode
    )
    return fig


@callback(
    Output("emissions-heatmap-plot", "figure"),
    Input("source-energy-store", "data"),
    Input("heatmap-equipment-scen-dropdown", "value"),
    Input("heatmap-emission-scen-dropdown", "value"),
    Input("heatmap-emission-type-dropdown", "value"),
    Input("unit-toggle", "value"),
    # prevent_initial_call=True
)
def update_emissions_heatmap(
    source_json, equipment_scenario, emission_scenario, emission_type, unit_mode
):
    if not source_json:
        return px.line(x=[0, 1], y=[0, 0], title="Waiting for data...")

    df = pd.read_json(StringIO(source_json), orient="split")

    fig = plot_emissions_heatmap(
        df,
        equipment_scenario,
        emission_scenario,
        unit_mode=unit_mode,
        emission_type=emission_type,
    )
    return fig
