import dash
from dash import html
import dash_bootstrap_components as dbc

from utils.config import URLS

from components.input import select_location, select_load_data

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
