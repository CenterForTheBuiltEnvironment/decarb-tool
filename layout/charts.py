from dash import html, dcc
import dash_bootstrap_components as dbc


def emissions_bar_chart():
    return html.Div(
        [
            html.Div(
                [
                    dcc.Dropdown(
                        id="emission-em-scen-dropdown",
                        options=[
                            {
                                "label": f"Emission Scenario {chr(96 + i)}",
                                "value": f"em_scenario_{chr(96 + i)}",
                            }
                            for i in range(1, 4)
                        ],  # to be populated dynamically
                        multi=True,
                        value=["em_scenario_a", "em_scenario_b", "em_scenario_c"],
                        placeholder="Emission Scenarios",
                        style={"width": "800px"},
                    ),
                ],
                className="d-flex align-items-center justify-content-center mb-1 gap-2",
            ),
            dcc.Graph(id="emissions-bar-plot"),
        ]
    )


def energy_emissions_chart():
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
                        value=[
                            "eq_scenario_1",
                            "eq_scenario_2",
                            "eq_scenario_3",
                            "eq_scenario_4",
                            "eq_scenario_5",
                        ],
                        placeholder="Equipment Scenarios",
                        style={"width": "550px"},
                    ),
                    dcc.Dropdown(
                        id="total-emission-scen-dropdown",
                        options=[
                            {
                                "label": f"Emission Scenario {chr(96 + i)}",
                                "value": f"em_scenario_{chr(96 + i)}",
                            }
                            for i in range(1, 4)
                        ],  # to be populated dynamically
                        multi=False,
                        value="em_scenario_a",
                        placeholder="Emission Scenarios",
                        style={"width": "250px"},
                    ),
                ],
                className="d-flex align-items-center justify-content-center mb-1 gap-2",
            ),
            dcc.Graph(id="energy-and-emissions-plot"),
        ]
    )


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
                        style={"width": "200px"},
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
                        style={"width": "200px"},
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
                    dbc.Label("Aggregation:", style={"marginBottom": "2.5px"}),
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
            dcc.Graph(id="meter-timeseries-plot"),
        ]
    )


def emissions_heatmap_chart():
    return html.Div(
        [
            html.Div(
                [
                    dcc.Dropdown(
                        id="heatmap-equipment-scen-dropdown",
                        options=[
                            {
                                "label": f"Equipment Scenario {i}",
                                "value": f"eq_scenario_{i}",
                            }
                            for i in range(1, 6)
                        ],  # to be populated dynamically
                        value="eq_scenario_1",
                        placeholder="Equipment Scenarios",
                        style={"width": "300px"},
                    ),
                    dcc.Dropdown(
                        id="heatmap-emission-scen-dropdown",
                        options=[
                            {
                                "label": f"Emission Scenario {chr(96 + i)}",
                                "value": f"em_scenario_{chr(96 + i)}",
                            }
                            for i in range(1, 4)
                        ],  # to be populated dynamically
                        value="em_scenario_a",
                        placeholder="Emission Scenarios",
                        style={"width": "300px"},
                    ),
                    dcc.Dropdown(
                        id="heatmap-emission-type-dropdown",
                        options=[
                            {"label": "Electricity", "value": "elec_emissions"},
                            {"label": "Gas", "value": "gas_emissions"},
                            {
                                "label": "Total (inc. Refrig.)",
                                "value": "total_emissions",
                            },
                        ],
                        value="elec_emissions",
                        placeholder="Category",
                        style={"width": "200px"},
                    ),
                ],
                className="d-flex align-items-center justify-content-center mb-1 gap-2",
            ),
            dcc.Graph(id="emissions-heatmap-plot"),
        ]
    )


def scatter_chart():
    return html.Div(
        [
            html.Div(
                [
                    dcc.Dropdown(
                        id="scatter-equipment-scen-dropdown",
                        options=[
                            {
                                "label": f"Equipment Scenario {i}",
                                "value": f"eq_scenario_{i}",
                            }
                            for i in range(1, 6)
                        ],  # to be populated dynamically
                        multi=True,
                        value=[
                            "eq_scenario_1",
                            "eq_scenario_2",
                            "eq_scenario_3",
                            "eq_scenario_4",
                            "eq_scenario_5",
                        ],
                        placeholder="Equipment Scenarios",
                        clearable=False,
                        style={"width": "500px"},
                    ),
                    html.Div(
                        [
                            dcc.Dropdown(
                                id="scatter-emission-scen-dropdown",
                                options=[
                                    {
                                        "label": f"Emission Scenario {chr(96 + i)}",
                                        "value": f"em_scenario_{chr(96 + i)}",
                                    }
                                    for i in range(1, 4)
                                ],  # to be populated dynamically
                                value="em_scenario_a",
                                placeholder="Emission Scenarios",
                                clearable=False,
                                style={"width": "300px"},
                            ),
                            dcc.Dropdown(
                                id="scatter-yvar-dropdown",
                                options=[
                                    {
                                        "label": "Electricity Emissions",
                                        "value": "elec_emissions",
                                    },
                                    {
                                        "label": "Gas Emissions",
                                        "value": "gas_emissions",
                                    },
                                    {
                                        "label": "Total Emissions (inc. Refrig.)",
                                        "value": "total_emissions",
                                    },
                                    {"label": "Electricity Use", "value": "elec_Wh"},
                                    {"label": "Gas Use", "value": "gas_Wh"},
                                ],
                                value="total_emissions",
                                placeholder="Y Variable",
                                clearable=False,
                                style={"width": "300px"},
                            ),
                            html.Div(
                                [
                                    dbc.Label("Aggregation:"),
                                    dcc.Dropdown(
                                        id="scatter-frequency-dropdown",
                                        options=[
                                            {"label": "Weekly", "value": "W"},
                                            {"label": "Daily", "value": "D"},
                                        ],
                                        value="D",
                                        clearable=False,
                                        style={"width": "120px"},
                                    ),
                                ],
                                style={
                                    "display": "flex",
                                    "gap": "10px",
                                    "justifyContent": "center",
                                    "alignItems": "center",
                                },
                            ),
                        ],
                        style={
                            "display": "flex",
                            "flex-direction": "column",
                            "gap": "5px",
                        },
                    ),
                ],
                className="d-flex align-items-top justify-content-center mb-1 gap-2",
            ),
            dcc.Graph(id="scatter-plot"),
        ]
    )


def chart_tabs():

    active_label_style = {"color": "#EF4692", "fontWeight": "bold"}

    return dbc.Tabs(
        [
            dbc.Tab(
                dcc.Loading(
                    id="loading-icon",
                    type="default",
                    children=emissions_bar_chart(),
                ),
                label="Emissions",
                active_label_style=active_label_style,
            ),
            dbc.Tab(
                dcc.Loading(
                    id="loading-icon",
                    type="default",
                    children=energy_emissions_chart(),
                ),
                label="Energy + Emissions",
                active_label_style=active_label_style,
            ),
            dbc.Tab(
                dcc.Loading(
                    id="loading-icon",
                    type="default",
                    children=meter_timeseries_chart(),
                ),
                label="Timeseries",
                active_label_style=active_label_style,
            ),
            dbc.Tab(
                dcc.Loading(
                    id="loading-icon",
                    type="default",
                    children=emissions_heatmap_chart(),
                ),
                label="Heatmap",
                active_label_style=active_label_style,
            ),
            dbc.Tab(
                dcc.Loading(
                    id="loading-icon",
                    type="default",
                    children=scatter_chart(),
                ),
                label="Scatter",
                active_label_style=active_label_style,
            ),
        ],
        className="mb-3",
        id="chart-tabs",
    )
