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
    build_completeness_modal,
    build_completeness_summary,
    LOAD_INDEX,  # slider min/max values in base SI units
)

from layout.output import (
    building_characteristics_card,
    load_characteristics_card,
    empty_state,
)

from src.loads import StandardLoad, STANDARD_COLUMNS, get_load_data
from utils.tooltips import with_icon, with_tooltip, TOOLTIPS
from utils.logging_config import get_logger

logger = get_logger(__name__)


dash.register_page(__name__, name="Loads", path=URLS.HOME.value, order=0)

# Preprocess once at the top of the file and split space-separated zips into rows
locations_df = pd.read_csv("data/input/locations.csv")
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
                        with_icon(
                            text="Loads",
                            order=5,
                            icon="basil:book-open-outline",
                            href="https://github.com/CenterForTheBuiltEnvironment/decarb-tool",
                        ),
                        html.Hr(),
                        select_location(locations_df=locations_df),
                        html.Hr(),
                        select_load_type(),
                        modal_load_data_selection(buildings_df=buildings_df),
                        build_completeness_modal(),
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
                        dmc.Title("Summary", order=6),
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
                span=4,
            ),
            dmc.GridCol(
                dmc.Paper(
                    [
                        dmc.Title("Load visualization", order=6),
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
                                with_tooltip(
                                    dmc.Button(
                                        "Specify Equipment ",
                                        rightSection=DashIconify(
                                            icon="tabler:arrow-narrow-right-dashed"
                                        ),
                                        variant="filled",
                                        color="blue",
                                        id="button-specify-equipment",
                                        n_clicks=0,
                                    ),
                                    TOOLTIPS["loads"]["specify_equipment_button"],
                                )
                            ],
                            href="/equipment",
                            style={"float": "right"},
                        ),
                    ],
                    bg="white",
                    radius="md",
                    withBorder=False,
                    p="md",
                ),
                span=5,
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
        if row["state_id"] == "CA":
            metadata.climate_zone_output = (
                metadata.ashrae_climate_zone + f" (CA Region {row["ca_climate"]:.0f})"
            )
        else:
            metadata.climate_zone_output = metadata.ashrae_climate_zone
        metadata.set_gea_grid_region_for_all(row["gea_grid_region"])

        logger.info(
            f"Updated metadata location to {metadata.location}, ASHRAE Climate Zone {metadata.climate_zone_output}, based on zip {selected_zip}"
        )

    return metadata.model_dump()


