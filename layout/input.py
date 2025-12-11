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
EMISSIONS_INDEX = METADATA_INDEX["emissions"]


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
                                    disabled=True,
                                ),
                                accept=".csv",
                                multiple=False,
                                disabled=True,
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


def build_equipment_table(equipment_data, active_ids=None):
    """
    Build an equipment scenarios table from a DataFrame or list of dicts.
    Multi-select via checkboxes. selected_ids is a list of eq_scen_id strings
    that are considered *active* (for calc) and will be highlighted.
    """
    if isinstance(equipment_data, list):
        equipment_df = pd.DataFrame(equipment_data)
    else:
        equipment_df = equipment_data

    column_config = [
        ("eq_scen_id", "Scenario ID"),
        ("eq_scen_name", "Scenario Name"),
        ("hr_wwhp", "HR WWHP"),
        ("awhp", "AWHP"),
        ("awhp_sizing_mode", "Sizing Mode"),
        ("awhp_sizing_value", "Sizing Value"),
        ("awhp_redundancy", "Redundancy"),
        ("awhp_use_cooling", "Use Cooling"),
        ("backup_heating", "Backup Heating"),
        ("chiller", "Chiller"),
    ]

    available_columns = [
        (col, label) for col, label in column_config if col in equipment_df.columns
    ]

    active_ids = set(active_ids or [])
    body_rows = []
    for idx, row in equipment_df.iterrows():
        scen_id = row.get("eq_scen_id", idx)
        scen_id_str = str(scen_id)
        is_active = scen_id_str in active_ids

        # Selection checkbox (active for calc)
        checkbox_cell = dmc.TableTd(dmc.Checkbox(value=scen_id_str))

        # Actions: EDIT + REMOVE (trash you already wired up)
        actions_cell = dmc.TableTd(
            dmc.Group(
                [
                    dmc.ActionIcon(
                        DashIconify(icon="mdi:pencil-outline"),
                        id={"type": "equipment-edit-btn", "eq_scen_id": scen_id_str},
                        variant="subtle",
                        size="sm",
                    ),
                    dmc.ActionIcon(
                        DashIconify(icon="mdi:trash-can-outline"),
                        id={"type": "equipment-remove-btn", "eq_scen_id": scen_id_str},
                        variant="subtle",
                        color="red",
                        size="sm",
                    ),
                ],
                gap="xs",
            )
        )

        data_cells = []
        for col, _ in available_columns:
            value = row.get(col, "")
            if isinstance(value, bool):
                value = "Yes" if value else "No"
            data_cells.append(dmc.TableTd(str(value)))

        row_style = {}
        if is_active:
            row_style = {
                "backgroundColor": "var(--mantine-color-blue-0)",
                "fontWeight": 500,
            }

        body_rows.append(
            dmc.TableTr(
                [checkbox_cell, actions_cell, *data_cells],
                style=row_style,
            )
        )

    header_cells = [
        dmc.TableTh(""),
        dmc.TableTh("Actions"),
    ]
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
        h=400,
        type="auto",
    )

    return dmc.CheckboxGroup(
        id="equipment-checkbox-group",
        value=list(active_ids),
        children=table,
    )


def add_equipment_modal():
    return dmc.Modal(
        id="equipment-add-modal",
        opened=False,  # controlled via callback
        title="Add equipment scenario",
        children=dmc.Stack(
            [
                dmc.Select(
                    id="add-base-scenario-select",
                    label="Base scenario",
                    placeholder="Choose scenario to copy",
                    data=[],  # filled from equipment-store
                    searchable=True,
                    nothingFoundMessage="No scenarios",
                    withScrollArea=True,
                ),
                dmc.TextInput(
                    id="add-scenario-id-input",
                    label="New scenario ID",
                    placeholder="e.g. eq_scenario_6",
                ),
                dmc.TextInput(
                    id="add-scenario-name-input",
                    label="New scenario name",
                    placeholder="Descriptive name",
                ),
                dmc.Text(
                    id="add-scenario-error",
                    size="xs",
                    c="red",
                ),
                dmc.Group(
                    [
                        dmc.Button(
                            "Cancel",
                            id="add-scenario-cancel-btn",
                            variant="outline",
                        ),
                        dmc.Button(
                            "Save",
                            id="add-scenario-save-btn",
                        ),
                    ],
                    justify="flex-end",
                    mt="sm",
                ),
            ]
        ),
    )


