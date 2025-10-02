from dash import html, dcc
import dash_bootstrap_components as dbc


def meter_timeseries_chart():

    return html.Div(
        [
            html.Div(
                [
                    dcc.Dropdown(
                        id="equipment-scen-dropdown",
                        options=[
                            {
                                "label": f"Eq. Scenario {i}",
                                "value": f"eq_scenario_{i}",
                            }
                            for i in range(1, 6)
                        ],  # to be populated dynamically
                        value="eq_scenario_1",
                        placeholder="Equipment Scenarios",
                        style={"width": "220px"},
                    ),
                    dcc.Dropdown(
                        id="emission-scen-dropdown",
                        options=[
                            {
                                "label": f"Em. Scenario {chr(96 + i)}",
                                "value": f"em_scenario_{chr(96 + i)}",
                            }
                            for i in range(1, 4)
                        ],  # to be populated dynamically
                        value="em_scenario_a",
                        placeholder="Emission Scenarios",
                        style={"width": "220px"},
                    ),
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
                        style={"width": "120px"},
                    ),
                ],
                className="d-flex align-items-center justify-content-center mb-1 gap-2",
            ),
            dcc.Loading(type="default", children=dcc.Graph(id="meter-timeseries-plot")),
        ]
    )


def total_emissions_chart():
    return html.Div(
        [
            html.Div(
                [
                    dcc.Dropdown(
                        id="total-equipment-scen-dropdown",
                        options=[
                            {
                                "label": "Equip. 1",
                                "value": "eq_scenario_1",
                            },
                            {
                                "label": "Equip. 2",
                                "value": "eq_scenario_2",
                            },
                            {
                                "label": "Equip. 3",
                                "value": "eq_scenario_3",
                            },
                            {
                                "label": "Equip. 4",
                                "value": "eq_scenario_4",
                            },
                            {
                                "label": "Equip. 5",
                                "value": "eq_scenario_5",
                            },
                        ],  # to be populated dynamically
                        multi=True,
                        value=["eq_scenario_1", "eq_scenario_2"],
                        placeholder="Equipment Scenarios",
                        style={"width": "300px"},
                    ),
                    dcc.Dropdown(
                        id="total-emission-scen-dropdown",
                        options=[
                            {
                                "label": f"Em.{chr(96 + i)}",
                                "value": f"em_scenario_{chr(96 + i)}",
                            }
                            for i in range(1, 4)
                        ],  # to be populated dynamically
                        multi=True,
                        value=["em_scenario_a", "em_scenario_b", "em_scenario_c"],
                        placeholder="Emission Scenarios",
                        style={"width": "300px"},
                    ),
                ],
                className="d-flex align-items-center justify-content-center mb-1 gap-2",
            ),
            dcc.Loading(type="default", children=dcc.Graph(id="total-emissions-plot")),
        ]
    )


def chart_two():
    return dcc.Graph(id="chart-two")


def chart_tabs():

    active_label_style = {"color": "#EF4692", "fontWeight": "bold"}

    return dbc.Tabs(
        [
            dbc.Tab(
                total_emissions_chart(),
                label="Total Emissions",
                active_label_style=active_label_style,
            ),
            dbc.Tab(
                meter_timeseries_chart(),
                label="Meter Timeseries",
                active_label_style=active_label_style,
            ),
            dbc.Tab(
                chart_two(), label="Heatmap", active_label_style=active_label_style
            ),
            dbc.Tab("This tab's content is never seen", label="Plot 4", disabled=True),
        ],
        className="mb-3",
        id="chart-tabs",
    )