@callback(
    [
        Output("selected-building-store", "data"),
        Output("modal-load-data", "opened", allow_duplicate=True),
        Output("metadata-store", "data", allow_duplicate=True),
        Output("load-data-path-store", "data"),
        Output("load-summary-store", "data"),
        Output("data-completeness-modal", "opened"),
        Output("completeness-summary-content", "children"),
        Output("pending-load-data-store", "data"),
    ],
    Input("confirm-building-button", "n_clicks"),
    State("building-radio-group", "value"),
    State("metadata-store", "data"),
    State("session-store", "data"),
    prevent_initial_call=True,
)
def confirm_selection(n_clicks, current_choice, metadata_data, session_data):
    """
    Handle library selection confirm.
    - For simulated data: proceed directly (update metadata, close modal)
    - For measured data: show completeness modal first
    """
    if not n_clicks or current_choice is None:
        raise dash.exceptions.PreventUpdate

    metadata = Metadata(**metadata_data) if metadata_data else Metadata.create()

    building = next(
        (b for b in BUILDINGS if str(b.get("building_id")) == str(current_choice)),
        None,
    )
    if building is None:
        # 8 outputs
        return no_update, no_update, metadata_data, no_update, no_update, no_update, no_update, no_update

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
    # Load data once, save parquet path, and compute summary payload
    # ------------------------------------------------------------------
    load_data_path = None
    summary_payload = None
    data_summary = None

    try:
        # 1) get StandardLoad for this selection
        load_obj = get_load_data(metadata)
        df = load_obj.df.sort_index()

        # Get data completeness summary
        data_summary = load_obj.get_data_summary()

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
        logger.info(
            f"Using load dataset with ID {metadata.building_id}, saved to {path}"
        )

        # -------------------------
        # Build summary for charts
        # -------------------------
        if not isinstance(df.index, pd.DatetimeIndex):
            raise ValueError("Expected DatetimeIndex in StandardLoad.df")

        # Monthly peaks (HHW & CHW) - keep in base units (W)
        monthly = df.copy()
        monthly["month"] = monthly.index.month
        peaks = (
            monthly.groupby("month", observed=True)[["heating_W", "cooling_W"]]
            .max()
            .reset_index()
        )

        monthly_summary = [
            {
                "month": int(row["month"]),
                "HHW_W": float(row["heating_W"]),
                "CHW_W": float(row["cooling_W"]),
            }
            for _, row in peaks.iterrows()
        ]

        # Temp bins: centered 5°C bins
        temp_df = df.copy()
        bin_width = 5
        half = bin_width / 2

        t_min = temp_df["t_out_C"].min()
        t_max = temp_df["t_out_C"].max()

        center_start = np.floor(t_min / bin_width) * bin_width
        center_end = np.ceil(t_max / bin_width) * bin_width
        centers = np.arange(center_start, center_end + bin_width, bin_width)
        bin_edges = np.arange(
            center_start - half, center_end + half + bin_width, bin_width
        )

        temp_df["t_bin"] = pd.cut(
            temp_df["t_out_C"],
            bins=bin_edges,
            labels=centers,
            include_lowest=True,
        )

        bin_stats = (
            temp_df.groupby("t_bin", observed=True)[["heating_W", "cooling_W"]]
            .mean()
            .reset_index()
        )

        temp_summary = [
            {
                "center": float(row["t_bin"]) if row["t_bin"] is not None else None,
                "HHW_W": float(row["heating_W"]),
                "CHW_W": float(row["cooling_W"]),
            }
            for _, row in bin_stats.iterrows()
        ]

        summary_payload = {
            "monthly_peaks": monthly_summary,
            "temp_bins": temp_summary,
        }

    except Exception as e:
        logger.error(
            f"Error loading/saving/summarizing load data for building {metadata.building_id}: {e}"
        )
        # leave load_data_path and summary_payload as None

    selected_building_payload = {
        "building_id": building.get("building_id"),
        "building_type": building.get("building_type"),
        "load_type": building.get("load_type"),
    }

    # ------------------------------------------------------------------
    # Check if this is measured data - if so, show completeness modal
    # ------------------------------------------------------------------
    load_type = metadata.load_data.load_type

    if load_type == "measured" and data_summary is not None:
        # Store pending data and show completeness modal
        pending_data = {
            "source_type": "measured",
            "selected_building": selected_building_payload,
            "metadata": metadata.model_dump(),
            "load_data_path": load_data_path,
            "summary_payload": summary_payload,
            "data_summary": {
                "start_date": data_summary["start_date"].isoformat() if data_summary.get("start_date") else None,
                "end_date": data_summary["end_date"].isoformat() if data_summary.get("end_date") else None,
                "num_hours": data_summary.get("num_hours"),
                "expected_hours": data_summary.get("expected_hours"),
                "is_complete": data_summary.get("is_complete"),
                "hours_complete": data_summary.get("hours_complete"),
                "data_complete": data_summary.get("data_complete"),
                "has_leap_day": data_summary.get("has_leap_day"),
                "spans_multiple_years": data_summary.get("spans_multiple_years"),
                "missing_hours": data_summary.get("missing_hours"),
                "column_stats": data_summary.get("column_stats", {}),
                "has_missing_values": data_summary.get("has_missing_values", False),
                "total_missing_values": data_summary.get("total_missing_values", 0),
            },
        }

        # Build completeness summary UI (need to convert dates back for display)
        display_summary = {
            **pending_data["data_summary"],
            "start_date": data_summary.get("start_date"),
            "end_date": data_summary.get("end_date"),
        }
        completeness_content = build_completeness_summary(display_summary, source_type="measured")

        return (
            no_update,  # selected-building-store
            no_update,  # modal-load-data opened (keep open)
            no_update,  # metadata-store
            no_update,  # load-data-path-store
            no_update,  # load-summary-store
            True,  # data-completeness-modal opened
            completeness_content,  # completeness-summary-content
            pending_data,  # pending-load-data-store
        )

    # For simulated data, proceed directly
    return (
        selected_building_payload,
        False,  # Close library modal
        metadata.model_dump(),
        load_data_path,
        summary_payload,
        False,  # Don't open completeness modal
        no_update,  # completeness-summary-content
        None,  # Clear pending data
    )


