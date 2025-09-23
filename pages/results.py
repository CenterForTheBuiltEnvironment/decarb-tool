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
    Output("year-slider", "min"),
    Output("year-slider", "max"),
    Output("year-slider", "marks"),
    Output("year-slider", "step"),
    Output("year-slider", "value"),
    Input("metadata-store", "data"),
)
def update_year_slider(data):
    if not data:
        # keep placeholder state
        return 0, 0, {}, None, 0

    # assume metadata is JSON -> rehydrate
    metadata = Metadata(**data)
    year_options = metadata.emissions.years

    return (
        min(year_options),
        max(year_options),
        {year: str(year) for year in year_options},
        10 if len(year_options) > 1 else None,
        min(year_options),
    )


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
    Input("year-slider", "value"),
    Input("stacked-toggle", "value"),
    Input("gas-toggle", "value"),
    Input("frequency-dropdown", "value"),
    Input("source-energy-store", "data"),
    Input("unit-toggle", "value"),
    # prevent_initial_call=True
)
def update_meter_plot(
    emission_year, stacked_value, gas_value, frequency_value, source_json, unit_mode
):
    if not source_json:
        return px.line(x=[0, 1], y=[0, 0], title="Waiting for data...")

    df = pd.read_json(StringIO(source_json), orient="split")

    year = emission_year

    # flags from toggles
    stacked = "stacked" in stacked_value
    include_gas = "gas" in gas_value
    frequency_value = frequency_value if frequency_value else "D"

    fig = plot_meter_timeseries(
        df,
        year,
        stacked=stacked,
        include_gas=include_gas,
        freq=frequency_value,
        unit_mode=unit_mode,
    )
    return fig
