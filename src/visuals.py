import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from utils.display_registry import format_emission_scenario_id, format_meter_name
from utils.units import (
    convert_dataframe,
    get_auto_scale,
    get_display_unit,
    # Legacy import for backward compatibility (axis labels with HTML)
    unit_map,
)

# colors
berkeley_blue = "#002676"
berkeley_gold = "#FDB515"
rose_medium = "#E7115E"


def apply_standard_layout(fig, y_offset=-0.4, subtitle_text=None):
    # Keep existing annotations (like subplot titles)
    existing_annotations = list(fig.layout.annotations) if fig.layout.annotations else []

    if subtitle_text:
        subtitle_annotation = dict(
            text=subtitle_text,
            x=0,
            xref="paper",
            y=y_offset,
            yref="paper",
            showarrow=False,
            font=dict(size=16, color="gray"),
            align="center",
        )
        existing_annotations.append(subtitle_annotation)

    fig.update_layout(
        annotations=existing_annotations,  # keep old + add subtitle
        title_font=dict(size=14),
        font=dict(size=16),
    )

    return fig


def shorten_scenario_name(scen_name, max_length=15):
    """Shorten scenario name while preserving (copy) suffix."""
    if len(scen_name) <= max_length:
        return scen_name
    if scen_name.endswith("(copy)"):
        return scen_name[:6] + "…(copy)"
    return scen_name[:12] + "…"