# -------------------------------------------------------------------
# Callback: Handle completeness modal confirm
# -------------------------------------------------------------------
@callback(
    [
        Output("selected-building-store", "data", allow_duplicate=True),
        Output("modal-load-data", "opened", allow_duplicate=True),
        Output("metadata-store", "data", allow_duplicate=True),
        Output("load-data-path-store", "data", allow_duplicate=True),
        Output("load-summary-store", "data", allow_duplicate=True),
        Output("data-completeness-modal", "opened", allow_duplicate=True),
        Output("pending-load-data-store", "data", allow_duplicate=True),
        Output("custom-metadata-error", "children"),
    ],
    Input("completeness-confirm-btn", "n_clicks"),
    State("pending-load-data-store", "data"),
    State("custom-building-id", "value"),
    State("custom-building-type", "value"),
    State("custom-vintage", "value"),
    State("custom-area", "value"),
    State("unit-toggle", "value"),
    prevent_initial_call=True,
)
def handle_completeness_confirm(
    n_clicks, pending_data, building_id, building_type, vintage, area, unit_mode
):
    """Finalize selection after user confirms in completeness modal."""
    from utils.units import sqft_to_sqm

    if not n_clicks or not pending_data:
        raise dash.exceptions.PreventUpdate

    # Extract data from pending store
    selected_building = pending_data.get("selected_building")
    metadata = pending_data.get("metadata")
    load_data_path = pending_data.get("load_data_path")
    summary_payload = pending_data.get("summary_payload")
    source_type = pending_data.get("source_type")
    load_stats = pending_data.get("load_stats", {})

    unit_mode = unit_mode or "SI"

    # For custom uploads, validate and save metadata fields
    if source_type == "custom":
        # Validate required fields
        errors = []
        if not building_id or not building_id.strip():
            errors.append("Building ID is required")
        if area is None or area <= 0:
            errors.append("Building Area is required and must be greater than 0")

        if errors:
            return (
                no_update, no_update, no_update, no_update, no_update,
                no_update, no_update,
                " | ".join(errors),
            )

        # Convert area to base units (sqm) if in IP mode
        area_sqm = sqft_to_sqm(area) if unit_mode == "IP" else area

        # Update metadata with custom fields
        if metadata:
            metadata["building_id"] = building_id.strip()
            metadata["building_type"] = building_type if building_type else None
            metadata["vintage"] = int(vintage) if vintage else None
            metadata["area_sqm"] = float(area_sqm)

            # Also populate LoadData fields with computed stats
            if load_stats:
                load_data = metadata.get("load_data", {})
                for key, value in load_stats.items():
                    if value is not None:
                        load_data[key] = value
                metadata["load_data"] = load_data

        # Log custom metadata
        logger.info(
            f"Custom upload metadata: building_id={building_id.strip()}, "
            f"building_type={building_type}, vintage={vintage}, "
            f"area_sqm={area_sqm:.1f}"
        )

        # Create selected_building payload for custom uploads
        selected_building = {
            "building_id": building_id.strip(),
            "building_type": building_type,
            "load_type": "custom",
        }

    return (
        selected_building,  # selected-building-store
        False,  # Close library modal
        metadata,  # metadata-store
        load_data_path,  # load-data-path-store
        summary_payload,  # load-summary-store
        False,  # Close completeness modal
        None,  # Clear pending data
        "",  # Clear error message
    )


# -------------------------------------------------------------------
# Callback: Handle completeness modal cancel
# -------------------------------------------------------------------
@callback(
    Output("data-completeness-modal", "opened", allow_duplicate=True),
    Output("pending-load-data-store", "data", allow_duplicate=True),
    Input("completeness-cancel-btn", "n_clicks"),
    prevent_initial_call=True,
)
def handle_completeness_cancel(n_clicks):
    """Cancel completeness modal - close it and discard pending data."""
    if not n_clicks:
        raise dash.exceptions.PreventUpdate

    return False, None  # Close modal and clear pending data


# -------------------------------------------------------------------
# Callback: Show/hide custom metadata inputs based on source type
# -------------------------------------------------------------------
@callback(
    Output("custom-metadata-inputs", "style"),
    Output("custom-area-label", "children"),
    Input("pending-load-data-store", "data"),
    Input("unit-toggle", "value"),
    prevent_initial_call=True,
)
def toggle_custom_metadata_inputs(pending_data, unit_mode):
    """Show metadata inputs for custom uploads, hide for measured data."""
    from utils.units import get_display_unit

    unit_mode = unit_mode or "SI"
    area_unit = get_display_unit("area", unit_mode)
    area_label = f"Building Area ({area_unit})"

    if not pending_data:
        return {"display": "none"}, area_label

    source_type = pending_data.get("source_type")
    if source_type == "custom":
        return {"display": "block"}, area_label
    else:
        return {"display": "none"}, area_label


