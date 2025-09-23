import dash_bootstrap_components as dbc
from dash import dcc, html
from dash_iconify import DashIconify
import pandas as pd
import json

from utils.units import unit_map

with open("data/input/metadata_index.json", "r") as f:
    metadata_index = json.load(f)


def unit_toggle():
    return dbc.RadioItems(
        id="unit-toggle",
        options=[
            {"label": "SI", "value": "SI"},
            {"label": "IP", "value": "IP"},
        ],
        value="SI",
        inline=True,
    )


def select_location(locations_df: pd.DataFrame):

    #! Use metadata_index here
    options = [
        {
            "label": f"{row['zip']} {row['city']}, {row['state_id']}",
            "value": row["zip"],
        }
        for _, row in locations_df.iterrows()
    ]
    return html.Div(
        [
            dbc.Label("1. Building Location"),
            html.P(
                "Select the building location. This will set the corresponding ASHRAE climate zone used for the analysis."
            ),
            html.Br(),
            dcc.Dropdown(
                id="location-input",
                options=options,
                placeholder="Search by city or zip...",
                searchable=True,
                clearable=True,
            ),
        ]
    )


def select_load_data():
    return html.Div(
        [
            dbc.Label(
                "2. Load Data",
            ),
            html.Br(),
            html.P("Select the type of load data you want to use for analysis."),
            html.Br(),
            dbc.Accordion(
                [
                    dbc.AccordionItem(
                        [
                            html.P(
                                "Use pre-simulated data for different building types."
                            ),
                            dbc.Button(
                                "Select Pre-Simulated Data",
                                color="secondary",
                                id="open-load-simulation-data-modal",
                            ),
                        ],
                        title="Pre-Simulated Data",
                    ),
                    dbc.AccordionItem(
                        [
                            html.P("Use measured data from real buildings."),
                            dbc.Button("Select building", color="secondary"),
                        ],
                        title="Measured Data",
                    ),
                    dbc.AccordionItem(
                        [
                            html.P("Upload your own hourly load data."),
                            dbc.Button("Upload Custom Data", color="secondary"),
                        ],
                        title="Upload Custom Data",
                    ),
                ],
                start_collapsed=True,
                flush=True,
            ),
        ]
    )


def set_emission_year():

    year_options = metadata_index["emissions"]["year"]

    return html.Div(
        [
            dbc.Label("3. Grid Year"),
            dcc.Slider(
                id="emission-year-input",
                min=min(year_options),
                max=max(year_options),
                step=5,
                included=False,
                value=min(year_options),
                marks={year: str(year) for year in year_options},
                tooltip={"placement": "bottom", "always_visible": True},
            ),
        ]
    )


def select_grid_scenario():
    options = [
        {
            "label": type,
            "value": type,
        }
        for type in metadata_index["emissions"]["emission_scenario"]
    ]
    return html.Div(
        [
            dbc.Label("4. Grid Scenario"),
            # html.P(
            #     "Select the grid emission scenario to use for the analysis. This will set the grid emission factors over time."
            # ),
            dcc.Dropdown(
                id="emission-scenario-input",
                options=options,
                value="MidCase",
            ),
        ]
    )


def set_shortrun_weighting():
    return html.Div(
        [
            dbc.Label("5. Short-Run Weighting"),
            # html.P(
            #     "Set the short-run weighting factor to adjust the importance of short-run marginal emission rates in the analysis."
            # ),
            dcc.Slider(
                id="shortrun-weighting-input",
                min=0.0,
                max=1.0,
                step=0.1,
                value=0.0,
                marks={0: "0", 0.5: "0.5", 1: "1"},
                # marks={i / 10: str(i / 10) for i in range(0, 11)},
                tooltip={"placement": "bottom", "always_visible": True},
            ),
        ]
    )


def set_static_emissions(unit_mode="SI"):

    conversion = unit_map["static_emission_intensity"][unit_mode]
    placeholder = conversion["label"]

    return html.Div(
        [
            dbc.Label("6. Static Emission Factors"),
            html.P("Annual Refrigerant Leakage."),
            dcc.Input(
                id="refrigerant-leakage-input",
                type="number",
                placeholder=placeholder,
                value=None,
                style={"width": "50%"},
            ),
            html.Hr(),
            html.P("Annual Natural Gas Leakage."),
            dcc.Input(
                id="natural-gas-leakage-input",
                type="number",
                placeholder=placeholder,
                value=None,
                style={"width": "50%"},
            ),
        ]
    )


