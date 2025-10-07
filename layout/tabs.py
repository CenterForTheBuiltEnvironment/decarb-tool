import dash
from dash import dcc, html

import dash_bootstrap_components as dbc

from layout.input import unit_toggle


def tabs():
    return dbc.Container(
        children=[
            html.Div(id="initial-load", style={"display": "none"}),
            dcc.Location(id="url", refresh=True),
            dbc.Row(
                dbc.Nav(
                    [
                        # left-aligned navigation items
                        *[
                            dbc.NavItem(
                                dbc.NavLink(
                                    page["name"],
                                    href=page["path"],
                                    id=f"navlink-{page['name']}",
                                    active="exact",
                                ),
                            )
                            for page in dash.page_registry.values()
                        ],
                        # right-aligned toggle
                        dbc.NavItem(
                            unit_toggle(), className="ms-auto"  # pushes it to the right
                        ),
                    ],
                    className="align-items-center",  # vertical alignment
                    pills=True,
                ),
            ),
            html.Hr(),
            dbc.Row(dash.page_container),
        ]
    )
