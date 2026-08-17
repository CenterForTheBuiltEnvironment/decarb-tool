import base64
import calendar
import io
from functools import lru_cache
from pathlib import Path

import dash
import dash_bootstrap_components as dbc
import dash_mantine_components as dmc
import numpy as np
import pandas as pd
from dash import Input, Output, State, callback, ctx, dcc, html, no_update
from dash_iconify import DashIconify

from layout.input import (
    build_base_load_modal,
    build_building_table,
    build_completeness_modal,
    build_completeness_summary,
    build_scale_load_modal,
    get_load_index,  # slider min/max values in base SI units (lazy-loaded)
    modal_load_data_selection,
    select_load_type,
    select_location,
)
from layout.output import (
    building_characteristics_card,
    empty_state,
    load_characteristics_card,
)
from src import paths
from src.config import URLS
from src.loads import STANDARD_COLUMNS, StandardLoad, get_load_data
from src.metadata import LoadData, Metadata
from utils.error_handling import create_success_notification
from utils.logging_config import get_logger
from utils.tooltips import TOOLTIPS, with_icon, with_tooltip

logger = get_logger(__name__)


dash.register_page(__name__, name="Loads", path=URLS.HOME.value, order=0)


# --- Lazy-loaded data accessors (cached after first call) ---
@lru_cache(maxsize=1)
def get_locations_df():
    """Lazy-load and cache locations data with zip code expansion."""
    df = pd.read_csv(paths.LOCATIONS_CSV)
    df = df.assign(zip=df["zips"].str.split()).explode("zip").drop(columns=["zips"])
    df["zip"] = df["zip"].astype(str)
    return df


@lru_cache(maxsize=1)
def get_buildings_df():
    """Lazy-load and cache building metadata."""
    return pd.read_csv(paths.BUILDING_METADATA_CSV)


def get_buildings_list():
    """Get buildings as list of dicts (for table display)."""
    return get_buildings_df().to_dict("records")


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
                        select_location(),
                        html.Hr(),
                        select_load_type(),
                        modal_load_data_selection(buildings_df=get_buildings_df()),
                        build_completeness_modal(),
                        build_scale_load_modal(),
                        build_base_load_modal(),
                        html.Div(
                            style={"marginTop": "20px"},
                            children=[
                                dmc.Group(
                                    [
                                        dmc.Indicator(
                                            dmc.Tooltip(
                                                dmc.Button(
                                                    "Scale Loads",
                                                    id="open-scale-load-modal",
                                                    variant="outline",
                                                    color="blue",
                                                    size="sm",
                                                    n_clicks=0,
                                                    disabled=True,
                                                ),
                                                id="scale-load-btn-tooltip",
                                                label="Select a load from the library first",
                                                withArrow=True,
                                                position="right",
                                            ),
                                            id="scale-load-btn-indicator",
                                            color="green",
                                            label=DashIconify(icon="mdi:check-bold", width=10),
                                            size=18,
                                            position="top-end",
                                            disabled=True,
                                            inline=True,
                                            withBorder=True,
                                        ),
                                        dmc.Indicator(
                                            dmc.Tooltip(
                                                dmc.Button(
                                                    "Base Load",
                                                    id="open-base-load-modal",
                                                    variant="outline",
                                                    color="blue",
                                                    size="sm",
                                                    n_clicks=0,
                                                    disabled=True,
                                                ),
                                                id="base-load-btn-tooltip",
                                                label="Select a load from the library first",
                                                withArrow=True,
                                                position="right",
                                            ),
                                            id="base-load-btn-indicator",
                                            color="green",
                                            label=DashIconify(icon="mdi:check-bold", width=10),
                                            size=18,
                                            position="top-end",
                                            disabled=True,
                                            inline=True,
                                            withBorder=True,
                                        ),
                                    ],
                                    gap="xs",
                                ),
                            ],
                        ),
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
                        html.Pre(id="metadata-display", style={"whiteSpace": "pre-wrap"}),
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


