import contextlib
import datetime
import io
import time
import zipfile
from pathlib import Path

import dash
import dash_mantine_components as dmc
import pandas as pd
from dash import Input, Output, State, callback, dcc, no_update

from layout.charts import chart_tabs
from layout.output import summary_project_info
from src.config import URLS
from src.energy import loads_to_site_energy, site_to_source
from src.equipment import EquipmentLibrary
from src.loads import get_load_data
from src.metadata import Metadata
from src.visuals import (
    empty_figure,
    plot_emission_scenarios_grouped,
    plot_emissions_heatmap,
    plot_energy_and_emissions,
    plot_meter_timeseries,
    plot_scatter_temp_vs_variable,
)
from utils.display_registry import format_emission_scenario_id, format_equipment_scenario_id
from utils.error_handling import (
    create_error_notification,
    create_success_notification,
    create_warning_notification,
)
from utils.logging_config import get_logger

logger = get_logger(__name__)


dash.register_page(__name__, name="Results", path=URLS.RESULTS.value, order=3)


def layout():
    return dmc.Container(
        [
            # Page-local mount signal: fires initialize_results_page only once
            # this page's own DOM subtree — including every dropdown/graph that
            # callback outputs to — has actually mounted. A page-agnostic Input
            # like url.pathname changes (and can fire dependent callbacks)
            # before dash-pages has finished swapping in this layout, which is
            # what caused the "nonexistent object ... emission-scen-dropdown"
            # client error. data=time.time() (not a static value) guarantees a
            # genuinely new value on every single visit, so a remount is never
            # mistaken for "nothing changed" and skipped.
            dcc.Store(id="results-page-mount", data=time.time()),
            dmc.Grid(
                [
                    dmc.GridCol(
                        [
                            dmc.Paper(
                                [
                                    dmc.LoadingOverlay(
                                        id="results-loading-overlay",
                                        # Always starts visible: this is a static prop
                                        # baked into the page's initial markup, not a
                                        # callback, so it can't be made conditional on
                                        # last-calculated-settings-store (unreadable at
                                        # layout() render time). control_loading_overlay
                                        # below hides it again quickly on every visit.
                                        visible=True,
                                        overlayProps={"radius": "md", "blur": 10},
                                        zIndex=10,
                                    ),
                                    chart_tabs(),
                                ],
                                p="md",
                                radius="md",
                                pos="relative",
                            ),
                        ],
                        span=12,
                    ),
                ],
                gutter="md",
            ),
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
    Input("equipment-scen-dropdown", "value"),
    Input("emission-scen-dropdown", "value"),
    Input("stacked-toggle", "value"),
    Input("gas-toggle", "value"),
    Input("frequency-dropdown", "value"),
    Input("unit-toggle", "value"),
    State("session-store", "data"),
    prevent_initial_call=True,
)
def update_meter_plot(
    equipment_scenarios,
    emission_scenarios,
    stacked_value,
    gas_value,
    frequency_value,
    unit_mode,
    session_data,
):
    df = load_source_energy(session_data)
    if df is None or not emission_scenarios or not equipment_scenarios:
        return empty_figure()

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
    Input("total-equipment-scen-dropdown", "value"),
    Input("total-emission-scen-dropdown", "value"),
    Input("unit-toggle", "value"),
    State("session-store", "data"),
    prevent_initial_call=True,
)
def update_total_emissions_plot(equipment_scenarios, emission_scenario, unit_mode, session_data):
    df = load_source_energy(session_data)
    if df is None or emission_scenario is None or not equipment_scenarios:
        return empty_figure()

    if isinstance(emission_scenario, str):
        emission_scenario = [emission_scenario]

    fig = plot_energy_and_emissions(df, equipment_scenarios, emission_scenario, unit_mode=unit_mode)
    return fig


