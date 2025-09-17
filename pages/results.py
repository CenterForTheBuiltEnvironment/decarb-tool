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

from src.visuals import plot_meter_timeseries

dash.register_page(__name__, path=URLS.RESULTS.value, order=2)


def layout():
    return dbc.Container(
        children=[
            dbc.Row(
                [
                    dbc.Col(
                        [
                            html.Div(id="building-info-results"),
                            # dbc.Label("Emissions"),
                            # html.Hr(),
                            # emission_period_slider(),
                            # html.Hr(),
                            # emission_rate_dropdown(),
                            html.Hr(),
                            summary_scenario_results(),
                            html.Hr(),
                            dbc.Button(
                                "Download Results",
                                color="primary",
                            ),
                        ],
                        width=3,
                    ),
                    dbc.Col(
                        [
                            dbc.Label(
                                [
                                    "Results-Info",
                                    html.Br(),
                                    html.Small(
                                        "Subtitle with additional information",
                                        className="text-muted",
                                    ),
                                ]
                            ),
                            results_utility_bar(),
                            chart_tabs(),
                            html.Hr(),
                        ],
                        width=9,
                    ),
                ]
            ),
            filter_sidebar(),
            settings_sidebar(),
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
    Output("filter-sidebar", "is_open"),
    Input("open-filter", "n_clicks"),
    State("filter-sidebar", "is_open"),
    prevent_initial_call=True,
)
def toggle_filter(n, is_open):
    return not is_open


@callback(
    Output("settings-sidebar", "is_open"),
    Input("open-settings", "n_clicks"),
    State("settings-sidebar", "is_open"),
    prevent_initial_call=True,
)
def toggle_settings(n, is_open):
    return not is_open


@callback(
    Output("meter-timeseries-plot", "figure"),
    Input("stacked-toggle", "value"),
    Input("gas-toggle", "value"),
    Input("frequency-dropdown", "value"),
    Input("source-energy-store", "data"),
    # prevent_initial_call=True
)
def update_meter_plot(stacked_value, gas_value, frequency_value, source_json):
    if not source_json:
        return px.line(x=[0, 1], y=[0, 0], title="Waiting for data...")

    df = pd.read_json(StringIO(source_json), orient="split")

    elec_cols = [
        "elec_hr_Wh",
        "elec_awhp_h_Wh",
        "elec_chiller_Wh",
        "elec_awhp_c_Wh",
        "elec_res_Wh",
    ]
    gas_cols = ["gas_boiler_Wh"]

    all_cols = elec_cols + gas_cols
    df = df[[c for c in all_cols if c in df.columns]]

    # flags from toggles
    stacked = "stacked" in stacked_value
    include_gas = "gas" in gas_value
    frequency_value = frequency_value if frequency_value else "D"

    fig = plot_meter_timeseries(
        df, stacked=stacked, include_gas=include_gas, freq=frequency_value
    )
    return fig
