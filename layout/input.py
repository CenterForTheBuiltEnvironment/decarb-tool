import dash_bootstrap_components as dbc
from dash import dcc, html
from dash_iconify import DashIconify
import dash_mantine_components as dmc
import pandas as pd
import json
from pathlib import Path

from utils.tooltips import with_tooltip
from utils.units import unit_map

from layout.table_config import (
    TABLE_STYLE,
    format_table_value,
    value_deemphasis_style,
    get_diff_fields,
)
from src.config import EquipmentTableRows, EmissionTableRows

META_INDEX_PATH = Path("data/input/metadata_index.json")
with META_INDEX_PATH.open("r") as f:
    METADATA_INDEX = json.load(f)

LOAD_INDEX = METADATA_INDEX["load_data_full"]
EMISSIONS_INDEX = METADATA_INDEX["emissions"]


def unit_toggle():
    return dmc.SegmentedControl(
        id="unit-toggle",  # keep your existing id if you already use it
        value="SI",  # or "IP"
        data=[
            {"label": "SI", "value": "SI"},
            {"label": "IP", "value": "IP"},
        ],
        color="blue",
        size="xs",
        radius="md",
        w=120,
        transitionDuration=500,
        transitionTimingFunction="linear",
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


def build_equipment_table(
    equipment_data, displayed_ids, active_ids=None, view_mode="simple"
):
    """
    Transposed equipment scenarios table:
    - Columns = equipment scenarios (eq_scen_id)
    - Rows    = properties (awhp, chiller, sizing, etc.)

    Layout (body rows, after header):
    1) Selected (checkbox + EDIT / REMOVE)
    2) Scenario ID (eq_scen_id)
    3+) Other properties

    Args:
        equipment_data: Equipment scenarios data (list or DataFrame)
        displayed_ids: List of scenario IDs to display as columns
        active_ids: Set of scenario IDs that are selected/active
        view_mode: One of "simple", "advanced", or "differences"
    """
    if isinstance(equipment_data, list):
        equipment_df = pd.DataFrame(equipment_data)
    else:
        equipment_df = equipment_data

    if equipment_df is None or equipment_df.empty:
        return dmc.CheckboxGroup(
            id="equipment-checkbox-group",
            value=[],
            children=dmc.Text("No equipment scenarios defined yet."),
        )

    # Ensure IDs exist
    if "eq_scen_id" not in equipment_df.columns:
        equipment_df["eq_scen_id"] = [f"eq_scen_{i}" for i in range(len(equipment_df))]

    # Filter to displayed scenarios that actually exist in the data
    available_ids = set(equipment_df["eq_scen_id"].tolist())
    valid_displayed_ids = [sid for sid in displayed_ids if sid in available_ids]

    if not valid_displayed_ids:
        return dmc.CheckboxGroup(
            id="equipment-checkbox-group",
            value=[],
            children=dmc.Text("No equipment scenarios to display."),
        )

    equipment_df = equipment_df[equipment_df["eq_scen_id"].isin(valid_displayed_ids)]
    equipment_df = (
        equipment_df.set_index("eq_scen_id").loc[valid_displayed_ids].reset_index()
    )

    # Rows to display (property name, label)
    # Note: eq_scen_id and eq_scen_name are excluded as they're shown in the header
    row_config = [
        ("hr_wwhp", "HR WWHP Model"),
        ("awhp", "AWHP Model"),
        ("awhp_sizing_mode", "AWHP Sizing Mode"),
        ("awhp_sizing_value", "AWHP Sizing Value"),
        ("awhp_redundancy", "AWHP Redundancy"),
        ("awhp_use_cooling", "AWHP Use Cooling"),
        ("backup_heating", "Backup Heating"),
        ("chiller", "Backup Cooling"),
    ]

    # Pre-compute which fields have differences across scenarios
    all_fields = [field for field, _ in row_config if field in equipment_df.columns]
    diff_fields = get_diff_fields(equipment_df, all_fields)

    # Filter rows based on view mode
    if view_mode == "simple":
        simple_fields = set(EquipmentTableRows.SIMPLE.value)
        available_rows = [
            (field, label)
            for field, label in row_config
            if field in equipment_df.columns and field in simple_fields
        ]
    elif view_mode == "differences":
        available_rows = [
            (field, label)
            for field, label in row_config
            if field in equipment_df.columns and field in diff_fields
        ]
        # Handle case where no differences exist
        if not available_rows:
            return dmc.CheckboxGroup(
                id="equipment-checkbox-group",
                value=list(active_ids) if active_ids else [],
                children=dmc.Text(
                    "All scenarios have identical values for the displayed properties.",
                    c="dimmed",
                    fs="italic",
                ),
            )
    else:  # "advanced" or default
        available_rows = [
            (field, label)
            for field, label in row_config
            if field in equipment_df.columns
        ]

    active_ids = set(active_ids or [])

    active_col_style = TABLE_STYLE.active_col_style
    inactive_col_style = TABLE_STYLE.inactive_col_style

    # ----- Styles -----
    prop_th_style = {
        "minWidth": TABLE_STYLE.property_col_width,
        "whiteSpace": "nowrap",
    }
    if TABLE_STYLE.sticky_property_col:
        prop_th_style.update(
            {
                "position": "sticky",
                "left": 0,
                "zIndex": 2,
                "background": "var(--mantine-color-body)",
                "textTransform": "none",
                "fontSize": "var(--mantine-font-size-sm)",
                "fontWeight": 400,
            }
        )

    scen_cell_style_base = {
        "minWidth": TABLE_STYLE.scenario_col_width,
        # "whiteSpace": "nowrap",
    }

    # ---------- Header row ----------
    scen_ids = []
    header_cells = [dmc.TableTh("Equipment Scenario", style=prop_th_style)]

    for idx, (_, row) in enumerate(equipment_df.iterrows(), start=1):
        scen_id = str(row.get("eq_scen_id", ""))
        scen_ids.append(scen_id)

        cell_style = {
            **scen_cell_style_base,
            **(active_col_style if scen_id in active_ids else inactive_col_style),
        }
        # Display just the number in the header
        header_cells.append(dmc.TableTh(str(idx), style=cell_style))

    header = dmc.TableThead(dmc.TableTr(header_cells))

    body_rows = []

    # ---------- Row 0: Selected (checkbox + actions) - moved to top ----------
    selected_cells = [dmc.TableTh("Selected", style=prop_th_style)]
    for scen_id in scen_ids:
        cell_style = {
            **scen_cell_style_base,
            **(active_col_style if scen_id in active_ids else inactive_col_style),
        }
        selected_cells.append(
            dmc.TableTd(
                dmc.Group(
                    [
                        with_tooltip(
                            dmc.Checkbox(value=scen_id, checked=scen_id in active_ids),
                            "equipment.select_eq_scenario",
                        ),
                        with_tooltip(
                            dmc.ActionIcon(
                                DashIconify(icon="mdi:pencil-outline"),
                                id={
                                    "type": "equipment-edit-btn",
                                    "eq_scen_id": scen_id,
                                },
                                variant="subtle",
                                size="sm",
                            ),
                            "equipment.edit_eq_scenario",
                        ),
                        with_tooltip(
                            dmc.ActionIcon(
                                DashIconify(icon="mdi:trash-can-outline"),
                                id={
                                    "type": "equipment-remove-btn",
                                    "eq_scen_id": scen_id,
                                },
                                variant="subtle",
                                color="red",
                                size="sm",
                            ),
                            "equipment.delete_eq_scenario",
                        ),
                    ],
                    gap="sm",
                    justify="flex-start",
                    wrap="nowrap",
                ),
                style=cell_style,
            )
        )
    body_rows.append(dmc.TableTr(selected_cells))

    # ---------- Row 1: Scenario selector dropdowns ----------
    # Build options from ALL scenarios in the library (not just displayed)
    all_scenario_options = [
        {
            "label": row.get("eq_scen_name", row.get("eq_scen_id", "")),
            "value": row.get("eq_scen_id"),
        }
        for _, row in pd.DataFrame(equipment_data).iterrows()
        if row.get("eq_scen_id")
    ]

    dropdown_cells = [dmc.TableTh("Scenario", style=prop_th_style)]
    for idx, scen_id in enumerate(scen_ids):
        cell_style = {
            **scen_cell_style_base,
            **(active_col_style if scen_id in active_ids else inactive_col_style),
        }
        dropdown_cells.append(
            dmc.TableTd(
                dmc.Select(
                    id={"type": "equipment-column-dropdown", "column": idx},
                    data=all_scenario_options,
                    value=scen_id,
                    size="xs",
                    allowDeselect=False,
                    style={"minWidth": "120px"},
                ),
                style=cell_style,
            )
        )
    body_rows.append(dmc.TableTr(dropdown_cells))

    # ---------- Property rows ----------
    diff_row_style = TABLE_STYLE.diff_row_style

    for field, label in available_rows:
        is_diff_row = field in diff_fields

        # Apply diff styling to the property label cell if row has differences
        prop_label_style = {**prop_th_style}
        if is_diff_row:
            prop_label_style.update(diff_row_style)

        row_cells = [dmc.TableTh(label, style=prop_label_style)]

        for idx, scen_id in enumerate(scen_ids):
            raw_value = equipment_df.iloc[idx].get(field, "")
            display_value = format_table_value(raw_value, field_name=field)

            # Build cell style: base + active/inactive + deemphasis + diff highlighting
            cell_style = {
                **scen_cell_style_base,
                **(active_col_style if scen_id in active_ids else inactive_col_style),
                **value_deemphasis_style(raw_value),
            }

            # Apply bold text only for data cells in rows with differences
            # (left border is only on the property label cell)
            if is_diff_row:
                cell_style["fontWeight"] = 900  # ? Is this still required?

            row_cells.append(dmc.TableTd(display_value, style=cell_style))

        body_rows.append(dmc.TableTr(row_cells))

    body = dmc.TableTbody(body_rows)

    # Force horizontal scrolling
    table_min_width = (
        TABLE_STYLE.property_col_width
        + TABLE_STYLE.scenario_col_width * max(len(scen_ids), 1)
    )

    table = dmc.ScrollArea(
        dmc.Table(
            [header, body],
            striped=True,
            highlightOnHover=True,
            withColumnBorders=False,
            horizontalSpacing=TABLE_STYLE.horizontal_spacing,
            verticalSpacing=TABLE_STYLE.vertical_spacing,
            style={"minWidth": table_min_width},
        ),
        type="auto",
        scrollbarSize=TABLE_STYLE.scrollbar_size,
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


def build_emissions_table(emission_data, active_ids=None, view_mode="simple"):
    """
    Transposed emissions scenarios table:
    - Columns = emission scenarios (em_scen_id)
    - Rows    = properties (year, region, etc.)

    Layout (body rows, after header):
    1) Selected (checkbox + EDIT / REMOVE)
    2) Scenario ID (em_scen_id)
    3+) Other properties

    Args:
        emission_data: Emission scenarios data (list or DataFrame)
        active_ids: Set of scenario IDs that are selected/active
        view_mode: One of "simple", "advanced", or "differences"
    """
    if isinstance(emission_data, list):
        emission_df = pd.DataFrame(emission_data)
    else:
        emission_df = emission_data

    if emission_df is None or emission_df.empty:
        return dmc.CheckboxGroup(
            id="emissions-checkbox-group",
            value=[],
            children=dmc.Text("No emission scenarios defined yet."),
        )

    # Ensure IDs exist
    if "em_scen_id" not in emission_df.columns:
        emission_df["em_scen_id"] = [f"em_scen_{i}" for i in range(len(emission_df))]

    # Sort for stable column order
    emission_df = emission_df.sort_values("em_scen_id").reset_index(drop=True)

    # Rows to display
    # Rows to display (property name, label)
    # Note: em_scen_id is excluded as it's shown in the header
    row_config = [
        ("grid_scenario", "Grid Scenario"),
        ("gea_grid_region", "GEA Grid Region"),
        ("emission_type", "Emission Type"),
        ("shortrun_weighting", "Short-run weighting"),
        ("annual_refrig_leakage_percent", "Refrigerant leakage (frac)"),
        ("annual_ng_leakage_g_per_kWh", "NG leakage (g/kWh)"),
        ("year", "Year"),
    ]

    # Pre-compute which fields have differences across scenarios
    all_fields = [field for field, _ in row_config if field in emission_df.columns]
    diff_fields = get_diff_fields(emission_df, all_fields)

    # Filter rows based on view mode
    if view_mode == "simple":
        simple_fields = set(EmissionTableRows.SIMPLE.value)
        available_rows = [
            (field, label)
            for field, label in row_config
            if field in emission_df.columns and field in simple_fields
        ]
    elif view_mode == "differences":
        available_rows = [
            (field, label)
            for field, label in row_config
            if field in emission_df.columns and field in diff_fields
        ]
        # Handle case where no differences exist
        if not available_rows:
            return dmc.CheckboxGroup(
                id="emissions-checkbox-group",
                value=list(active_ids) if active_ids else [],
                children=dmc.Text(
                    "All scenarios have identical values for the displayed properties.",
                    c="dimmed",
                    fs="italic",
                ),
            )
    else:  # "advanced" or default
        available_rows = [
            (field, label)
            for field, label in row_config
            if field in emission_df.columns
        ]

    active_ids = set(active_ids or [])

    active_col_style = TABLE_STYLE.active_col_style
    inactive_col_style = TABLE_STYLE.inactive_col_style

    # ----- Styles -----
    prop_th_style = {
        "minWidth": TABLE_STYLE.property_col_width,
        "whiteSpace": "nowrap",
    }
    if TABLE_STYLE.sticky_property_col:
        prop_th_style.update(
            {
                "position": "sticky",
                "left": 0,
                "zIndex": 2,
                "background": "var(--mantine-color-body)",
                "textTransform": "none",
                "fontSize": "var(--mantine-font-size-sm)",
                "fontWeight": 400,
            }
        )

    scen_cell_base = {
        "minWidth": TABLE_STYLE.scenario_col_width,
        "whiteSpace": "nowrap",
    }

    # ---------- Header row ----------
    scen_ids = []
    header_cells = [dmc.TableTh("Emission Scenario", style=prop_th_style)]

    for idx, (_, row) in enumerate(emission_df.iterrows(), start=1):
        scen_id = str(row.get("em_scen_id", ""))
        scen_ids.append(scen_id)

        cell_style = {
            **scen_cell_base,
            **(active_col_style if scen_id in active_ids else inactive_col_style),
        }
        # Display just the number in the header
        header_cells.append(dmc.TableTh(str(idx), style=cell_style))

    header = dmc.TableThead(dmc.TableTr(header_cells))

    body_rows = []

    # ---------- Row 1: Selected ----------
    selected_cells = [dmc.TableTh("Selected", style=prop_th_style)]
    for scen_id in scen_ids:
        cell_style = {
            **scen_cell_base,
            **(active_col_style if scen_id in active_ids else inactive_col_style),
        }
        selected_cells.append(
            dmc.TableTd(
                dmc.Group(
                    [
                        dmc.Checkbox(value=scen_id, checked=scen_id in active_ids),
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
                    wrap="nowrap",
                    justify="flex-start",
                ),
                style=cell_style,
            )
        )
    body_rows.append(dmc.TableTr(selected_cells))

    # ---------- Property rows ----------
    diff_row_style = TABLE_STYLE.diff_row_style

    for field, label in available_rows:
        is_diff_row = field in diff_fields

        # Apply diff styling to the property label cell if row has differences
        prop_label_style = {**prop_th_style}
        if is_diff_row:
            prop_label_style.update(diff_row_style)

        row_cells = [dmc.TableTh(label, style=prop_label_style)]

        for idx, scen_id in enumerate(scen_ids):
            raw_value = emission_df.iloc[idx].get(field, "")
            display_value = format_table_value(raw_value, field_name=field)

            # Build cell style: base + active/inactive + deemphasis
            cell_style = {
                **scen_cell_base,
                **(active_col_style if scen_id in active_ids else inactive_col_style),
                **value_deemphasis_style(raw_value),
            }

            # Apply bold text only for data cells in rows with differences
            if is_diff_row:
                cell_style["fontWeight"] = 600

            row_cells.append(dmc.TableTd(display_value, style=cell_style))

        body_rows.append(dmc.TableTr(row_cells))

    body = dmc.TableTbody(body_rows)

    # Force horizontal scrolling
    table_min_width = (
        TABLE_STYLE.property_col_width
        + TABLE_STYLE.scenario_col_width * max(len(scen_ids), 1)
    )

    table = dmc.ScrollArea(
        dmc.Table(
            [header, body],
            striped=True,
            highlightOnHover=True,
            withColumnBorders=False,
            horizontalSpacing=TABLE_STYLE.horizontal_spacing,
            verticalSpacing=TABLE_STYLE.vertical_spacing,
            style={
                "minWidth": table_min_width,
            },
        ),
        type="auto",
        scrollbarSize=TABLE_STYLE.scrollbar_size,
        offsetScrollbars=True,
    )

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
