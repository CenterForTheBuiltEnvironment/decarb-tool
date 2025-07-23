import numpy as np
import pandas as pd
from utils.interp import interp1_zero


#! remove later
# Mock data for HR WWHP performance curves

hr_wwhp_curves = pd.DataFrame(
    {
        "model": ["GenericHRWWHP"] * 5,
        "oa_t": [0, 5, 10, 15, 20],
        "capacity": [1000, 1200, 1400, 1500, 1600],
        "cop": [2.5, 2.7, 3.0, 3.2, 3.3],
    }
)

awhp_curves = pd.DataFrame(
    {
        "model": ["GenericAWHP"] * 6,
        "oa_t": [0, 5, 10, 15, 20, 35],
        "capacity": [500, 600, 700, 750, 800, 850],  # Watts
        "cop": [2.0, 2.5, 3.0, 3.2, 3.3, 3.4],
    }
)

boilers = pd.DataFrame({"model": ["GenericBoiler"], "eff": [0.85]})


def loads_to_site_energy(
    equip_scenario: pd.Series, df: pd.DataFrame, detail: bool = True
) -> pd.DataFrame:
    """
    Convert building heating and cooling loads into site energy consumption
    (electricity and gas) based on a specific equipment scenario.

    Parameters
    ----------
    equip_scenario : pd.Series
        A single-row equipment scenario containing keys such as:
            - 'hr_wwhp': str or None
            - 'awhp_h': str or None
            - 'awhp_c': str or None
            - 'awhp_sizing': float or int
            - 'boiler': str or None
            - 'chiller_cop': float (optional)
        This series defines which technologies are active and how they should operate.

    df : pd.DataFrame
        Hourly time-series DataFrame with at least the following columns:
            - 'datetime': datetime64[ns]
            - 'hhw': float, heating hot water load [kWh]
            - 'chw': float, chilled water load [kWh]
            - 'oa_t': float, outdoor air temperature [°C]

    detail : bool, default=True
        If True, adds intermediate outputs to the returned DataFrame (e.g.,
        load served by each technology, COPs, capacity). Set to False to
        return only energy use columns.

    Returns
    -------
    df : pd.DataFrame
        A copy of the input DataFrame with added columns:
            - 'elec': total site electricity use [kWh]
            - 'gas': total site gas use [kWh]
            - Various optional columns depending on technologies present:
                - 'elec_hr', 'elec_awhp_h', 'elec_awhp_c', 'elec_res', 'elec_chiller'
                - 'gas_boiler'
                - COP and capacity info for HR WWHP and AWHPs
                - Load breakdowns (e.g., 'hr_hhw', 'awhp_hhw', etc.)

    Notes
    -----
    The function follows a sequential dispatch strategy:
        1. Heat Recovery WWHP
        2. Air-to-Water Heat Pump for heating
        3. Boiler
        4. Electric resistance heating
        5. AWHP for cooling
        6. Electric chiller fallback

    All loads are fully served by the end of the function; no unserved load remains.

    Raises
    ------
    ValueError
        If required performance curve data or sizing parameters are missing or invalid.

    See Also
    --------
    site_to_source : Converts site energy to source emissions using grid/marginal data.
    """

    s = equip_scenario.copy()

    df = df.copy()

    # Initialize dataframe with required columns
    df = df.assign(
        hhw_remainder=df["hhw"],
        chw_remainder=df["chw"],
        hr_hhw=np.nan,
        hr_chw=np.nan,
        simult_h=np.nan,
        hr_cop_h=np.nan,
        awhp_num=np.nan,
        awhp_hhw=np.nan,
        awhp_cop_h=np.nan,
        awhp_cap_h=np.nan,
        elec=0.0,
        elec_hr=np.nan,
        elec_awhp_h=np.nan,
        elec_awhp_c=np.nan,
        elec_res=np.nan,
        gas=0.0,
    )

    # ---- Phase 1: Heat Recovery WWHP ----
    # Checks if the scenario includes a hr_wwhp.
    # If yes:
    #       - Pulls its performance curve (capacity and COP).
    #       - Calculates how much simultaneous heating/cooling is happening.
    #       - Allocates the minimum of the simultaneous load and the unit capacity.
    #       - Computes electricity use from load / COP.

    if pd.notnull(s.get("hr_wwhp")):
        model_name = s["hr_wwhp"]

        # Filter the performance curve for the selected model
        hr_curve = hr_wwhp_curves[hr_wwhp_curves["model"] == model_name]

        if hr_curve.empty:
            raise ValueError(f"No curve data found for HR WWHP model: {model_name}")

        # Interpolate capacity and COP as a function of outdoor air temperature
        df["hr_cap"] = interp1_zero(hr_curve["oa_t"], hr_curve["capacity"], df["oa_t"])
        df["hr_cop"] = interp1_zero(hr_curve["oa_t"], hr_curve["cop"], df["oa_t"])

        # Simultaneous load is min of available hhw and chw loads
        df["simult"] = np.minimum(df["hhw"], df["chw"])

        # Limit simultaneous load by available unit capacity
        df["simult_served"] = np.minimum(df["simult"], df["hr_cap"])

        # Assign heating and cooling served
        df["hr_hhw"] = df["simult_served"]
        df["hr_chw"] = df["simult_served"]
        df["hr_cop_h"] = df["hr_cop"]  # save for output
        df["elec_hr"] = df["simult_served"] / df["hr_cop"]
        df["elec"] += df["elec_hr"]

        # Subtract load served by this unit from remainder
        df["hhw_remainder"] -= df["hr_hhw"]
        df["chw_remainder"] -= df["hr_chw"]

    # ---- Phase 2: AWHP Heating ----
    # Checks if the scenario includes a awhp_h.
    # If yes:
    #   - Interpolates per-unit capacity and COP vs outdoor air temperature for selected AWHP model.
    #   - Sizes the number of AWHP units based on:
    #       - Either a fixed number (awhp_sizing is integer).
    #       - Or based on load (e.g., enough units to cover a % of peak heating load).
    #   - Serves as much remaining HHW load as possible, up to combined capacity.
    #   - Calculates electric use: load served ÷ COP

    if pd.notnull(s.get("awhp_h")):
        model_name = s["awhp_h"]
        awhp_curve = awhp_curves[awhp_curves["model"] == model_name]

        if awhp_curve.empty:
            raise ValueError(f"No curve data found for AWHP model: {model_name}")

        # Interpolate per-unit capacity and COP vs OA temperature
        df["awhp_cap_unit"] = interp1_zero(
            awhp_curve["oa_t"], awhp_curve["capacity"], df["oa_t"]
        )
        df["awhp_cop_h"] = interp1_zero(
            awhp_curve["oa_t"], awhp_curve["cop"], df["oa_t"]
        )

        # Determine number of AWHP units
        sizing = s["awhp_sizing"]

        if pd.isna(sizing):
            raise ValueError("awhp_sizing must be provided when awhp_h is set.")

        if sizing < 1:
            # Size based on % of peak load (e.g., 0.75 means 75% of peak HHW)
            hhw_peak = df["hhw"].max()
            single_cap_ref = interp1_zero(
                awhp_curve["oa_t"], awhp_curve["capacity"], [0]
            )[
                0
            ]  # conservative (cold)
            num_units = int(np.ceil((hhw_peak * sizing) / single_cap_ref))
        else:
            # Assume user specified number of units directly
            num_units = int(sizing)

        df["awhp_num"] = num_units
        df["awhp_cap_h"] = df["awhp_cap_unit"] * num_units

        # Determine how much of the remaining HHW can be served
        df["awhp_hhw"] = np.minimum(df["hhw_remainder"], df["awhp_cap_h"])

        # Electric use = load / COP
        df["elec_awhp_h"] = df["awhp_hhw"] / df["awhp_cop_h"]
        df["elec"] += df["elec_awhp_h"]

        # Subtract AWHP-served load from remainder
        df["hhw_remainder"] -= df["awhp_hhw"]

    # ---- Phase 3: Boiler ----
    # Check if scnenario includes a boiler.
    # If yes:
    #   - It serves all remaining HHW load.
    #   - Its efficiency is pulled from a lookup table (boilers DataFrame).
    #   - The energy input is added to the gas column (not electricity).
    #   - Remaining HHW is set to 0.

    if pd.notnull(s.get("boiler")):
        model_name = s["boiler"]
        boiler_row = boilers[boilers["model"] == model_name]

        if boiler_row.empty:
            raise ValueError(f"No efficiency data found for boiler model: {model_name}")

        boiler_eff = boiler_row.iloc[0]["eff"]

        # All remaining HHW served by boiler
        df["boiler_hhw"] = df["hhw_remainder"]
        df["gas_boiler"] = df["boiler_hhw"] / boiler_eff

        df["gas"] += df["gas_boiler"]

        # All remaining HHW is now served
        df["hhw_remainder"] = 0.0

    # ---- Phase 4: Resistance Heating ----
    # If any HHW load remains after HR WWHP, AWHP, and boiler:
    #   - It is served by electric resistance heating.
    #   - Assumes COP = 1 (1 W of electricity per 1 W of thermal output).
    #   - Adds to elec_res and elec.

    if df["hhw_remainder"].sum() > 0:
        df["elec_res"] = df["hhw_remainder"]  # COP = 1
        df["elec"] += df["elec_res"]

    # Set remaining HHW to 0 after resistance heating
    df["hhw_remainder"] = 0.0

    # ---- Phase 5: AWHP Cooling ----
    # Checks if the scenario includes a awhp_c.
    # If yes:
    #   - Interpolates per-unit capacity and COP vs outdoor air temperature for selected AWHP cooling model.
    #   - Sizes the number of AWHP units based on:
    #       - Either a fixed number (awhp_sizing is integer).
    #       - Or based on load (e.g., enough units to cover a % of peak chilled water load).
    #   - Serves as much remaining CHW load as possible,
    #       up to combined capacity.
    #   - Calculates electric use: load served ÷ COP
    #
    # If no awhp_c is specified, we assume an electric chiller fallback.

    if pd.notnull(s.get("awhp_c")):
        model_name = s["awhp_c"]
        awhp_curve = awhp_curves[awhp_curves["model"] == model_name]

        if awhp_curve.empty:
            raise ValueError(
                f"No curve data found for AWHP cooling model: {model_name}"
            )

        # Interpolate per-unit capacity and COP
        df["awhp_cap_unit_c"] = interp1_zero(
            awhp_curve["oa_t"], awhp_curve["capacity"], df["oa_t"]
        )
        df["awhp_cop_c"] = interp1_zero(
            awhp_curve["oa_t"], awhp_curve["cop"], df["oa_t"]
        )

        # Reuse sizing from awhp_sizing
        sizing = s["awhp_sizing"]
        if pd.isna(sizing):
            raise ValueError("awhp_sizing must be provided when awhp_c is set.")

        if sizing < 1:
            # Percent of peak chilled water load
            chw_peak = df["chw"].max()
            single_cap_ref = interp1_zero(
                awhp_curve["oa_t"], awhp_curve["capacity"], [35]
            )[
                0
            ]  # conservative at hot temp

            if single_cap_ref == 0:
                raise ValueError(
                    f"AWHP cooling model '{model_name}' has zero capacity at 35°C — check awhp_curves coverage."
                )

            num_units = int(np.ceil((chw_peak * sizing) / single_cap_ref))

        df["awhp_num_c"] = num_units
        df["awhp_cap_c"] = df["awhp_cap_unit_c"] * num_units

        # Determine how much CHW can be served
        df["awhp_chw"] = np.minimum(df["chw_remainder"], df["awhp_cap_c"])

        # Electric use = load / COP
        df["elec_awhp_c"] = df["awhp_chw"] / df["awhp_cop_c"]
        df["elec"] += df["elec_awhp_c"]

        # Subtract from remainder
        df["chw_remainder"] -= df["awhp_chw"]

    # ---- Phase 6: Electric Chiller Fallback ----
    # If any CHW load remains after AWHP cooling:
    #   - It is served by an electric chiller.
    #   - Assumes a default COP of 5.0 (can be adjusted).
    #   - Adds to elec_chiller and elec.
    #   - Remaining CHW is set to 0.

    if df["chw_remainder"].sum() > 0:
        # Check if scenario specifies a chiller COP
        if "chiller_cop" in s and not pd.isna(s["chiller_cop"]):
            chiller_cop = s["chiller_cop"]
        else:
            chiller_cop = 5.0  # default COP: #? could be part of config

        # Only operate if any chw load remains
        df["chiller_chw"] = df["chw_remainder"]
        df["elec_chiller"] = df["chiller_chw"] / chiller_cop
        df["elec"] += df["elec_chiller"]

        # All CHW now served
        df["chw_remainder"] = 0.0

    return df


