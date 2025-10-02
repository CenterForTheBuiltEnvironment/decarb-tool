import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from utils.units import unit_map


def apply_standard_layout(fig, subtitle_text=None):
    """Apply standard layout settings to a Plotly figure."""
    annotations = []
    if subtitle_text:
        annotations.append(
            go.layout.Annotation(
                x=0,
                y=-0.4,
                xref="paper",
                yref="paper",
                text=subtitle_text,
                showarrow=False,
                xanchor="left",
                yanchor="bottom",
                font=dict(size=16, color="gray"),
            )
        )

    fig.update_layout(annotations=annotations, margin=dict(b=120, pad=10))
    return fig


def plot_total_emissions_bar(
    df, equipment_scenarios, emission_scenarios, unit_mode="SI"
):

    variable_type = "emissions"

    metadata_cols = ["scenario_id", "em_scen_id"]

    emission_cols = ["elec_emissions", "gas_emissions", "total_refrig_emissions"]

    all_cols = metadata_cols + emission_cols

    filtered = df[
        (df["scenario_id"].isin(equipment_scenarios))
        & (df["em_scen_id"].isin(emission_scenarios))
    ]

    df = filtered[[c for c in all_cols if c in filtered.columns]]

    conversion = unit_map[variable_type][unit_mode]

    df.loc[:, emission_cols] = df.loc[:, emission_cols].apply(conversion["func"])
    yaxis_title = conversion["label"]

    df_totals = df.groupby(["scenario_id", "em_scen_id"], as_index=False)[
        emission_cols
    ].sum()

    # Melt to long format for stacking
    df_long = df_totals.melt(
        id_vars=["scenario_id", "em_scen_id"],
        value_vars=emission_cols,
        var_name="emission_type",
        value_name="emissions",
    )

    fig = px.bar(
        df_long,
        x="scenario_id",
        y="emissions",
        color="emission_type",
        facet_col="em_scen_id",
        barmode="stack",
    )

    fig.update_layout(yaxis_title=yaxis_title)

    fig.update_xaxes(title_text="")

    fig = apply_standard_layout(fig, "Total Emissions by Equipment and Scenarios.")

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
            xaxis_title="Time",
            yaxis_title=(yaxis_title if aggfunc == "sum" else f"Average {yaxis_title}"),
            legend_title="Meter",
            template="decarb-tool-theme",
        )

        fig = apply_standard_layout(fig, "Stacked Meter Usage, aggregated over time.")

    return fig


def plot_emissions_heatmap(df, year):
    """
    Plot a heatmap of electricity emissions (elec_emissions) by hour and day of the year.
    """
    df = df[df.index.year == year].copy()
    df["hour"] = df.index.hour
    df["doy"] = df.index.dayofyear

    # Check if the 'elec_emissions' column exists
    if "elec_emissions" not in df.columns:
        raise ValueError("Missing required column: 'elec_emissions'")

    # Ensure the index is datetime
    if not pd.api.types.is_datetime64_any_dtype(df.index):
        raise ValueError("The index must be a datetime type.")

    # Extract hour and day of year
    df["hour"] = df.index.hour
    df["doy"] = df.index.dayofyear

    # Pivot to 2D array (hour x day of year)
    heatmap_data = df.pivot_table(
        index="hour", columns="doy", values="elec_emissions", aggfunc="mean"
    )

    # Create the heatmap plot
    fig = go.Figure(
        data=go.Heatmap(
            z=heatmap_data.values,
            x=heatmap_data.columns,
            y=heatmap_data.index,
            colorscale="YlGnBu",
            colorbar=dict(title="Electricity Emissions (kg CO₂)"),
            hovertemplate="Day of Year: %{x}<br>Hour: %{y}<br>Emissions: %{z:.2f} kg CO₂<extra></extra>",
            zsmooth="best",
        )
    )

    fig.update_layout(
        title="Electricity Emissions Heatmap (Hour of Day vs. Day of Year)",
        xaxis_title="Day of Year",
        yaxis_title="Hour of Day",
    )

    fig.show()


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
        yaxis={"categoryorder": "total ascending"},
    )
    fig.show()


