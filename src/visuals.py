import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots


def plot_meter_timeseries(
    df,
    year,
    scenario_id=None,
    freq="D",
    stacked=False,
    include_gas=True,
    category_orders=None,
    aggfunc="sum",
):
    """
    Plot time series data for meters (electricity, gas) with flexible aggregation.

    Parameters
    ----------
    df : pd.DataFrame
        Time series DataFrame with a DateTimeIndex and columns for meter readings.
    freq : str, default "D"
        Resampling frequency: "H"=hourly, "D"=daily, "W"=weekly, "M"=monthly.
    stacked : bool, default False
        If True, plot stacked area chart. If False, plot line chart.
    include_totals : bool, default True
        Whether to include total electricity and gas series (only applies if stacked=False).
    include_gas : bool, default True
        Whether to include gas meters in the stacked chart (only applies if stacked=True).
    category_orders : list or None, default None
        Category order for stacked chart (only applies if stacked=True).
    aggfunc : str, default "sum"
        Aggregation function to apply when resampling. Options: "sum", "mean".
    """

    df = df[df.index.year == year]
    df = df.loc[df.scenario_id == scenario_id] if scenario_id else df.copy()
    df = df.drop(columns=["scenario_id"], errors="ignore")

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
            yaxis_title=(
                "Electricity/Gas Usage [Wh]"
                if aggfunc == "sum"
                else "Average Usage [Wh]"
            ),
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

        # Filter out gas meters if requested
        if not include_gas:
            df_melt = df_melt[~df_melt["Meter"].str.contains("gas", case=False)]

        fig = px.area(
            df_melt,
            x=df_resampled.index.name or "index",
            y="Usage",
            color="Meter",
            line_group="Meter",
            category_orders={"Meter": category_orders} if category_orders else None,
            title=f"Stacked Meter Usage ({freq} Aggregation, {aggfunc})",
        )

        fig.update_traces(stackgroup="one")
        fig.update_layout(
            xaxis_title="Time",
            yaxis_title="Usage [Wh]" if aggfunc == "sum" else "Average Usage [Wh]",
            legend_title="Meter",
            template="decarb-tool-theme",
        )

    return fig


def plot_emissions_heatmap(df, year):
    """
    Plot a heatmap of electricity emissions (elec_emissions) by hour and day of the year.

    Parameters:
    -----------
    df : pandas.DataFrame
        DataFrame containing hourly electricity emissions data. Must have a datetime index.

    Required Columns:
    -----------------
    ['elec_emissions'] (and a datetime index)
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


def plot_energy_breakdown(df):
    """
    Plot a summary of energy usage by component.
    Parameters:
    -----------
    df : pandas.DataFrame
        DataFrame containing energy usage data. Must have columns for each component and total electricity and gas usage.

    Required Columns:
    -----------------
    ['elec_hr_Wh', 'elec_awhp_h_Wh', 'elec_awhp_c_Wh', 'elec_res_Wh', 'elec_chiller_Wh', 'elec_Wh', 'gas_boiler_Wh']

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

    summary = (
        df[required_columns].sum().sort_values(ascending=False) / 1000
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


def plot_energy_and_emissions(df, year):
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

    df = df[df.index.year == year]

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
        title=f"Annual Energy & Emissions by Scenario, {year}",
        barmode="group",
        # Add space between subplots
        xaxis=dict(domain=[0, 0.3]),
        xaxis2=dict(domain=[0.5, 1.0]),
    )

    fig.update_yaxes(title_text="kWh", row=1, col=1)
    fig.update_yaxes(title_text="Emissions [kgCO₂]", row=1, col=2)

    return fig
