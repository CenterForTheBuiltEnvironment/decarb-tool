import dash_bootstrap_components as dbc
from dash import dcc, html
import pandas as pd
import json

with open("data/input/metadata_index.json", "r") as f:
    metadata_index = json.load(f)


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
                "Select the building location. This will also set the corresponding ASHRAE climate zone for the analysis."
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
