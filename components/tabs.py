import dash
from dash import dcc, html

import dash_bootstrap_components as dbc


def tabs():
    return dbc.Container(
        children=[
            html.Div(id="initial-load", style={"display": "none"}),
            dcc.Location(id="url", refresh=True),
            dbc.Row(
                dbc.Nav(
                    [
                        dbc.NavItem(
                            dbc.NavLink(
                                page["name"],
                                href=page["path"],
                            )
                        )
                        for page in dash.page_registry.values()
                    ],
                ),
            ),
            html.Hr(),
            dbc.Row(dash.page_container),
        ]
    )