@callback(
    Output("summary-selection-info", "children"),
    Input("metadata-store", "data"),
    Input("unit-toggle", "value"),
)
def show_metadata(data, unit_mode):
    if not data:
        return "No metadata yet"

    unit_mode = unit_mode or "SI"
    metadata = Metadata(**data)

    return (
        building_characteristics_card(metadata, unit_mode=unit_mode),
        dmc.Space(h=10),
        load_characteristics_card(metadata, unit_mode=unit_mode),
    )


def parse_custom_load_data(contents, filename, session_id="default"):
    """Parse and validate uploaded CSV file contents.

    Returns dict with status, filepath, data_summary, and summary_payload.
    """
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
        load_obj = StandardLoad(df)

        # Get data completeness summary
        data_summary = load_obj.get_data_summary()

        # Log data characteristics
        logger.info(
            f"Loaded custom data: {load_obj.num_hours} hours, "
            f"has_leap_day={load_obj.has_leap_day}, "
            f"spans_multiple_years={load_obj.spans_multiple_years}, "
            f"range={load_obj.df.index.min()} to {load_obj.df.index.max()}"
        )

        # Save to session folder
        folder = Path(f"/tmp/{session_id}")
        folder.mkdir(parents=True, exist_ok=True)
        temp_file = folder / f"custom_load_{Path(filename).stem}.parquet"
        load_obj.to_parquet(temp_file)

        # Build summary payload for charts (same logic as confirm_selection)
        df_sorted = load_obj.df.sort_index()

        # Monthly peaks
        monthly = df_sorted.copy()
        monthly["month"] = monthly.index.month
        peaks = (
            monthly.groupby("month", observed=True)[["heating_W", "cooling_W"]]
            .max()
            .reset_index()
        )
        monthly_summary = [
            {
                "month": int(row["month"]),
                "HHW_W": float(row["heating_W"]),
                "CHW_W": float(row["cooling_W"]),
            }
            for _, row in peaks.iterrows()
        ]

        # Temp bins
        temp_df = df_sorted.copy()
        bin_width = 5
        half = bin_width / 2
        t_min = temp_df["t_out_C"].min()
        t_max = temp_df["t_out_C"].max()
        center_start = np.floor(t_min / bin_width) * bin_width
        center_end = np.ceil(t_max / bin_width) * bin_width
        centers = np.arange(center_start, center_end + bin_width, bin_width)
        bin_edges = np.arange(
            center_start - half, center_end + half + bin_width, bin_width
        )
        temp_df["t_bin"] = pd.cut(
            temp_df["t_out_C"],
            bins=bin_edges,
            labels=centers,
            include_lowest=True,
        )
        bin_stats = (
            temp_df.groupby("t_bin", observed=True)[["heating_W", "cooling_W"]]
            .mean()
            .reset_index()
        )
        temp_summary = [
            {
                "center": float(row["t_bin"]) if row["t_bin"] is not None else None,
                "HHW_W": float(row["heating_W"]),
                "CHW_W": float(row["cooling_W"]),
            }
            for _, row in bin_stats.iterrows()
        ]

        summary_payload = {
            "monthly_peaks": monthly_summary,
            "temp_bins": temp_summary,
        }

        # Compute load statistics for LoadData fields
        load_stats = load_obj.compute_load_stats()

        return {
            "status": "success",
            "message": f"Successfully loaded {len(df)} rows of custom load data",
            "filepath": str(temp_file),
            "data_summary": data_summary,
            "summary_payload": summary_payload,
            "load_stats": load_stats,
        }

    except Exception as e:
        logger.error(f"Error parsing custom load data: {e}")
        return {"status": "error", "message": f"Error processing file: {str(e)}"}