@callback(
    Output("location-input", "options"),
    Input("location-input", "search_value"),
    Input("location-input", "value"),  # Also trigger when value changes
)
def filter_location_options(search_value, current_value):
    """Server-side search for location dropdown (avoids sending 44K options to client)."""
    locations = get_locations_df()
    options = []

    # Always include current selection first (so it stays visible)
    if current_value:
        selected_row = locations[locations["zip"] == current_value]
        if not selected_row.empty:
            row = selected_row.iloc[0]
            label = f"{row['zip']} {row['city']}, {row['state_id']}"
            options.append({"label": label, "value": current_value})

    # Add search results if user is searching (min 2 chars)
    if search_value and len(search_value) >= 2:
        search_lower = search_value.lower()

        # Filter by zip or city (case-insensitive)
        mask = locations["zip"].str.lower().str.startswith(search_lower) | locations[
            "city"
        ].str.lower().str.contains(search_lower, regex=False)
        filtered = locations[mask].head(100)

        # Add filtered results (excluding current value to avoid duplicate)
        for _, row in filtered.iterrows():
            if row["zip"] != current_value:
                label = f"{row['zip']} {row['city']}, {row['state_id']}"
                options.append({"label": label, "value": row["zip"]})

    return options


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
        locations = get_locations_df()
        row = locations.loc[locations["zip"] == selected_zip].iloc[0]
        metadata.location = row["city"]
        metadata.ashrae_climate_zone = row["ASHRAE"]
        if row["state_id"] == "CA":
            metadata.climate_zone_output = (
                metadata.ashrae_climate_zone + f" (CA Region {row['ca_climate']:.0f})"
            )
        else:
            metadata.climate_zone_output = metadata.ashrae_climate_zone
        metadata.set_gea_grid_region_for_all(row["gea_grid_region"])

        logger.info(
            f"Updated metadata location to {metadata.location}, ASHRAE Climate Zone {metadata.climate_zone_output}, based on zip {selected_zip}"
        )

    return metadata.model_dump()


