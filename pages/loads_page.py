import base64
import calendar
import io
from pathlib import Path

import dash
from dash import dcc, html, Input, Output, State, callback, ctx, no_update
import dash_bootstrap_components as dbc
import dash_mantine_components as dmc
from dash_iconify import DashIconify

import pandas as pd
import numpy as np

from src.config import URLS
from src.metadata import Metadata, LoadData
from src.loads import StandardLoad, STANDARD_COLUMNS


from layout.input import (
    select_location,
    select_load_type,
    modal_load_data_selection,
    build_building_table,
)

from layout.output import (
    building_characteristics_card,
    load_characteristics_card,
    empty_state,
)

from src.loads import StandardLoad, STANDARD_COLUMNS, get_load_data


dash.register_page(__name__, name="Loads", path=URLS.HOME.value, order=0)

# Preprocess once at the top of the file
locations_df = pd.read_csv("data/input/locations.csv")

# Split space-separated zips into rows
locations_df = (
    locations_df.assign(zip=locations_df["zips"].str.split())
    .explode("zip")
    .drop(columns=["zips"])
)
locations_df["zip"] = locations_df["zip"].astype(str)


# Load building metadata from CSV
buildings_df = pd.read_csv("data/input/building_metadata.csv")
BUILDINGS = buildings_df.to_dict("records")


def layout():
    return dmc.Grid(
        [
            dmc.GridCol(
                dmc.Paper(
                    [
                        html.H5("Loads"),
                        html.Hr(),
                        select_location(locations_df=locations_df),
                        html.Hr(),
                        select_load_type(),
                        modal_load_data_selection(buildings_df=buildings_df),
                    ],
                    bg="gray.0",
                    radius="md",
                    withBorder=False,
                    p="md",
                    shadow="xs",
                ),
                span=3,
            ),
            dmc.GridCol(
                dmc.Paper(
                    [
                        html.H5("Summary"),
                        html.Div(
                            id="summary-selection-info",
                        ),
                        html.Pre(
                            id="metadata-display", style={"whiteSpace": "pre-wrap"}
                        ),
                    ],
                    bg="white",
                    radius="md",
                    withBorder=False,
                    p="md",
                ),
                span=3,
            ),
            dmc.GridCol(
                dmc.Paper(
                    [
                        html.H5("Load visualization"),
                        html.Div(
                            id="load-visualization-panel",
                            children=[
                                empty_state(icon="ph:chart-line-up"),
                                dmc.Divider(),
                                empty_state(
                                    title="Same here!",
                                    description="A nice plot will pop up here once load data is selected.",
                                    icon="ph:bug",
                                ),
                            ],
                        ),
                        dmc.Space(h=20),
                        dcc.Link(
                            [
                                dmc.Button(
                                    "Specify Equipment ",
                                    rightSection=DashIconify(
                                        icon="tabler:arrow-narrow-right-dashed"
                                    ),
                                    size="md",
                                    radius="md",
                                    variant="gradient",
                                    gradient={"from": "indigo", "to": "cyan"},
                                    id="button-specify-equipment",
                                    n_clicks=0,
                                    style={"float": "right"},
                                ),
                            ],
                            href="/equipment",
                        ),
                    ],
                    bg="white",
                    radius="md",
                    withBorder=False,
                    p="md",
                ),
                span=6,
            ),
        ],
        gutter="xl",
    )


@callback(
    Output("url", "href"),
    Input("button-specify-equipment", "n_clicks"),
    prevent_initial_call=True,
)
def navigate_to_equipment(n_clicks):
    if not n_clicks:  # ignore None or 0
        raise dash.exceptions.PreventUpdate
    return "/equipment"


@callback(
    Output("modal-load-data", "opened"),
    Input("open-load-library-modal", "n_clicks"),
    State("modal-load-data", "opened"),
    prevent_initial_call=True,
)
def toggle_modal(n_clicks, opened):
    if not n_clicks:
        raise dash.exceptions.PreventUpdate
    return not opened


#! Needs to be reworked later + add trigger from modal confirm button
@callback(
    Output("metadata-store", "data"),
    Input("location-input", "value"),
    State("metadata-store", "data"),
    prevent_initial_call=True,
)
def update_metadata(
    selected_zip,
    metadata_data,
):
    # Figure out which input triggered
    trigger = ctx.triggered_id

    if not trigger:  # no trigger
        return metadata_data

    metadata = Metadata(**metadata_data) if metadata_data else Metadata.create()

    if trigger == "location-input" and selected_zip:
        # look up the location row
        row = locations_df.loc[locations_df["zip"] == selected_zip].iloc[0]
        metadata.location = row["city"]
        metadata.ashrae_climate_zone = row["ASHRAE"]
        metadata.set_gea_grid_region_for_all(row["gea_grid_region"])

    return metadata.model_dump()