@callback(
    [
        Output("upload-data-alert", "children"),
        Output("data-completeness-modal", "opened", allow_duplicate=True),
        Output("completeness-summary-content", "children", allow_duplicate=True),
        Output("pending-load-data-store", "data", allow_duplicate=True),
        Output("upload-data", "contents"),  # Reset upload to allow re-upload
    ],
    Input("upload-data", "contents"),
    State("upload-data", "filename"),
    State("metadata-store", "data"),
    State("session-store", "data"),
    prevent_initial_call=True,
)
def process_upload(contents, filename, metadata_data, session_data):
    """Process uploaded custom load data file and show completeness modal."""
    if not contents:
        return no_update, no_update, no_update, no_update, no_update

    session_id = session_data.get("session_id") if session_data else "default"
    result = parse_custom_load_data(contents, filename, session_id)

    # Create alert component based on result
    if result["status"] == "success":
        # Get the data summary for display
        data_summary = result.get("data_summary", {})

        # Prepare pending data for confirmation
        metadata = Metadata(**metadata_data) if metadata_data else Metadata.create()
        metadata.load_data.load_type = "custom"
        metadata.custom_load_path = result["filepath"]

        # Serialize dates for JSON storage
        pending_data = {
            "source_type": "custom",
            "selected_building": None,  # No building for custom uploads
            "metadata": metadata.model_dump(),
            "load_data_path": result["filepath"],
            "summary_payload": result.get("summary_payload"),
            "data_summary": {
                "start_date": data_summary["start_date"].isoformat() if data_summary.get("start_date") else None,
                "end_date": data_summary["end_date"].isoformat() if data_summary.get("end_date") else None,
                "num_hours": data_summary.get("num_hours"),
                "expected_hours": data_summary.get("expected_hours"),
                "is_complete": data_summary.get("is_complete"),
                "hours_complete": data_summary.get("hours_complete"),
                "data_complete": data_summary.get("data_complete"),
                "has_leap_day": data_summary.get("has_leap_day"),
                "spans_multiple_years": data_summary.get("spans_multiple_years"),
                "missing_hours": data_summary.get("missing_hours"),
                "column_stats": data_summary.get("column_stats", {}),
                "has_missing_values": data_summary.get("has_missing_values", False),
                "total_missing_values": data_summary.get("total_missing_values", 0),
            },
            "load_stats": result.get("load_stats", {}),
            "filename": filename,
        }

        # Build completeness summary UI
        completeness_content = build_completeness_summary(data_summary, source_type="custom")

        # Show info alert that file was parsed
        alert = dbc.Alert(
            [
                DashIconify(icon="bi:info-circle-fill", className="me-2"),
                f"Parsed '{filename}' - please review data summary and confirm.",
            ],
            color="info",
            dismissable=True,
            is_open=True,
        )

        return (
            alert,  # upload-data-alert
            True,  # data-completeness-modal opened
            completeness_content,  # completeness-summary-content
            pending_data,  # pending-load-data-store
            None,  # Clear upload contents to allow re-upload
        )
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
        return alert, no_update, no_update, no_update, None  # Clear upload contents


