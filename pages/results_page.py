import contextlib
import datetime
import io
import zipfile
from pathlib import Path

import dash
import dash_mantine_components as dmc
import pandas as pd
import plotly.express as px
from dash import Input, Output, State, callback, dcc
from dash_iconify import DashIconify

from layout.charts import chart_tabs
from layout.output import summary_project_info
from src.config import URLS
from src.metadata import Metadata
from src.visuals import (
    plot_emission_scenarios_grouped,
    plot_emissions_heatmap,
    plot_energy_and_emissions,
    plot_meter_timeseries,
    plot_scatter_temp_vs_variable,
)
from utils.display_registry import format_emission_scenario_id
from utils.logging_config import get_logger

logger = get_logger(__name__)


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
                rightSection=DashIconify(icon="material-symbols-light:download", width=20),
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
        logger.error(f"Failed to load source_energy.pkl for session {session_id}: {e}")
        return None


@callback(
    Output("summary-project-info", "children"),
    Input("metadata-store", "data"),
    Input("unit-toggle", "value"),
)
def show_project_summary(metadata_json, unit_mode):
    if not metadata_json:
        return "No project metadata available."

    unit_mode = unit_mode or "SI"
    metadata = Metadata(**metadata_json)
    return summary_project_info(metadata, unit_mode=unit_mode)


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
def update_total_emissions_plot(session_data, equipment_scenarios, emission_scenario, unit_mode):
    df = load_source_energy(session_data)
    if df is None:
        return px.line(x=[0, 1], y=[0, 0], title="Waiting for data...")

    if isinstance(emission_scenario, str):
        emission_scenario = [emission_scenario]

    fig = plot_energy_and_emissions(df, equipment_scenarios, emission_scenario, unit_mode=unit_mode)
    return fig


@callback(
    Output("emissions-bar-plot", "figure"),
    Input("session-store", "data"),
    Input("emission-em-scen-dropdown", "value"),
    Input("unit-toggle", "value"),
    State("selected-equipment-store", "data"),  # preserves user ordering
)
def update_emissions_bar_plot(session_data, emission_scenarios, unit_mode, selected_equipment_ids):
    df = load_source_energy(session_data)
    if df is None:
        return px.line(x=[0, 1], y=[0, 0], title="Waiting for data...")

    # Use user-defined order from selected-equipment-store
    df_ids = set(df["eq_scen_id"].unique())
    if selected_equipment_ids:
        equipment_scenarios = [sid for sid in selected_equipment_ids if sid in df_ids]
    else:
        equipment_scenarios = list(df_ids)

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


# Immediate notification when download button is clicked
@callback(
    Output("notification-container", "sendNotifications", allow_duplicate=True),
    Input("download-button", "n_clicks"),
    State("unit-toggle", "value"),
    prevent_initial_call=True,
)
def show_download_notification(n_clicks, unit_mode):
    """Show immediate feedback when download button is clicked."""
    if not n_clicks:
        raise dash.exceptions.PreventUpdate

    unit_mode = unit_mode or "SI"
    unit_label = "SI (metric)" if unit_mode == "SI" else "IP (imperial)"

    # Notification with loading spinner
    notification = {
        "id": "download-notification",
        "title": "Preparing Download",
        "message": f"Exporting results in {unit_label} units...",
        "color": "blue",
        "loading": True,  # Shows spinning wheel
        "autoClose": 6000,  # Keep visible longer (6 seconds)
        "action": "show",
    }

    return [notification]


# Download the full results/source energy dataframe as CSV
@callback(
    Output("download-data", "data"),
    Input("download-button", "n_clicks"),
    State("session-store", "data"),
    State("unit-toggle", "value"),
    prevent_initial_call=True,
)
def download_results(n_clicks, session_data, unit_mode):
    """Download the entire results dataframe as a .csv file with unit conversion."""
    import numpy as np

    from utils.units import (
        COLUMN_DISPLAY_NAMES,
        convert_dataframe,
        get_category,
        get_column_label,
    )

    # Only trigger on actual button click
    if not n_clicks:
        raise dash.exceptions.PreventUpdate

    if not session_data or "session_id" not in session_data:
        raise dash.exceptions.PreventUpdate

    df = load_source_energy(session_data)
    if df is None:
        raise dash.exceptions.PreventUpdate

    unit_mode = unit_mode or "SI"

    # Convert values based on unit mode
    df = convert_dataframe(df, unit_mode)

    # Round numeric values: 2 decimals normally, 3 for values < 1
    def smart_round(val):
        if pd.isna(val) or not isinstance(val, int | float | np.number):
            return val
        if abs(val) < 1 and val != 0:
            return round(val, 3)
        return round(val, 2)

    for col in df.columns:
        if df[col].dtype in [np.float64, np.float32, float]:
            df[col] = df[col].apply(smart_round)

    # Rename columns:
    # - Columns with a category: use get_column_label (includes unit)
    # - Columns without a category but with display name: use display name only
    column_renames = {}
    for col in df.columns:
        if get_category(col) is not None:
            # Has unit conversion - include unit in label
            column_renames[col] = get_column_label(col, unit_mode)
        elif col in COLUMN_DISPLAY_NAMES:
            # No unit conversion but has display name
            column_renames[col] = COLUMN_DISPLAY_NAMES[col]
        # else: keep original column name
    df = df.rename(columns=column_renames)

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_string = df.to_csv(index=True)

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(f"results_{timestamp}.csv", csv_string)

    buf.seek(0)
    return dcc.send_bytes(buf.getvalue(), f"results_{timestamp}.zip")


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
    State("equipment-scenario-number-map", "data"),  # display numbers (1-5)
)
def populate_equipment_dropdowns(session_data, selected_equipment_ids, number_map):
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
        # No user ordering available - sort by numeric suffix as fallback
        def eq_sort_key(scen_id):
            if scen_id.startswith("eq_scenario_"):
                with contextlib.suppress(ValueError):
                    return int(scen_id[len("eq_scenario_") :])
            return scen_id

        eq_ids = sorted(df_ids, key=eq_sort_key)

    if not eq_ids:
        # Fallback: nothing computed
        return [], [], [], None, [], None, [], []

    # Build options list with user-friendly labels using display numbers (1-5)
    number_map = number_map or {}
    options = [
        {
            "label": f"Equipment Scen. {number_map.get(scen_id, '?')}",
            "value": scen_id,
        }
        for scen_id in eq_ids
    ]

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

    # Sort emission scenarios by their letter suffix (em_scenario_a < em_scenario_b < ...)
    def em_sort_key(scen_id):
        if scen_id.startswith("em_scenario_"):
            return scen_id[len("em_scenario_") :]
        return scen_id

    em_ids = sorted(em_ids, key=em_sort_key)

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

    # Build options with user-friendly labels
    options = [
        {"label": format_emission_scenario_id(scen_id), "value": scen_id} for scen_id in em_ids
    ]

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
