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
    Convert heating/cooling loads into site energy consumption based on equipment scenario.
    """
    s = equip_scenario.copy()

    df = df.copy()

    # Initialize new columns
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
    #     If awhp_h is specified in the scenario, we simulate:

    #   1. Interpolating COP & capacity vs outdoor air temperature for the selected AWHP model.
    #   2. Sizing the number of AWHP units:
    #      - Either fixed (awhp_sizing is a number like 2 or 3)
    #      - Or based on load (e.g., enough units to cover a % of peak heating load).
    #   3. Serving as much remaining HHW load as possible, up to combined capacity.
    #   4. Calculating electric use: load served ÷ COP.

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

        if sizing < 10:
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
    # If a boiler is specified in the scenario:

    # - It is assumed to have unlimited capacity (can serve all remaining HHW).
    # - Its efficiency is pulled from a lookup table (boilers DataFrame).
    # - The energy input is added to the gas column (not electricity).

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
    # Trigger: Only runs if hhw_remainder > 0 after HR WWHP, AWHP, and boiler.
    # - Assumption: COP = 1 → 1 W of electricity per 1 W of thermal output.
    # - Result:
    #       - Remaining hhw_remainder is fully served.
    #       - Adds to elec_res and elec.

    df["elec_res"] = df["hhw_remainder"]  # COP = 1
    df["elec"] += df["elec_res"]

    # All HHW is now served
    df["hhw_remainder"] = 0.0

    # ---- Phase 5: AWHP Cooling ----
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

        if sizing < 10:
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
    if "chiller_cop" in s and not pd.isna(s["chiller_cop"]):
        chiller_cop = s["chiller_cop"]
    else:
        chiller_cop = 4.0  # default COP

    # Only operate if any chw load remains
    df["chiller_chw"] = df["chw_remainder"]
    df["elec_chiller"] = df["chiller_chw"] / chiller_cop
    df["elec"] += df["elec_chiller"]

    # All CHW now served
    df["chw_remainder"] = 0.0

    return df