# -------------------------------------------------------------------
# Callback: filter and rebuild table
# -------------------------------------------------------------------
@callback(
    Output("building-table-container", "children"),
    [
        Input("load-type-filter", "value"),
        Input("climate-filter", "value"),
        Input("building-type-filter", "value"),
        Input("area-range-slider", "value"),
        Input("hhw-range-slider", "value"),
        Input("chw-range-slider", "value"),
        # Input("temp-range-slider", "value"),
        Input("metadata-store", "data"),  # re-sort when metadata changes
        Input("unit-toggle", "value"),  # unit mode for table display
    ],
    State("building-radio-group", "value"),
)
def update_table(
    load_type_filter,
    climate_filter,
    building_type_filter,
    area_range,
    hhw_range,
    chw_range,
    # temp_range,
    metadata_data,
    unit_mode,
    current_choice,
):
    from utils.units import sqm_to_sqft, W_to_BTUh, ton_to_W

    unit_mode = unit_mode or "SI"

    # -----------------------------
    # Convert slider values back to base SI units for filtering
    # Sliders show: SI mode = kW, IP mode = MMBTU/h (heating) / TR (cooling)
    # Data is stored in: W (for power), m² (for area)
    # -----------------------------
    if area_range and len(area_range) == 2:
        if unit_mode == "IP":
            # ft² → m²
            area_range = [a / 10.7639 for a in area_range]
        else:
            # Already in m² (slider shows m² in SI mode)
            pass

    if hhw_range and len(hhw_range) == 2:
        if unit_mode == "IP":
            # MMBTU/h → W (1 MMBTU/h = 1e6 BTU/h = 1e6/3.412 W)
            w_per_mmbtu = 1e6 / W_to_BTUh
            hhw_range = [h * w_per_mmbtu for h in hhw_range]
        else:
            # kW → W
            hhw_range = [h * 1000 for h in hhw_range]

    if chw_range and len(chw_range) == 2:
        if unit_mode == "IP":
            # TR → W (1 TR = 3517 W)
            chw_range = [c * ton_to_W for c in chw_range]
        else:
            # kW → W
            chw_range = [c * 1000 for c in chw_range]

    # -----------------------------
    # 0) Base filter: load_type
    # -----------------------------
    if load_type_filter in (None, "all"):
        df = buildings_df.copy()
    else:
        if "load_type" in buildings_df.columns:
            df = buildings_df[buildings_df["load_type"] == load_type_filter].copy()
        else:
            df = buildings_df.copy()

    if df.empty:
        return build_building_table(df, selected_id=None, unit_mode=unit_mode)

    # -----------------------------
    # 1) Additional filters
    # -----------------------------

    # Climate zone filter (use same logic as below for column detection)
    if climate_filter:
        clim_col = None
        for cand in ("ashrae_climate_zone", "climate"):
            if cand in df.columns:
                clim_col = cand
                break
        if clim_col:
            df = df[df[clim_col] == climate_filter]

    # Building type filter
    if building_type_filter and "building_type" in df.columns:
        df = df[df["building_type"] == building_type_filter]

    # Area range filter (try area_sqm or area_m2) - values now in m²
    if area_range and len(area_range) == 2:
        amin, amax = area_range
        area_col = None
        for cand in ("area_sqm", "area_m2"):
            if cand in df.columns:
                area_col = cand
                break
        if area_col:
            df = df[df[area_col].between(amin, amax)]

    # HHW peak range filter - values now in W
    if hhw_range and len(hhw_range) == 2 and "hhw_max_load" in df.columns:
        hmin, hmax = hhw_range
        df = df[df["hhw_max_load"].between(hmin, hmax)]

    # CHW peak range filter - values now in W
    if chw_range and len(chw_range) == 2 and "chw_max_load" in df.columns:
        cmin, cmax = chw_range
        df = df[df["chw_max_load"].between(cmin, cmax)]

    if df.empty:
        return build_building_table(df, selected_id=None, unit_mode=unit_mode)

    # -----------------------------
    # 2) Metadata-based priority sort (unchanged)
    # -----------------------------
    meta_location = None
    meta_climate = None
    if metadata_data:
        meta_location = metadata_data.get("location")
        meta_climate = metadata_data.get("ashrae_climate_zone")

    # detect location column
    loc_col = None
    for cand in ("location", "city"):
        if cand in df.columns:
            loc_col = cand
            break

    # detect climate column
    clim_col = None
    for cand in ("ashrae_climate_zone", "climate"):
        if cand in df.columns:
            clim_col = cand
            break

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

    # -----------------------------
    # 3) Preserve selection if still visible
    # -----------------------------
    selected_id = None
    if "building_id" in df.columns:
        visible_ids = set(df["building_id"].astype(str).tolist())
        if current_choice is not None and str(current_choice) in visible_ids:
            selected_id = current_choice

    return build_building_table(df, selected_id, unit_mode=unit_mode)