@callback(
    [
        Output("selected-building-store", "data"),
        Output("modal-load-data", "opened", allow_duplicate=True),
        Output("metadata-store", "data", allow_duplicate=True),
        Output("load-data-path-store", "data"),
    ],
    Input("confirm-building-button", "n_clicks"),
    State("building-radio-group", "value"),
    State("metadata-store", "data"),
    State("session-store", "data"),
    prevent_initial_call=True,
)
def confirm_selection(n_clicks, current_choice, metadata_data, session_data):
    if not n_clicks or current_choice is None:
        raise dash.exceptions.PreventUpdate

    metadata = Metadata(**metadata_data) if metadata_data else Metadata.create()

    building = next(
        (b for b in BUILDINGS if str(b.get("building_id")) == str(current_choice)),
        None,
    )
    if building is None:
        return no_update, no_update, metadata_data, no_update

    # --- building_id explicitly on Metadata ------------------------------------
    metadata.building_id = str(building.get("building_id"))

    # --- Split building dict into metadata vs load_data updates ----------------
    meta_fields = set(Metadata.model_fields.keys())
    load_fields = set(LoadData.model_fields.keys())

    metadata_updates = {}
    load_updates = {}

    for key, value in building.items():
        if key == "building_id":
            continue

        # treat None, "", and NaN as "missing"
        if (
            value is None
            or value == ""
            or (isinstance(value, float) and pd.isna(value))
        ):
            continue

        if key in load_fields:
            load_updates[key] = value
        elif key in meta_fields and key != "load_data":
            metadata_updates[key] = value

    # type fixes
    if "vintage" in metadata_updates:
        v = metadata_updates["vintage"]
        if pd.notna(v) and v != "":
            metadata_updates["vintage"] = int(v)
        else:
            metadata_updates.pop("vintage", None)

    if "ashrae_climate_zone" in metadata_updates:
        metadata_updates["ashrae_climate_zone"] = str(
            metadata_updates["ashrae_climate_zone"]
        )

    # apply updates
    for field, value in metadata_updates.items():
        setattr(metadata, field, value)

    for field, value in load_updates.items():
        setattr(metadata.load_data, field, value)

    # gea grid region
    region = building.get("gea_grid_region")
    if region:
        metadata.set_gea_grid_region_for_all(region)

    # optional: path column in buildings_df
    if "load_file_path" in building and building["load_file_path"]:
        metadata.custom_load_path = building["load_file_path"]

    # ------------------------------------------------------------------
    # Save filtered load data into /tmp/<session_id>/... and store path
    # ------------------------------------------------------------------
    load_data_path = no_update
    try:
        # 1) get StandardLoad for this selection
        load_obj = get_load_data(metadata)

        # 2) build session folder
        session_id = session_data.get("session_id") if session_data else "default"
        folder = Path(f"/tmp/{session_id}")
        folder.mkdir(parents=True, exist_ok=True)

        # 3) choose file name
        fname = f"load_data_building_{metadata.building_id}_{metadata.load_data.load_type}.parquet"
        path = folder / fname

        # 4) save as parquet
        load_obj.to_parquet(path)

        # 5) store path as string
        load_data_path = str(path)

        print(f"Saved load data for building {metadata.building_id} to {path}")

    except Exception as e:
        print(
            f"Error loading/saving load data for building {metadata.building_id}: {e}"
        )

    selected_building_payload = {
        "building_id": building.get("building_id"),
        "building_type": building.get("building_type"),
        "load_type": building.get("load_type"),
    }

    return (
        selected_building_payload,
        False,
        metadata.model_dump(),
        load_data_path,
    )


@callback(Output("summary-selection-info", "children"), Input("metadata-store", "data"))
def show_metadata(data):
    if not data:
        return "No metadata yet"

    metadata = Metadata(**data)

    return (
        building_characteristics_card(metadata),
        dmc.Space(h=10),
        load_characteristics_card(metadata),
    )


def parse_custom_load_data(contents, filename):
    """Parse and validate uploaded CSV file contents."""
    content_type, content_string = contents.split(",")
    decoded = base64.b64decode(content_string)

    try:
        # Read CSV into DataFrame
        df = pd.read_csv(io.StringIO(decoded.decode("utf-8")))

        # Check for required columns (using template names)
        missing_cols = [col for col in STANDARD_COLUMNS if col not in df.columns]
        if missing_cols:
            raise ValueError(f"Missing required columns: {missing_cols}")

        # Create StandardLoad object (this runs validation)
        load_data = StandardLoad(df)

        # Save to temporary file
        temp_dir = Path("data/output/custom")
        temp_dir.mkdir(parents=True, exist_ok=True)
        temp_file = temp_dir / f"custom_load_{Path(filename).stem}.parquet"
        load_data.to_parquet(temp_file)

        return {
            "status": "success",
            "message": f"Successfully loaded {len(df)} rows of custom load data",
            "filepath": str(temp_file),
        }

    except Exception as e:
        return {"status": "error", "message": f"Error processing file: {str(e)}"}


