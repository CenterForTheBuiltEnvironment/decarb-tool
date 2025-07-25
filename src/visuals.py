import pandas as pd
import plotly.express as px
import plotly.graph_objects as go


def plot_electricity_breakdown(df):
    """
    Plot a bar chart of electricity components, highlighting the total 'elec' in a different color.

    Parameters:
    -----------
    df : pandas.DataFrame
        DataFrame containing hourly or aggregate electricity use data.

    Required Columns:
    -----------------
    ['elec_hr', 'elec_awhp_h', 'elec_awhp_c', 'elec_res', 'elec_chiller', 'elec']
    """

    # Define required components
    elec_components = [
        "elec_hr",
        "elec_awhp_h",
        "elec_awhp_c",
        "elec_res",
        "elec_chiller",
    ]
    required_columns = elec_components + ["elec"]

    # Check for missing columns
    missing = [col for col in required_columns if col not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns in DataFrame: {missing}")

    # Compute sums
    summary = df[required_columns].sum().sort_values(ascending=False)

    # Prepare DataFrame for Plotly
    summary_df = summary.reset_index()
    summary_df.columns = ["Component", "Annual_kWh"]
    summary_df["Type"] = summary_df["Component"].apply(
        lambda x: "Total" if x == "elec" else "Component"
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
    fig.update_layout(yaxis={"categoryorder": "total ascending"})
    fig.show()


def plot_electricity_emissions_heatmap(df):
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
        )
    )

    fig.update_layout(
        title="Electricity Emissions Heatmap (Hour of Day vs. Day of Year)",
        xaxis_title="Day of Year",
        yaxis_title="Hour of Day",
        yaxis=dict(autorange="reversed"),  # Reverse the hour axis so 0 is at the top
    )

    fig.show()
