import dash
from dash import html
import dash_bootstrap_components as dbc

from src.config import URLS

from layout.input import filter_equipment_type

dash.register_page(__name__, path=URLS.EQUIPMENT.value, order=1)


def layout():
    return dbc.Container(
        children=[
            dbc.Row(
                [
                    dbc.Col(
                        [
                            html.H4("Specify Equipment"),
                            filter_equipment_type(),
                        ],
                        width=8,
                    ),
                    dbc.Col(
                        [
                            html.H4("Summary"),
                            html.P("This page is under construction."),
                        ],
                        width=4,
                    ),
                ]
            )
        ]
    )
