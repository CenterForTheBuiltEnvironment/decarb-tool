from pprint import pprint
import dash
from dash import dcc, html, Input, Output, State, callback, ctx, no_update
import dash_bootstrap_components as dbc
import dash_mantine_components as dmc
import base64
import io
from pathlib import Path

from dash_iconify import DashIconify
import pandas as pd

from src.config import URLS
from src.metadata import Metadata, LoadData
from src.loads import StandardLoad, STANDARD_COLUMNS


from layout.input import (
    select_gea_grid_region,
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
                        dcc.Link(
                            [
                                dmc.Button(
                                    [
                                        "Specify Equipment ",
                                        DashIconify(
                                            icon="tabler:arrow-narrow-right-dashed",
                                            width=20,
                                        ),
                                    ],
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
                span=3,
            ),
            dmc.GridCol(
                dmc.Paper(
                    [
                        html.H5("Load visualization"),
                        empty_state(
                            icon="ph:chart-line-up",
                        ),
                        dmc.Divider(),
                        empty_state(
                            title="Same here!",
                            description="A nice plot will pop up here once load data is selected.",
                            icon="ph:bug",
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
        Output("modal-load-data", "opened", allow_duplicate=True),  # dmc.Modal
        Output("metadata-store", "data", allow_duplicate=True),
    ],
    Input("confirm-building-button", "n_clicks"),
    State("building-radio-group", "value"),
    State("metadata-store", "data"),
    prevent_initial_call=True,
)
def confirm_selection(n_clicks, current_choice, metadata_data):
    if not n_clicks or current_choice is None:
        raise dash.exceptions.PreventUpdate

    metadata = Metadata(**metadata_data) if metadata_data else Metadata.create()

    building = next(
        (b for b in BUILDINGS if str(b.get("building_id")) == str(current_choice)),
        None,
    )
    if building is None:
        return no_update, no_update, metadata_data

    # --- Split building dict into metadata vs load_data updates -----------------
    # Pydantic v2: use model_fields
    meta_fields = set(Metadata.model_fields.keys())
    load_fields = set(LoadData.model_fields.keys())

    metadata_updates = {}
    load_updates = {}

    for key, value in building.items():
        if key in ("building_id",):  # explicitly ignore
            continue
        if value in (None, ""):
            continue

        if key in load_fields:
            load_updates[key] = value
        elif key in meta_fields and key != "load_data":
            metadata_updates[key] = value
        # else: ignore extra columns

    # place to fix types if needed
    if "vintage" in metadata_updates:
        metadata_updates["vintage"] = int(metadata_updates["vintage"])

    if "ashrae_climate_zone" in metadata_updates:
        metadata_updates["ashrae_climate_zone"] = str(
            metadata_updates["ashrae_climate_zone"]
        )

    # --- Apply updates to metadata ---------------------------------------------
    for field, value in metadata_updates.items():
        setattr(metadata, field, value)

    for field, value in load_updates.items():
        setattr(metadata.load_data, field, value)

    # --- Special handling for gea_grid_region, if present ----------------------
    region = building.get("gea_grid_region")
    if region:
        metadata.set_gea_grid_region_for_all(region)

    # --- Optional: custom_load_path if you have such a column ------------------
    if "load_file_path" in building and building["load_file_path"]:
        metadata.custom_load_path = building["load_file_path"]

    selected_building_payload = {
        "building_id": building.get("building_id"),
        "building_type": building.get("building_type"),
        "load_type": building.get("load_type"),
    }

    return selected_building_payload, False, metadata.model_dump()


@callback(Output("summary-selection-info", "children"), Input("metadata-store", "data"))
def show_metadata(data):
    if not data:
        return "No metadata yet"

    metadata = Metadata(**data)  # ← convert dict → Metadata

    return (
        building_characteristics_card(metadata),
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

    # Parse and validate the file
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

        # Update metadata to use custom load data
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
    # 0) Start from full DF and filter by load type
    if load_type_filter in (None, "all"):
        df = buildings_df.copy()
    else:
        df = buildings_df[buildings_df["load_type"] == load_type_filter].copy()

    if df.empty:
        return build_building_table(df, selected_id=None)

    # 1) Pull current metadata values
    meta_location = None
    meta_climate = None
    if metadata_data:
        meta_location = metadata_data.get("location")
        meta_climate = metadata_data.get("ashrae_climate_zone")

    # 2) Figure out which columns in df hold location + climate
    #    (tries a couple of reasonable options)
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

    # 3) Implement your 3-step priority logic
    priority_col_added = False

    # Helper: apply priority given a mask
    def apply_priority(mask_series):
        nonlocal df, priority_col_added
        df["__priority"] = 1  # default
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
        # We at least know climate; use it directly
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

    # 4) Preserve selection if still visible
    selected_id = None
    if "building_id" in df.columns:
        visible_ids = set(df["building_id"].astype(str).tolist())
        if current_choice is not None and str(current_choice) in visible_ids:
            selected_id = current_choice

    # 5) Rebuild table with new ordering
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


# -------------------------------------------------------------------
# Confirm selection (update metadata and close modal)
# -------------------------------------------------------------------
#! Framework that can be used later
# @callback(
#     [
#         Output("selected-building-store", "data"),
#         Output("modal-load-data", "is_open", allow_duplicate=True),
#         Output("metadata-store", "data", allow_duplicate=True),
#     ],
#     Input("confirm-building-button", "n_clicks"),
#     State("building-radio-group", "value"),
#     State("metadata-store", "data"),
#     prevent_initial_call=True,
# )
# def confirm_selection(n_clicks, current_choice, metadata_data):
#     if current_choice is None:
#         return no_update, no_update, no_update

#     # Update metadata with selected building
#     metadata = Metadata(**metadata_data) if metadata_data else Metadata.create()
#     building = next(
#         (b for b in BUILDINGS if b["building_id"] == current_choice),
#         None,
#     )
#     if building:
#         # Update metadata fields as needed based on building data
#         # metadata.building_id = building["building_id"]
#         # metadata.load_type = building["load_type"]
#         pass

#     return current_choice, False, metadata.model_dump()
