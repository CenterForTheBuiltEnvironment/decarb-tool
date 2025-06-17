import dash
from dash import html, dcc
import dash_bootstrap_components as dbc

from utils.config import URLS

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
                            # PLACHOLDER COMPONENT IMPORT
                            html.Hr(),
                            dbc.Button(
                                "Upload Emissions Data",
                                id="upload-emissions-button",
                                color="primary",
                            ),
                            html.Hr(),
                            dbc.Label(),
                            # PLACHOLDER COMPONENT IMPORT
                        ],
                        width=4,
                    ),
                    dbc.Col(
                        [],
                        width=6,
                    ),
                    dbc.Col(
                        [],
                        width=2,
                    ),
                ]
            )
        ],
        fluid=True,
    )
