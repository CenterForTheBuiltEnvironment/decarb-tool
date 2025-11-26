import dash_bootstrap_components as dbc
from dash import dcc, html
from dash_iconify import DashIconify
import dash_mantine_components as dmc
import pandas as pd
import json
from pathlib import Path

from utils.units import unit_map

META_INDEX_PATH = Path("data/input/metadata_index.json")
with META_INDEX_PATH.open("r") as f:
    METADATA_INDEX = json.load(f)

LOAD_INDEX = METADATA_INDEX["load_data_full"]


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


# --------------------------------
# LOADS page inputs
# --------------------------------


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
            dbc.Label(
                "Building Location",
                style={"fontWeight": "bold", "marginBottom": "10px"},
            ),
            html.P(
                "Select the building location. This will set the corresponding ASHRAE climate zone used for the analysis."
            ),
            dcc.Dropdown(
                id="location-input",
                options=options,
                placeholder="Search by city or zip...",
                searchable=True,
                clearable=True,
            ),
        ]
    )


def select_load_type():
    return html.Div(
        [
            dbc.Label(
                "Load Data",
                style={"fontWeight": "bold", "marginBottom": "10px"},
            ),
            html.Br(),
            html.P("Select the type of load data you want to use for analysis."),
            dbc.Accordion(
                [
                    dbc.AccordionItem(
                        [
                            html.P(
                                "Choose from a library of pre-simulated and measured load profiles."
                            ),
                            dbc.Button(
                                "Open Library",
                                color="secondary",
                                id="open-load-library-modal",
                            ),
                        ],
                        title="Select From Library",
                    ),
                    dbc.AccordionItem(
                        [
                            html.P("Upload your own hourly load data in CSV format."),
                            dcc.Upload(
                                id="upload-data",
                                children=dbc.Button(
                                    [
                                        "Upload Custom Data ",
                                        DashIconify(
                                            icon="material-symbols:upload", width=20
                                        ),
                                    ],
                                    color="secondary",
                                ),
                                accept=".csv",
                                multiple=False,
                            ),
                            html.Div(id="upload-data-alert", className="mt-2"),
                        ],
                        title="Upload Custom Data",
                    ),
                ],
                start_collapsed=True,
                flush=True,
            ),
        ]
    )


def build_building_table(buildings_data, selected_id=None):
    """
    Build a table from a DataFrame with predefined columns.
    Only displays columns that exist in the data.
    """
    # Define desired columns with their display names
    column_config = [
        ("location", "Location"),
        ("ashrae_climate_zone", "Climate Zone"),
        ("building_type", "Building Type"),
        ("load_type", "Source"),
        ("area_sqm", "Area [m²]"),
        ("hhw_max_load", "Peak HHW Load [W]"),
        ("chw_max_load", "Peak CHW Load [W]"),
        ("annual_heating_cooling_ratio", "Annual H/C Ratio"),
        ("min_temp", "Min Temp [°C]"),
        ("max_temp", "Max Temp [°C]"),
    ]

    available_columns = [
        (col, label) for col, label in column_config if col in buildings_data.columns
    ]

    # Build body rows
    body_rows = []
    for idx, row in buildings_data.iterrows():
        cells = [
            dmc.TableTd(dmc.Radio(value=str(row.get("building_id", idx))))
        ]  # use 'building_id' field or index
        cells.extend([dmc.TableTd(str(row[col])) for col, _ in available_columns])
        body_rows.append(dmc.TableTr(cells))

    # Build header
    header_cells = [dmc.TableTh("")]  # radio column
    header_cells.extend([dmc.TableTh(label) for _, label in available_columns])
    header = dmc.TableThead(dmc.TableTr(header_cells))

    body = dmc.TableTbody(body_rows)

    table = dmc.ScrollArea(
        dmc.Table(
            [header, body],
            striped=True,
            highlightOnHover=True,
            withColumnBorders=False,
            horizontalSpacing="sm",
            verticalSpacing="xs",
        ),
        h=400,  # Set height in pixels
        type="auto",
    )

    return dmc.RadioGroup(
        id="building-radio-group",
        value=selected_id,
        children=table,
    )