@callback(
    [
        Output("upload-data-alert", "children"),
        Output("metadata-store", "data", allow_duplicate=True),
    ],
    Input("upload-data", "contents"),
    State("upload-data", "filename"),
    State("metadata-store", "data"),
    prevent_initial_call=True,
)
def process_upload(contents, filename, metadata_data):
    """Process uploaded custom load data file."""
    if not contents:
        return no_update, no_update

    result = parse_custom_load_data(contents, filename)

    # Create alert component based on result
    if result["status"] == "success":
        alert = dbc.Alert(
            [
                DashIconify(icon="bi:check-circle-fill", className="me-2"),
                result["message"],
            ],
            color="success",
            dismissable=True,
            is_open=True,
        )

        metadata = Metadata(**metadata_data) if metadata_data else Metadata.create()
        metadata.load_data.load_type = "load_custom"
        metadata.custom_load_path = result["filepath"]

        return alert, metadata.model_dump()
    else:
        alert = dbc.Alert(
            [
                DashIconify(icon="bi:exclamation-circle-fill", className="me-2"),
                result["message"],
            ],
            color="danger",
            dismissable=True,
            is_open=True,
        )
        return alert, no_update


# -------------------------------------------------------------------
# Callback: filter and rebuild table
# -------------------------------------------------------------------
@callback(
    Output("building-table-container", "children"),
    [
        Input("load-type-filter", "value"),
        Input("metadata-store", "data"),  # re-sort when metadata changes
    ],
    State("building-radio-group", "value"),
)
def update_table(load_type_filter, metadata_data, current_choice):

    if load_type_filter in (None, "all"):
        df = buildings_df.copy()
    else:
        df = buildings_df[buildings_df["load_type"] == load_type_filter].copy()

    if df.empty:
        return build_building_table(df, selected_id=None)

    meta_location = None
    meta_climate = None
    if metadata_data:
        meta_location = metadata_data.get("location")
        meta_climate = metadata_data.get("ashrae_climate_zone")

    # ? This could be streamlined, usually it's location + ashrae_climate_zone
    loc_col = None
    for cand in ("location", "city"):
        if cand in df.columns:
            loc_col = cand
            break

    clim_col = None
    for cand in ("ashrae_climate_zone", "climate"):
        if cand in df.columns:
            clim_col = cand
            break

    # implement your 3-step priority logic (location, climate zone, rest) for sorting table
    priority_col_added = False

    def apply_priority(mask_series):
        nonlocal df, priority_col_added
        df["__priority"] = 1
        df.loc[mask_series, "__priority"] = 0
        priority_col_added = True

    if loc_col and clim_col and meta_location and meta_climate:
        # Step 1: exact match on BOTH location + climate
        mask_both = (df[loc_col] == meta_location) & (df[clim_col] == meta_climate)
        if mask_both.any():
            apply_priority(mask_both)
        else:
            # Step 2: same climate zone only
            if meta_climate:
                mask_climate = df[clim_col] == meta_climate
                if mask_climate.any():
                    apply_priority(mask_climate)
    elif clim_col and meta_climate:
        mask_climate = df[clim_col] == meta_climate
        if mask_climate.any():
            apply_priority(mask_climate)

    # Step 3: if no matches, leave df order as-is
    if priority_col_added:
        sort_cols = ["__priority"]
        if "building_type" in df.columns:
            sort_cols.append("building_type")
        if "building_id" in df.columns:
            sort_cols.append("building_id")

        df = df.sort_values(sort_cols).drop(columns="__priority")

    selected_id = None
    if "building_id" in df.columns:
        visible_ids = set(df["building_id"].astype(str).tolist())
        if current_choice is not None and str(current_choice) in visible_ids:
            selected_id = current_choice

    return build_building_table(df, selected_id)


# -------------------------------------------------------------------
# Enable/disable confirm button
# -------------------------------------------------------------------
@callback(
    Output("confirm-building-button", "disabled"),
    Input("building-radio-group", "value"),
)
def toggle_confirm_button(current_choice):
    return current_choice is None


# -------------------------------------------------------------------
# Show summary of selected building (on radio change)
# -------------------------------------------------------------------
@callback(
    Output("selected-building-text", "children"),
    Input("building-radio-group", "value"),
)
def update_selected_text(current_choice):
    if current_choice is None:
        return "No building selected yet."

    building = next(
        (
            building
            for building in BUILDINGS
            if building["building_id"] == current_choice
        ),
        None,
    )
    if building is None:
        return f"Selected building ID: {current_choice}"

    return f"Selected: {building['building_id']} – {building['building_type']} ({building['load_type']})"


