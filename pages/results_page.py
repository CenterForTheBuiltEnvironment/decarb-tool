import dash
from dash import html, dcc, Input, Output, State, callback
import dash_mantine_components as dmc
from dash_iconify import DashIconify

import datetime
import pandas as pd
import plotly.express as px
from pathlib import Path

from src.config import URLS

from layout.output import summary_project_info, empty_state

from layout.charts import chart_tabs

from src.metadata import Metadata
from src.visuals import (
    plot_meter_timeseries,
    plot_energy_and_emissions,
    plot_emission_scenarios_grouped,
    plot_emissions_heatmap,
    plot_scatter_temp_vs_variable,
)

dash.register_page(__name__, name="Results", path=URLS.RESULTS.value, order=3)


def layout():
    return dmc.Container(
        [
            dmc.Grid(
                [
                    dmc.GridCol(
                        [
                            dmc.Paper(
                                [
                                    chart_tabs(),
                                ],
                                p="md",
                                radius="md",
                            ),
                        ],
                        span=12,
                    ),
                ],
                gutter="md",
            ),
            dmc.Button(
                "Download data ",
                rightSection=DashIconify(
                    icon="material-symbols-light:download", width=20
                ),
                variant="outline",
                color="blue",
                id="download-button",
                n_clicks=0,
                style={"float": "right"},
                mr="md",
            ),
            dcc.Download(id="download-data"),
        ],
        fluid=True,
    )


def load_source_energy(session_data):
    """Load the source energy dataframe for this user session."""

    if not session_data or "session_id" not in session_data:
        return None

    session_id = session_data["session_id"]
    folder = Path(f"/tmp/{session_data['session_id']}")
    filepath = folder / "source_energy.pkl"

    if not filepath.exists():
        return None

    try:
        return pd.read_pickle(filepath)
    except Exception as e:
        print(f"[ERROR] Failed to load source_energy.pkl for session {session_id}: {e}")
        return None


@callback(
    Output("summary-project-info", "children"),
    Input("metadata-store", "data"),
)
def show_project_summary(metadata_json):
    if not metadata_json:
        return "No project metadata available."

    metadata = Metadata(**metadata_json)
    return summary_project_info(metadata)


@callback(
    Output("meter-timeseries-plot", "figure"),
    Input("session-store", "data"),
    Input("equipment-scen-dropdown", "value"),
    Input("emission-scen-dropdown", "value"),
    Input("stacked-toggle", "value"),
    Input("gas-toggle", "value"),
    Input("frequency-dropdown", "value"),
    Input("unit-toggle", "value"),
    # prevent_initial_call=True
)
def update_meter_plot(
    session_data,
    equipment_scenarios,
    emission_scenarios,
    stacked_value,
    gas_value,
    frequency_value,
    unit_mode,
):

    df = load_source_energy(session_data)
    if df is None:
        return px.line(x=[0, 1], y=[0, 0], title="Waiting for data...")

    # flags from toggles
    stacked = "stacked" in stacked_value
    include_gas = "gas" in gas_value
    frequency_value = frequency_value if frequency_value else "D"

    fig = plot_meter_timeseries(
        df,
        equipment_scenarios,
        emission_scenarios,
        stacked=stacked,
        include_gas=include_gas,
        freq=frequency_value,
        unit_mode=unit_mode,
    )
    return fig


@callback(
    Output("energy-and-emissions-plot", "figure"),
    Input("session-store", "data"),
    Input("total-equipment-scen-dropdown", "value"),
    Input("total-emission-scen-dropdown", "value"),
    Input("unit-toggle", "value"),
)
def update_total_emissions_plot(
    session_data, equipment_scenarios, emission_scenario, unit_mode
):
    df = load_source_energy(session_data)
    if df is None:
        return px.line(x=[0, 1], y=[0, 0], title="Waiting for data...")

    if isinstance(emission_scenario, str):
        emission_scenario = [emission_scenario]

    fig = plot_energy_and_emissions(
        df, equipment_scenarios, emission_scenario, unit_mode=unit_mode
    )
    return fig


@callback(
    Output("emissions-bar-plot", "figure"),
    Input("session-store", "data"),
    Input("emission-em-scen-dropdown", "value"),
    Input("unit-toggle", "value"),
    # prevent_initial_call=True
)
def update_emissions_bar_plot(session_data, emission_scenarios, unit_mode):

    df = load_source_energy(session_data)
    if df is None:
        return px.line(x=[0, 1], y=[0, 0], title="Waiting for data...")

    equipment_scenarios = df["eq_scen_id"].unique().tolist()

    # Ensure emission_scenarios is a list
    if isinstance(emission_scenarios, str):
        emission_scenarios = [emission_scenarios]

    fig = plot_emission_scenarios_grouped(
        df, equipment_scenarios, emission_scenarios, unit_mode=unit_mode
    )
    return fig


