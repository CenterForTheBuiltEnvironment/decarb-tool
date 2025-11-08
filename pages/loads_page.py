from pprint import pprint
import dash
from dash import dcc, html, Input, Output, State, callback, ctx, no_update
import dash_bootstrap_components as dbc
import base64
import io
import json
import tempfile
from pathlib import Path

from dash_iconify import DashIconify
import pandas as pd

from src.config import URLS
from src.metadata import Metadata
from src.loads import StandardLoad, STANDARD_COLUMNS



from layout.input import (
    select_gea_grid_region,
    select_location,
    select_load_data,
    modal_load_simulation_data,
)

from layout.output import summary_loads_selection


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


def layout():

    return dbc.Container(
        children=[
            dbc.Row(
                [
                    dbc.Col(
                        [
                            html.H5("Loads"),
                            html.Hr(),
                            select_location(locations_df=locations_df),
                            html.Hr(),
                            select_load_data(),
                            modal_load_simulation_data(),
                        ],
                        width=4,
                        style={"backgroundColor": "#f8f9fa", "borderRadius": "10px"},
                    ),
                    dbc.Col(
                        [
                            html.Div(
                                id="plot-container",
                                children=[
                                    html.Img(
                                        src="/assets/img/map-placeholder.png",
                                        style={
                                            "width": "100%",
                                            "margin": "auto",
                                            "display": "block",
                                            "opacity": "0.7",
                                        },
                                    ),
                                ],
                            ),
                        ],
                        width=4,
                    ),
                    dbc.Col(
                        [
                            html.H5("Summary"),
                            html.Hr(),
                            html.Div(
                                id="summary-selection-info",
                            ),
                            html.Pre(
                                id="metadata-display", style={"whiteSpace": "pre-wrap"}
                            ),
                            dcc.Link(
                                [
                                    dbc.Button(
                                        [
                                            "Specify Equipment ",
                                            DashIconify(
                                                icon="tabler:arrow-narrow-right-dashed",
                                                width=20,
                                            ),
                                        ],
                                        color="primary",
                                        id="button-specify-equipment",
                                        n_clicks=0,
                                        style={"float": "right"},
                                    ),
                                ],
                                href="/equipment",
                            ),
                        ],
                        width=4,
                    ),
                ],
            ),
        ]
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
    Output("modal-load-simulation-data", "is_open"),
    [
        Input("open-load-simulation-data-modal", "n_clicks"),
        Input("button-close-simulation-data-modal", "n_clicks"),
    ],
    [State("modal-load-simulation-data", "is_open")],
)
def toggle_modal(open_clicks, close_clicks, is_open):
    if open_clicks or close_clicks:
        return not is_open
    return is_open


@callback(
    Output("metadata-store", "data"),
    Input("location-input", "value"),
    Input("building-type-input", "value"),
    Input("vintage-input", "value"),
    State("metadata-store", "data"),
    prevent_initial_call=True,
)
def update_metadata(
    selected_zip,
    selected_building_type,
    selected_vintage,
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

    elif trigger == "building-type-input" and selected_building_type:
        metadata.building_type = selected_building_type

    elif trigger == "vintage-input" and selected_vintage:
        metadata.vintage = selected_vintage

    return metadata.model_dump()


@callback(Output("summary-selection-info", "children"), Input("metadata-store", "data"))
def show_metadata(data):
    if not data:
        return "No metadata yet"

    return summary_loads_selection(data)


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
        return {
            "status": "error",
            "message": f"Error processing file: {str(e)}"
        }


@callback(
    [Output("upload-data-alert", "children"),
     Output("metadata-store", "data", allow_duplicate=True)],
    Input("upload-data", "contents"),
    State("upload-data", "filename"),
    State("metadata-store", "data"),
    prevent_initial_call=True
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
                result["message"]
            ],
            color="success",
            dismissable=True,
            is_open=True,
        )
        
        # Update metadata to use custom load data
        metadata = Metadata(**metadata_data) if metadata_data else Metadata.create()
        metadata.load_type = "load_custom"
        metadata.custom_load_path = result["filepath"]
        
        return alert, metadata.model_dump()
    else:
        alert = dbc.Alert(
            [
                DashIconify(icon="bi:exclamation-circle-fill", className="me-2"),
                result["message"]
            ],
            color="danger",
            dismissable=True,
            is_open=True,
        )
        return alert, no_update