@callback(
    Output("emissions-bar-plot", "figure"),
    Input("emission-em-scen-dropdown", "value"),
    Input("unit-toggle", "value"),
    State("selected-equipment-store", "data"),  # preserves user ordering
    State("session-store", "data"),
    prevent_initial_call=True,
)
def update_emissions_bar_plot(emission_scenarios, unit_mode, selected_equipment_ids, session_data):
    df = load_source_energy(session_data)
    if df is None or not emission_scenarios:
        return empty_figure()

    # Use user-defined order from selected-equipment-store
    df_ids = set(df["eq_scen_id"].unique())
    if selected_equipment_ids:
        equipment_scenarios = [sid for sid in selected_equipment_ids if sid in df_ids]
    else:
        equipment_scenarios = list(df_ids)

    if not equipment_scenarios:
        return empty_figure()

    # Ensure emission_scenarios is a list
    if isinstance(emission_scenarios, str):
        emission_scenarios = [emission_scenarios]

    fig = plot_emission_scenarios_grouped(
        df, equipment_scenarios, emission_scenarios, unit_mode=unit_mode
    )
    return fig


@callback(
    Output("emissions-heatmap-plot", "figure"),
    Input("heatmap-equipment-scen-dropdown", "value"),
    Input("heatmap-emission-scen-dropdown", "value"),
    Input("heatmap-emission-type-dropdown", "value"),
    Input("unit-toggle", "value"),
    State("session-store", "data"),
    prevent_initial_call=True,
)
def update_emissions_heatmap(
    equipment_scenario, emission_scenario, emission_type, unit_mode, session_data
):
    df = load_source_energy(session_data)
    if df is None or not equipment_scenario or not emission_scenario:
        return empty_figure()

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
    Input("scatter-equipment-scen-dropdown", "value"),
    Input("scatter-emission-scen-dropdown", "value"),
    Input("scatter-yvar-dropdown", "value"),
    Input("scatter-frequency-dropdown", "value"),
    Input("unit-toggle", "value"),
    State("session-store", "data"),
    prevent_initial_call=True,
)
def update_scatter_plot(
    equipment_scenarios,
    emission_scenario,
    y_variable,
    frequency_value,
    unit_mode,
    session_data,
):
    df = load_source_energy(session_data)
    if df is None or not equipment_scenarios or not emission_scenario:
        return empty_figure()

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
    State("metadata-store", "data"),
    State("equipment-store", "data"),
    State("selected-equipment-store", "data"),
    State("selected-emissions-store", "data"),
    prevent_initial_call=True,
)
def download_results(
    n_clicks,
    session_data,
    unit_mode,
    metadata_json,
    equipment_json,
    selected_eq_ids,
    selected_em_ids,
):
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
        _add_metadata_files(
            zf, metadata_json, equipment_json, selected_eq_ids, selected_em_ids, unit_mode
        )

    buf.seek(0)
    return dcc.send_bytes(buf.getvalue(), f"results_{timestamp}.zip")


def _add_metadata_files(
    zf, metadata_json, equipment_json, selected_eq_ids, selected_em_ids, unit_mode
):
    import json as _json

    from src.equipment import EquipmentLibrary
    from src.export import build_metadata_summary, build_settings_bundle
    from src.metadata import Metadata

    if not metadata_json or not equipment_json:
        return

    try:
        metadata = Metadata(**metadata_json)
        equipment_library = EquipmentLibrary(**equipment_json)
        selected_eq = list(selected_eq_ids) if selected_eq_ids else []
        selected_em = list(selected_em_ids) if selected_em_ids else []

        summary = build_metadata_summary(
            metadata, equipment_library, selected_eq, selected_em, unit_mode
        )
        zf.writestr("settings_summary.txt", summary)

        bundle = build_settings_bundle(metadata, equipment_library, selected_eq, selected_em)
        zf.writestr("settings.json", _json.dumps(bundle, indent=2, default=str))
    except Exception:
        pass  # never block the download for a metadata failure


