from dash import html, dcc
import dash_bootstrap_components as dbc

def meter_timeseries_chart():

    return html.Div([
        html.Div([
            dbc.Checklist(
                id="stacked-toggle",
                options=[{"label": "Stacked", "value": "stacked"}],
                value=["stacked"],  # default on
                inline=True
            ),
            dbc.Checklist(
                id="gas-toggle",
                options=[{"label": "Include Gas", "value": "gas"}],
                value=["gas"],  # default on
                inline=True
            ),
            dcc.Dropdown(
                id="frequency-dropdown",
                options=[
                    {"label": "Hourly", "value": "h"},
                    {"label": "Daily", "value": "D"},
                    {"label": "Weekly", "value": "W"},
                    {"label": "Monthly", "value": "ME"},
                ],
                value="D", 
                clearable=False
            ),
        ], className="mb-2"),
        dcc.Loading(
            type="default",
            children=dcc.Graph(id="meter-timeseries-plot")
        )
    ])
