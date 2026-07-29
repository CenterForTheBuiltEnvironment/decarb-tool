import json
from functools import lru_cache

import dash_bootstrap_components as dbc
import dash_mantine_components as dmc
import pandas as pd
from dash import dcc, html
from dash_iconify import DashIconify

from layout.table_config import (
    TABLE_STYLE,
    format_table_value,
    get_diff_fields,
    value_deemphasis_style,
)
from src import paths
from src.config import EmissionTableRows, EquipmentTableRows
from utils.tooltips import with_tooltip


@lru_cache(maxsize=1)
def _get_metadata_index():
    """Lazy-load and cache the metadata index JSON."""
    with paths.METADATA_INDEX_JSON.open("r") as f:
        return json.load(f)


def get_load_index():
    """Get load data index from metadata index (lazy-loaded)."""
    return _get_metadata_index()["load_data_full"]


def get_emissions_index():
    """Get emissions index from metadata index (lazy-loaded)."""
    return _get_metadata_index()["emissions"]


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


def legend_toggle():
    """Toggle to show/hide the scenario legend accordion."""
    return dmc.Switch(
        id="legend-toggle",
        label="Show Scenario Legend",
        size="sm",
        checked=False,
    )


def scenario_legend_accordion():
    """Collapsible accordion showing ID to name mappings for scenarios."""
    return dmc.Accordion(
        id="scenario-legend-accordion",
        value=["equipment", "emission"],  # Both sections open by default
        children=[
            dmc.AccordionItem(
                [
                    dmc.AccordionControl("Equipment Scenarios", fz="sm"),
                    dmc.AccordionPanel(
                        html.Div(id="equipment-legend-content"),
                    ),
                ],
                value="equipment",
            ),
            dmc.AccordionItem(
                [
                    dmc.AccordionControl("Emission Scenarios", fz="sm"),
                    dmc.AccordionPanel(
                        html.Div(id="emission-legend-content"),
                    ),
                ],
                value="emission",
            ),
        ],
        multiple=True,
        variant="separated",
        radius="md",
        styles={"control": {"padding": "8px"}, "content": {"padding": "8px"}},
    )


# --------------------------------
# LOADS page inputs
# --------------------------------


def select_location():
    """Location selector with server-side search (options loaded via callback)."""
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
                options=[],  # Options loaded dynamically via callback
                placeholder="Type to search by city or zip...",
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
                                        DashIconify(icon="material-symbols:upload", width=20),
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