@callback(
    Output("emissions-heatmap-plot", "figure"),
    Input("session-store", "data"),
    Input("heatmap-equipment-scen-dropdown", "value"),
    Input("heatmap-emission-scen-dropdown", "value"),
    Input("heatmap-emission-type-dropdown", "value"),
    Input("unit-toggle", "value"),
    # prevent_initial_call=True
)
def update_emissions_heatmap(
    session_data, equipment_scenario, emission_scenario, emission_type, unit_mode
):
    df = load_source_energy(session_data)
    if df is None:
        return px.line(x=[0, 1], y=[0, 0], title="Waiting for data...")

    fig = plot_emissions_heatmap(
        df,
        equipment_scenario,
        emission_scenario,
        unit_mode=unit_mode,
        emission_type=emission_type,
    )
    return fig


@callback(
    Output("scatter-plot", "figure"),
    Input("session-store", "data"),
    Input("scatter-equipment-scen-dropdown", "value"),
    Input("scatter-emission-scen-dropdown", "value"),
    Input("scatter-yvar-dropdown", "value"),
    Input("scatter-frequency-dropdown", "value"),
    Input("unit-toggle", "value"),
    # prevent_initial_call=True
)
def update_scatter_plot(
    session_data,
    equipment_scenarios,
    emission_scenario,
    y_variable,
    frequency_value,
    unit_mode,
):
    df = load_source_energy(session_data)
    if df is None:
        return px.line(x=[0, 1], y=[0, 0], title="Waiting for data...")

    frequency_value = frequency_value if frequency_value else "D"

    fig = plot_scatter_temp_vs_variable(
        df,
        y_var=y_variable,
        equipment_scenarios=equipment_scenarios,
        emission_scenarios=[emission_scenario],
        agg=frequency_value,
        unit_mode=unit_mode,
    )
    return fig


# Download the full results/source energy dataframe as CSV
@callback(
    Output("download-data", "data"),
    Input("download-button", "n_clicks"),
    State("session-store", "data"),
    prevent_initial_call=True,
)
def download_results(n_clicks, session_data):
    """Download the entire results dataframe as a .csv file"""
    if not session_data or "session_id" not in session_data:
        raise dash.exceptions.PreventUpdate

    df = load_source_energy(session_data)

    filename = f"results_{datetime.datetime.now()}.csv"

    # Use dcc.send_data_frame to stream the dataframe as CSV
    return dcc.send_data_frame(df.to_csv, filename, index=True)


@callback(
    # total-equipment-scen-dropdown (multi)
    Output("total-equipment-scen-dropdown", "data"),
    Output("total-equipment-scen-dropdown", "value"),
    # equipment-scen-dropdown (single)
    Output("equipment-scen-dropdown", "data"),
    Output("equipment-scen-dropdown", "value"),
    # heatmap-equipment-scen-dropdown (single)
    Output("heatmap-equipment-scen-dropdown", "data"),
    Output("heatmap-equipment-scen-dropdown", "value"),
    # scatter-equipment-scen-dropdown (multi)
    Output("scatter-equipment-scen-dropdown", "data"),
    Output("scatter-equipment-scen-dropdown", "value"),
    Input("session-store", "data"),
    State("selected-equipment-store", "data"),  # optional, keeps user ordering
)
def populate_equipment_dropdowns(session_data, selected_equipment_ids):
    """
    Populate all equipment scenario dropdowns with only the scenarios
    that were actually computed for this session.
    """
    df = load_source_energy(session_data)
    if df is None:
        # No data yet: return empty dropdowns
        return [], [], [], None, [], None, [], []

    # Get unique eq_scen_id values from the results
    df_ids = df["eq_scen_id"].unique().tolist()

    # Optionally intersect with selected_equipment_store to preserve order
    if selected_equipment_ids:
        # Keep only those that are in df, and preserve user selection order
        eq_ids = [sid for sid in selected_equipment_ids if sid in df_ids]
    else:
        eq_ids = df_ids

    if not eq_ids:
        # Fallback: nothing computed
        return [], [], [], None, [], None, [], []

    # Build options list
    options = [{"label": scen_id, "value": scen_id} for scen_id in eq_ids]

    # Defaults:
    # - For multi-select dropdowns: select all by default
    # - For single-select dropdowns: pick the first one
    total_equipment_options = options
    total_equipment_value = eq_ids[:]  # all

    meter_options = options
    meter_value = eq_ids[0]

    heatmap_options = options
    heatmap_value = eq_ids[0]

    scatter_options = options
    scatter_value = eq_ids[:]  # all

    return (
        total_equipment_options,
        total_equipment_value,
        meter_options,
        meter_value,
        heatmap_options,
        heatmap_value,
        scatter_options,
        scatter_value,
    )