@callback(
    Output("load-visualization-panel", "children"),
    Input("load-data-path-store", "data"),
    prevent_initial_call=True,
)
def update_load_visualization(load_path):
    # If no path (or some weird empty value), leave the layout as-is
    if not load_path:
        raise dash.exceptions.PreventUpdate

    try:
        load = StandardLoad.from_parquet(load_path)
        df = load.df.sort_index()

        if not isinstance(df.index, pd.DatetimeIndex):
            raise ValueError("Expected DatetimeIndex in StandardLoad.df")

        # ------------------------------------------------------------------
        # Chart 1: Monthly peak HHW & CHW (W -> kW)
        # ------------------------------------------------------------------
        monthly = df.copy()
        monthly["month"] = monthly.index.month

        peaks = monthly.groupby("month")[["heating_W", "cooling_W"]].max().reset_index()
        peaks["HHW_kW"] = peaks["heating_W"] / 1000.0
        peaks["CHW_kW"] = peaks["cooling_W"] / 1000.0

        monthly_data = [
            {
                "month": calendar.month_abbr[int(row["month"])],
                "HHW": round(row["HHW_kW"], 0),
                "CHW": round(row["CHW_kW"], 0),
            }
            for _, row in peaks.iterrows()
        ]

        monthly_chart = dmc.AreaChart(
            h=260,
            data=monthly_data,
            dataKey="month",
            withLegend=True,
            xAxisLabel="Month",
            yAxisLabel="Peak load (kW)",
            curveType="linear",
            tooltipAnimationDuration=200,
            series=[
                {"name": "HHW", "color": "red.6"},
                {"name": "CHW", "color": "blue.6"},
            ],
        )

        # ------------------------------------------------------------------
        # Chart 2: HHW & CHW vs 5°C T_out bins (CompositeChart)
        # ------------------------------------------------------------------
        if "t_out_C" not in df.columns:
            raise ValueError("t_out_C column missing in load data")

        temp_df = df.copy()

        # define bin width and half-width
        bin_width = 5
        half = bin_width / 2

        t_min = temp_df["t_out_C"].min()
        t_max = temp_df["t_out_C"].max()

        center_start = np.floor((t_min) / bin_width) * bin_width
        center_end = np.ceil((t_max) / bin_width) * bin_width

        centers = np.arange(center_start, center_end + bin_width, bin_width)

        bin_edges = np.arange(
            center_start - half, center_end + half + bin_width, bin_width
        )

        temp_df["t_bin"] = pd.cut(
            temp_df["t_out_C"],
            bins=bin_edges,
            labels=centers,  # label bin by its center (clean!)
            include_lowest=True,
        )

        bin_stats = (
            temp_df.groupby("t_bin", observed=True)[["heating_W", "cooling_W"]]
            .mean()
            .reset_index()
        )

        # convert to kW + label formatting
        bin_stats["HHW_kW"] = bin_stats["heating_W"] / 1000.0
        bin_stats["CHW_kW"] = bin_stats["cooling_W"] / 1000.0
        bin_stats["bin_label"] = bin_stats["t_bin"].apply(
            lambda c: f"{int(c)} °C" if pd.notna(c) else "N/A"
        )

        bin_data = [
            {
                "bin": row["bin_label"],
                "HHW": round(row["HHW_kW"], 0),
                "CHW": round(row["CHW_kW"], 0),
            }
            for _, row in bin_stats.iterrows()
        ]

        temp_chart = dmc.CompositeChart(
            h=260,
            data=bin_data,
            dataKey="bin",
            withLegend=True,
            xAxisLabel="Outdoor temperature (°C)",
            yAxisLabel="Avg load (kW)",
            tooltipAnimationDuration=200,
            series=[
                {"name": "HHW", "type": "bar", "color": "red.6", "yAxisId": "left"},
                {"name": "CHW", "type": "bar", "color": "blue.6", "yAxisId": "left"},
            ],
        )

        return dmc.Stack(
            [
                dmc.Text(
                    "Monthly peak heating (HHW) and cooling (CHW) loads",
                    size="sm",
                    c="dimmed",
                ),
                monthly_chart,
                dmc.Divider(my="sm"),
                dmc.Text(
                    "Average heating and cooling vs outdoor temperature bins (5°C)",
                    size="sm",
                    c="dimmed",
                ),
                temp_chart,
            ],
            gap="md",
        )

    except Exception as e:
        print(f"Error building load charts from {load_path}: {e}")
        return [
            empty_state(
                title="Unable to show load preview",
                description="There was a problem reading the load data.",
                icon="ph:warning-circle",
            )
        ]