def build_building_table(buildings_data, selected_id=None, unit_mode: str = "SI"):
    """
    Build a table from a DataFrame with predefined columns.
    Only displays columns that exist in the data.
    Supports unit conversion with auto-scaling via unit_mode ("SI" or "IP").
    """
    from utils.units import (
        AUTO_SCALE_CONFIG,
        get_auto_scale_for_values,
        get_category,
        get_converter,
    )

    # Define desired columns with their base display names (without units)
    # Format: (column_name, display_name)
    column_config = [
        ("location", "Location"),
        ("ashrae_climate_zone", "Climate Zone"),
        ("building_type", "Building Type"),
        ("load_type", "Source"),
        ("area_sqm", "Area"),
        ("hhw_max_load", "Peak HHW Load"),
        ("chw_max_load", "Peak CHW Load"),
        ("annual_heating_cooling_ratio", "Annual H/C Ratio"),
        ("min_temp", "Min Temp"),
        ("max_temp", "Max Temp"),
    ]

    available_columns = [
        (col, label) for col, label in column_config if col in buildings_data.columns
    ]

    # Pre-calculate auto-scaling for each column
    # Store (scale_factor, unit_label) for each column
    column_scales = {}
    for col, _ in available_columns:
        category = get_category(col)
        if category:
            # Get all non-null values for this column (in base units)
            values = buildings_data[col].dropna().tolist()
            if values:
                scale, unit = get_auto_scale_for_values(values, category, unit_mode)
                column_scales[col] = (scale, unit)

    # Build header labels with auto-scaled units
    def get_header_label(col_name: str, base_label: str) -> str:
        if col_name in column_scales:
            _, unit = column_scales[col_name]
            return f"{base_label} [{unit}]"
        return base_label

    # Build body rows with auto-scaling (directly from base units)
    # Convert to list of dicts for faster iteration (iterrows is very slow)
    records = buildings_data.to_dict("records")
    body_rows = []
    for idx, row in enumerate(records):
        cells = [
            dmc.TableTd(dmc.Radio(value=str(row.get("building_id", idx))))
        ]  # use 'building_id' field or index

        for col, _ in available_columns:
            raw_value = row.get(col)
            # Scale value if it has a registered category
            if col in column_scales and raw_value is not None:
                try:
                    category = get_category(col)
                    if category in AUTO_SCALE_CONFIG:
                        scale, _ = column_scales[col]
                        scaled = float(raw_value) / scale
                    else:
                        scaled = get_converter(category, unit_mode)(float(raw_value))

                    # Format based on magnitude of scaled value
                    if abs(scaled) >= 1000:
                        display_value = f"{scaled:,.0f}"
                    elif abs(scaled) >= 1:
                        display_value = f"{scaled:,.1f}"
                    else:
                        display_value = f"{scaled:,.2f}"
                except (TypeError, ValueError):
                    display_value = str(raw_value)
            else:
                display_value = str(raw_value) if raw_value is not None else "—"

            cells.append(dmc.TableTd(display_value))

        body_rows.append(dmc.TableTr(cells))

    # Build header (use normal case, not uppercase)
    header_style = {"textTransform": "none", "fontWeight": 500}
    header_cells = [dmc.TableTh("", style=header_style)]  # radio column
    header_cells.extend(
        [
            dmc.TableTh(get_header_label(col, label), style=header_style)
            for col, label in available_columns
        ]
    )
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
    load_index = get_load_index()
    building_type_options = sorted(load_index["building_type"])
    climate_zone_options = sorted(load_index["ashrae_climate_zone"])
    load_type_options = ["all"] + load_index["load_type"]

    area_min, area_max = load_index["area_sqm"]
    hhw_min, hhw_max = load_index["hhw_max_load"]
    chw_min, chw_max = load_index["chw_max_load"]

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
                                    {"value": v, "label": v.capitalize()} for v in load_type_options
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
                                data=[{"value": cz, "label": cz} for cz in climate_zone_options],
                                value=None,
                                clearable=True,
                                style={"width": 180},
                            ),
                            # Building type
                            dmc.Select(
                                id="building-type-filter",
                                label="Building type",
                                placeholder="All",
                                data=[{"value": bt, "label": bt} for bt in building_type_options],
                                value=None,
                                clearable=True,
                                searchable=True,
                                style={"width": 220},
                            ),
                            dmc.Stack(
                                [
                                    dmc.Text(
                                        id="area-slider-label",
                                        children="Area (m²)",
                                        size="sm",
                                        fw=500,
                                    ),
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
                                    dmc.Text(
                                        id="hhw-slider-label",
                                        children="HHW Peak Load [kW]",
                                        size="sm",
                                        fw=500,
                                    ),
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
                                    dmc.Text(
                                        id="chw-slider-label",
                                        children="CHW Peak Load [kW]",
                                        size="sm",
                                        fw=500,
                                    ),
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
    equipment_data, displayed_ids, active_ids=None, view_mode="simple", unit_mode="SI"
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
        unit_mode: "SI" or "IP" for unit conversion
    """
    from utils.units import get_unit_converter, get_unit_label

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
    equipment_df = equipment_df.set_index("eq_scen_id").loc[valid_displayed_ids].reset_index()

    # Get unit label for temperature (dynamic based on unit_mode)
    temp_unit = get_unit_label("temperature", unit_mode)

    # Rows to display (property name, label)
    # Note: eq_scen_id and eq_scen_name are excluded as they're shown in the header
    row_config = [
        ("hr_wwhp", "HR WWHP Model"),
        ("hr_wwhp_performance_model", "HR WWHP Performance Calculation Model"),
        ("hr_wwhp_h_supply_t", f"HR WWHP Heating Supply Temp ({temp_unit})"),
        ("awhp", "AWHP Model"),
        ("awhp_performance_model", "AWHP Performance Calculation Model"),
        ("awhp_h_supply_t", f"AWHP Heating Supply Temp ({temp_unit})"),
        ("awhp_sizing_mode", "AWHP Sizing Mode"),
        ("awhp_sizing_value", "AWHP Sizing Value"),
        ("awhp_redundancy", "AWHP Redundancy"),
        ("awhp_use_cooling", "AWHP Use Cooling"),
        ("awhp_sizing_priority", "AWHP Sizing Priority"),
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
            (field, label) for field, label in row_config if field in equipment_df.columns
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

    # Get converter for temperature values
    temp_converter = get_unit_converter("temperature", unit_mode)
    temp_fields = {"hr_wwhp_h_supply_t", "awhp_h_supply_t"}

    for field, label in available_rows:
        is_diff_row = field in diff_fields

        # Apply diff styling to the property label cell if row has differences
        prop_label_style = {**prop_th_style}
        if is_diff_row:
            prop_label_style.update(diff_row_style)

        row_cells = [dmc.TableTh(label, style=prop_label_style)]

        for idx, scen_id in enumerate(scen_ids):
            raw_value = equipment_df.iloc[idx].get(field, "")

            # Apply unit conversion for temperature fields
            if field in temp_fields and raw_value is not None:
                try:
                    converted = temp_converter(float(raw_value))
                    display_value = f"{converted:.1f}"
                except (ValueError, TypeError):
                    display_value = format_table_value(raw_value, field_name=field)
            else:
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
    table_min_width = TABLE_STYLE.property_col_width + TABLE_STYLE.scenario_col_width * max(
        len(scen_ids), 1
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
                        dmc.Select(
                            id="edit-hr-wwhp-performance-model",
                            label="HR HP Performance Calculation Model",
                            placeholder="None",
                            data=[  # not including fixed_COP and performance_curves atm
                                {
                                    "label": "Interpolated table (HHWST fixed)",
                                    "value": "interpolate_HHWST",
                                }
                            ],
                            clearable=True,
                            searchable=True,
                        ),
                        dmc.Select(
                            id="edit-awhp-performance-model",
                            label="AWHP Performance Calculation Model",
                            placeholder="None",
                            data=[  # not including fixed_COP and performance_curves atm
                                {
                                    "label": "Interpolated table (HHWST fixed)",
                                    "value": "interpolate_HHWST_fixed",
                                },
                                {
                                    "label": "Interpolated table (HHWST reset)",
                                    "value": "interpolate_HHWST_reset",
                                },
                            ],
                            clearable=True,
                            searchable=True,
                        ),
                        dmc.Stack(
                            gap=4,
                            children=[
                                dmc.Text(
                                    id="edit-hr-wwhp-h-supply-t-label",
                                    children="HR HP Heating supply temp (°C)",
                                    size="sm",
                                    fw=500,
                                ),
                                dmc.NumberInput(
                                    id="edit-hr-wwhp-h-supply-t-value",
                                    placeholder="Enter temperature",
                                    min=32.2,  # Updated dynamically by callback
                                    max=73.9,  # Updated dynamically by callback
                                    step=0.1,
                                    decimalScale=1,
                                ),
                            ],
                        ),
                        dmc.Stack(
                            gap=4,
                            children=[
                                dmc.Text(
                                    id="edit-awhp-h-supply-t-label",
                                    children="AWHP Heating supply temp (°C)",
                                    size="sm",
                                    fw=500,
                                ),
                                dmc.NumberInput(
                                    id="edit-awhp-h-supply-t-value",
                                    placeholder="Enter temperature",
                                    min=35,  # Updated dynamically by callback
                                    max=60,  # Updated dynamically by callback
                                    step=0.1,
                                    decimalScale=1,
                                ),
                            ],
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
                        dmc.Group(
                            [
                                dmc.Switch(
                                    id="edit-awhp-use-cooling",
                                    label="Use heat pump also for cooling",
                                    mt="xs",
                                ),
                                dmc.Select(
                                    id="edit-awhp-sizing-priority",
                                    label="Sizing priority",
                                    placeholder="None",
                                    data=[
                                        {
                                            "label": "Heating load",
                                            "value": "heating",
                                        },
                                        {
                                            "label": "Cooling load",
                                            "value": "cooling",
                                        },
                                        {
                                            "label": "Larger of heating and cooling load",
                                            "value": "larger",
                                        },
                                    ],
                                    clearable=True,
                                    searchable=True,
                                ),
                            ],
                            grow=True,
                        ),
                    ],
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


def build_emissions_table(emission_data, active_ids=None, view_mode="simple", unit_mode="SI"):
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
        unit_mode: "SI" or "IP" for unit conversion
    """
    from utils.units import get_unit_converter, get_unit_label

    emission_df = pd.DataFrame(emission_data) if isinstance(emission_data, list) else emission_data

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

    # Get unit label for NG emission rate (dynamic based on unit_mode)
    ng_emission_rate_unit = get_unit_label("emissions_rate", unit_mode)

    # Rows to display (property name, label)
    # Note: em_scen_id is excluded as it's shown in the header
    row_config = [
        ("grid_scenario", "Grid Scenario"),
        ("gea_grid_region", "GEA Grid Region"),
        ("emission_type", "Emission Type"),
        ("shortrun_weighting", "Short-run weighting"),
        ("annual_refrig_leakage_percent", "Refrigerant leakage (frac)"),
        ("ng_emission_rate_gCO2e_per_kWh", f"Gas emissions rate ({ng_emission_rate_unit})"),
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
            (field, label) for field, label in row_config if field in emission_df.columns
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
        # Display capital letter in the header (A, B, C, ...)
        letter = chr(64 + idx)  # 1 -> 'A', 2 -> 'B', etc.
        header_cells.append(dmc.TableTh(letter, style=cell_style))

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

    # Get converter for NG emission rate values
    ng_emission_rate_converter = get_unit_converter("emissions_rate", unit_mode)

    for field, label in available_rows:
        is_diff_row = field in diff_fields

        # Apply diff styling to the property label cell if row has differences
        prop_label_style = {**prop_th_style}
        if is_diff_row:
            prop_label_style.update(diff_row_style)

        row_cells = [dmc.TableTh(label, style=prop_label_style)]

        for idx, scen_id in enumerate(scen_ids):
            raw_value = emission_df.iloc[idx].get(field, "")

            # Apply unit conversion for NG emission rate
            if field == "ng_emission_rate_gCO2e_per_kWh" and raw_value is not None:
                try:
                    converted = ng_emission_rate_converter(float(raw_value))
                    display_value = f"{converted:.2f}"
                except (ValueError, TypeError):
                    display_value = format_table_value(raw_value, field_name=field)
            else:
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
    table_min_width = TABLE_STYLE.property_col_width + TABLE_STYLE.scenario_col_width * max(
        len(scen_ids), 1
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
                dmc.TextInput(
                    id="add-em-scenario-name-input",
                    label="Scenario name",
                    placeholder="Descriptive name",
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


def build_completeness_modal():
    """
    Modal to show data completeness summary before confirming load data selection.
    Shows for measured library data and custom uploads (not for simulated data).
    For custom uploads, also shows metadata input fields.
    """
    # Building type options from metadata index
    building_type_options = [
        {"value": bt, "label": bt} for bt in sorted(get_load_index()["building_type"])
    ]

    return dmc.Modal(
        title="Data Completeness Summary",
        id="data-completeness-modal",
        size="lg",
        centered=True,
        withCloseButton=True,
        children=[
            html.Div(id="completeness-summary-content"),
            # Metadata inputs section (shown only for custom uploads)
            html.Div(
                id="custom-metadata-inputs",
                style={"display": "none"},  # Hidden by default, shown via callback
                children=[
                    dmc.Divider(my="md"),
                    dmc.Text("Building Metadata", fw=600, size="lg"),
                    dmc.Text(
                        "Please provide building information for this custom dataset.",
                        size="sm",
                        c="dimmed",
                        mb="md",
                    ),
                    dmc.SimpleGrid(
                        cols=2,
                        spacing="md",
                        children=[
                            dmc.TextInput(
                                id="custom-building-id",
                                label="Building ID",
                                placeholder="Enter a unique identifier",
                                required=True,
                                withAsterisk=True,
                            ),
                            dmc.Select(
                                id="custom-building-type",
                                label="Building Type",
                                placeholder="Select building type (optional)",
                                data=building_type_options,
                                clearable=True,
                                searchable=True,
                            ),
                            dmc.Select(
                                id="custom-vintage",
                                label="Vintage (Decade Built)",
                                placeholder="Select decade (optional)",
                                data=["1960s", "1980s", "1990s", "2000s", "2010s", "2020s"],
                                clearable=True,
                            ),
                            dmc.Stack(
                                gap=4,
                                children=[
                                    dmc.Group(
                                        gap=2,
                                        children=[
                                            dmc.Text(
                                                id="custom-area-label",
                                                children="Building Area (m²)",
                                                size="sm",
                                                fw=500,
                                            ),
                                            dmc.Text("*", c="red", size="sm"),
                                        ],
                                    ),
                                    dmc.NumberInput(
                                        id="custom-area",
                                        placeholder="Enter building area",
                                        min=0,
                                        required=True,
                                    ),
                                ],
                            ),
                        ],
                    ),
                    dmc.Text(
                        id="custom-metadata-error",
                        c="red",
                        size="sm",
                        mt="sm",
                    ),
                ],
            ),
            dmc.Group(
                [
                    dmc.Button(
                        "Cancel",
                        id="completeness-cancel-btn",
                        variant="outline",
                    ),
                    dmc.Button(
                        "Confirm Selection",
                        id="completeness-confirm-btn",
                        color="blue",
                    ),
                ],
                justify="flex-end",
                mt="md",
            ),
        ],
    )


def build_completeness_summary(data_summary: dict, source_type: str = "measured") -> html.Div:
    """
    Build the summary content from StandardLoad.get_data_summary().

    Args:
        data_summary: Dictionary from StandardLoad.get_data_summary()
        source_type: "measured" or "custom" for display purposes

    Returns:
        Dash component with formatted summary
    """
    if not data_summary:
        return dmc.Text("No data summary available.", c="dimmed")

    # Extract values
    start_date = data_summary.get("start_date")
    end_date = data_summary.get("end_date")
    num_hours = data_summary.get("num_hours", 0)
    expected_hours = data_summary.get("expected_hours", 8760)
    is_complete = data_summary.get("is_complete", False)
    has_leap_day = data_summary.get("has_leap_day", False)
    spans_multiple_years = data_summary.get("spans_multiple_years", False)
    missing_hours = data_summary.get("missing_hours", 0)
    column_stats = data_summary.get("column_stats", {})
    has_missing_values = data_summary.get("has_missing_values", False)
    total_missing_values = data_summary.get("total_missing_values", 0)

    # Format dates
    start_str = start_date.strftime("%Y-%m-%d %H:%M") if start_date else "N/A"
    end_str = end_date.strftime("%Y-%m-%d %H:%M") if end_date else "N/A"

    # Build status display
    if is_complete:
        status_icon = DashIconify(icon="mdi:check-circle", color="green", width=20)
        status_text = dmc.Text("Complete", c="green", fw=600)
    else:
        # Build descriptive status message
        issues = []
        if missing_hours > 0:
            issues.append(f"{missing_hours} hours missing")
        if has_missing_values:
            issues.append(f"{total_missing_values} missing values")
        issue_text = ", ".join(issues) if issues else "incomplete"
        status_icon = DashIconify(icon="mdi:alert-circle", color="orange", width=20)
        status_text = dmc.Text(f"Incomplete - {issue_text}", c="orange", fw=600)

    # Build info rows
    info_rows = [
        dmc.Group(
            [
                dmc.Text("Start Date:", fw=500, w=140),
                dmc.Text(start_str),
            ],
            gap="xs",
        ),
        dmc.Group(
            [
                dmc.Text("End Date:", fw=500, w=140),
                dmc.Text(end_str),
            ],
            gap="xs",
        ),
        dmc.Group(
            [
                dmc.Text("Total Hours:", fw=500, w=140),
                dmc.Text(f"{num_hours:,}"),
            ],
            gap="xs",
        ),
        dmc.Group(
            [
                dmc.Text("Expected Hours:", fw=500, w=140),
                dmc.Text(f"{expected_hours:,}"),
            ],
            gap="xs",
        ),
    ]

    # Status row
    status_row = dmc.Group(
        [
            dmc.Text("Status:", fw=500, w=140),
            status_icon,
            status_text,
        ],
        gap="xs",
    )

    # Build check items for time-based properties
    check_items = [
        dmc.Group(
            [
                DashIconify(
                    icon="mdi:check-circle" if not has_leap_day else "mdi:information",
                    color="green" if not has_leap_day else "blue",
                    width=16,
                ),
                dmc.Text(
                    f"Contains leap day (Feb 29): {'Yes' if has_leap_day else 'No'}",
                    size="sm",
                ),
            ],
            gap="xs",
        ),
        dmc.Group(
            [
                DashIconify(
                    icon=("mdi:check-circle" if not spans_multiple_years else "mdi:information"),
                    color="green" if not spans_multiple_years else "blue",
                    width=16,
                ),
                dmc.Text(
                    f"Spans multiple years: {'Yes' if spans_multiple_years else 'No'}",
                    size="sm",
                ),
            ],
            gap="xs",
        ),
    ]

    # Build column quality section
    column_labels = {
        "t_out_C": "Outdoor Temperature",
        "heating_W": "Heating Load",
        "cooling_W": "Cooling Load",
    }

    column_rows = []
    for col, label in column_labels.items():
        stats = column_stats.get(col, {})
        missing = stats.get("missing_count", 0)
        completeness = stats.get("completeness_pct", 100)

        if missing == 0:
            icon = DashIconify(icon="mdi:check-circle", color="green", width=16)
            value_text = dmc.Text("100%", c="green", size="sm")
        else:
            icon = DashIconify(icon="mdi:alert-circle", color="orange", width=16)
            value_text = dmc.Text(f"{completeness}% ({missing:,} missing)", c="orange", size="sm")

        column_rows.append(
            dmc.Group(
                [
                    icon,
                    dmc.Text(f"{label}:", size="sm", w=140),
                    value_text,
                ],
                gap="xs",
            )
        )

    # Build warning messages
    warnings = []
    if missing_hours > 0:
        warnings.append(f"Dataset is missing {missing_hours} hours of data.")
    if has_missing_values:
        warnings.append(f"Dataset has {total_missing_values} missing values in data columns.")
    if not is_complete:
        warnings.append("Results may be understated. Consider providing a complete dataset.")

    warning_alert = None
    if warnings:
        warning_alert = dmc.Alert(
            dmc.Stack([dmc.Text(w, size="sm") for w in warnings], gap=4),
            title="Data Quality Warning",
            color="orange",
            icon=DashIconify(icon="mdi:alert"),
        )

    # Source badge
    source_badge = dmc.Badge(
        source_type.capitalize(),
        color="blue" if source_type == "measured" else "grape",
        variant="light",
    )

    return dmc.Stack(
        [
            dmc.Group(
                [
                    dmc.Text("Dataset Overview", fw=600, size="lg"),
                    source_badge,
                ],
                justify="space-between",
            ),
            dmc.Divider(),
            dmc.Stack(info_rows, gap="xs"),
            dmc.Divider(),
            status_row,
            dmc.Divider(),
            dmc.Text("Data Column Quality", fw=500, size="sm"),
            dmc.Stack(column_rows, gap="xs"),
            dmc.Divider(),
            dmc.Stack(check_items, gap="xs"),
            warning_alert,
        ],
        gap="sm",
    )


def edit_emission_modal():
    # helper to turn a list of values into Mantine Select data
    def _options(values):
        return [{"value": str(v), "label": str(v)} for v in values]

    emissions_index = get_emissions_index()
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
                        dmc.TextInput(
                            id="edit-em-scenario-name-input",
                            label="Scenario name",
                            style={"flex": 2},
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
                            data=_options(emissions_index["emission_scenario"]),
                            searchable=True,
                            clearable=False,
                        ),
                        dmc.Select(
                            id="edit-em-gea-grid-region",
                            label="GEA grid region",
                            placeholder="Select grid region",
                            data=_options(emissions_index["gea_grid_region"]),
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
                            data=_options(emissions_index["emission_type"]),
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
                            data=_options(emissions_index["year"]),
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
                        dmc.Stack(
                            [
                                dmc.Text(
                                    id="edit-em-ng-emission-rate-label",
                                    children="Gas emissions rate (g/kWh)",
                                    size="sm",
                                    fw=500,
                                ),
                                dmc.NumberInput(
                                    id="edit-em-ng-emission-rate",
                                    min=0,
                                    step=1,
                                ),
                            ],
                            gap=4,
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