def plot_energy_and_emissions(df, equipment_scenarios, emission_scenarios, unit_mode="SI"):
    # --- Filter scenarios ---
    df = df[
        (df["eq_scen_id"].isin(equipment_scenarios)) & (df["em_scen_id"].isin(emission_scenarios))
    ].copy()

    # Use passed equipment_scenarios order (preserves user-defined order)
    # Filter to only include scenarios that exist in the data
    df_ids = set(df["eq_scen_id"].unique())
    scenarios = [s for s in equipment_scenarios if s in df_ids]
    name_map = dict(zip(df["eq_scen_id"], df["eq_scen_name"], strict=False))

    n_scen = len(scenarios)
    opacities = np.linspace(1, 1, n_scen)  # fade scenarios slightly, ignore for now

    # NOTE: Don't use convert_dataframe - we use auto-scaling directly from base units

    # --- Pre-calculate totals in BASE units to determine auto-scaling ---
    energy_totals = []
    emissions_totals = []
    for scen in scenarios:
        df_s = df[df["eq_scen_id"] == scen]
        # Energy columns are in Wh (base unit)
        elec = (
            df_s[
                [
                    "elec_hr_Wh",
                    "elec_awhp_h_Wh",
                    "elec_awhp_c_Wh",
                    "elec_res_Wh",
                    "elec_chiller_Wh",
                ]
            ]
            .sum()
            .sum()
        )
        gas = df_s["gas_boiler_Wh"].sum()
        energy_totals.extend([elec, gas])

        # Emissions columns are in kg CO₂e (base unit)
        elec_em = df_s["elec_emissions"].sum()
        gas_em = df_s["gas_emissions"].sum()
        refrig_em = df_s["total_refrig_emissions"].sum()
        emissions_totals.extend([elec_em, gas_em, refrig_em])

    # --- Determine auto-scaling (from base units directly) ---
    energy_scale, energy_unit = get_auto_scale(energy_totals, "energy", unit_mode)
    emissions_scale, emissions_unit = get_auto_scale(emissions_totals, "emissions", unit_mode)

    # --- Axis labels with auto-scaled units ---
    yaxis_title_energy = f'Energy <span style="font-weight:200">| {energy_unit}</span>'
    yaxis_title_emissions = f'Emissions <span style="font-weight:200">| {emissions_unit}</span>'

    # --- Hover units (use scaled units) ---
    energy_hover_unit = energy_unit
    emissions_hover_unit = emissions_unit

    # --- Colors ---
    color_map_energy = {"Electricity": berkeley_blue, "Gas": berkeley_gold}
    color_map_emissions = {
        "Electricity": berkeley_blue,
        "Gas": berkeley_gold,
        "Refrigerant": rose_medium,
    }

    # --- Build subplot container ---
    fig = make_subplots(
        rows=1,
        cols=2,
        subplot_titles=["Energy", "Emissions"],
        horizontal_spacing=0.15,
    )

    # --- ENERGY STACKED BAR ---
    for i, scen in enumerate(scenarios):
        df_s = df[df["eq_scen_id"] == scen]

        scen_name = name_map.get(scen, scen)
        scen_name_short = shorten_scenario_name(scen_name)

        elec_total = (
            df_s[
                [
                    "elec_hr_Wh",
                    "elec_awhp_h_Wh",
                    "elec_awhp_c_Wh",
                    "elec_res_Wh",
                    "elec_chiller_Wh",
                ]
            ]
            .sum()
            .sum()
        )
        gas_total = df_s["gas_boiler_Wh"].sum()

        # Apply auto-scaling
        elec_scaled = elec_total / energy_scale
        gas_scaled = gas_total / energy_scale

        # Electricity
        fig.add_trace(
            go.Bar(
                x=[scen_name_short],
                y=[elec_scaled],
                name="Electricity",
                marker=dict(color=color_map_energy["Electricity"], opacity=opacities[i]),
                hovertemplate=(
                    f"Scenario: {scen_name}<br>"
                    f"Electricity: {elec_scaled:,.1f} {energy_hover_unit}"
                    "<extra></extra>"
                ),
                showlegend=False,
            ),
            row=1,
            col=1,
        )

        # Gas
        fig.add_trace(
            go.Bar(
                x=[scen_name_short],
                y=[gas_scaled],
                name="Gas",
                marker=dict(color=color_map_energy["Gas"], opacity=opacities[i]),
                hovertemplate=(
                    f"Scenario: {scen_name}<br>"
                    f"Gas: {gas_scaled:,.1f} {energy_hover_unit}"
                    "<extra></extra>"
                ),
                showlegend=False,
            ),
            row=1,
            col=1,
        )

    added_legends = set()  # manage legends, would otherwise duplicate

    # --- EMISSIONS STACKED BAR ---
    for i, scen in enumerate(scenarios):
        df_s = df[df["eq_scen_id"] == scen]
        scen_name = name_map.get(scen, scen)
        scen_name_short = shorten_scenario_name(scen_name)

        elec_em = df_s["elec_emissions"].sum().sum()
        gas_em = df_s["gas_emissions"].sum().sum()
        refrig_em = df_s["total_refrig_emissions"].sum().sum()

        # Apply auto-scaling
        elec_em_scaled = elec_em / emissions_scale
        gas_em_scaled = gas_em / emissions_scale
        refrig_em_scaled = refrig_em / emissions_scale

        show_legend = "Electricity" not in added_legends
        fig.add_trace(
            go.Bar(
                x=[scen_name_short],
                y=[elec_em_scaled],
                name="Electricity",
                marker=dict(color=color_map_emissions["Electricity"], opacity=opacities[i]),
                hovertemplate=(
                    f"Scenario: {scen_name}<br>"
                    f"Electricity: {elec_em_scaled:,.1f} {emissions_hover_unit}"
                    "<extra></extra>"
                ),
                showlegend=show_legend,
            ),
            row=1,
            col=2,
        )
        added_legends.add("Electricity")

        show_legend = "Gas" not in added_legends
        fig.add_trace(
            go.Bar(
                x=[scen_name_short],
                y=[gas_em_scaled],
                name="Gas",
                marker=dict(color=color_map_emissions["Gas"], opacity=opacities[i]),
                hovertemplate=(
                    f"Scenario: {scen_name}<br>"
                    f"Gas: {gas_em_scaled:,.1f} {emissions_hover_unit}"
                    "<extra></extra>"
                ),
                showlegend=show_legend,
            ),
            row=1,
            col=2,
        )
        added_legends.add("Gas")

        show_legend = "Refrigerant" not in added_legends
        fig.add_trace(
            go.Bar(
                x=[scen_name_short],
                y=[refrig_em_scaled],
                name="Refrigerant",
                marker=dict(color=color_map_emissions["Refrigerant"], opacity=opacities[i]),
                hovertemplate=(
                    f"Scenario: {scen_name}<br>"
                    f"Refrigerant: {refrig_em_scaled:,.1f} {emissions_hover_unit}"
                    "<extra></extra>"
                ),
                showlegend=show_legend,
            ),
            row=1,
            col=2,
        )
        added_legends.add("Refrigerant")

    # --- Layout ---
    fig.update_layout(barmode="stack", height=600, margin=dict(b=150))

    fig.update_yaxes(title_text=yaxis_title_energy, row=1, col=1)
    fig.update_yaxes(title_text=yaxis_title_emissions, row=1, col=2)

    fig = apply_standard_layout(
        fig, y_offset=-0.42, subtitle_text="Annual Energy & Emissions by Scenario."
    )

    return fig


