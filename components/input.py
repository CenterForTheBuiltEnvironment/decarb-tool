import dash_bootstrap_components as dbc
from dash import dcc, html


def select_location():
    return html.Div(
        [
            dbc.Label(
                "1. Building Location",
            ),
            html.Br(),
            dbc.Input(
                type="text",
                placeholder="Enter location...",
                id="location-input",
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
    return dbc.Modal(
        [
            dbc.ModalHeader("Select Pre-Simulated Data"),
            dbc.ModalBody(
                [
                    html.P("Choose a building type:"),
                    dbc.RadioItems(
                        options=[
                            {"label": "Residential", "value": "residential"},
                            {"label": "Commercial", "value": "commercial"},
                            {"label": "Industrial", "value": "industrial"},
                        ],
                        value="residential",
                        id="building-type-radio",
                    ),
                    html.Br(),
                    dbc.Button("Load Data", color="primary", id="load-data-button"),
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