def plot_energy_and_emissions(df, equipment_scenarios, emission_scenarios):
    """
    Plot annual totals for energy (left) and emissions (right) by scenario.
    No legend or annotations; scenario/category info is in hover tooltips.
    """

    if "scenario_id" not in df.columns:
        raise ValueError("DataFrame must include a 'scenario_id' column.")

    elec_components = [
        "elec_hr_Wh",
        "elec_awhp_h_Wh",
        "elec_awhp_c_Wh",
        "elec_res_Wh",
        "elec_chiller_Wh",
    ]
    gas_components = ["gas_boiler_Wh"]

    color_map_energy = {"Heating": "red", "Cooling": "blue", "Gas": "orange"}
    color_map_emissions = {
        "Electricity": "black",
        "Gas": "yellow",
        "Refrigerant": "green",
    }

    df = df[
        (df["scenario_id"].isin(equipment_scenarios))
        & (df["em_scen_id"].isin(emission_scenarios))
    ]

    scenarios = df["scenario_id"].unique()
    n_scen = len(scenarios)
    opacities = np.linspace(0.7, 0.3, n_scen)

    fig = make_subplots(rows=1, cols=2, column_widths=[0.5, 0.5])

    # --- LOOP OVER SCENARIOS ---
    for i, scen in enumerate(scenarios):
        df_s = df[df["scenario_id"] == scen]

        # --- ENERGY TOTALS ---
        elec_heat = (
            df_s[["elec_hr_Wh", "elec_awhp_h_Wh", "elec_res_Wh"]].sum().sum() / 1000
        )
        elec_cool = df_s[["elec_awhp_c_Wh", "elec_chiller_Wh"]].sum().sum() / 1000
        gas_heat = df_s["gas_boiler_Wh"].sum() / 1000

        totals_energy = [
            {"Type": "Gas", "Category": "Heating", "kWh": gas_heat},
            {"Type": "Electricity", "Category": "Heating", "kWh": elec_heat},
            {"Type": "Electricity", "Category": "Cooling", "kWh": elec_cool},
        ]

        for s in totals_energy:
            fig.add_trace(
                go.Bar(
                    x=[s["Type"]],
                    y=[s["kWh"]],
                    width=0.2,
                    marker=dict(
                        color=color_map_energy[s["Category"]],
                        opacity=opacities[i],
                    ),
                    hovertemplate=(
                        f"Scenario: {scen}<br>"
                        f"Type: {s['Type']}<br>"
                        f"Category: {s['Category']}<br>"
                        f"kWh: {s['kWh']:.0f}<extra></extra>"
                    ),
                    showlegend=False,
                ),
                row=1,
                col=1,
            )

        # --- EMISSIONS TOTALS ---
        elec_emissions = df_s["elec_emissions"].sum().sum()
        gas_emissions = df_s["gas_emissions"].sum().sum()
        refrigerant_emissions = df_s["total_refrig_emissions"].sum().sum()

        totals_emissions = [
            {"Type": "Gas", "Category": "Emissions", "Value": gas_emissions},
            {"Type": "Electricity", "Category": "Emissions", "Value": elec_emissions},
            {
                "Type": "Refrigerant",
                "Category": "Emissions",
                "Value": refrigerant_emissions,
            },
        ]

        for s in totals_emissions:
            fig.add_trace(
                go.Bar(
                    x=[s["Type"]],
                    y=[s["Value"]],
                    width=0.2,
                    marker=dict(
                        color=color_map_emissions[s["Type"]],
                        opacity=opacities[i],
                    ),
                    hovertemplate=(
                        f"Scenario: {scen}<br>"
                        f"Type: {s['Type']}<br>"
                        f"Value: {s['Value']:.1f} kgCO₂<extra></extra>"
                    ),
                    showlegend=False,
                ),
                row=1,
                col=2,
            )

    fig.update_layout(
        xaxis=dict(domain=[0, 0.3]),
        xaxis2=dict(domain=[0.5, 1.0]),
    )

    fig.update_yaxes(title_text="kWh", row=1, col=1)
    fig.update_yaxes(title_text="Emissions [kgCO₂]", row=1, col=2)

    fig = apply_standard_layout(fig, "Annual Energy & Emissions by Scenario")

    return fig