def _equipment_dropdown_outputs(session_data, selected_equipment_ids):
    """
    Compute all equipment scenario dropdown options/values from only the
    scenarios that were actually computed for this session. Returns the
    8-tuple (data/value pairs for total, meter, heatmap, scatter dropdowns).
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

    # Build options list with user-friendly labels derived from each
    # scenario's own id, never renumbered based on the active subset
    options = [
        {"label": format_equipment_scenario_id(scen_id), "value": scen_id} for scen_id in eq_ids
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


def _emission_dropdown_outputs(
    session_data,
    selected_emission_ids,
    prev_emission_scen,
    prev_total_em,
    prev_heatmap_em,
    prev_scatter_em,
):
    """
    Compute all emission scenario dropdown options/values from only the
    scenarios that were actually computed for this session. Returns the
    10-tuple (5 data/value pairs).

    We:
      - read em_scen_id from source_energy
      - intersect with selected-emissions-store (to preserve user order / choices)
      - for single-select dropdowns, keep the user's chosen scenario if it's
        still active; the one multi-select dropdown always shows every
        active scenario (see emission_em_value below).
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
        # No user ordering available - sort by letter suffix as fallback
        def em_sort_key(scen_id):
            if scen_id.startswith("em_scenario_"):
                return scen_id[len("em_scenario_") :]
            return scen_id

        em_ids = sorted(df_ids, key=em_sort_key)

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

    # Helper: preserve the user's single chosen scenario across visits, if
    # it's still active; otherwise fall back to the first one.
    def pick_single_value(prev_val):
        if isinstance(prev_val, str):
            return prev_val if prev_val in em_ids else em_ids[0]
        return em_ids[0]

    # Decide values for each dropdown
    emission_scen_value = pick_single_value(prev_emission_scen)
    total_emission_value = pick_single_value(prev_total_em)
    # emission-em-scen-dropdown is the one multi-select among these: always
    # default to every currently active scenario, rather than trying to
    # reconcile against its stale previous value. An earlier version
    # intersected the previous value with em_ids (plus a separately-tracked
    # "known ids" set for newly-added scenarios), but that silently dropped
    # any active scenario that simply wasn't in the dropdown's last value —
    # e.g. selecting A, C, D on the Emissions page after previously having
    # A, B, C active would drop D, since D was neither in the stale previous
    # value nor considered "new".
    emission_em_value = em_ids[:]
    heatmap_em_value = pick_single_value(prev_heatmap_em)
    scatter_em_value = pick_single_value(prev_scatter_em)

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