def _build_summary_payload(load_obj: "StandardLoad") -> dict:
    """Build monthly_peaks + temp_bins summary payload from a StandardLoad."""
    df = load_obj.df.sort_index()

    monthly = df.copy()
    monthly["month"] = monthly.index.month
    peaks = monthly.groupby("month", observed=True)[["heating_W", "cooling_W"]].max().reset_index()
    monthly_summary = [
        {
            "month": int(row["month"]),
            "HHW_W": float(row["heating_W"]),
            "CHW_W": float(row["cooling_W"]),
        }
        for _, row in peaks.iterrows()
    ]

    temp_df = df.copy()
    bin_width = 5
    half = bin_width / 2
    t_min = temp_df["t_out_C"].min()
    t_max = temp_df["t_out_C"].max()
    center_start = np.floor(t_min / bin_width) * bin_width
    center_end = np.ceil(t_max / bin_width) * bin_width
    centers = np.arange(center_start, center_end + bin_width, bin_width)
    bin_edges = np.arange(center_start - half, center_end + half + bin_width, bin_width)
    temp_df["t_bin"] = pd.cut(
        temp_df["t_out_C"], bins=bin_edges, labels=centers, include_lowest=True
    )
    bin_stats = (
        temp_df.groupby("t_bin", observed=True)[["heating_W", "cooling_W"]].mean().reset_index()
    )
    temp_summary = [
        {
            "center": float(row["t_bin"]) if row["t_bin"] is not None else None,
            "HHW_W": float(row["heating_W"]),
            "CHW_W": float(row["cooling_W"]),
        }
        for _, row in bin_stats.iterrows()
    ]

    return {"monthly_peaks": monthly_summary, "temp_bins": temp_summary}


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
        Output("scale-info-store", "data", allow_duplicate=True),
        Output("base-load-info-store", "data", allow_duplicate=True),
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
        (b for b in get_buildings_list() if str(b.get("building_id")) == str(current_choice)),
        None,
    )
    if building is None:
        return (
            no_update,
            no_update,
            metadata_data,
            no_update,
            no_update,
            no_update,
            no_update,
            no_update,
            no_update,
            no_update,
        )

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
        if value is None or value == "" or (isinstance(value, float) and pd.isna(value)):
            continue

        if key in load_fields:
            load_updates[key] = value
        elif key in meta_fields and key != "load_data":
            metadata_updates[key] = value

    # type fixes
    if "vintage" in metadata_updates:
        v = metadata_updates["vintage"]
        if pd.notna(v) and v != "":
            try:
                metadata_updates["vintage"] = int(v)
            except (TypeError, ValueError):
                metadata_updates.pop("vintage", None)
        else:
            metadata_updates.pop("vintage", None)

    if "ashrae_climate_zone" in metadata_updates:
        metadata_updates["ashrae_climate_zone"] = str(metadata_updates["ashrae_climate_zone"])

    # apply updates
    for field, value in metadata_updates.items():
        setattr(metadata, field, value)

    metadata.load_data = LoadData.model_validate(
        {**metadata.load_data.model_dump(), **load_updates}
    )

    # gea grid region
    region = building.get("gea_grid_region")
    if region:
        metadata.set_gea_grid_region_for_all(region)

    # optional: path column in buildings_df
    if building.get("load_file_path"):
        metadata.custom_load_path = building["load_file_path"]

    # Clear any previous scaling override so the fresh selection starts unscaled
    metadata.session_load_path = None

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
        logger.info(f"Using load dataset with ID {metadata.building_id}, saved to {path}")

        # Build summary for charts
        if not isinstance(df.index, pd.DatetimeIndex):
            raise ValueError("Expected DatetimeIndex in StandardLoad.df")

        summary_payload = _build_summary_payload(load_obj)

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
                "start_date": (
                    data_summary["start_date"].isoformat()
                    if data_summary.get("start_date")
                    else None
                ),
                "end_date": (
                    data_summary["end_date"].isoformat() if data_summary.get("end_date") else None
                ),
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
            no_update,  # scale-info-store
            no_update,  # base-load-info-store
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
        None,  # Clear scale-info-store
        None,  # Clear base-load-info-store
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
        Output("scale-info-store", "data", allow_duplicate=True),
        Output("base-load-info-store", "data", allow_duplicate=True),
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
                no_update,
                no_update,
                no_update,
                no_update,
                no_update,
                no_update,
                no_update,
                " | ".join(errors),
            )

        # Convert area to base units (sqm) if in IP mode
        area_sqm = sqft_to_sqm(area) if unit_mode == "IP" else area

        # Update metadata with custom fields
        if metadata:
            metadata["building_id"] = building_id.strip()
            metadata["building_type"] = building_type if building_type else None
            metadata["vintage"] = int(vintage) if vintage is not None else None
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
        None,  # Clear scale-info-store
        None,  # Clear base-load-info-store
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
    Input("scale-info-store", "data"),
    Input("base-load-info-store", "data"),
)
def show_metadata(data, unit_mode, scale_info, base_load_info):
    if not data:
        return "No metadata yet"

    unit_mode = unit_mode or "SI"
    metadata = Metadata(**data)

    return (
        building_characteristics_card(metadata, unit_mode=unit_mode),
        dmc.Space(h=10),
        load_characteristics_card(
            metadata,
            unit_mode=unit_mode,
            is_scaled=bool(scale_info),
            is_base_loaded=bool(base_load_info),
        ),
    )