def plot_emission_scenarios_grouped(
    df,
    equipment_scenarios,
    emission_scenarios,
    unit_mode="SI",
):
    # --- Filter scenarios ---
    df = df[
        (df["eq_scen_id"].isin(equipment_scenarios)) & (df["em_scen_id"].isin(emission_scenarios))
    ].copy()

    # NOTE: Don't use convert_dataframe - we use auto-scaling directly from base units

    # --- Pre-calculate all emissions totals in BASE units for auto-scaling ---
    emissions_totals = []
    for em_scen in emission_scenarios:
        df_e = df[df["em_scen_id"] == em_scen]
        for scen in equipment_scenarios:
            df_s = df_e[df_e["eq_scen_id"] == scen]
            if not df_s.empty:
                # Emissions columns are in kg CO₂e (base unit)
                emissions_totals.append(df_s["elec_emissions"].sum())
                emissions_totals.append(df_s["gas_emissions"].sum())
                emissions_totals.append(df_s["total_refrig_emissions"].sum())

    # --- Determine auto-scaling (from base units directly) ---
    emissions_scale, emissions_unit = get_auto_scale(emissions_totals, "emissions", unit_mode)

    # --- Axis label with auto-scaled units ---
    yaxis_title_emissions = f'Emissions <span style="font-weight:200">| {emissions_unit}</span>'

    # --- Hover unit (use scaled unit) ---
    emissions_hover_unit = emissions_unit

    # --- Colors ---
    color_map_emissions = {
        "Electricity": berkeley_blue,
        "Gas": berkeley_gold,
        "Refrigerant": rose_medium,
    }

    # --- Create subplots (shared y-axis) ---
    n_em_scen = len(emission_scenarios)
    fig = make_subplots(
        rows=1,
        cols=n_em_scen,
        subplot_titles=[format_emission_scenario_id(em_scen) for em_scen in emission_scenarios],
        horizontal_spacing=0.12,
        shared_yaxes=True,
    )

    # --- Track which legend items have been added ---
    added_legends = set()

    # --- Plot emissions for each emission scenario ---
    for i, em_scen in enumerate(emission_scenarios):
        df_e = df[df["em_scen_id"] == em_scen]

        for scen in equipment_scenarios:
            df_s = df_e[df_e["eq_scen_id"] == scen]

            # if this combo doesn't exist in data, skip safely
            if df_s.empty:
                continue

            scen_name = df_s["eq_scen_name"].iloc[0]  # for hover template
            scen_name_short = shorten_scenario_name(scen_name)

            elec_em = df_s["elec_emissions"].sum()
            gas_em = df_s["gas_emissions"].sum()
            refrig_em = df_s["total_refrig_emissions"].sum()

            # Apply auto-scaling
            elec_em_scaled = elec_em / emissions_scale
            gas_em_scaled = gas_em / emissions_scale
            refrig_em_scaled = refrig_em / emissions_scale

            # Electricity
            show_legend = "Electricity" not in added_legends
            fig.add_trace(
                go.Bar(
                    x=[scen_name_short],  # 👈 use name instead of ID
                    y=[elec_em_scaled],
                    name="Electricity",
                    marker=dict(color=color_map_emissions["Electricity"]),
                    hovertemplate=(
                        f"Equipment: {scen_name}<br>"
                        f"Electricity: {elec_em_scaled:,.1f} {emissions_hover_unit}"
                        "<extra></extra>"
                    ),
                    showlegend=show_legend,
                ),
                row=1,
                col=i + 1,
            )
            added_legends.add("Electricity")

            # Gas
            show_legend = "Gas" not in added_legends
            fig.add_trace(
                go.Bar(
                    x=[scen_name_short],
                    y=[gas_em_scaled],
                    name="Gas",
                    marker=dict(color=color_map_emissions["Gas"]),
                    hovertemplate=(
                        f"Equipment: {scen_name}<br>"
                        f"Gas: {gas_em_scaled:,.1f} {emissions_hover_unit}"
                        "<extra></extra>"
                    ),
                    showlegend=show_legend,
                ),
                row=1,
                col=i + 1,
            )
            added_legends.add("Gas")

            # Refrigerant
            show_legend = "Refrigerant" not in added_legends
            fig.add_trace(
                go.Bar(
                    x=[scen_name_short],
                    y=[refrig_em_scaled],
                    name="Refrigerant",
                    marker=dict(color=color_map_emissions["Refrigerant"]),
                    hovertemplate=(
                        f"Equipment: {scen_name}<br>"
                        f"Refrigerant: {refrig_em_scaled:,.1f} {emissions_hover_unit}"
                        "<extra></extra>"
                    ),
                    showlegend=show_legend,
                ),
                row=1,
                col=i + 1,
            )
            added_legends.add("Refrigerant")

    # --- Layout ---
    fig.update_layout(barmode="stack", height=600, margin=dict(b=150))

    fig = apply_standard_layout(
        fig,
        y_offset=-0.4,
        subtitle_text="Annual Emissions per Equipment and grouped by Emission Scenario.",
    )

    # Shared y-axis label
    fig.update_yaxes(title_text=yaxis_title_emissions, row=1, col=1)

    return fig