# -------------------------------------------------------------------
# Callback: update slider labels and properties based on unit_mode
# -------------------------------------------------------------------
@callback(
    # Slider labels
    Output("area-slider-label", "children"),
    Output("hhw-slider-label", "children"),
    Output("chw-slider-label", "children"),
    # Slider properties (min, max, step, marks, value)
    Output("area-range-slider", "min"),
    Output("area-range-slider", "max"),
    Output("area-range-slider", "step"),
    Output("area-range-slider", "marks"),
    Output("area-range-slider", "value"),
    Output("hhw-range-slider", "min"),
    Output("hhw-range-slider", "max"),
    Output("hhw-range-slider", "step"),
    Output("hhw-range-slider", "marks"),
    Output("hhw-range-slider", "value"),
    Output("chw-range-slider", "min"),
    Output("chw-range-slider", "max"),
    Output("chw-range-slider", "step"),
    Output("chw-range-slider", "marks"),
    Output("chw-range-slider", "value"),
    Input("unit-toggle", "value"),
    prevent_initial_call=False,
)
def update_slider_units(unit_mode):
    """Update slider labels and ranges based on unit mode (SI/IP)."""
    from utils.units import get_display_unit, sqm_to_sqft, W_to_BTUh, W_to_tons

    unit_mode = unit_mode or "SI"

    # Get base values from LOAD_INDEX (in SI units, stored as W)
    area_min_si, area_max_si = LOAD_INDEX["area_sqm"]
    hhw_min_si, hhw_max_si = LOAD_INDEX["hhw_max_load"]
    chw_min_si, chw_max_si = LOAD_INDEX["chw_max_load"]

    # Get display units
    area_unit = get_display_unit("area", unit_mode)

    if unit_mode == "IP":
        # Convert area: m² → ft²
        area_min = int(sqm_to_sqft(area_min_si))
        area_max = int(sqm_to_sqft(area_max_si))
        area_step = 5000

        # Convert HHW: W → MMBTU/h (1 MMBTU/h = 1e6 BTU/h = 1e6/3.412 W)
        # Using MMBTU/h to avoid excessively large numbers
        mmbtu_per_w = W_to_BTUh / 1e6  # W to MMBTU/h
        hhw_min = round(hhw_min_si * mmbtu_per_w, 1)
        hhw_max = round(hhw_max_si * mmbtu_per_w, 1)
        hhw_step = 0.5
        hhw_label_unit = "MMBTU/h"

        # Convert CHW: W → TR (tons of refrigeration)
        chw_min = round(W_to_tons(chw_min_si), 0)
        chw_max = round(W_to_tons(chw_max_si), 0)
        chw_step = 50
        chw_label_unit = "TR"
    else:
        # SI mode - use kW for power
        area_min = area_min_si
        area_max = area_max_si
        area_step = 500

        # Convert W to kW for display
        hhw_min = int(hhw_min_si / 1000)
        hhw_max = int(hhw_max_si / 1000)
        hhw_step = 50
        hhw_label_unit = "kW"

        chw_min = int(chw_min_si / 1000)
        chw_max = int(chw_max_si / 1000)
        chw_step = 50
        chw_label_unit = "kW"

    # Format mark labels
    def format_large_number(n):
        if abs(n) >= 1_000_000:
            return f"{n / 1_000_000:.1f}M"
        elif abs(n) >= 1_000:
            return f"{n / 1_000:.0f}k"
        return f"{n:.1f}" if isinstance(n, float) else str(int(n))

    area_label = f"Area ({area_unit})"
    hhw_label = f"HHW Peak Load [{hhw_label_unit}]"
    chw_label = f"CHW Peak Load [{chw_label_unit}]"

    # Build marks
    area_marks = [
        {"value": area_min, "label": format_large_number(area_min)},
        {"value": area_max, "label": format_large_number(area_max)},
    ]
    hhw_marks = [
        {"value": hhw_min, "label": format_large_number(hhw_min)},
        {"value": hhw_max, "label": format_large_number(hhw_max)},
    ]
    chw_marks = [
        {"value": chw_min, "label": format_large_number(chw_min)},
        {"value": chw_max, "label": format_large_number(chw_max)},
    ]

    return (
        # Labels
        area_label,
        hhw_label,
        chw_label,
        # Area slider
        area_min,
        area_max,
        area_step,
        area_marks,
        [area_min, area_max],
        # HHW slider
        hhw_min,
        hhw_max,
        hhw_step,
        hhw_marks,
        [hhw_min, hhw_max],
        # CHW slider
        chw_min,
        chw_max,
        chw_step,
        chw_marks,
        [chw_min, chw_max],
    )


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
        return dmc.Group(
            [
                DashIconify(icon="mdi:home-off-outline", width=15),
                dmc.Text("No building selected yet.", c="gray", size="sm"),
            ],
            gap="xs",
        )

    building = next(
        (b for b in BUILDINGS if str(b["building_id"]) == str(current_choice)),
        None,
    )

    if building is None:
        return dmc.Group(
            [
                DashIconify(icon="mdi:alert-circle-outline", width=15),
                dmc.Text(
                    f"Only found building ID: {current_choice}", c="red", size="sm"
                ),
            ],
            gap="xs",
        )

    building_type = building["building_type"]
    location = building["location"]
    ashrae_climate_zone = building["ashrae_climate_zone"]

    return dmc.Group(
        [
            DashIconify(
                icon="mdi:office-building-marker-outline",
                width=15,
            ),
            dmc.Text(
                [
                    "Select ",
                    dmc.Text(building_type, fw=800, span=True),
                    " building in ",
                    dmc.Text(location, fw=800, span=True),
                    ", ASHRAE Climate Zone ",
                    dmc.Text(ashrae_climate_zone, fw=800, span=True),
                    "?",
                ],
                c="blue",
                size="sm",
            ),
        ],
        gap="xs",
        align="center",
    )


