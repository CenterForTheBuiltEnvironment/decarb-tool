import dash
import json
from dash import dcc, html, Input, Output, State, callback, ctx
import dash_bootstrap_components as dbc

import pandas as pd

from components.output import summary_selection_info
from src.config import URLS

from src.metadata import Metadata

from components.input import (
    select_location,
    select_load_data,
    modal_load_simulation_data,
)


dash.register_page(__name__, path=URLS.HOME.value, order=0)

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
                            select_location(locations_df=locations_df),
                            html.Hr(),
                            select_load_data(),
                            modal_load_simulation_data(),
                            html.Hr(),
                            dbc.Button(
                                "Specify Equipment",
                                color="secondary",
                            ),
                            dbc.Button(
                                "Calculate Emissions",
                                color="primary",
                            ),
                        ],
                        width=4,
                    ),
                    dbc.Col(
                        [dcc.Graph(id="map-graph")],
                        width=5,
                    ),
                    dbc.Col(
                        [
                            html.Div(
                                id="summary-selection-info",
                            ),
                            html.Pre(
                                id="metadata-display", style={"whiteSpace": "pre-wrap"}
                            ),
                        ],
                        width=3,
                    ),
                ],
            ),
        ]
    )


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
    selected_zip, selected_building_type, selected_vintage, metadata_data
):
    # Figure out which input triggered
    trigger = ctx.triggered_id

    if not trigger:  # no trigger
        return metadata_data

    # rebuild metadata object
    metadata = Metadata(**metadata_data)

    if trigger == "location-input" and selected_zip:
        # look up the location row
        row = locations_df.loc[locations_df["zip"] == selected_zip].iloc[0]
        metadata.location = row["city"]
        metadata.ashrae_climate_zone = row["ASHRAE"]

    elif trigger == "building-type-input" and selected_building_type:
        metadata.building_type = selected_building_type

    elif trigger == "vintage-input" and selected_vintage:
        metadata.vintage = selected_vintage

    return metadata.model_dump()


@callback(Output("summary-selection-info", "children"), Input("metadata-store", "data"))
def show_metadata(data):
    if not data:
        return "No metadata yet"

    return summary_selection_info(data)