def plot_meter_timeseries(
    df,
    equipment_scenario,
    emission_scenario,
    freq="D",
    stacked=False,
    include_gas=True,
    category_orders=None,
    aggfunc="sum",
    unit_mode="SI",
):
    """
    Plot time series data for meters (electricity, gas) with flexible aggregation.
    """

    metadata_cols = ["eq_scen_id", "em_scen_id"]

    energy_cols = [
        "elec_hr_Wh",
        "elec_awhp_h_Wh",
        "elec_chiller_Wh",
        "elec_awhp_c_Wh",
        "elec_res_Wh",
        "gas_boiler_Wh",
    ]

    filtered = df[
        (df["eq_scen_id"] == equipment_scenario) & (df["em_scen_id"] == emission_scenario)
    ].copy()

    all_cols = metadata_cols + energy_cols
    df = filtered[[c for c in all_cols if c in df.columns]]

    # NOTE: Don't use convert_dataframe - we use auto-scaling directly from base units

    df = df.drop(columns=["eq_scen_id"], errors="ignore")
    df = df.drop(columns=["em_scen_id"], errors="ignore")

    if not isinstance(df.index, pd.DatetimeIndex):
        raise ValueError("DataFrame index must be a DateTimeIndex")

    # Validate aggregation function
    if aggfunc not in ["sum", "mean"]:
        raise ValueError("aggfunc must be either 'sum' or 'mean'")

    # Resample data with chosen aggregation (values remain in base units Wh)
    if aggfunc == "sum":
        df_resampled = df.resample(freq).sum()
        usage_label = "Usage"
    else:
        df_resampled = df.resample(freq).mean()
        usage_label = "Average usage"

    # Filter out gas meters if requested
    if not include_gas:
        df_resampled = df_resampled[
            [col for col in df_resampled.columns if "gas" not in col.lower()]
        ]

    # --- Auto-scaling based on resampled data (in base units Wh) ---
    all_values = df_resampled.values.flatten()
    all_values = [v for v in all_values if v is not None and not np.isnan(v)]
    energy_scale, energy_unit = get_auto_scale(all_values, "energy", unit_mode)

    # Apply scaling to resampled data
    df_resampled = df_resampled / energy_scale

    # Build axis title with auto-scaled unit
    yaxis_title = f'Energy <span style="font-weight:200">| {energy_unit}</span>'
    hover_unit = energy_unit

    # Rename columns to user-friendly display names
    df_resampled = df_resampled.rename(columns=format_meter_name)

    if not stacked:
        # Melt for line chart
        df_melt = df_resampled.reset_index().melt(
            id_vars=df_resampled.index.name or "index",
            var_name="Meter",
            value_name="Usage",
        )

        fig = px.line(
            df_melt,
            x=df_resampled.index.name or "index",
            y="Usage",
            color="Meter",
            title=f"Meter Usage ({freq} Aggregation, {aggfunc})",
        )

        fig.update_layout(
            xaxis_title="Time",
            yaxis_title=(yaxis_title if aggfunc == "sum" else f"Average {yaxis_title}"),
            legend_title="Meter",
        )

        # --- Unify hover per trace ---
        # Each trace is one meter
        for tr in fig.data:
            meter_name = tr.name  # px sets this
            tr.meta = meter_name  # so we can use %{meta}
            tr.hovertemplate = (
                "Time: %{x|%Y-%m-%d %H:%M}<br>"
                "Meter: %{meta}<br>"
                f"{usage_label}: " + f"%{{y:,.2f}} {hover_unit}"
                "<extra></extra>"
            )

    else:
        # Drop meters with all zero usage
        nonzero_cols = df_resampled.columns[df_resampled.sum(axis=0) != 0]
        df_resampled = df_resampled[nonzero_cols]

        # Melt for stacked chart
        df_melt = df_resampled.reset_index().melt(
            id_vars=df_resampled.index.name or "index",
            var_name="Meter",
            value_name="Usage",
        )

        fig = px.area(
            df_melt,
            x=df_resampled.index.name or "index",
            y="Usage",
            color="Meter",
            line_group="Meter",
            category_orders={"Meter": category_orders} if category_orders else None,
        )

        fig.update_traces(stackgroup="one")
        fig.update_layout(
            xaxis_title="",
            yaxis_title=(yaxis_title if aggfunc == "sum" else f"Average {yaxis_title}"),
            template="decarb-tool-theme",
            margin=dict(b=150),
            height=600,
        )

        fig = apply_standard_layout(
            fig,
            y_offset=-0.2,
            subtitle_text="Stacked Meter Usage, aggregated over time.",
        )

        for tr in fig.data:
            meter_name = tr.name
            tr.meta = meter_name
            tr.hovertemplate = (
                "Time: %{x|%Y-%m-%d %H:%M}<br>"
                "Meter: %{meta}<br>"
                f"{usage_label}: " + f"%{{y:,.2f}} {hover_unit}"
                "<extra></extra>"
            )

    return fig