def modal_load_data_selection(buildings_df: pd.DataFrame):

    # --- options from metadata_index.json ----------------------------------
    building_type_options = sorted(LOAD_INDEX["building_type"])
    climate_zone_options = sorted(LOAD_INDEX["ashrae_climate_zone"])
    load_type_options = ["all"] + LOAD_INDEX["load_type"]

    area_min, area_max = LOAD_INDEX["area_sqm"]
    hhw_min, hhw_max = LOAD_INDEX["hhw_max_load"]
    chw_min, chw_max = LOAD_INDEX["chw_max_load"]

    return dmc.Modal(
        title="Load Data Library",
        children=[
            dmc.Text(
                "Select simulated or measured load data from library.",
                fw=400,
                size="sm",
            ),
            dmc.Space(h="md"),
            # ------------------ FILTER CONTROLS ----------------------------
            dmc.Stack(
                gap="xl",
                children=[
                    dmc.Group(
                        align="space-between",
                        justify="space-around",
                        gap="lg",
                        children=[
                            # Load type
                            dmc.Select(
                                id="load-type-filter",
                                label="Load type",
                                data=[
                                    {"value": v, "label": v.capitalize()}
                                    for v in load_type_options
                                ],
                                value="all",
                                clearable=False,
                                style={"width": 180},
                            ),
                            # Climate zone
                            dmc.Select(
                                id="climate-filter",
                                label="Climate zone",
                                placeholder="All",
                                data=[
                                    {"value": cz, "label": cz}
                                    for cz in climate_zone_options
                                ],
                                value=None,
                                clearable=True,
                                style={"width": 180},
                            ),
                            # Building type
                            dmc.Select(
                                id="building-type-filter",
                                label="Building type",
                                placeholder="All",
                                data=[
                                    {"value": bt, "label": bt}
                                    for bt in building_type_options
                                ],
                                value=None,
                                clearable=True,
                                searchable=True,
                                style={"width": 220},
                            ),
                            dmc.Stack(
                                [
                                    dmc.Text("Area (m²)", size="sm", fw=500),
                                    dmc.RangeSlider(
                                        id="area-range-slider",
                                        min=area_min,
                                        max=area_max,
                                        step=500,
                                        value=[area_min, area_max],
                                        marks=[
                                            {"value": area_min, "label": str(area_min)},
                                            {"value": area_max, "label": str(area_max)},
                                        ],
                                        style={"width": 250},
                                    ),
                                ],
                            ),
                            dmc.Stack(
                                [
                                    dmc.Text("HHW Peak Load [W]", size="sm", fw=500),
                                    dmc.RangeSlider(
                                        id="hhw-range-slider",
                                        min=hhw_min,
                                        max=hhw_max,
                                        step=1000,
                                        value=[hhw_min, hhw_max],
                                        marks=[
                                            {"value": hhw_min, "label": str(hhw_min)},
                                            {"value": hhw_max, "label": str(hhw_max)},
                                        ],
                                        style={"width": 250},
                                    ),
                                ],
                            ),
                            dmc.Stack(
                                [
                                    dmc.Text("CHW Peak Load [W]", size="sm", fw=500),
                                    dmc.RangeSlider(
                                        id="chw-range-slider",
                                        min=chw_min,
                                        max=chw_max,
                                        step=1000,
                                        value=[chw_min, chw_max],
                                        marks=[
                                            {"value": chw_min, "label": str(chw_min)},
                                            {"value": chw_max, "label": str(chw_max)},
                                        ],
                                        style={"width": 250},
                                    ),
                                ],
                            ),
                        ],
                    ),
                ],
            ),
            dmc.Space(h="xl"),
            # ------------------ TABLE + CONFIRM ----------------------------
            html.Div(
                id="building-table-container",
                children=build_building_table(buildings_df, selected_id=None),
            ),
            dmc.Space(h="xl"),
            dmc.Group(
                justify="space-between",
                align="center",
                children=[
                    dmc.Text(
                        id="selected-building-text",
                        children="No building selected yet.",
                        c="dimmed",
                        size="sm",
                    ),
                    dmc.Button(
                        "Confirm selection",
                        id="confirm-building-button",
                        variant="filled",
                        disabled=True,
                    ),
                ],
            ),
            dcc.Store(id="selected-building-store"),
        ],
        id="modal-load-data",
        size="80%",
        radius="md",
        centered=True,
        withCloseButton=True,
    )


# --------------------------------
# EQUIPMENT page inputs
# --------------------------------


def with_none_option(options, none_label="None"):
    return [{"label": none_label, "value": "None"}] + options


