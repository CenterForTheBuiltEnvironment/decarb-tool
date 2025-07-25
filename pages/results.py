import dash
from dash import html, dcc
import dash_bootstrap_components as dbc

from src.config import URLS

from components.input import (
    emission_rate_dropdown,
    emission_data_upload_button,
    emission_period_slider,
)

from components.output import summary_project_info, summary_scenario_results

dash.register_page(__name__, path=URLS.RESULTS.value, order=2)


def layout():
    return dbc.Container(
        children=[
            dbc.Row(
                [
                    dbc.Col(
                        [
                            dbc.Label("Emissions"),
                            html.Hr(),
                            emission_period_slider(),
                            html.Hr(),
                            emission_rate_dropdown(),
                            html.Hr(),
                            emission_data_upload_button(),
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
                            html.Hr(),
                            dcc.Graph(
                                id="results-graph",
                                figure={
                                    "data": [
                                        {
                                            "x": [1, 2, 3],
                                            "y": [4, 1, 2],
                                            "type": "bar",
                                            "name": "Sample Data",
                                        }
                                    ],
                                    "layout": {
                                        "title": "Sample Results Graph",
                                        "xaxis": {"title": "X-axis"},
                                        "yaxis": {"title": "Y-axis"},
                                    },
                                },
                            ),
                            html.Hr(),
                        ],
                        width=6,
                    ),
                    dbc.Col(
                        [
                            summary_project_info(),
                            summary_scenario_results(),
                            html.Hr(),
                            dbc.Button(
                                "Download Results",
                                color="primary",
                            ),
                        ],
                        width=3,
                    ),
                ]
            )
        ],
        fluid=True,
    )
