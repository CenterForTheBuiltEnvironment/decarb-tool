import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from utils.units import unit_map, get_unit_converter, get_hover_unit


# colors
berkeley_blue = "#002676"
berkeley_gold = "#FDB515"
rose_medium = "#E7115E"


def apply_standard_layout(fig, y_offset=-0.4, subtitle_text=None):
    # Keep existing annotations (like subplot titles)
    existing_annotations = (
        list(fig.layout.annotations) if fig.layout.annotations else []
    )

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


def plot_energy_and_emissions(
    df, equipment_scenarios, emission_scenarios, unit_mode="SI"
):

    col_to_type = {
        # Energy
        "elec_hr_Wh": "energy",
        "elec_awhp_h_Wh": "energy",
        "elec_awhp_c_Wh": "energy",
        "elec_res_Wh": "energy",
        "elec_chiller_Wh": "energy",
        "gas_boiler_Wh": "energy",
        # Emissions
        "elec_emissions": "emissions",
        "gas_emissions": "emissions",
        "total_refrig_emissions": "emissions",
    }

    # --- Filter scenarios ---
    df = df[
        (df["eq_scen_id"].isin(equipment_scenarios))
        & (df["em_scen_id"].isin(emission_scenarios))
    ].copy()

    scenarios = df["eq_scen_id"].unique()
    name_map = dict(zip(df["eq_scen_id"], df["eq_scen_name"]))

    n_scen = len(scenarios)
    opacities = np.linspace(1, 1, n_scen)  # fade scenarios slightly, ignore for now

    # --- Convert all columns according to unit mode ---
    for col in df.columns:
        if col in col_to_type:
            var_type = col_to_type[col]
            conv = get_unit_converter(var_type, unit_mode)
            df.loc[:, col] = df[col].apply(conv)

    # --- Axis labels ---
    yaxis_title_energy = unit_map["energy"][unit_mode]["label"]
    yaxis_title_emissions = unit_map["emissions"][unit_mode]["label"]

    # --- Hover units ---
    energy_hover_unit = get_hover_unit("energy", unit_mode)
    emissions_hover_unit = get_hover_unit("emissions", unit_mode)

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
        scen_name_short = scen_name[:12] + "…" if len(scen_name) > 15 else scen_name

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

        # Electricity
        fig.add_trace(
            go.Bar(
                x=[scen_name_short],
                y=[elec_total],
                name="Electricity",
                marker=dict(
                    color=color_map_energy["Electricity"], opacity=opacities[i]
                ),
                hovertemplate=(
                    f"Scenario: {scen_name}<br>"
                    f"Electricity: {elec_total:.0f} {energy_hover_unit}"
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
                y=[gas_total],
                name="Gas",
                marker=dict(color=color_map_energy["Gas"], opacity=opacities[i]),
                hovertemplate=(
                    f"Scenario: {scen_name}<br>"
                    f"Gas: {gas_total:.0f} {energy_hover_unit}"
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
        scen_name_short = scen_name[:12] + "…" if len(scen_name) > 15 else scen_name

        elec_em = df_s["elec_emissions"].sum().sum()
        gas_em = df_s["gas_emissions"].sum().sum()
        refrig_em = df_s["total_refrig_emissions"].sum().sum()

        show_legend = "Electricity" not in added_legends
        fig.add_trace(
            go.Bar(
                x=[scen_name_short],
                y=[elec_em],
                name="Electricity",
                marker=dict(
                    color=color_map_emissions["Electricity"], opacity=opacities[i]
                ),
                hovertemplate=(
                    f"Scenario: {scen_name}<br>"
                    f"Electricity: {elec_em:.1f} {emissions_hover_unit}"
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
                y=[gas_em],
                name="Gas",
                marker=dict(color=color_map_emissions["Gas"], opacity=opacities[i]),
                hovertemplate=(
                    f"Scenario: {scen_name}<br>"
                    f"Gas: {gas_em:.1f} {emissions_hover_unit}"
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
                y=[refrig_em],
                name="Refrigerant",
                marker=dict(
                    color=color_map_emissions["Refrigerant"], opacity=opacities[i]
                ),
                hovertemplate=(
                    f"Scenario: {scen_name}<br>"
                    f"Refrigerant: {refrig_em:.1f} {emissions_hover_unit}"
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
        fig, y_offset=-0.35, subtitle_text="Annual Energy & Emissions by Scenario."
    )

    return fig


def plot_emission_scenarios_grouped(
    df,
    equipment_scenarios,
    emission_scenarios,
    unit_mode="SI",
):
    col_to_type = {
        "elec_emissions": "emissions",
        "gas_emissions": "emissions",
        "total_refrig_emissions": "emissions",
    }

    # --- Filter scenarios ---
    df = df[
        (df["eq_scen_id"].isin(equipment_scenarios))
        & (df["em_scen_id"].isin(emission_scenarios))
    ].copy()

    # --- Unit conversion ---
    for col in df.columns:
        if col in col_to_type:
            var_type = col_to_type[col]
            conv = get_unit_converter(var_type, unit_mode)  # <- our helper
            df.loc[:, col] = df[col].apply(conv)

    # --- Axis label ---
    yaxis_title_emissions = unit_map["emissions"][unit_mode]["label"]

    # --- Hover unit ---
    emissions_hover_unit = get_hover_unit("emissions", unit_mode)

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
        subplot_titles=[f"{em_scen}" for em_scen in emission_scenarios],
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
            scen_name_short = scen_name[:12] + "…" if len(scen_name) > 15 else scen_name

            elec_em = df_s["elec_emissions"].sum()
            gas_em = df_s["gas_emissions"].sum()
            refrig_em = df_s["total_refrig_emissions"].sum()

            # Electricity
            show_legend = "Electricity" not in added_legends
            fig.add_trace(
                go.Bar(
                    x=[scen_name_short],  # 👈 use name instead of ID
                    y=[elec_em],
                    name="Electricity",
                    marker=dict(color=color_map_emissions["Electricity"]),
                    hovertemplate=(
                        f"Equipment: {scen_name}<br>"
                        f"Electricity: {elec_em:.1f} {emissions_hover_unit}"
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
                    y=[gas_em],
                    name="Gas",
                    marker=dict(color=color_map_emissions["Gas"]),
                    hovertemplate=(
                        f"Equipment: {scen_name}<br>"
                        f"Gas: {gas_em:.1f} {emissions_hover_unit}"
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
                    y=[refrig_em],
                    name="Refrigerant",
                    marker=dict(color=color_map_emissions["Refrigerant"]),
                    hovertemplate=(
                        f"Equipment: {scen_name}<br>"
                        f"Refrigerant: {refrig_em:.1f} {emissions_hover_unit}"
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
        y_offset=-0.35,
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

    # Setting up unit conversion
    variable_type = "energy"

    metadata_cols = ["eq_scen_id", "em_scen_id"]

    convert_cols = [
        "elec_hr_Wh",
        "elec_awhp_h_Wh",
        "elec_chiller_Wh",
        "elec_awhp_c_Wh",
        "elec_res_Wh",
        "gas_boiler_Wh",
    ]

    filtered = df[
        (df["eq_scen_id"] == equipment_scenario)
        & (df["em_scen_id"] == emission_scenario)
    ].copy()

    all_cols = metadata_cols + convert_cols
    df = filtered[[c for c in all_cols if c in df.columns]]

    conv = get_unit_converter(variable_type, unit_mode)
    hover_unit = get_hover_unit(variable_type, unit_mode)

    df.loc[:, [c for c in convert_cols if c in df.columns]] = df[
        [c for c in convert_cols if c in df.columns]
    ].apply(conv)

    yaxis_title = unit_map[variable_type][unit_mode]["label"]

    df = df.drop(columns=["eq_scen_id"], errors="ignore")
    df = df.drop(columns=["em_scen_id"], errors="ignore")

    if not isinstance(df.index, pd.DatetimeIndex):
        raise ValueError("DataFrame index must be a DateTimeIndex")

    # Validate aggregation function
    if aggfunc not in ["sum", "mean"]:
        raise ValueError("aggfunc must be either 'sum' or 'mean'")

    # Resample data with chosen aggregation
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
                f"{usage_label}: " + f"%{{y:.2f}} {hover_unit}"
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
                f"{usage_label}: " + f"%{{y:.2f}} {hover_unit}"
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

    # Setting up unit conversion
    variable_type = "emissions"

    metadata_cols = ["eq_scen_id", "em_scen_id"]

    convert_cols = [
        "elec_emissions",
        "gas_emissions",
        "total_refrig_emissions",
        "total_emissions",
    ]

    all_cols = metadata_cols + convert_cols

    filtered = df[
        (df["eq_scen_id"] == equipment_scenario)
        & (df["em_scen_id"] == emission_scenario)
    ].copy()

    # keep only what exists
    df = filtered[[c for c in all_cols if c in filtered.columns]].copy()

    # --- unit conversion (to current mode) ---
    conv = get_unit_converter(variable_type, unit_mode)
    hover_unit = get_hover_unit(variable_type, unit_mode)

    # convert only cols that are present
    cols_to_convert = [c for c in convert_cols if c in df.columns]
    if cols_to_convert:
        df.loc[:, cols_to_convert] = df[cols_to_convert].apply(conv)

    # colorbar / legend title from unit_map (HTML-ish like your other plots)
    legend_title = unit_map[variable_type][unit_mode]["label"]

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
    heatmap_data = df.pivot_table(
        index="hour", columns="doy", values=emission_type, aggfunc="mean"
    )

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

    fig = apply_standard_layout(
        fig,
        y_offset=-0.3,
        subtitle_text=f"Annual heatmap of hourly emissions for {emission_type}.",
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
    temp_cols = ["t_out_C"]

    # --- Create col_to_type dict dynamically ---
    col_to_type = {col: "energy" for col in energy_cols}
    col_to_type.update({col: "emissions" for col in emission_cols})
    col_to_type.update({col: "temperature" for col in temp_cols})

    # --- Convert units if needed ---
    for col, var_type in col_to_type.items():
        if col in df.columns:
            conv = get_unit_converter(var_type, unit_mode)
            df[col] = df[col].apply(conv)

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
    y_hover_unit = get_hover_unit(y_var_type, unit_mode)
    t_hover_unit = get_hover_unit("temperature", unit_mode)

    # --- Filter scenarios ---
    df = df[
        (df["eq_scen_id"].isin(equipment_scenarios))
        & (df["em_scen_id"].isin(emission_scenarios))
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
    daily = df.groupby(
        ["period", "eq_scen_id", "em_scen_id", "label"], as_index=False
    ).agg({"t_out_C": "mean", y_var: "mean"})

    # --- Build figure ---
    fig = go.Figure()
    for (scen_id, em_scen), df_s in daily.groupby(["eq_scen_id", "em_scen_id"]):
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
