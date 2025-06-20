import dash
from dash import html, Input, Output, State, callback
import dash_bootstrap_components as dbc

from utils.config import URLS

from components.input import (
    select_location,
    select_load_data,
    modal_load_simulation_data,
)

dash.register_page(__name__, path=URLS.HOME.value, order=0)


def layout():
    return dbc.Container(
        children=[
            dbc.Row(
                [
                    dbc.Col(
                        [
                            html.H2("Welcome to the Berkeley Decarb Tool"),
                            html.P(
                                "Please enter the information below to get started."
                            ),
                        ],
                        width=12,
                    ),
                ],
            ),
            dbc.Row(
                [
                    dbc.Col(
                        [
                            select_location(),
                            html.Hr(),
                            select_load_data(),
                            modal_load_simulation_data(),
                            html.Hr(),
                            dbc.Button(
                                "Specify Equipment",
                                color="secondary",
                            ),
                            dbc.Button(
                                "Calculate Emissions",
                                color="primary",
                            ),
                        ],
                        width=5,
                    ),
                    dbc.Col(
                        [],
                        width=7,
                    ),
                ],
            ),
        ]
    )


@callback(
    Output("modal-load-simulation-data", "is_open"),
    [
        Input("open-load-simulation-data-modal", "n_clicks"),
        Input("button-close-simulation-data-modal", "n_clicks"),
    ],
    [State("modal-load-simulation-data", "is_open")],
)
def toggle_modal(open_clicks, close_clicks, is_open):
    if open_clicks or close_clicks:
        return not is_open
    return is_open