def plot_emissions_heatmap(
    df,
    equipment_scenario,
    emission_scenario,
    unit_mode="SI",
    emission_type="elec_emissions",
):
    """
    Plot a heatmap of electricity emissions (elec_emissions) by hour and day of the year.
    """

    metadata_cols = ["eq_scen_id", "em_scen_id"]

    emission_cols = [
        "elec_emissions",
        "gas_emissions",
        "total_refrig_emissions",
        "total_emissions",
    ]

    all_cols = metadata_cols + emission_cols

    filtered = df[
        (df["eq_scen_id"] == equipment_scenario) & (df["em_scen_id"] == emission_scenario)
    ].copy()

    # keep only what exists
    df = filtered[[c for c in all_cols if c in filtered.columns]].copy()

    # --- Unit conversion (centralized) ---
    df = convert_dataframe(df, unit_mode)

    hover_unit = get_display_unit("emissions", unit_mode)
    legend_title = unit_map["emissions"][unit_mode]["label"]

    # Check if the 'elec_emissions' column exists
    if emission_type not in df.columns:
        raise ValueError(f"Missing required column: '{emission_type}'")

    # Ensure the index is datetime
    if not pd.api.types.is_datetime64_any_dtype(df.index):
        raise ValueError("The index must be a datetime type.")

    # Extract hour and day of year
    df["hour"] = df.index.hour
    df["doy"] = df.index.dayofyear

    # Pivot to 2D array (hour x day of year)
    heatmap_data = df.pivot_table(index="hour", columns="doy", values=emission_type, aggfunc="mean")

    # Create the heatmap plot
    fig = go.Figure(
        data=go.Heatmap(
            z=heatmap_data.values,
            x=heatmap_data.columns,
            y=heatmap_data.index,
            zmin=0,  # fix to zero to visualize constant refrigerant emissions
            colorscale="YlGnBu",
            colorbar=dict(title=legend_title),
            hovertemplate=(
                "Day of Year: %{x}<br>"
                "Hour: %{y}<br>"
                f"Emissions: %{{z:.2f}} {hover_unit}"
                "<extra></extra>"
            ),
            zsmooth="best",
        )
    )

    fig.update_layout(
        xaxis_title="Day of Year",
        yaxis_title="Hour of Day",
        margin=dict(b=150),
        height=600,
        template="decarb-tool-theme",
    )

    # Map emission type to display name
    emission_type_labels = {
        "elec_emissions": "Electricity Emissions",
        "gas_emissions": "Gas Emissions",
        "total_refrig_emissions": "Refrigerant Emissions",
        "total_emissions": "Total Emissions",
    }
    emission_label = emission_type_labels.get(emission_type, emission_type)

    fig = apply_standard_layout(
        fig,
        y_offset=-0.3,
        subtitle_text=f"Annual heatmap of hourly {emission_label.lower()}.",
    )

    return fig