def edit_equipment_modal():
    return dmc.Modal(
        id="equipment-edit-modal",
        opened=False,
        title="Edit equipment scenario",
        size="lg",
        children=dmc.Stack(
            [
                dmc.Group(
                    [
                        dmc.TextInput(
                            id="edit-scenario-id-input",
                            label="Scenario ID",
                            disabled=True,
                            style={"flex": 1},
                        ),
                        dmc.TextInput(
                            id="edit-scenario-name-input",
                            label="Scenario name",
                            style={"flex": 2},
                        ),
                    ],
                    grow=True,
                ),
                dmc.Divider(label="Heat pump selection", labelPosition="center"),
                dmc.SimpleGrid(
                    cols=2,
                    spacing="md",
                    children=[
                        dmc.Select(
                            id="edit-hr-wwhp-select",
                            label="HR Heat Pump",
                            placeholder="None",
                            data=[],  # filled by callback
                            clearable=True,
                            searchable=True,
                        ),
                        dmc.Select(
                            id="edit-awhp-select",
                            label="Air-to-water Heat Pump",
                            placeholder="None",
                            data=[],
                            clearable=True,
                            searchable=True,
                        ),
                    ],
                ),
                dmc.Divider(label="Heat pump sizing", labelPosition="center"),
                dmc.Stack(
                    [
                        dmc.SegmentedControl(
                            id="edit-awhp-sizing-mode",
                            data=[
                                {
                                    "label": "% peak load (integer)",
                                    "value": "integer_sizing_peak_load",
                                },
                                {
                                    "label": "% peak load (fractional)",
                                    "value": "fractional_sizing_peak_load",
                                },
                                {
                                    "label": "Fixed number of units",
                                    "value": "fixed_num_units",
                                },
                            ],
                            fullWidth=True,
                        ),
                        dmc.Group(
                            [
                                dmc.NumberInput(
                                    id="edit-awhp-sizing-value",
                                    label="Sizing value",
                                    description="% of peak load or number of units",
                                    min=0,
                                    max=5,
                                    step=0.05,  # will be overridden dynamically
                                    style={"flex": 1},
                                ),
                                dmc.NumberInput(
                                    id="edit-awhp-redundancy",
                                    label="Redundant units",
                                    min=0,
                                    max=5,
                                    step=1,
                                    style={"flex": 1},
                                ),
                            ],
                            grow=True,
                        ),
                        dmc.Switch(
                            id="edit-awhp-use-cooling",
                            label="Use heat pump also for cooling",
                            mt="xs",
                        ),
                    ]
                ),
                dmc.Divider(label="Backup equipment", labelPosition="center"),
                dmc.SimpleGrid(
                    cols=2,
                    spacing="md",
                    children=[
                        dmc.Select(
                            id="edit-backup-heating-select",
                            label="Backup heating",
                            placeholder="Select backup heater",
                            data=[],
                            clearable=True,
                            searchable=True,
                        ),
                        dmc.Select(
                            id="edit-chiller-select",
                            label="Chiller",
                            placeholder="Select chiller",
                            data=[],
                            clearable=True,
                            searchable=True,
                        ),
                    ],
                ),
                dmc.Text(
                    id="edit-scenario-error",
                    size="xs",
                    c="red",
                ),
                dmc.Group(
                    [
                        dmc.Button(
                            "Cancel",
                            id="edit-scenario-cancel-btn",
                            variant="outline",
                        ),
                        dmc.Button(
                            "Save",
                            id="edit-scenario-save-btn",
                        ),
                    ],
                    justify="flex-end",
                    mt="sm",
                ),
            ]
        ),
    )


# --------------------------------
# EMISSION page inputs
# --------------------------------


