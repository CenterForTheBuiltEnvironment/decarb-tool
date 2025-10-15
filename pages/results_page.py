import os

import dash
from dash import html, dcc, Input, Output, State, callback
import dash_bootstrap_components as dbc

import pandas as pd
import plotly.express as px
from pathlib import Path

from io import StringIO

from src.config import URLS

from layout.output import summary_project_info, summary_scenario_results

from layout.charts import chart_tabs

from src.metadata import Metadata
from src.visuals import (
    plot_meter_timeseries,
    plot_energy_and_emissions,
    plot_emission_scenarios_grouped,
    plot_emissions_heatmap,
    plot_scatter_temp_vs_variable,
)

dash.register_page(__name__, name="Results", path=URLS.RESULTS.value, order=3)


DATA_PATH = "data/output"  #  where session files are stored


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
        ],
        fluid=True,
    )


def load_source_energy(session_data):
    """Load the source energy dataframe for this user session."""
    if not session_data or "id" not in session_data:
        return None

    session_id = session_data["id"]
    filepath = os.path.join(DATA_PATH, session_id, "source_energy.pkl")

    if not os.path.exists(filepath):
        return None

    try:
        return pd.read_pickle(filepath)
    except Exception as e:
        print(f"[ERROR] Failed to load source_energy.pkl for session {session_id}: {e}")
        return None


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
    Input("session-store", "data"),
    Input("equipment-scen-dropdown", "value"),
    Input("emission-scen-dropdown", "value"),
    Input("stacked-toggle", "value"),
    Input("gas-toggle", "value"),
    Input("frequency-dropdown", "value"),
    Input("unit-toggle", "value"),
    # prevent_initial_call=True
)
def update_meter_plot(
    session_data,
    equipment_scenarios,
    emission_scenarios,
    stacked_value,
    gas_value,
    frequency_value,
    unit_mode,
):

    df = load_source_energy(session_data)
    if df is None:
        return px.line(x=[0, 1], y=[0, 0], title="Waiting for data...")

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
    Input("session-store", "data"),
    Input("total-equipment-scen-dropdown", "value"),
    Input("total-emission-scen-dropdown", "value"),
    Input("unit-toggle", "value"),
)
def update_total_emissions_plot(
    session_data, equipment_scenarios, emission_scenario, unit_mode
):
    df = load_source_energy(session_data)
    if df is None:
        return px.line(x=[0, 1], y=[0, 0], title="Waiting for data...")

    if isinstance(emission_scenario, str):
        emission_scenario = [emission_scenario]

    fig = plot_energy_and_emissions(
        df, equipment_scenarios, emission_scenario, unit_mode=unit_mode
    )
    return fig


@callback(
    Output("emissions-bar-plot", "figure"),
    Input("session-store", "data"),
    Input("emission-em-scen-dropdown", "value"),
    Input("unit-toggle", "value"),
    # prevent_initial_call=True
)
def update_emissions_bar_plot(session_data, emission_scenarios, unit_mode):

    df = load_source_energy(session_data)
    if df is None:
        return px.line(x=[0, 1], y=[0, 0], title="Waiting for data...")

    equipment_scenarios = df["eq_scen_id"].unique().tolist()

    # Ensure emission_scenarios is a list
    if isinstance(emission_scenarios, str):
        emission_scenarios = [emission_scenarios]

    fig = plot_emission_scenarios_grouped(
        df, equipment_scenarios, emission_scenarios, unit_mode=unit_mode
    )
    return fig


@callback(
    Output("emissions-heatmap-plot", "figure"),
    Input("session-store", "data"),
    Input("heatmap-equipment-scen-dropdown", "value"),
    Input("heatmap-emission-scen-dropdown", "value"),
    Input("heatmap-emission-type-dropdown", "value"),
    Input("unit-toggle", "value"),
    # prevent_initial_call=True
)
def update_emissions_heatmap(
    session_data, equipment_scenario, emission_scenario, emission_type, unit_mode
):
    df = load_source_energy(session_data)
    if df is None:
        return px.line(x=[0, 1], y=[0, 0], title="Waiting for data...")

    fig = plot_emissions_heatmap(
        df,
        equipment_scenario,
        emission_scenario,
        unit_mode=unit_mode,
        emission_type=emission_type,
    )
    return fig


@callback(
    Output("scatter-plot", "figure"),
    Input("session-store", "data"),
    Input("scatter-equipment-scen-dropdown", "value"),
    Input("scatter-emission-scen-dropdown", "value"),
    Input("scatter-yvar-dropdown", "value"),
    Input("scatter-frequency-dropdown", "value"),
    Input("unit-toggle", "value"),
    # prevent_initial_call=True
)
def update_scatter_plot(
    session_data,
    equipment_scenarios,
    emission_scenario,
    y_variable,
    frequency_value,
    unit_mode,
):
    df = load_source_energy(session_data)
    if df is None:
        return px.line(x=[0, 1], y=[0, 0], title="Waiting for data...")

    frequency_value = frequency_value if frequency_value else "D"

    fig = plot_scatter_temp_vs_variable(
        df,
        y_var=y_variable,
        equipment_scenarios=equipment_scenarios,
        emission_scenarios=[emission_scenario],
        agg=frequency_value,
        unit_mode=unit_mode,
    )
    return fig