def select_equipment(equipment_data):

    equipment_list = equipment_data.get("equipment", [])

    def options_for(eq_type):
        return [
            {
                "label": f"{eq.get('model', '')} ({eq.get('eq_subtype', '')})",
                "value": eq.get("eq_id"),
            }
            for eq in equipment_list
            if eq.get("eq_type") == eq_type
        ]

    hr_heat_pump_options = with_none_option(options_for("hr_heat_pump"))
    heat_pump_options = with_none_option(options_for("heat_pump"))

    boiler_options = [
        {
            "label": f"{eq.get('model', '')} ({eq.get('eq_subtype', '')})",
            "value": eq.get("eq_id"),
        }
        for eq in equipment_list
        if eq.get("eq_type") == "boiler"
    ]

    chiller_options = [
        {
            "label": f"{eq.get('model', '')} ({eq.get('eq_subtype', '')})",
            "value": eq.get("eq_id"),
        }
        for eq in equipment_list
        if eq.get("eq_type") == "chiller"
    ]

    label_styling = {"width": "180px", "align": "right"}

    return html.Div(
        [
            dbc.InputGroup(
                [
                    dbc.InputGroupText("HR Heat Pump", style=label_styling),
                    dbc.Select(
                        id="hr-wwhp-input",
                        options=hr_heat_pump_options,
                        value=(
                            hr_heat_pump_options[1]["value"]
                            if hr_heat_pump_options
                            else None
                        ),
                    ),
                ]
            ),
            dbc.InputGroup(
                [
                    dbc.InputGroupText("Heat Pump", style=label_styling),
                    dbc.Select(
                        id="awhp-input",
                        options=heat_pump_options,
                        value=(
                            heat_pump_options[1]["value"] if heat_pump_options else None
                        ),
                    ),
                ]
            ),
            html.Hr(style={"marginTop": "10px", "marginBottom": "10px"}),
            dbc.Label("Heat Pump Sizing", style=label_styling),
            html.Div(
                children=[
                    dbc.RadioItems(
                        id="awhp-sizing-radio",
                        options=[
                            {"label": "% Peak Load", "value": "peak_load_percentage"},
                            {"label": "No. Units", "value": "num_of_units"},
                        ],
                        value="peak_load_percentage",
                        inline=True,
                        style={"marginRight": "15px"},
                    ),
                    html.Div(
                        dcc.Slider(
                            id="awhp-sizing-slider",
                            min=0,
                            max=1,
                            step=0.05,
                            value=0.85,
                            marks={i: f"{i * 100}%" for i in range(0, 21, 5)},
                            tooltip={"placement": "bottom", "always_visible": True},
                        ),
                        style={"flex": "1"},  # make slider expand
                    ),
                ],
                style={"display": "flex", "alignItems": "center", "gap": "10px"},
            ),
            dbc.Checkbox(
                label="Use Heat Pump also for Cooling",
                id="awhp-use-cooling",
                style={"marginTop": "10px", "marginBottom": "10px"},
            ),
            html.Hr(
                style={
                    "marginTop": "25px",
                    "marginBottom": "10px",
                    "borderTop": "2px solid grey",
                }
            ),
            dbc.Label(
                "Backup Equipment", style={"fontWeight": "bold", "marginBottom": "20px"}
            ),
            dbc.InputGroup(
                [
                    dbc.InputGroupText("Heating", style=label_styling),
                    dbc.Select(
                        id="boiler-input",
                        options=boiler_options,
                        value=(boiler_options[0]["value"] if boiler_options else None),
                    ),
                ]
            ),
            dbc.InputGroup(
                [
                    dbc.InputGroupText("Cooling", style=label_styling),
                    dbc.Select(
                        id="chiller-input",
                        options=chiller_options,
                        value=(
                            chiller_options[0]["value"] if chiller_options else None
                        ),
                    ),
                ]
            ),
        ]
    )


