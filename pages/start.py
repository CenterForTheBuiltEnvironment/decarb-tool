import dash
from dash import dcc, html, Input, Output, State, callback
import dash_bootstrap_components as dbc

import pandas as pd

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
                            html.H2("Welcome to the Berkeley Decarb Tool"),
                            html.P(
                                "Please enter the information below to get started."
                            ),
                        ],
                        width=12,
                    ),
                ],
            ),
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
                        width=5,
                    ),
                    dbc.Col(
                        [dcc.Graph(id="map-graph")],
                        width=7,
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
    State("metadata-store", "data"),
    prevent_initial_call=True,
)
def update_metadata_location(selected_zip, metadata_data):
    if not selected_zip:
        return metadata_data

    # look up the location row
    row = locations_df.loc[locations_df["zip"] == int(selected_zip)].iloc[0]

    # rebuild metadata object
    metadata = Metadata(**metadata_data)
    metadata.location = row["city"]  # or f"{row['name']} ({row['zip']})"
    metadata.ashrae_climate_zone = row["ashrae_climate_zone"]

    return metadata.dict()
