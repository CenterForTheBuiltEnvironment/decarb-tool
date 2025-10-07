from pprint import pprint
import dash
from dash import dcc, html, Input, Output, State, callback, ctx, no_update
import dash_bootstrap_components as dbc

from dash_iconify import DashIconify

import pandas as pd

from src.config import URLS

from src.metadata import Metadata

# from src.equipment import EquipmentLibrary

# from src.loads import get_load_data
# from src.emissions import get_emissions_data

# from src.energy import loads_to_site_energy, site_to_source

from layout.input import (
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
                            html.Hr(),
                        ],
                        width=4,
                        style={"backgroundColor": "#f8f9fa", "borderRadius": "10px"},
                    ),
                    dbc.Col(
                        [
                            html.Div(),
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

    return summary_loads_selection(data)


# @callback(
#     Output("site-energy-store", "data"),
#     Input("calculate-button-start-page", "n_clicks"),
#     State("metadata-store", "data"),
#     State("equipment-store", "data"),
#     prevent_initial_call=True,
# )
# def run_loads_to_site(n_clicks, metadata_json, equipment_json):
#     if not n_clicks or n_clicks < 1:
#         return no_update  # do nothing until button clicked at least once

#     if not metadata_json or not equipment_json:
#         return no_update

#     metadata = Metadata(**metadata_json) if metadata_json else None
#     equipment = EquipmentLibrary(**equipment_json) if equipment_json else None

#     load_data = get_load_data(metadata)

#     site_energy = loads_to_site_energy(
#         load_data, equipment, metadata.equipment_scenarios, detail=True
#     )

#     print(site_energy.head())  #! for debugging: remove later

#     return site_energy.to_json(date_format="iso", orient="split")


# @callback(
#     Output("source-energy-store", "data"),
#     Output("calc-status", "children"),
#     Input("site-energy-store", "data"),
#     State("metadata-store", "data"),
#     prevent_initial_call=True,
# )
# def run_site_to_source(site_energy_json, metadata_json):
#     site_energy = pd.read_json(StringIO(site_energy_json), orient="split")
#     metadata = Metadata(**metadata_json) if metadata_json else None

#     source_energy = site_to_source(site_energy, metadata=metadata)

#     return (
#         source_energy.to_json(date_format="iso", orient="split"),
#         "Calculation finished!",
#     )
