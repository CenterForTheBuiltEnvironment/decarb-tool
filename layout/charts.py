from dash import html, dcc
import dash_bootstrap_components as dbc


def meter_timeseries_chart():

    return html.Div(
        [
            html.Div(
                [
                    dbc.Checklist(
                        id="stacked-toggle",
                        options=[{"label": "Stacked", "value": "stacked"}],
                        value=["stacked"],  # default on
                        inline=True,
                    ),
                    dbc.Checklist(
                        id="gas-toggle",
                        options=[{"label": "Include Gas", "value": "gas"}],
                        value=["gas"],  # default on
                        inline=True,
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
                        clearable=False,
                        style={"width": "250px"},
                    ),
                ],
                className="d-flex align-items-center justify-content-center mb-1 gap-2",
            ),
            dcc.Loading(type="default", children=dcc.Graph(id="meter-timeseries-plot")),
        ]
    )


def chart_one():
    return dcc.Graph(id="chart-one")


def chart_two():
    return dcc.Graph(id="chart-two")


def chart_tabs():

    active_label_style = {"color": "#EF4692", "fontWeight": "bold"}

    return dbc.Tabs(
        [
            dbc.Tab(
                meter_timeseries_chart(),
                label="Chart X",
                active_label_style=active_label_style,
            ),
            dbc.Tab(
                chart_one(), label="Chart Y", active_label_style=active_label_style
            ),
            dbc.Tab(
                chart_two(), label="Chart Z", active_label_style=active_label_style
            ),
            dbc.Tab("This tab's content is never seen", label="Tab 3", disabled=True),
        ],
        className="mb-3",
        id="chart-tabs",
    )