def parse_custom_load_data(contents, filename, session_id="default"):
    """Parse and validate uploaded CSV file contents.

    Returns dict with status, filepath, data_summary, and summary_payload.
    """
    _, content_string = contents.split(",")
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

        summary_payload = _build_summary_payload(load_obj)

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
        return {"status": "error", "message": f"Error processing file: {e!s}"}


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
                "start_date": (
                    data_summary["start_date"].isoformat()
                    if data_summary.get("start_date")
                    else None
                ),
                "end_date": (
                    data_summary["end_date"].isoformat() if data_summary.get("end_date") else None
                ),
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
    from utils.units import W_to_BTUh, ton_to_W

    unit_mode = unit_mode or "SI"

    # -----------------------------
    # Convert slider values back to base SI units for filtering
    # Sliders show: SI mode = kW, IP mode = kBTU/h (heating) / TR (cooling)
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
            # kBTU/h → W (1 kBTU/h = 1e3 BTU/h = 1e3/3.412 W)
            w_per_kbtu = 1e3 / W_to_BTUh
            hhw_range = [h * w_per_kbtu for h in hhw_range]
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
    buildings = get_buildings_df()
    if load_type_filter in (None, "all"):
        df = buildings.copy()
    else:
        if "load_type" in buildings.columns:
            df = buildings[buildings["load_type"] == load_type_filter].copy()
        else:
            df = buildings.copy()

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
    from utils.units import W_to_BTUh, W_to_tons, get_display_unit, sqm_to_sqft

    unit_mode = unit_mode or "SI"

    # Get base values from load index (in SI units, stored as W)
    load_index = get_load_index()
    area_min_si, area_max_si = load_index["area_sqm"]
    hhw_min_si, hhw_max_si = load_index["hhw_max_load"]
    chw_min_si, chw_max_si = load_index["chw_max_load"]

    # Get display units
    area_unit = get_display_unit("area", unit_mode)

    if unit_mode == "IP":
        # Convert area: m² → ft²
        area_min = int(sqm_to_sqft(area_min_si))
        area_max = int(sqm_to_sqft(area_max_si))
        area_step = 5000

        # Convert HHW: W → kBTU/h (1 kBTU/h = 1e3 BTU/h = 1e3/3.412 W)
        # Using kBTU/h to avoid excessively large numbers
        kbtu_per_w = W_to_BTUh / 1e3  # W to kBTU/h
        hhw_min = round(hhw_min_si * kbtu_per_w, 1)
        hhw_max = round(hhw_max_si * kbtu_per_w, 1)
        hhw_step = 0.5
        hhw_label_unit = "kBTU/h"

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
        (b for b in get_buildings_list() if str(b["building_id"]) == str(current_choice)),
        None,
    )

    if building is None:
        return dmc.Group(
            [
                DashIconify(icon="mdi:alert-circle-outline", width=15),
                dmc.Text(f"Only found building ID: {current_choice}", c="red", size="sm"),
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
    from utils.units import C_to_F, get_auto_scale_for_values, get_unit_label

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
        power_scale, power_unit = get_auto_scale_for_values(all_power_w, "power", unit_mode)

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


# -------------------------------------------------------------------
# Scale loads feature
# -------------------------------------------------------------------


@callback(
    Output("open-scale-load-modal", "disabled"),
    Output("open-scale-load-modal", "color"),
    Output("scale-load-btn-tooltip", "disabled"),
    Output("scale-load-btn-indicator", "disabled"),
    Input("metadata-store", "data"),
    Input("scale-info-store", "data"),
)
def update_scale_btn_state(metadata_data, scale_info):
    """Enable/disable the Scale Loads button and show active state when scaling is applied."""
    load_selected = metadata_data and Metadata(**metadata_data).load_data.load_type in (
        "simulated",
        "measured",
    )
    is_active = bool(scale_info)
    return (
        not load_selected,  # button disabled
        "green" if is_active else "blue",  # button color
        load_selected,  # tooltip disabled (hidden when button is enabled)
        not is_active,  # indicator disabled (shown when active)
    )


@callback(
    Output("scale-load-modal", "opened", allow_duplicate=True),
    Output("scale-reference-info", "children"),
    Input("open-scale-load-modal", "n_clicks"),
    Input("scale-cancel-btn", "n_clicks"),
    State("metadata-store", "data"),
    State("unit-toggle", "value"),
    prevent_initial_call=True,
)
def toggle_scale_modal(open_clicks, cancel_clicks, metadata_data, unit_mode):
    """Open or close the scale load modal."""
    from utils.units import W_to_BTUh, W_to_kW, W_to_tons, sqm_to_sqft

    if ctx.triggered_id == "scale-cancel-btn":
        return False, no_update

    if not metadata_data:
        return False, no_update

    unit_mode = unit_mode or "SI"
    metadata = Metadata(**metadata_data)
    ld = metadata.load_data

    def _fmt(val, decimals=1):
        return f"{val:,.{decimals}f}" if val is not None else "—"

    if unit_mode == "IP":
        area_val = sqm_to_sqft(metadata.area_sqm) if metadata.area_sqm else None
        area_unit = "ft²"
        hhw_val = ld.hhw_max_load * W_to_BTUh if ld.hhw_max_load is not None else None
        hhw_unit = "BTU/h"
        chw_val = W_to_tons(ld.chw_max_load) if ld.chw_max_load is not None else None
        chw_unit = "TR"
    else:
        area_val = metadata.area_sqm
        area_unit = "m²"
        hhw_val = W_to_kW(ld.hhw_max_load) if ld.hhw_max_load is not None else None
        hhw_unit = "kW"
        chw_val = W_to_kW(ld.chw_max_load) if ld.chw_max_load is not None else None
        chw_unit = "kW"

    ref_info = dmc.Stack(
        gap=4,
        children=[
            dmc.Text("Library building reference values:", size="sm", fw=600),
            dmc.Text(f"Area: {_fmt(area_val, 0)} {area_unit}", size="sm"),
            dmc.Text(f"Peak heating: {_fmt(hhw_val)} {hhw_unit}", size="sm"),
            dmc.Text(f"Peak cooling: {_fmt(chw_val)} {chw_unit}", size="sm"),
        ],
    )

    return True, ref_info


@callback(
    Output("scale-preview-text", "children"),
    Output("scale-target-label", "children"),
    Output("scale-error-text", "children"),
    Input("scale-method-select", "value"),
    Input("scale-target-value", "value"),
    State("metadata-store", "data"),
    State("unit-toggle", "value"),
    prevent_initial_call=True,
)
def update_scale_preview(method, target_value, metadata_data, unit_mode):
    """Update the input label and live scale-factor preview."""
    from utils.units import BTUh_to_W, ton_to_W

    unit_mode = unit_mode or "SI"

    labels = {
        "area": f"Your building area [{'ft²' if unit_mode == 'IP' else 'm²'}]",
        "peak_heating": f"Your peak heating load [{'BTU/h' if unit_mode == 'IP' else 'kW'}]",
        "peak_cooling": f"Your peak cooling load [{'TR' if unit_mode == 'IP' else 'kW'}]",
    }
    label = labels.get(method, "Enter value")

    try:
        target_value = float(target_value)
    except (TypeError, ValueError):
        return "", label, ""

    if not metadata_data or target_value <= 0:
        return "", label, ""

    metadata = Metadata(**metadata_data)
    ld = metadata.load_data

    try:
        if method == "area":
            ref_si = metadata.area_sqm
            target_si = target_value / 10.7639 if unit_mode == "IP" else target_value
        elif method == "peak_heating":
            ref_si = ld.hhw_max_load
            target_si = target_value * BTUh_to_W if unit_mode == "IP" else target_value * 1000
        else:  # peak_cooling
            ref_si = ld.chw_max_load
            target_si = target_value * ton_to_W if unit_mode == "IP" else target_value * 1000

        if not ref_si or ref_si <= 0:
            return "", label, f"Reference value for '{method}' not available in library data."

        scale_factor = target_si / ref_si
        if scale_factor <= 0:
            return "", label, "Scale factor must be positive."

        return f"Scale factor: {scale_factor:.3f}x", label, ""

    except Exception as e:
        return "", label, str(e)


@callback(
    Output("metadata-store", "data", allow_duplicate=True),
    Output("load-summary-store", "data", allow_duplicate=True),
    Output("scale-load-modal", "opened", allow_duplicate=True),
    Output("scale-info-store", "data"),
    Output("notification-container", "sendNotifications", allow_duplicate=True),
    Input("scale-apply-btn", "n_clicks"),
    State("scale-method-select", "value"),
    State("scale-target-value", "value"),
    State("metadata-store", "data"),
    State("load-data-path-store", "data"),
    State("unit-toggle", "value"),
    prevent_initial_call=True,
)
def apply_scale(n_clicks, method, target_value, metadata_data, load_data_path, unit_mode):
    """Apply load scaling: multiply every hourly heating_W and cooling_W by scale_factor."""
    from utils.units import BTUh_to_W, W_to_BTUh, W_to_kW, W_to_tons, ton_to_W

    no_change = (no_update, no_update, no_update, no_update, no_update)

    if not n_clicks:
        raise dash.exceptions.PreventUpdate

    unit_mode = unit_mode or "SI"

    if not metadata_data or not load_data_path:
        return no_change

    try:
        target_value = float(target_value)
    except (TypeError, ValueError):
        return no_change

    if target_value <= 0:
        return no_change

    metadata = Metadata(**metadata_data)
    ld = metadata.load_data

    # Compute scale factor
    try:
        if method == "area":
            ref_si = metadata.area_sqm
            target_si = target_value / 10.7639 if unit_mode == "IP" else target_value
            method_label = "building area"
        elif method == "peak_heating":
            ref_si = ld.hhw_max_load
            target_si = target_value * BTUh_to_W if unit_mode == "IP" else target_value * 1000
            method_label = "peak heating load"
        else:  # peak_cooling
            ref_si = ld.chw_max_load
            target_si = target_value * ton_to_W if unit_mode == "IP" else target_value * 1000
            method_label = "peak cooling load"

        if not ref_si or ref_si <= 0:
            return no_change

        scale_factor = target_si / ref_si
        if scale_factor <= 0:
            return no_change

    except Exception as e:
        logger.error(f"Scale factor computation failed: {e}")
        return no_change

    # Load, scale, and save parquet
    try:
        load_obj = StandardLoad.from_parquet(load_data_path)

        orig_hhw_max = float(load_obj.df["heating_W"].max())
        orig_chw_max = float(load_obj.df["cooling_W"].max())

        scaled_df = load_obj.df.copy()
        scaled_df["heating_W"] = scaled_df["heating_W"] * scale_factor
        scaled_df["cooling_W"] = scaled_df["cooling_W"] * scale_factor
        scaled_load = StandardLoad(scaled_df.reset_index())
        scaled_load.to_parquet(load_data_path)

    except Exception as e:
        logger.error(f"Error scaling load data: {e}")
        return no_change

    # Recompute stats and update metadata
    new_stats = scaled_load.compute_load_stats()
    if method == "area":
        metadata.area_sqm = target_si
    metadata.load_data = LoadData.model_validate({**ld.model_dump(), **new_stats})
    metadata.session_load_path = load_data_path

    # Rebuild summary payload for charts
    summary_payload = _build_summary_payload(scaled_load)

    # Build confirmation alert
    def _display_power(w_val):
        if w_val is None:
            return "—"
        if unit_mode == "IP":
            if method == "peak_cooling":
                return f"{W_to_tons(w_val):.1f} TR"
            return f"{w_val * W_to_BTUh:,.0f} BTU/h"
        return f"{W_to_kW(w_val):.1f} kW"

    new_hhw = new_stats["hhw_max_load"]
    new_chw = new_stats["chw_max_load"]

    scale_info = {
        "method": method_label,
        "scale_factor": round(scale_factor, 6),
        "orig_hhw_max_W": orig_hhw_max,
        "orig_chw_max_W": orig_chw_max,
        "new_hhw_max_W": new_hhw,
        "new_chw_max_W": new_chw,
    }

    notification = create_success_notification(
        "Load scaled",
        f"Scale factor {scale_factor:.3f}x (based on {method_label})",
        notification_id="scale-load-notification",
    )

    logger.info(
        f"Applied load scale factor {scale_factor:.4f} (method={method_label}) to {load_data_path}"
    )

    return metadata.model_dump(), summary_payload, False, scale_info, [notification]


# -------------------------------------------------------------------
# Base Load callbacks
# -------------------------------------------------------------------


@callback(
    Output("open-base-load-modal", "disabled"),
    Output("open-base-load-modal", "color"),
    Output("base-load-btn-tooltip", "disabled"),
    Output("base-load-btn-indicator", "disabled"),
    Input("metadata-store", "data"),
    Input("base-load-info-store", "data"),
)
def update_base_load_btn_state(metadata_data, base_load_info):
    """Enable/disable the Base Load button and show active state when a base load is applied."""
    load_selected = metadata_data and Metadata(**metadata_data).load_data.load_type in (
        "simulated",
        "measured",
    )
    is_active = bool(base_load_info)
    return (
        not load_selected,
        "green" if is_active else "blue",
        load_selected,
        not is_active,
    )


@callback(
    Output("base-load-modal", "opened", allow_duplicate=True),
    Output("base-load-current-values", "children"),
    Input("open-base-load-modal", "n_clicks"),
    Input("base-load-cancel-btn", "n_clicks"),
    State("metadata-store", "data"),
    State("unit-toggle", "value"),
    prevent_initial_call=True,
)
def toggle_base_load_modal(open_clicks, cancel_clicks, metadata_data, unit_mode):
    """Open or close the base load modal, showing current peak values for reference."""
    from utils.units import W_to_BTUh, W_to_kW, W_to_tons

    if ctx.triggered_id == "base-load-cancel-btn":
        return False, no_update

    if not metadata_data:
        return False, no_update

    unit_mode = unit_mode or "SI"
    metadata = Metadata(**metadata_data)
    ld = metadata.load_data

    def _fmt(val, decimals=1):
        return f"{val:,.{decimals}f}" if val is not None else "—"

    if unit_mode == "IP":
        hhw_val = ld.hhw_max_load * W_to_BTUh if ld.hhw_max_load is not None else None
        hhw_unit = "BTU/h"
        chw_val = W_to_tons(ld.chw_max_load) if ld.chw_max_load is not None else None
        chw_unit = "TR"
    else:
        hhw_val = W_to_kW(ld.hhw_max_load) if ld.hhw_max_load is not None else None
        hhw_unit = "kW"
        chw_val = W_to_kW(ld.chw_max_load) if ld.chw_max_load is not None else None
        chw_unit = "kW"

    current_values = dmc.Stack(
        gap=4,
        children=[
            dmc.Text("Current peak loads:", size="sm", fw=600),
            dmc.Text(f"Peak heating: {_fmt(hhw_val)} {hhw_unit}", size="sm"),
            dmc.Text(f"Peak cooling: {_fmt(chw_val)} {chw_unit}", size="sm"),
        ],
    )

    return True, current_values


@callback(
    Output("base-load-preview-text", "children"),
    Output("base-load-value-label", "children"),
    Output("base-load-error-text", "children"),
    Output("base-load-method-desc", "children"),
    Input("base-load-method-select", "value"),
    Input("base-load-apply-select", "value"),
    Input("base-load-value", "value"),
    State("metadata-store", "data"),
    State("unit-toggle", "value"),
    prevent_initial_call=True,
)
def update_base_load_preview(method, apply_to, value, metadata_data, unit_mode):
    """Update label, method description, and live preview text."""
    from utils.units import BTUh_to_W, W_to_BTUh, W_to_kW

    unit_mode = unit_mode or "SI"
    power_unit = "BTU/h" if unit_mode == "IP" else "kW"

    method_descs = {
        "floor": (
            "Raises any hour whose load falls below the specified value up to that minimum. "
            "Hours already at or above the floor are unchanged."
        ),
        "offset": (
            "Adds a fixed amount to every hourly load value, including the peak. "
            "Useful for modelling a year-round process load."
        ),
    }
    method_desc = method_descs.get(method, "")

    apply_labels = {
        "heating": f"Heating base load [{power_unit}]",
        "cooling": f"Cooling base load [{power_unit}]",
        "both": f"Base load [{power_unit}] (applied to heating and cooling)",
    }
    label = apply_labels.get(apply_to, f"Value [{power_unit}]")

    try:
        value = float(value)
    except (TypeError, ValueError):
        return "", label, "", method_desc

    if not metadata_data or value <= 0:
        return "", label, "", method_desc

    metadata = Metadata(**metadata_data)
    ld = metadata.load_data

    # Convert input to Watts
    value_W = value * BTUh_to_W if unit_mode == "IP" else value * 1000

    def _peak_display(w_val):
        if w_val is None:
            return "—"
        if unit_mode == "IP":
            return f"{w_val * W_to_BTUh:,.0f} BTU/h"
        return f"{W_to_kW(w_val):.1f} kW"

    lines = []
    applies_to_heating = apply_to in ("heating", "both")
    applies_to_cooling = apply_to in ("cooling", "both")

    if method == "floor":
        if applies_to_heating and ld.hhw_max_load is not None:
            if value_W > ld.hhw_max_load:
                lines.append(
                    f"Heating: floor ({_peak_display(value_W)}) exceeds current peak — all hours will be set to floor"
                )
            else:
                lines.append(f"Heating peak unchanged at {_peak_display(ld.hhw_max_load)}")
        if applies_to_cooling and ld.chw_max_load is not None:
            if value_W > ld.chw_max_load:
                lines.append(
                    f"Cooling: floor ({_peak_display(value_W)}) exceeds current peak — all hours will be set to floor"
                )
            else:
                lines.append(f"Cooling peak unchanged at {_peak_display(ld.chw_max_load)}")
    else:  # offset
        if applies_to_heating and ld.hhw_max_load is not None:
            new_hhw = ld.hhw_max_load + value_W
            lines.append(f"New peak heating: {_peak_display(new_hhw)} (+{_peak_display(value_W)})")
        if applies_to_cooling and ld.chw_max_load is not None:
            new_chw = ld.chw_max_load + value_W
            lines.append(f"New peak cooling: {_peak_display(new_chw)} (+{_peak_display(value_W)})")

    preview = " · ".join(lines) if lines else ""
    return preview, label, "", method_desc


@callback(
    Output("metadata-store", "data", allow_duplicate=True),
    Output("load-summary-store", "data", allow_duplicate=True),
    Output("base-load-modal", "opened", allow_duplicate=True),
    Output("base-load-info-store", "data"),
    Output("notification-container", "sendNotifications", allow_duplicate=True),
    Input("base-load-apply-btn", "n_clicks"),
    State("base-load-method-select", "value"),
    State("base-load-apply-select", "value"),
    State("base-load-value", "value"),
    State("metadata-store", "data"),
    State("load-data-path-store", "data"),
    State("unit-toggle", "value"),
    prevent_initial_call=True,
)
def apply_base_load(n_clicks, method, apply_to, value, metadata_data, load_data_path, unit_mode):
    """Apply base load modification: floor or offset on heating and/or cooling loads."""
    from utils.units import BTUh_to_W

    no_change = (no_update, no_update, no_update, no_update, no_update)

    if not n_clicks:
        raise dash.exceptions.PreventUpdate

    unit_mode = unit_mode or "SI"

    if not metadata_data or not load_data_path:
        return no_change

    try:
        value = float(value)
    except (TypeError, ValueError):
        return no_change

    if value <= 0:
        return no_change

    # Convert to Watts
    value_W = value * BTUh_to_W if unit_mode == "IP" else value * 1000

    applies_to_heating = apply_to in ("heating", "both")
    applies_to_cooling = apply_to in ("cooling", "both")

    try:
        load_obj = StandardLoad.from_parquet(load_data_path)
        modified_df = load_obj.df.copy()

        if method == "floor":
            if applies_to_heating:
                modified_df["heating_W"] = modified_df["heating_W"].clip(lower=value_W)
            if applies_to_cooling:
                modified_df["cooling_W"] = modified_df["cooling_W"].clip(lower=value_W)
        else:  # offset
            if applies_to_heating:
                modified_df["heating_W"] = modified_df["heating_W"] + value_W
            if applies_to_cooling:
                modified_df["cooling_W"] = modified_df["cooling_W"] + value_W

        modified_load = StandardLoad(modified_df.reset_index())
        modified_load.to_parquet(load_data_path)

    except Exception as e:
        logger.error(f"Error applying base load modification: {e}")
        return no_change

    # Recompute stats and update metadata
    metadata = Metadata(**metadata_data)
    ld = metadata.load_data
    new_stats = modified_load.compute_load_stats()
    metadata.load_data = LoadData.model_validate({**ld.model_dump(), **new_stats})
    metadata.session_load_path = load_data_path

    summary_payload = _build_summary_payload(modified_load)

    apply_to_label = {"heating": "heating", "cooling": "cooling", "both": "heating + cooling"}[
        apply_to
    ]
    method_label = "floor" if method == "floor" else "offset"
    value_display = f"{value:,.0f} BTU/h" if unit_mode == "IP" else f"{value:.1f} kW"

    base_load_info = {
        "method": method_label,
        "apply_to": apply_to,
        "value_W": value_W,
        "value_display": value_display,
    }

    notification = create_success_notification(
        "Base load applied",
        f"{method_label.capitalize()} of {value_display} applied to {apply_to_label}",
        notification_id="base-load-notification",
    )

    logger.info(
        f"Applied base load {method_label} of {value_W:.1f} W to {apply_to} loads in {load_data_path}"
    )

    return metadata.model_dump(), summary_payload, False, base_load_info, [notification]
