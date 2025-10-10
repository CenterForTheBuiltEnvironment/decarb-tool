import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from utils.units import unit_map


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
        (df["scenario_id"].isin(equipment_scenarios))
        & (df["em_scen_id"].isin(emission_scenarios))
    ]

    scenarios = df["scenario_id"].unique()
    n_scen = len(scenarios)
    opacities = np.linspace(1, 1, n_scen)  # fade scenarios slightly, ignore for now

    # --- Convert all columns according to unit mode ---
    for col in df.columns:
        if col in col_to_type:
            var_type = col_to_type[col]
            df.loc[:, col] = df[col].apply(unit_map[var_type][unit_mode]["func"])

    # --- Axis labels ---
    yaxis_title_energy = unit_map["energy"][unit_mode]["label"]
    yaxis_title_emissions = unit_map["emissions"][unit_mode]["label"]

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
        df_s = df[df["scenario_id"] == scen]

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
            / 1000
        )
        gas_total = df_s["gas_boiler_Wh"].sum() / 1000

        # Electricity
        fig.add_trace(
            go.Bar(
                x=[scen],
                y=[elec_total],
                name="Electricity",
                marker=dict(
                    color=color_map_energy["Electricity"], opacity=opacities[i]
                ),
                hovertemplate=f"Scenario: {scen}<br>Electricity: {elec_total:.0f} kWh<extra></extra>",
                showlegend=False,
            ),
            row=1,
            col=1,
        )

        # Gas
        fig.add_trace(
            go.Bar(
                x=[scen],
                y=[gas_total],
                name="Gas",
                marker=dict(color=color_map_energy["Gas"], opacity=opacities[i]),
                hovertemplate=f"Scenario: {scen}<br>Gas: {gas_total:.0f} kWh<extra></extra>",
                showlegend=False,
            ),
            row=1,
            col=1,
        )

    added_legends = set()  # manage legends, would otherwise duplicate

    # --- EMISSIONS STACKED BAR ---
    for i, scen in enumerate(scenarios):
        df_s = df[df["scenario_id"] == scen]

        elec_em = df_s["elec_emissions"].sum().sum()
        gas_em = df_s["gas_emissions"].sum().sum()
        refrig_em = df_s["total_refrig_emissions"].sum().sum()

        show_legend = "Electricity" not in added_legends
        fig.add_trace(
            go.Bar(
                x=[scen],
                y=[elec_em],
                name="Electricity",
                marker=dict(
                    color=color_map_emissions["Electricity"], opacity=opacities[i]
                ),
                hovertemplate=f"Scenario: {scen}<br>Electricity: {elec_em:.1f} kgCO₂<extra></extra>",
                showlegend=show_legend,
            ),
            row=1,
            col=2,
        )
        added_legends.add("Electricity")

        show_legend = "Gas" not in added_legends
        fig.add_trace(
            go.Bar(
                x=[scen],
                y=[gas_em],
                name="Gas",
                marker=dict(color=color_map_emissions["Gas"], opacity=opacities[i]),
                hovertemplate=f"Scenario: {scen}<br>Gas: {gas_em:.1f} kgCO₂<extra></extra>",
                showlegend=show_legend,
            ),
            row=1,
            col=2,
        )
        added_legends.add("Gas")

        show_legend = "Refrigerant" not in added_legends
        fig.add_trace(
            go.Bar(
                x=[scen],
                y=[refrig_em],
                name="Refrigerant",
                marker=dict(
                    color=color_map_emissions["Refrigerant"], opacity=opacities[i]
                ),
                hovertemplate=f"Scenario: {scen}<br>Refrigerant: {refrig_em:.1f} kgCO₂<extra></extra>",
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
    df, equipment_scenarios, emission_scenarios, unit_mode="SI"
):
    col_to_type = {
        "elec_emissions": "emissions",
        "gas_emissions": "emissions",
        "total_refrig_emissions": "emissions",
    }

    # --- Filter scenarios ---
    df = df[
        (df["scenario_id"].isin(equipment_scenarios))
        & (df["em_scen_id"].isin(emission_scenarios))
    ]

    # --- Unit conversion ---
    for col in df.columns:
        if col in col_to_type:
            var_type = col_to_type[col]
            df.loc[:, col] = df[col].apply(unit_map[var_type][unit_mode]["func"])

    # --- Axis label ---
    yaxis_title_emissions = unit_map["emissions"][unit_mode]["label"]

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
            df_s = df_e[df_e["scenario_id"] == scen]
            elec_em = df_s["elec_emissions"].sum()
            gas_em = df_s["gas_emissions"].sum()
            refrig_em = df_s["total_refrig_emissions"].sum()

            # Electricity
            show_legend = "Electricity" not in added_legends
            fig.add_trace(
                go.Bar(
                    x=[scen],
                    y=[elec_em],
                    name="Electricity",
                    marker=dict(color=color_map_emissions["Electricity"]),
                    hovertemplate=f"Equipment: {scen}<br>Electricity: {elec_em:.1f} kgCO₂<extra></extra>",
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
                    x=[scen],
                    y=[gas_em],
                    name="Gas",
                    marker=dict(color=color_map_emissions["Gas"]),
                    hovertemplate=f"Equipment: {scen}<br>Gas: {gas_em:.1f} kgCO₂<extra></extra>",
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
                    x=[scen],
                    y=[refrig_em],
                    name="Refrigerant",
                    marker=dict(color=color_map_emissions["Refrigerant"]),
                    hovertemplate=f"Equipment: {scen}<br>Refrigerant: {refrig_em:.1f} kgCO₂<extra></extra>",
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

    metadata_cols = ["scenario_id", "em_scen_id"]

    convert_cols = [
        "elec_hr_Wh",
        "elec_awhp_h_Wh",
        "elec_chiller_Wh",
        "elec_awhp_c_Wh",
        "elec_res_Wh",
        "gas_boiler_Wh",
    ]

    all_cols = metadata_cols + convert_cols

    filtered = df[
        (df["scenario_id"] == equipment_scenario)
        & (df["em_scen_id"] == emission_scenario)
    ]

    df = filtered[[c for c in all_cols if c in df.columns]]

    conversion = unit_map[variable_type][unit_mode]

    df.loc[:, convert_cols] = df.loc[:, convert_cols].apply(conversion["func"])
    yaxis_title = conversion["label"]

    df = df.drop(columns=["scenario_id"], errors="ignore")
    df = df.drop(columns=["em_scen_id"], errors="ignore")

    if not isinstance(df.index, pd.DatetimeIndex):
        raise ValueError("DataFrame index must be a DateTimeIndex")

    # Validate aggregation function
    if aggfunc not in ["sum", "mean"]:
        raise ValueError("aggfunc must be either 'sum' or 'mean'")

    # Resample data with chosen aggregation
    if aggfunc == "sum":
        df_resampled = df.resample(freq).sum()
    else:
        df_resampled = df.resample(freq).mean()

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
        )

        fig = apply_standard_layout(
            fig,
            y_offset=-0.35,
            subtitle_text="Stacked Meter Usage, aggregated over time.",
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

    metadata_cols = ["scenario_id", "em_scen_id"]

    convert_cols = [
        "elec_emissions",
        "gas_emissions",
        "total_refrig_emissions",
        "total_emissions",
    ]

    all_cols = metadata_cols + convert_cols

    filtered = df[
        (df["scenario_id"] == equipment_scenario)
        & (df["em_scen_id"] == emission_scenario)
    ].copy()  # 👈 Add .copy() here

    df = filtered[[c for c in all_cols if c in df.columns]].copy()

    conversion = unit_map[variable_type][unit_mode]

    df.loc[:, convert_cols] = df.loc[:, convert_cols].apply(conversion["func"])
    legend_title = conversion["label"]

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
            hovertemplate="Day of Year: %{x}<br>Hour: %{y}<br>Emissions: %{z:.2f} kg CO₂<extra></extra>",
            zsmooth="best",
        )
    )

    fig.update_layout(
        xaxis_title="Day of Year",
        yaxis_title="Hour of Day",
        margin=dict(b=150),
        height=500,
        template="decarb-tool-theme",
    )

    fig = apply_standard_layout(
        fig,
        y_offset=-0.4,
        subtitle_text=f"Annual heatmap of hourly emissions for {emission_type}.",
    )

    return fig


def plot_energy_breakdown(df, equipment_scenarios, emission_scenarios):
    """
    Plot a summary of energy usage by component.
    """

    elec_components = [
        "elec_hr_Wh",
        "elec_awhp_h_Wh",
        "elec_awhp_c_Wh",
        "elec_res_Wh",
        "elec_chiller_Wh",
    ]

    gas_components = [
        "gas_boiler_Wh",
    ]

    required_columns = elec_components + ["elec_Wh"] + gas_components

    # check for missing columns
    missing = [col for col in required_columns if col not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns in DataFrame: {missing}")

    filtered = df[
        (df["scenario_id"].isin(equipment_scenarios))
        & (df["em_scen_id"].isin(emission_scenarios))
    ]

    summary = (
        filtered[required_columns].sum().sort_values(ascending=False) / 1000
    )  # Convert to kWh

    # prepare df for Plotly
    summary_df = summary.reset_index()
    summary_df.columns = ["Component", "Annual_kWh"]
    summary_df["Type"] = summary_df["Component"].apply(
        lambda x: "Total" if x == "elec_Wh" else "Component"
    )

    # Create plot
    fig = px.bar(
        summary_df,
        x="Annual_kWh",
        y="Component",
        color="Type",
        orientation="h",
        title="Annual Electricity Use by Component (kWh)",
        labels={"Annual_kWh": "Electricity Use (kWh)", "Component": "Component"},
        text="Annual_kWh",
        color_discrete_map={"Total": "crimson", "Component": "steelblue"},
    )

    fig.update_traces(texttemplate="%{text:.2s}", textposition="outside")
    fig.update_layout(
        yaxis={"categoryorder": "category ascending"},
    )
    fig.show()