def plot_scatter_temp_vs_variable(
    df,
    y_var,
    equipment_scenarios=None,
    emission_scenarios=None,
    agg="D",
    unit_mode="SI",
):
    energy_cols = [
        "elec_hr_Wh",
        "elec_awhp_h_Wh",
        "elec_awhp_c_Wh",
        "elec_res_Wh",
        "elec_chiller_Wh",
        "gas_boiler_Wh",
        "elec_Wh",
        "gas_Wh",
    ]
    emission_cols = [
        "elec_emissions",
        "gas_emissions",
        "total_refrig_emissions",
        "total_emissions",
    ]

    # --- Unit conversion (centralized) ---
    df = convert_dataframe(df, unit_mode)

    # --- Determine y-axis type and label ---
    if y_var not in df.columns:
        raise ValueError(f"{y_var} not found in DataFrame columns.")

    if y_var in energy_cols:
        y_var_type = "energy"
    elif y_var in emission_cols:
        y_var_type = "emissions"
    else:
        raise ValueError(f"{y_var} not recognized as energy or emissions variable.")

    yaxis_title = unit_map[y_var_type][unit_mode]["label"]
    xaxis_title_temp = unit_map["temperature"][unit_mode]["label"]

    # hover units (short, plain text)
    y_hover_unit = get_display_unit(y_var_type, unit_mode)
    t_hover_unit = get_display_unit("temperature", unit_mode)

    # --- Filter scenarios ---
    df = df[
        (df["eq_scen_id"].isin(equipment_scenarios)) & (df["em_scen_id"].isin(emission_scenarios))
    ].copy()

    if not pd.api.types.is_datetime64_any_dtype(df.index):
        raise ValueError("DataFrame index must be datetime for daily averaging.")

    # --- Use readable scenario names if available ---
    if "eq_scen_name" in df.columns:
        df["label"] = df["eq_scen_name"]
    else:
        df["label"] = df["eq_scen_id"]

    if agg == "D":
        df["period"] = df.index.date  # daily
        agg_label = "daily"
    elif agg == "W":
        df["period"] = df.index.to_period("W").start_time  # weekly
        agg_label = "weekly"
    else:
        raise ValueError("Aggregation method not recognized. Use 'D' or 'W'.")

    # --- Now group on columns only ---
    daily = df.groupby(["period", "eq_scen_id", "em_scen_id", "label"], as_index=False).agg(
        {"t_out_C": "mean", y_var: "mean"}
    )

    # --- Build figure ---
    fig = go.Figure()
    for (_, _), df_s in daily.groupby(["eq_scen_id", "em_scen_id"]):
        scen_name = df_s["label"].iloc[0]
        customdata = df_s[["label", "em_scen_id", "t_out_C", y_var]].values
        fig.add_trace(
            go.Scatter(
                x=df_s["t_out_C"],
                y=df_s[y_var],
                mode="markers",
                marker=dict(size=10, opacity=0.6),
                name=f"{scen_name}",
                customdata=customdata,
                hovertemplate=(
                    "Equipment: %{customdata[0]}<br>"
                    "Emissions scenario: %{customdata[1]}<br>"
                    # temperature row
                    f"T_out ({agg_label} mean): %{{customdata[2]:.2f}} {t_hover_unit}<br>"
                    # y_var row (pretty name)
                    f"{y_var.replace('_',' ').title()} ({agg_label} mean): "
                    f"%{{customdata[3]:.2f}} {y_hover_unit}"
                    "<extra></extra>"
                ),
            )
        )

    fig.update_layout(
        xaxis_title=xaxis_title_temp,
        yaxis_title=yaxis_title,
        height=450,
        margin=dict(b=150, t=10),
        legend_title_text="Scenario",
        template="decarb-tool-theme",
    )

    fig = apply_standard_layout(
        fig,
        y_offset=-0.35,
        subtitle_text=f"Average Outdoor Temperature against {y_var.replace('_',' ').title()}.",
    )

    return fig
