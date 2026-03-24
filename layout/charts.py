import dash_mantine_components as dmc
from dash import dcc


def _controls_bar(children):
    return dmc.Group(
        children,
        justify="flex-start",
        align="center",
        gap="sm",
        wrap="wrap",
        mb="xs",
    )


def _chart_block(controls, graph_id, height=600):
    return dmc.Stack(
        [
            dmc.Space(h=5),
            controls,
            dmc.Paper(
                dcc.Loading(
                    type="default",
                    children=dcc.Graph(
                        id=graph_id,
                        style={"height": f"{height}px", "width": "100%"},
                        config={"responsive": True},
                    ),
                ),
                shadow="xs",
                radius="md",
                p="md",
                style={"minHeight": f"{height + 120}px"},  # Account for padding
            ),
            dmc.Space(h=5),
        ],
        gap="xs",
    )


def _emission_scen_seed():
    return [
        {
            "label": f"Emission Scenario {chr(96 + i)}",
            "value": f"em_scenario_{chr(96 + i)}",
        }
        for i in range(1, 4)
    ]


def emissions_bar_chart():
    controls = _controls_bar(
        [
            dmc.MultiSelect(
                id="emission-em-scen-dropdown",
                data=_emission_scen_seed(),  # will be overwritten dynamically
                value=["em_scenario_a", "em_scenario_b", "em_scenario_c"],
                placeholder="Emission Scenarios",
                searchable=True,
                clearable=True,
            ),
        ]
    )
    return _chart_block(controls, "emissions-bar-plot")


def energy_emissions_chart():
    controls = _controls_bar(
        [
            dmc.MultiSelect(
                id="total-equipment-scen-dropdown",
                data=[],  # dynamic
                value=[],  # dynamic
                placeholder="Equipment Scenarios",
                searchable=True,
                clearable=True,
            ),
            dmc.Select(
                id="total-emission-scen-dropdown",
                data=_emission_scen_seed(),  # dynamic later
                value="em_scenario_a",
                placeholder="Emission Scenarios",
                searchable=True,
                clearable=False,
                allowDeselect=False,
            ),
        ]
    )
    return _chart_block(controls, "energy-and-emissions-plot")


def meter_timeseries_chart():
    controls = _controls_bar(
        [
            dmc.Select(
                id="equipment-scen-dropdown",
                data=[],  # dynamic
                value=None,  # dynamic
                placeholder="Equipment Scenarios",
                searchable=True,
                clearable=False,
                allowDeselect=False,
            ),
            dmc.Select(
                id="emission-scen-dropdown",
                data=_emission_scen_seed(),  # dynamic later
                value="em_scenario_a",
                placeholder="Emission Scenarios",
                searchable=True,
                clearable=False,
                allowDeselect=False,
            ),
            dmc.CheckboxGroup(
                id="stacked-toggle",
                value=["stacked"],
                children=[dmc.Checkbox(label="Stacked", value="stacked")],
            ),
            dmc.CheckboxGroup(
                id="gas-toggle",
                value=["gas"],
                children=[dmc.Checkbox(label="Include Gas", value="gas")],
            ),
            dmc.Text("Aggregation:", size="sm", fw=500),
            dmc.Select(
                id="frequency-dropdown",
                data=[
                    {"label": "Hourly", "value": "h"},
                    {"label": "Daily", "value": "D"},
                    {"label": "Weekly", "value": "W"},
                    {"label": "Monthly", "value": "ME"},
                ],
                value="D",
                clearable=False,
                allowDeselect=False,
            ),
        ]
    )
    return _chart_block(controls, "meter-timeseries-plot")


def emissions_heatmap_chart():
    controls = _controls_bar(
        [
            dmc.Select(
                id="heatmap-equipment-scen-dropdown",
                data=[],  # dynamic
                value=None,  # dynamic
                placeholder="Equipment Scenarios",
                searchable=True,
                clearable=False,
                allowDeselect=False,
            ),
            dmc.Select(
                id="heatmap-emission-scen-dropdown",
                data=_emission_scen_seed(),  # dynamic later
                value="em_scenario_a",
                placeholder="Emission Scenarios",
                searchable=True,
                clearable=False,
                allowDeselect=False,
            ),
            dmc.Select(
                id="heatmap-emission-type-dropdown",
                data=[
                    {"label": "Electricity", "value": "elec_emissions"},
                    {"label": "Gas", "value": "gas_emissions"},
                    {"label": "Total (inc. Refrig.)", "value": "total_emissions"},
                ],
                value="elec_emissions",
                placeholder="Category",
                searchable=True,
                clearable=False,
                allowDeselect=False,
            ),
        ]
    )
    return _chart_block(controls, "emissions-heatmap-plot")


def scatter_chart():
    controls = dmc.Group(
        [
            dmc.MultiSelect(
                id="scatter-equipment-scen-dropdown",
                data=[],  # dynamic
                value=[],  # dynamic
                placeholder="Equipment Scenarios",
                searchable=True,
                clearable=False,
            ),
            dmc.Select(
                id="scatter-emission-scen-dropdown",
                data=_emission_scen_seed(),  # dynamic later
                value="em_scenario_a",
                placeholder="Emission Scenarios",
                searchable=True,
                clearable=False,
                allowDeselect=False,
            ),
            dmc.Select(
                id="scatter-yvar-dropdown",
                data=[
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
                searchable=True,
                clearable=False,
                allowDeselect=False,
            ),
            dmc.Group(
                [
                    dmc.Text("Aggregation:", size="sm", fw=500),
                    dmc.Select(
                        id="scatter-frequency-dropdown",
                        data=[
                            {"label": "Weekly", "value": "W"},
                            {"label": "Daily", "value": "D"},
                        ],
                        value="D",
                        clearable=False,
                        allowDeselect=False,
                    ),
                ],
                gap="sm",
            ),
        ],
        justify="flex-start",
        align="center",
        gap="sm",
        wrap="wrap",
        mb="xs",
    )
    return _chart_block(controls, "scatter-plot")


def chart_tabs():
    return dmc.Tabs(
        [
            dmc.TabsList(
                [
                    dmc.TabsTab("Emissions", value="emissions"),
                    dmc.TabsTab("Energy + Emissions", value="energy"),
                    dmc.TabsTab("Timeseries", value="timeseries"),
                    dmc.TabsTab("Heatmap", value="heatmap"),
                    dmc.TabsTab("Scatter", value="scatter"),
                ]
            ),
            dmc.TabsPanel(emissions_bar_chart(), value="emissions"),
            dmc.TabsPanel(energy_emissions_chart(), value="energy"),
            dmc.TabsPanel(meter_timeseries_chart(), value="timeseries"),
            dmc.TabsPanel(emissions_heatmap_chart(), value="heatmap"),
            dmc.TabsPanel(scatter_chart(), value="scatter"),
        ],
        id="chart-tabs",
        value="emissions",
        mt="sm",
        keepMounted=True,  # Keep all tabs rendered to prevent layout shift on tab switch
    )