def site_to_source(
    df: pd.DataFrame, emissions_scenario: dict, grid_scenarios: pd.DataFrame
) -> pd.DataFrame:
    """
    Convert site energy data to source energy emissions, and estimate refrigerant-related emissions.

    Parameters
    ----------
    df : pandas.DataFrame
        Timeseries dataframe with at least the following columns:
            - datetime: datetime64[ns]
            - elec: float, electricity consumption in kWh
            - gas (optional): float, gas consumption in kWh
            - total_refrig_emissions_inventory (optional): float, refrigerant inventory in kg CO₂e

    emissions_scenario : dict
        A dictionary containing emissions scenario metadata. Expected keys:
            - em_scen_id: int, unique identifier for the emissions scenario
            - emissions_type: str, one of ["Combustion only", "Includes pre-combustion"]
            - grid_region: str, regional emissions zone (e.g., "CAISO", "PJM")
            - grid_scenario: str, grid scenario name (e.g., "Reference")
            - grid_year: int, target emissions year (e.g., 2024)
            - shortrun_weighting: float, between 0 and 1
            - gas_emissions_rate: float, gCO2e per kWh of gas energy
            - annual_refrig_leakage: float (optional), refrigerant leakage fraction per year (e.g., 0.02)

    grid_scenarios : pandas.DataFrame
        Emissions dataset with marginal emissions rates per hour and region.
        Required columns:
            - grid_region, grid_scenario, grid_year, month, hour
            - lrmer_co2e_c, srmer_co2e_c
            - lrmer_co2e_p, srmer_co2e_p (if using pre-combustion)

    Returns
    -------
    df : pandas.DataFrame
        Original dataframe with additional emissions columns:
            - em_scen_id
            - grid_region (if not already present)
            - elec_emissions_rate (gCO2e per kWh)
            - elec_emissions (kgCO2e)
            - gas_emissions (kgCO2e)
            - total_refrig_emissions (kgCO2e, optional)

    Raises
    ------
    ValueError
        If `emissions_type` is unknown or required data is missing.
    """

    # Validate types
    if not isinstance(emissions_scenario, dict):
        raise TypeError("emissions_scenario must be a dict")
    if not isinstance(df, pd.DataFrame):
        raise TypeError("df must be a pandas DataFrame")
    if not isinstance(grid_scenarios, pd.DataFrame):
        raise TypeError("grid_scenarios must be a pandas DataFrame")

    s = emissions_scenario.copy()
    df = df.copy()

    # Tag emissions scenario
    df["em_scen_id"] = s.get("em_scen_id", -1)

    # Determine grid region
    if pd.isna(s.get("grid_region")):
        if "grid_region" in df.columns:
            s["grid_region"] = df["grid_region"].iloc[0]
        else:
            s["grid_region"] = "CAISO"
    else:
        df["grid_region"] = s["grid_region"]

    # Filter grid emissions data
    grid_data = grid_scenarios[
        (grid_scenarios["grid_region"] == s["grid_region"])
        & (grid_scenarios["grid_scenario"] == s["grid_scenario"])
        & (grid_scenarios["grid_year"] == s["grid_year"])
    ].copy()

    if grid_data.empty:
        raise ValueError(
            f"No matching grid emissions data for region={s['grid_region']}, "
            f"scenario={s['grid_scenario']}, year={s['grid_year']}"
        )

    # Calculate hourly grid emissions rate [g/kWh]
    if s["emissions_type"] == "Combustion only":
        grid_data["elec_emissions_rate"] = (
            grid_data["lrmer_co2e_c"] * (1 - s["shortrun_weighting"])
            + grid_data["srmer_co2e_c"] * s["shortrun_weighting"]
        )
    elif s["emissions_type"] == "Includes pre-combustion":
        grid_data["elec_emissions_rate"] = (
            grid_data["lrmer_co2e_c"] + grid_data["lrmer_co2e_p"]
        ) * (1 - s["shortrun_weighting"]) + (
            grid_data["srmer_co2e_c"] + grid_data["srmer_co2e_p"]
        ) * s[
            "shortrun_weighting"
        ]
    else:
        raise ValueError(f"Invalid emissions_type: {s['emissions_type']}")

    # Add hour and month to join on
    df["month"] = df["datetime"].dt.month
    df["hour"] = df["datetime"].dt.hour

    # Join emissions rate
    df = df.merge(
        grid_data[["month", "hour", "elec_emissions_rate"]],
        on=["month", "hour"],
        how="left",
    )
    df.drop(columns=["month", "hour"], inplace=True)

    # Calculate electricity emissions (kg CO₂e)
    df["elec_emissions"] = df["elec"] * df["elec_emissions_rate"] / 1_000_000

    # Calculate gas emissions (kg CO₂e)
    if "gas" in df.columns:
        df["gas_emissions"] = s["gas_emissions_rate"] * df["gas"] / 1_000_000
    else:
        df["gas_emissions"] = 0.0

    # Refrigerant emissions
    if (
        "total_refrig_emissions_inventory" in df.columns
        and "annual_refrig_leakage" in s
    ):
        df["total_refrig_emissions"] = (
            df["total_refrig_emissions_inventory"] * s["annual_refrig_leakage"] / 8760
        )
    else:
        df["total_refrig_emissions"] = 0.0

    return df