@callback(
    Output("results-ready-store", "data", allow_duplicate=True),
    Output("results-refresh-store", "data", allow_duplicate=True),
    Output("notification-container", "sendNotifications", allow_duplicate=True),
    Output("last-calculated-settings-store", "data", allow_duplicate=True),
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
    Input("results-page-mount", "data"),
    State("metadata-store", "data"),
    State("equipment-store", "data"),
    State("selected-equipment-store", "data"),
    State("selected-emissions-store", "data"),
    State("session-store", "data"),
    State("last-calculated-settings-store", "data"),
    # previous values of the single-select dropdowns, to keep the user's
    # chosen scenario if it's still active
    State("emission-scen-dropdown", "value"),
    State("total-emission-scen-dropdown", "value"),
    State("heatmap-emission-scen-dropdown", "value"),
    State("scatter-emission-scen-dropdown", "value"),
    prevent_initial_call="initial_duplicate",
)
def initialize_results_page(
    _page_mounted,
    metadata_json,
    equipment_json,
    selected_scenarios,
    selected_emission_ids,
    session_data,
    last_calculated_settings,
    prev_emission_scen,
    prev_total_em,
    prev_heatmap_em,
    prev_scatter_em,
):
    """Auto-calculate on arrival at Results, then (re)populate every
    equipment/emission dropdown in one shot.

    Triggered solely by results-page-mount, a dcc.Store defined in this
    page's own layout() with a fresh time.time() value on every visit (not a
    static default) — so a remount is never mistaken for "nothing changed"
    and skipped, and it can never fire before the rest of this same
    layout() return (every dropdown/graph below) has mounted, since they're
    all part of the exact same insertion.

    This used to be three separate callbacks: this one (triggered by the
    app-wide "url" pathname) bumped results-refresh-store, which a second
    and third callback (populate_equipment_dropdowns / populate_emission_
    dropdowns) used as their own Input to write the actual dropdowns. Each
    extra hop was a separate place the client could resolve a change before
    this page's components were registered, which is what produced the
    "nonexistent object ... emission-scen-dropdown" client error — merging
    everything into one callback with one Input removes every hop but the
    first. prevent_initial_call="initial_duplicate" is required by the
    allow_duplicate Outputs above; unlike plain True, it still fires on the
    very first dispatch, which matters here since a fresh page mount is
    never the app's one true cold-start dispatch anyway.

    Whether to skip the expensive recompute is decided by comparing the
    CURRENT settings directly against a snapshot of what was actually used
    for the last successful calculation (last-calculated-settings-store) —
    not by a separately-maintained "dirty" boolean. An earlier version used
    a settings-dirty-store flag set by a watcher callback on metadata-store/
    equipment-store/selected-equipment-store/selected-emissions-store, but
    that watcher re-fired (and wrongly marked settings dirty) on every page
    navigation, not just on real edits — a fresh results-page-mount fires on
    every single visit to this page. A direct snapshot comparison, done here
    at the only place that matters (arrival at Results), sidesteps that
    entirely.

    The dropdowns are always recomputed below, regardless of which branch
    the calculation takes (including the early-exit guards), so a revisit
    with unchanged settings still repaints them from whatever is
    authoritatively on disk instead of leaving them on the hardcoded
    placeholder values baked into layout/charts.py. results-ready-store, by
    contrast, keeps its narrower meaning ("a fresh calculation just
    completed") and is only bumped on real success, since it also gates the
    Download button.
    """

    def run_calc():
        current_settings = {
            "metadata": metadata_json,
            "equipment": equipment_json,
            "selected_equipment": selected_scenarios,
            "selected_emissions": selected_emission_ids,
        }

        if (
            current_settings == last_calculated_settings
            and load_source_energy(session_data) is not None
        ):
            return no_update, time.time(), no_update, no_update

        if not metadata_json:
            return no_update, time.time(), no_update, no_update

        metadata = Metadata(**metadata_json)

        if not metadata.load_data.load_type:
            return no_update, time.time(), no_update, no_update

        if not metadata.base_gea_grid_region:
            notification = create_warning_notification(
                "Missing Grid Region",
                "Could not determine grid region. Please select a location on the Loads page.",
            )
            return no_update, time.time(), [notification], no_update

        if not equipment_json or not selected_scenarios or not session_data:
            return no_update, time.time(), no_update, no_update

        try:
            folder = Path(f"/tmp/{session_data['session_id']}")
            folder.mkdir(parents=True, exist_ok=True)

            equipment = EquipmentLibrary(**equipment_json)
            load_data = get_load_data(metadata)

            # Step 1: loads → site energy
            site_energy = loads_to_site_energy(
                load_data,
                equipment,
                scenario_ids=selected_scenarios,
                detail=True,
            )

            # Step 2: site → source emissions
            if selected_emission_ids:
                metadata.emission_settings = [
                    scen
                    for scen in metadata.emission_settings
                    if scen.em_scen_id in selected_emission_ids
                ]
            source_energy = site_to_source(site_energy, metadata=metadata)

            source_path = folder / "source_energy.pkl"
            source_energy.to_pickle(source_path)
            logger.info(f"Auto-calculated source energy on Results navigation: {source_path}")

            success = create_success_notification(
                "Calculation Complete",
                "Source emissions calculation finished successfully.",
            )
            return time.time(), time.time(), [success], current_settings

        except Exception as e:
            logger.exception(f"Auto-calculation error on Results navigation: {e}")
            notification = create_error_notification(
                "Calculation Error",
                "Automatic calculation failed. Please check your load and settings.",
            )
            return no_update, time.time(), [notification], no_update

    calc_result = run_calc()
    equipment_outputs = _equipment_dropdown_outputs(session_data, selected_scenarios)
    emission_outputs = _emission_dropdown_outputs(
        session_data,
        selected_emission_ids,
        prev_emission_scen,
        prev_total_em,
        prev_heatmap_em,
        prev_scatter_em,
    )

    return (*calc_result, *equipment_outputs, *emission_outputs)


@callback(
    Output("results-loading-overlay", "visible"),
    Input("emissions-bar-plot", "figure"),
    prevent_initial_call=True,
)
def control_loading_overlay(_figure):
    """Hide the loading overlay once the default (Emissions) tab's chart has
    actually redrawn with current data — i.e. once initialize_results_page
    and the first real chart redraw have all completed.

    Both this callback's Input and Output only exist while the Results page
    is mounted, which is what makes it safe (see the note on
    initialize_results_page above). It reliably fires exactly once per visit
    because initialize_results_page always concretely sets every emission
    dropdown output (never no_update), which in turn always re-triggers this
    chart's figure callback — whether or not a recalculation actually
    happened.
    """
    return False