def build_emissions_table(emission_data, active_ids=None):
    """
    Build an emissions scenarios table where:
      - Columns = emission scenarios (em_scen_id)
      - Rows    = properties (year, region, etc.)

    Layout (body rows, after header):
      1) Selected (checkboxes + EDIT / REMOVE)
      2) Scenario ID (em_scen_id)
      3+) Other properties
    """
    if isinstance(emission_data, list):
        emission_df = pd.DataFrame(emission_data)
    else:
        emission_df = emission_data

    if emission_df.empty:
        return dmc.Text("No emission scenarios defined yet.")

    # Ensure an ID for each scenario
    if "em_scen_id" not in emission_df.columns:
        emission_df["em_scen_id"] = [f"em_scen_{i}" for i in range(len(emission_df))]

    # Order scenarios by em_scen_id
    emission_df = emission_df.sort_values("em_scen_id").reset_index(drop=True)

    # Fields we want to show as rows (properties)
    row_config = [
        ("em_scen_id", "Scenario ID"),
        ("grid_scenario", "Grid Scenario"),
        ("gea_grid_region", "GEA Grid Region"),
        ("time_zone", "Time Zone"),
        ("emission_type", "Emission Type"),
        ("shortrun_weighting", "Short-run weighting"),
        ("annual_refrig_leakage_percent", "Refrigerant leakage (frac)"),
        ("annual_ng_leakage_g_per_kWh", "NG leakage (g/kWh)"),
        ("year", "Year"),
    ]

    available_rows = [
        (field, label) for field, label in row_config if field in emission_df.columns
    ]

    active_ids = set(active_ids or [])

    # Style for active vs inactive columns
    active_col_style = {
        "backgroundColor": "var(--mantine-color-blue-0)",
        "fontWeight": 500,
    }
    inactive_col_style = {}

    # ---------- Header row ----------
    header_cells = [dmc.TableTh("Property")]
    scen_ids = []

    for _, scen_row in emission_df.iterrows():
        scen_id = str(scen_row.get("em_scen_id", ""))
        scen_ids.append(scen_id)

        cell_style = active_col_style if scen_id in active_ids else inactive_col_style
        header_cells.append(dmc.TableTh(scen_id, style=cell_style))

    header = dmc.TableThead(dmc.TableTr(header_cells))

    body_rows = []

    # ---------- Row 1: Selected (checkboxes + actions) ----------
    selected_cells = [dmc.TableTh("Selected")]
    for scen_id in scen_ids:
        cell_style = active_col_style if scen_id in active_ids else inactive_col_style
        selected_cells.append(
            dmc.TableTd(
                dmc.Group(
                    [
                        dmc.Checkbox(
                            value=scen_id,
                            checked=scen_id in active_ids,
                        ),
                        dmc.Space("  |  "),  # spacer
                        dmc.ActionIcon(
                            DashIconify(icon="mdi:pencil-outline"),
                            id={"type": "emission-edit-btn", "em_scen_id": scen_id},
                            variant="subtle",
                            size="sm",
                        ),
                        dmc.ActionIcon(
                            DashIconify(icon="mdi:trash-can-outline"),
                            id={"type": "emission-remove-btn", "em_scen_id": scen_id},
                            variant="subtle",
                            color="red",
                            size="sm",
                        ),
                    ],
                    gap="xs",
                    justify="center",
                    align="start",
                ),
                style=cell_style,
            )
        )
    body_rows.append(dmc.TableTr(selected_cells))

    # ---------- Remaining rows: properties ----------
    for field, label in available_rows:
        row_cells = [dmc.TableTh(label)]
        for idx, scen_id in enumerate(scen_ids):
            cell_style = (
                active_col_style if scen_id in active_ids else inactive_col_style
            )
            value = emission_df.iloc[idx].get(field, "")
            if isinstance(value, float):
                value = f"{value:.4g}"
            row_cells.append(dmc.TableTd(str(value), style=cell_style))
        body_rows.append(dmc.TableTr(row_cells))

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
        h=500,
        type="auto",
    )

    # Wrap in CheckboxGroup so the 'Selected' row is one multi-select control
    return dmc.CheckboxGroup(
        id="emissions-checkbox-group",
        value=list(active_ids),
        children=table,
    )