def set_grid_year():

    year_options = METADATA_INDEX["emissions"]["year"]

    return html.Div(
        [
            dbc.Label("Grid Year"),
            dcc.Slider(
                id="grid-year-input",
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
        for type in METADATA_INDEX["emissions"]["emission_scenario"]
    ]
    return html.Div(
        [
            dbc.Label("Grid Scenario"),
            # html.P(
            #     "Select the grid emission scenario to use for the analysis. This will set the grid emission factors over time."
            # ),
            dcc.Dropdown(
                id="grid-scenario-input",
                options=options,
                value="MidCase",
            ),
        ]
    )


def set_emission_type():
    options = [
        {
            "label": type,
            "value": type,
        }
        for type in METADATA_INDEX["emissions"]["emission_type"]
    ]
    return html.Div(
        [
            dbc.Label("Emission Type", style={"fontWeight": "bold"}),
            dbc.RadioItems(
                id="emission-type-input",
                options=options[
                    ::-1
                ],  # reverse order to have "Includes pre-combustion" first
                value="Includes pre-combustion",
                inline=True,
            ),
        ]
    )


def set_shortrun_weighting():
    return html.Div(
        [
            dbc.Label("Short-Run Weighting"),
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

    conversion = unit_map["gas_emission_factor"][unit_mode]
    gas_emission_factor_placeholder = conversion["default_value"]

    return html.Div(
        [
            dbc.Label("Static Emission Factors", style={"fontWeight": "bold"}),
            html.P("Annual Refrigerant Leakage."),
            html.Div(
                children=[
                    dcc.Input(
                        id="refrigerant-leakage-input",
                        type="number",
                        value=5,
                        style={"width": "40%"},
                        step=1,
                    ),
                    html.Div("%", style={"marginLeft": "8px"}),
                ],
                style={"display": "flex", "alignItems": "center"},
            ),
            html.Br(),
            html.P("Natural Gas Emission Factor"),
            html.Div(
                children=[
                    dcc.Input(
                        id="ng-emission-factor-input",
                        type="number",
                        value=gas_emission_factor_placeholder,
                        style={"width": "40%"},
                        step=1,
                        readOnly=True,
                        disabled=True,
                    ),
                    html.Div(
                        "gCO₂e/kWh",
                        style={"marginLeft": "8px"},
                        id="ng-emission-factor-unit",
                    ),  # fixed unit
                ],
                style={"display": "flex", "alignItems": "center"},
            ),
        ]
    )


def select_gea_grid_region():
    options = [
        {
            "label": region,
            "value": region,
        }
        for region in METADATA_INDEX["emissions"]["gea_grid_region"]
    ]
    return html.Div(
        [
            dbc.Label(
                "GEA Grid Region",
                style={"fontWeight": "bold", "marginBottom": "10px"},
            ),
            html.P("Select the GEA grid region to use for the analysis."),
            dcc.Dropdown(
                id="gea-grid-region-input",
                options=options,
                value="CAISO",
            ),
        ]
    )


def equipment_scenario_saving_buttons():
    return html.Div(
        [
            html.P("Save my current equipment settings as:"),
            dbc.ButtonGroup(
                [
                    dbc.Button(
                        "Scenario 1",
                        id="update-eq-scen-1",
                        outline=True,
                        color="secondary",
                    ),
                    dbc.Button(
                        "Scenario 2",
                        id="update-eq-scen-2",
                        outline=True,
                        color="secondary",
                    ),
                    dbc.Button(
                        "Scenario 3",
                        id="update-eq-scen-3",
                        outline=True,
                        color="secondary",
                    ),
                    dbc.Button(
                        "Scenario 4",
                        id="update-eq-scen-4",
                        outline=True,
                        color="secondary",
                    ),
                    dbc.Button(
                        "Scenario 5",
                        id="update-eq-scen-5",
                        outline=True,
                        color="secondary",
                    ),
                ],
                size="md",
                vertical=False,
            ),
            # Store to remember which button was clicked
            dcc.Store(id="scenario-trigger-store"),
            # Modal for name input
            dbc.Modal(
                [
                    dbc.ModalHeader(dbc.ModalTitle("Save Scenario")),
                    dbc.ModalBody(
                        dbc.Input(
                            id="scenario-name-input",
                            placeholder="Enter scenario name...",
                            type="text",
                        )
                    ),
                    dbc.ModalFooter(
                        dbc.Button(
                            "Confirm", id="confirm-scenario-name", color="primary"
                        )
                    ),
                ],
                id="scenario-name-modal",
                is_open=False,
                backdrop="static",
                keyboard=False,
                centered=True,
            ),
            html.Hr(),
        ],
    )


def emission_scenario_saving_buttons():
    return html.Div(
        [
            html.P("Save my current settings as:"),
            dbc.ButtonGroup(
                [
                    dbc.Button(
                        "Scenario A",
                        id="update-scen-A",
                        outline=True,
                        color="secondary",
                        n_clicks=0,
                    ),
                    # html.Span(" "),  # spacer
                    dbc.Button(
                        "Scenario B",
                        id="update-scen-B",
                        outline=True,
                        color="secondary",
                        n_clicks=0,
                    ),
                    # html.Span(" "),  # spacer
                    dbc.Button(
                        "Scenario C",
                        id="update-scen-C",
                        outline=True,
                        color="secondary",
                        n_clicks=0,
                    ),
                ],
                size="md",
                vertical=False,
            ),
        ],
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