@callback(
    # emission-scen-dropdown (for meter timeseries)
    Output("emission-scen-dropdown", "data"),
    Output("emission-scen-dropdown", "value"),
    # total-emission-scen-dropdown (for total energy/emissions plot)
    Output("total-emission-scen-dropdown", "data"),
    Output("total-emission-scen-dropdown", "value"),
    # emission-em-scen-dropdown (for grouped bar)
    Output("emission-em-scen-dropdown", "data"),
    Output("emission-em-scen-dropdown", "value"),
    # heatmap-emission-scen-dropdown (for heatmap)
    Output("heatmap-emission-scen-dropdown", "data"),
    Output("heatmap-emission-scen-dropdown", "value"),
    # scatter-emission-scen-dropdown (for scatter)
    Output("scatter-emission-scen-dropdown", "data"),
    Output("scatter-emission-scen-dropdown", "value"),
    Input("session-store", "data"),
    State("selected-emissions-store", "data"),  # preserves user ordering
    # previous values to infer single vs multi & keep user choices where possible
    State("emission-scen-dropdown", "value"),
    State("total-emission-scen-dropdown", "value"),
    State("emission-em-scen-dropdown", "value"),
    State("heatmap-emission-scen-dropdown", "value"),
    State("scatter-emission-scen-dropdown", "value"),
)
def populate_emission_dropdowns(
    session_data,
    selected_emission_ids,
    prev_emission_scen,
    prev_total_em,
    prev_em_em,
    prev_heatmap_em,
    prev_scatter_em,
):
    """
    Populate all emission scenario dropdowns with only the scenarios
    that were actually computed for this session.

    We:
      - read em_scen_id from source_energy
      - intersect with selected-emissions-store (to preserve user order / choices)
      - infer single vs multi from previous value type (str vs list).
    """
    df = load_source_energy(session_data)
    if df is None or "em_scen_id" not in df.columns:
        # No data yet: return empty dropdowns
        empty_opts, none_val = [], None
        return (
            empty_opts,
            none_val,
            empty_opts,
            none_val,
            empty_opts,
            none_val,
            empty_opts,
            none_val,
            empty_opts,
            none_val,
        )

    df_ids = df["em_scen_id"].unique().tolist()

    # If we have user-selected emissions, intersect in that order.
    if selected_emission_ids:
        em_ids = [sid for sid in selected_emission_ids if sid in df_ids]
    else:
        em_ids = df_ids

    if not em_ids:
        empty_opts, none_val = [], None
        return (
            empty_opts,
            none_val,
            empty_opts,
            none_val,
            empty_opts,
            none_val,
            empty_opts,
            none_val,
            empty_opts,
            none_val,
        )

    # Build options
    options = [{"label": scen_id, "value": scen_id} for scen_id in em_ids]

    # Helper: choose new value based on previous value type (single vs multi)
    def pick_value(prev_val):
        if not em_ids:
            return None

        # If dropdown is multi-select, its value is a list
        if isinstance(prev_val, list):
            # Keep only those still available; if none left, select all
            filtered = [v for v in prev_val if v in em_ids]
            return filtered or em_ids[:]  # list

        # If dropdown is single-select, its value is a string (or None)
        if isinstance(prev_val, str):
            return prev_val if prev_val in em_ids else em_ids[0]

        # Fallback: first scenario
        return em_ids[0]

    # Decide values for each dropdown
    emission_scen_value = pick_value(prev_emission_scen)
    total_emission_value = pick_value(prev_total_em)
    emission_em_value = pick_value(prev_em_em)
    heatmap_em_value = pick_value(prev_heatmap_em)
    scatter_em_value = pick_value(prev_scatter_em)

    return (
        options,
        emission_scen_value,
        options,
        total_emission_value,
        options,
        emission_em_value,
        options,
        heatmap_em_value,
        options,
        scatter_em_value,
    )