@callback(
    Output("load-visualization-panel", "children"),
    [
        Input("load-summary-store", "data"),
        Input("url", "pathname"),
        Input("unit-toggle", "value"),
    ],
    prevent_initial_call=False,
)
def update_load_visualization(summary_data, pathname, unit_mode):

    # Only draw when we are on the Loads page
    if pathname != URLS.HOME.value:
        raise dash.exceptions.PreventUpdate

    # No summary yet → keep whatever is in the layout (empty_state defaults)
    if not summary_data:
        raise dash.exceptions.PreventUpdate

    unit_mode = unit_mode or "SI"

    # Import unit conversion helpers
    from utils.units import get_unit_label, C_to_F, get_auto_scale_for_values

    temp_unit = get_unit_label("temperature", unit_mode)

    try:
        monthly_summary = summary_data.get("monthly_peaks", []) or []
        temp_summary = summary_data.get("temp_bins", []) or []

        # ------------------------------------------------------------------
        # Determine auto-scaling for power values (already in base units W)
        # ------------------------------------------------------------------
        all_power_w = []
        for item in monthly_summary:
            all_power_w.extend([item["HHW_W"], item["CHW_W"]])
        for item in temp_summary:
            all_power_w.extend([item["HHW_W"], item["CHW_W"]])

        # Filter out None values
        all_power_w = [w for w in all_power_w if w is not None]

        # Get auto-scale (scale_factor, unit_label) - works directly with base units
        power_scale, power_unit = get_auto_scale_for_values(
            all_power_w, "power", unit_mode
        )

        # Helper to scale W values to display values
        def scale_power(w):
            if w is None:
                return 0
            return w / power_scale

        # ------------------------------------------------------------------
        # Chart 1: Monthly peak HHW & CHW from summary
        # ------------------------------------------------------------------
        monthly_data = [
            {
                "month": calendar.month_abbr[item["month"]],
                "HHW": round(scale_power(item["HHW_W"]), 1),
                "CHW": round(scale_power(item["CHW_W"]), 1),
            }
            for item in monthly_summary
        ]

        monthly_chart = dmc.AreaChart(
            h=260,
            data=monthly_data,
            dataKey="month",
            withLegend=True,
            xAxisLabel="Month",
            yAxisLabel=f"Peak load ({power_unit})",
            curveType="linear",
            tooltipAnimationDuration=200,
            series=[
                {"name": "HHW", "color": "red.6"},
                {"name": "CHW", "color": "blue.6"},
            ],
        )

        # ------------------------------------------------------------------
        # Chart 2: HHW & CHW vs temperature bins from summary
        # ------------------------------------------------------------------
        bin_data = []
        for item in temp_summary:
            if item["center"] is not None:
                if unit_mode == "IP":
                    # Convert to °F and round to nearest 10 for cleaner labels
                    temp_val = round(C_to_F(item["center"]) / 10) * 10
                else:
                    temp_val = item["center"]
                bin_label = f"{int(temp_val)} {temp_unit}"
            else:
                bin_label = "N/A"
            bin_data.append(
                {
                    "bin": bin_label,
                    "HHW": round(scale_power(item["HHW_W"]), 1),
                    "CHW": round(scale_power(item["CHW_W"]), 1),
                }
            )

        temp_chart = dmc.CompositeChart(
            h=260,
            data=bin_data,
            dataKey="bin",
            withLegend=True,
            xAxisLabel=f"Outdoor temperature ({temp_unit})",
            yAxisLabel=f"Avg load ({power_unit})",
            tooltipAnimationDuration=200,
            series=[
                {"name": "HHW", "type": "bar", "color": "red.6", "yAxisId": "left"},
                {"name": "CHW", "type": "bar", "color": "blue.6", "yAxisId": "left"},
            ],
        )

        # Dynamic bin size description
        bin_size_desc = "~10°F" if unit_mode == "IP" else "5°C"

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
                    f"Average heating and cooling vs outdoor temperature bins ({bin_size_desc})",
                    size="sm",
                    c="dimmed",
                ),
                temp_chart,
            ],
            gap="md",
        )

    except Exception as e:
        logger.error(f"Error building load charts from summary data: {e}")
        return [
            empty_state(
                title="Unable to show load preview",
                description="There was a problem reading the load summary.",
                icon="ph:warning-circle",
            )
        ]