def scenario_saving_buttons():
    return html.Div(
        [
            html.P("Save as:"),
            html.Div(
                [
                    dbc.Button(
                        "Scenario A",
                        color="secondary",
                    ),
                    html.Span(" "),  # spacer
                    dbc.Button("Scenario B", color="secondary"),
                    html.Span(" "),  # spacer
                    dbc.Button("Scenario C", color="secondary"),
                ],
                style={
                    "backgroundColor": "#f8f9fa",
                    "padding": "5px",
                    "borderRadius": "5px",
                },
            ),
        ],
    )


def modal_load_simulation_data():

    building_type_options = [
        {
            "label": type,
            "value": type,
        }
        for type in metadata_index["load_data_simulated"]["building_type"]
    ]

    vintage_options = [
        {
            "label": type,
            "value": type,
        }
        for type in metadata_index["load_data_simulated"]["vintage"]
    ]

    return dbc.Modal(
        [
            dbc.ModalHeader("Select Pre-Simulated Data"),
            dbc.ModalBody(
                [
                    html.P("Choose a building type:"),
                    dbc.RadioItems(
                        options=building_type_options,
                        id="building-type-input",
                    ),
                    html.Br(),
                    html.P("Choose a building vintage:"),
                    dbc.RadioItems(
                        options=vintage_options,
                        id="vintage-input",
                        value=vintage_options[0]["value"],
                    ),
                    # html.Br(),
                    # dbc.Button("Load Data", color="primary", id="load-data-button"), #! can be removed, load should happen in one step
                ]
            ),
            dbc.ModalFooter(
                dbc.Button(
                    "Close",
                    id="button-close-simulation-data-modal",
                    className="ml-auto",
                )
            ),
        ],
        id="modal-load-simulation-data",
        size="lg",
    )


def filter_equipment_type():

    options = [
        {
            "label": type,
            "value": type,
        }
        for type in metadata_index["equipment"]["equipment_type"]
    ]
    return html.Div(
        [
            dbc.Label("Filter by Equipment Type"),
            dcc.Dropdown(
                id="equipment-type-input",
                options=options,
                placeholder="Select equipment type...",
                clearable=True,
            ),
        ]
    )


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


def emission_period_slider():
    return html.Div(
        [
            html.Small("Emission Year", className="text-muted"),
            html.Br(),
            dcc.Slider(
                id="year-slider",
                min=0,  # placeholder
                max=0,  # placeholder
                step=None,
                marks={},
                value=0,
                tooltip={"placement": "bottom", "always_visible": True},
            ),
        ]
    )


def results_utility_bar():
    return html.Div(
        [
            dbc.Button(
                DashIconify(icon="mdi:filter-variant", width=24),
                id="open-filter",
                color="secondary",
            ),
            dbc.Button(
                DashIconify(icon="mdi:cog-outline", width=24),
                id="open-settings",
                color="secondary",
            ),
        ],
        className="d-flex justify-content-end p-2",
    )


# Sidebar panels
def filter_sidebar():
    return dbc.Offcanvas(
        [
            html.H5("Scenarios", className="mb-3"),
            dbc.Checklist(
                options=[
                    {"label": "Scenario A", "value": "A"},
                    {"label": "Scenario B", "value": "B"},
                ],
                value=["A"],
                id="filter-checklist",
            ),
            html.Hr(),
            html.H5("Emissions", className="mb-3"),
            emission_period_slider(),  # no metadata passed in
            html.Hr(),
            emission_rate_dropdown(),
        ],
        id="filter-sidebar",
        placement="start",
        is_open=False,
    )


def settings_sidebar():
    return dbc.Offcanvas(
        [
            html.H5("Settings", className="mb-3"),
            dbc.Switch(id="dark-mode", label="Enable Dark Mode", value=False),
        ],
        id="settings-sidebar",
        title="Settings",
        placement="end",
        is_open=False,
    )
