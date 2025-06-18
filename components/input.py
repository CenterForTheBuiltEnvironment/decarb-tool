import dash_bootstrap_components as dbc
from dash import dcc, html


def emission_rate_dropdown():
    return html.Div(
        [
            html.Small(
                "Emission Rate",
                className="text-muted",
            ),
            html.Br(),
            dbc.Select(
                options=[
                    {"label": "LRMER", "value": "lrmer"},
                    {"label": "SRMER", "value": "srmer"},
                    {"label": "Total Emissions", "value": "total"},
                ],
                value="srmer",
            ),
        ]
    )


def emission_data_upload_button():
    return dbc.Button(
        "Upload Emissions Data",
        color="primary",
    )


def emission_period_slider():
    return html.Div(
        [
            html.Small(
                "Emission Period",
                className="text-muted",
            ),
            html.Br(),
            dcc.Slider(
                id="year-slider",
                min=2020,
                max=2050,
                step=5,
                value=2025,
                marks={i: str(i) for i in range(2020, 2060, 10)},
            ),
        ]
    )