def add_emission_modal():
    return dmc.Modal(
        id="emissions-add-modal",
        opened=False,  # controlled via callback
        title="Add emission scenario",
        children=dmc.Stack(
            [
                dmc.Select(
                    id="add-em-base-scenario-select",
                    label="Base scenario",
                    placeholder="Choose scenario to copy",
                    data=[],  # filled from metadata-store
                    searchable=True,
                    nothingFoundMessage="No scenarios",
                    withScrollArea=True,
                ),
                dmc.TextInput(
                    id="add-em-scenario-id-input",
                    label="New scenario ID",
                    placeholder="e.g. em_scenario_4",
                ),
                dmc.Text(
                    id="add-em-scenario-error",
                    size="xs",
                    c="red",
                ),
                dmc.Group(
                    [
                        dmc.Button(
                            "Cancel",
                            id="add-em-scenario-cancel-btn",
                            variant="outline",
                        ),
                        dmc.Button(
                            "Save",
                            id="add-em-scenario-save-btn",
                        ),
                    ],
                    justify="flex-end",
                    mt="sm",
                ),
            ]
        ),
    )


def edit_emission_modal():
    # helper to turn a list of values into Mantine Select data
    def _options(values):
        return [{"value": str(v), "label": str(v)} for v in values]

    return dmc.Modal(
        id="emissions-edit-modal",
        opened=False,
        title="Edit emission scenario",
        size="lg",
        children=dmc.Stack(
            [
                dmc.Group(
                    [
                        dmc.TextInput(
                            id="edit-em-scenario-id-input",
                            label="Scenario ID",
                            disabled=True,
                            style={"flex": 1},
                        ),
                    ],
                    grow=True,
                ),
                dmc.SimpleGrid(
                    cols=2,
                    spacing="md",
                    children=[
                        dmc.Select(
                            id="edit-em-grid-scenario",
                            label="Grid scenario",
                            placeholder="Select grid scenario",
                            data=_options(EMISSIONS_INDEX["emission_scenario"]),
                            searchable=True,
                            clearable=False,
                        ),
                        dmc.Select(
                            id="edit-em-gea-grid-region",
                            label="GEA grid region",
                            placeholder="Select grid region",
                            data=_options(EMISSIONS_INDEX["gea_grid_region"]),
                            searchable=True,
                            clearable=False,
                        ),
                    ],
                ),
                dmc.SimpleGrid(
                    cols=2,
                    spacing="md",
                    children=[
                        dmc.TextInput(
                            id="edit-em-time-zone",
                            label="Time zone",
                            placeholder="e.g. America/Los_Angeles",
                            disabled=True,
                        ),
                        dmc.Select(
                            id="edit-em-emission-type",
                            label="Emission type",
                            placeholder="Select emission type",
                            data=_options(EMISSIONS_INDEX["emission_type"]),
                            searchable=False,
                            clearable=False,
                        ),
                    ],
                ),
                dmc.SimpleGrid(
                    cols=2,
                    spacing="md",
                    children=[
                        dmc.NumberInput(
                            id="edit-em-shortrun-weighting",
                            label="Short-run weighting",
                            min=0,
                            max=1,
                            step=0.1,
                        ),
                        dmc.Select(
                            id="edit-em-year",
                            label="Year",
                            placeholder="Select year",
                            data=_options(EMISSIONS_INDEX["year"]),
                            searchable=False,
                            clearable=False,
                        ),
                    ],
                ),
                dmc.SimpleGrid(
                    cols=2,
                    spacing="md",
                    children=[
                        dmc.NumberInput(
                            id="edit-em-refrig-leakage",
                            label="Annual refrigerant leakage (fraction)",
                            min=0,
                            max=1,
                            step=0.01,
                        ),
                        dmc.NumberInput(
                            id="edit-em-ng-leakage",
                            label="Annual NG leakage (g/kWh)",
                            min=0,
                            step=1,
                        ),
                    ],
                ),
                dmc.Text(
                    id="edit-em-scenario-error",
                    size="xs",
                    c="red",
                ),
                dmc.Group(
                    [
                        dmc.Button(
                            "Cancel",
                            id="edit-em-scenario-cancel-btn",
                            variant="outline",
                        ),
                        dmc.Button(
                            "Save",
                            id="edit-em-scenario-save-btn",
                        ),
                    ],
                    justify="flex-end",
                    mt="sm",
                ),
            ]
        ),
    )
