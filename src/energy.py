import numpy as np
import pandas as pd
from typing import Optional

from src.loads import StandardLoad
from src.equipment import EquipmentLibrary, Equipment

from utils.interp import interp_vector


# def _interp_vector(xp, fp, x):
#     """Robust 1D interpolation (left/right clamp)."""
#     xp = np.asarray(xp, dtype=float)
#     fp = np.asarray(fp, dtype=float)
#     x = np.asarray(x, dtype=float)
#     return np.interp(x, xp, fp, left=fp[0], right=fp[-1])


def _per_unit_capacity_kw(e: Equipment, t_out: np.ndarray) -> np.ndarray:
    """Per-unit thermal capacity [kW] vs outdoor temperature."""
    if e.performance and e.performance.cap_curve:
        return interp_vector(
            e.performance.cap_curve.t_out_C, e.performance.cap_curve.capacity_kw, t_out
        )
    # fallback to fixed capacity if provided
    if e.capacity_kw is not None:
        return np.full_like(t_out, fill_value=float(e.capacity_kw), dtype=float)
    raise ValueError(
        f"Equipment '{e.eq_id}' has no capacity info (cap_curve or capacity_kw)."
    )


def _per_unit_cop(e: Equipment, t_out: np.ndarray) -> np.ndarray:
    """Per-unit COP vs outdoor temperature."""
    # If the device has a COP curve, use it
    if e.performance and e.performance.cop_curve:
        return interp_vector(
            e.performance.cop_curve.t_out_C, e.performance.cop_curve.cop, t_out
        )
    # Some devices (boiler/resistance) use efficiency instead (not COP).
    # We'll not use COP for them here.
    return np.full_like(t_out, fill_value=np.nan, dtype=float)


def _constant_efficiency(e: Equipment) -> Optional[float]:
    if e.performance and e.performance.efficiency is not None:
        return float(e.performance.efficiency)
    return None


def loads_to_site_energy(
    load: StandardLoad,
    library: EquipmentLibrary,
    scenario_id: str,
    detail: bool = True,
) -> pd.DataFrame:
    """
    Convert hourly heating/cooling loads to site energy (kWh_electricity and kWh_gas)
    using the selected equipment scenario from the EquipmentLibrary.

    Parameters
    ----------
    load : StandardLoad
        Canonical loads wrapper (index = timestamp; cols: t_out_C, heating_W, cooling_W).
    library : EquipmentLibrary
        Validated equipment + scenarios.
    scenario_id : str
        Which scenario in the library to use.
    detail : bool
        If True, include per-technology breakdown columns.

    Returns
    -------
    pd.DataFrame
        DataFrame indexed by timestamp with totals and (optionally) detail columns.
        Key outputs:
          - elec_kWh: total site electricity per hour
          - gas_kWh: total site gas (fuel) per hour
    """

    # ---- pull inputs ----
    df = load.df.copy()  # index = timestamp
    temps = df["t_out_C"].to_numpy()
    # Convert thermal loads from W → kW (per hour this equals kWh_th)
    df["hhw_kW"] = df["heating_W"] / 1000.0
    df["chw_kW"] = df["cooling_W"] / 1000.0

    # Remainders in kW_th
    df["hhw_rem_kW"] = df["hhw_kW"].copy()
    df["chw_rem_kW"] = df["chw_kW"].copy()

    # Outputs
    df["elec_kWh"] = 0.0
    df["gas_kWh"] = 0.0

    # detail columns (create lazily; safer to pre-create as NaN for clarity)
    if detail:
        for c in [
            "hr_hhw_kW",
            "hr_chw_kW",
            "elec_hr_kWh",
            "hr_cop",
            "awhp_hhw_kW",
            "awhp_cap_h_kW",
            "elec_awhp_h_kWh",
            "awhp_cop_h",
            "boiler_hhw_kW",
            "gas_boiler_kWh",
            "boiler_eff",
            "res_hhw_kW",
            "elec_res_kWh",
            "awhp_chw_kW",
            "awhp_cap_c_kW",
            "elec_awhp_c_kWh",
            "awhp_cop_c",
            "chiller_chw_kW",
            "elec_chiller_kWh",
            "chiller_cop",
            "awhp_num_h",
            "awhp_num_c",
        ]:
            df[c] = np.nan

    # ---- scenario ----
    scen = library.get_scenario(scenario_id)

    # =========================
    # Phase 1 – HR WWHP (optional)
    # =========================
    if scen.hr_wwhp:
        hr = library.get_equipment(scen.hr_wwhp)
        # 1 unit assumption (extend later if you add hr sizing)
        hr_cap_unit_kW = _per_unit_capacity_kw(hr, temps)  # kW_th per unit
        hr_cop = _per_unit_cop(hr, temps)  # may be NaN if missing

        # If no COP curve, we cannot compute electric consumption
        if np.isnan(hr_cop).all():
            raise ValueError(f"HR WWHP '{hr.eq_id}' lacks a COP curve.")

        # simultaneous service (limited by capacity and both remainders)
        simult_kW = np.minimum(df["hhw_rem_kW"].to_numpy(), df["chw_rem_kW"].to_numpy())
        served_kW = np.minimum(simult_kW, hr_cap_unit_kW)  # 1 unit

        elec_kWh = served_kW / hr_cop

        # apply
        df["hr_hhw_kW"] = served_kW
        df["hr_chw_kW"] = served_kW
        df["hr_cop"] = hr_cop
        df["elec_hr_kWh"] = elec_kWh
        df["elec_kWh"] += elec_kWh
        df["hhw_rem_kW"] -= served_kW
        df["chw_rem_kW"] -= served_kW

    # =========================
    # Phase 2 – AWHP Heating
    # =========================
    if scen.awhp_h:
        awhp_h = library.get_equipment(scen.awhp_h)
        cap_unit_h_kW = _per_unit_capacity_kw(awhp_h, temps)
        cop_h = _per_unit_cop(awhp_h, temps)
        if np.isnan(cop_h).all():
            raise ValueError(f"AWHP heating '{awhp_h.eq_id}' lacks a COP curve.")

        # Determine number of units
        sizing = float(scen.awhp_sizing)
        if sizing < 1.0:
            # fraction of peak HHW at a conservative temperature (e.g., 0°C)
            peak_hhw_kW = float(df["hhw_kW"].max())
            if awhp_h.performance and awhp_h.performance.cap_curve:
                cap_ref = interp_vector(
                    awhp_h.performance.cap_curve.t_out_C,
                    awhp_h.performance.cap_curve.capacity_kw,
                    np.array([0.0]),
                )[0]
            elif awhp_h.capacity_kw:
                cap_ref = float(awhp_h.capacity_kw)
            else:
                raise ValueError(f"AWHP '{awhp_h.eq_id}' lacks a capacity reference.")
            num_h = int(np.ceil((peak_hhw_kW * sizing) / cap_ref)) if cap_ref > 0 else 0
        else:
            num_h = int(np.ceil(sizing))

        num_h = max(num_h, 0)

        cap_total_h_kW = cap_unit_h_kW * num_h
        served_h_kW = np.minimum(df["hhw_rem_kW"].to_numpy(), cap_total_h_kW)
        elec_h_kWh = served_h_kW / cop_h

        df["awhp_hhw_kW"] = served_h_kW
        df["awhp_cap_h_kW"] = cap_total_h_kW
        df["awhp_cop_h"] = cop_h
        df["elec_awhp_h_kWh"] = elec_h_kWh
        df["elec_kWh"] += elec_h_kWh
        df["hhw_rem_kW"] -= served_h_kW
        df["awhp_num_h"] = float(num_h)

    # =========================
    # Phase 3 – Boiler (optional)
    # =========================
    if scen.boiler:
        blr = library.get_equipment(scen.boiler)
        eff = _constant_efficiency(blr)
        if eff is None or eff <= 0:
            raise ValueError(f"Boiler '{blr.eq_id}' requires a positive 'efficiency'.")

        boiler_served_kW = df["hhw_rem_kW"].to_numpy()
        gas_kWh = boiler_served_kW / eff

        df["boiler_hhw_kW"] = boiler_served_kW
        df["gas_boiler_kWh"] = gas_kWh
        df["boiler_eff"] = eff
        df["gas_kWh"] += gas_kWh
        df["hhw_rem_kW"] = 0.0

    # =========================
    # Phase 4 – Electric resistance (if heating remains)
    # =========================
    remaining_h_kW = df["hhw_rem_kW"].to_numpy()
    if np.any(remaining_h_kW > 1e-9):
        elec_res_kWh = remaining_h_kW  # COP = 1
        df["res_hhw_kW"] = remaining_h_kW
        df["elec_res_kWh"] = elec_res_kWh
        df["elec_kWh"] += elec_res_kWh
        df["hhw_rem_kW"] = 0.0

    # =========================
    # Phase 5 – AWHP Cooling
    # =========================
    if scen.awhp_c:
        awhp_c = library.get_equipment(scen.awhp_c)
        cap_unit_c_kW = _per_unit_capacity_kw(awhp_c, temps)
        cop_c = _per_unit_cop(awhp_c, temps)
        if np.isnan(cop_c).all():
            raise ValueError(f"AWHP cooling '{awhp_c.eq_id}' lacks a COP curve.")

        # Use same sizing logic as heating (from awhp_sizing)
        sizing = float(scen.awhp_sizing)
        if sizing < 1.0:
            peak_chw_kW = float(df["chw_kW"].max())
            if awhp_c.performance and awhp_c.performance.cap_curve:
                cap_ref = interp_vector(
                    awhp_c.performance.cap_curve.t_out_C,
                    awhp_c.performance.cap_curve.capacity_kw,
                    np.array([35.0]),  # conservative hot condition
                )[0]
            elif awhp_c.capacity_kw:
                cap_ref = float(awhp_c.capacity_kw)
            else:
                raise ValueError(f"AWHP '{awhp_c.eq_id}' lacks a capacity reference.")
            num_c = int(np.ceil((peak_chw_kW * sizing) / cap_ref)) if cap_ref > 0 else 0
        else:
            num_c = int(np.ceil(sizing))

        num_c = max(num_c, 0)

        cap_total_c_kW = cap_unit_c_kW * num_c
        served_c_kW = np.minimum(df["chw_rem_kW"].to_numpy(), cap_total_c_kW)
        elec_c_kWh = served_c_kW / cop_c

        df["awhp_chw_kW"] = served_c_kW
        df["awhp_cap_c_kW"] = cap_total_c_kW
        df["awhp_cop_c"] = cop_c
        df["elec_awhp_c_kWh"] = elec_c_kWh
        df["elec_kWh"] += elec_c_kWh
        df["chw_rem_kW"] -= served_c_kW
        df["awhp_num_c"] = float(num_c)

    # =========================
    # Phase 6 – Electric chiller fallback
    # =========================
    if df["chw_rem_kW"].sum() > 1e-9:
        chiller_cop = 5.0  # default
        if scen.chiller:
            chl = library.get_equipment(scen.chiller)
            # prefer explicit efficiency (treat as COP for chiller), otherwise try COP curve
            eff = _constant_efficiency(chl)
            if eff and eff > 0:
                chiller_cop = eff
            else:
                cop_curve = _per_unit_cop(chl, temps)  # could be array
                if not np.isnan(cop_curve).all():
                    # if a curve exists, use the hourly values
                    served_kW = df["chw_rem_kW"].to_numpy()
                    elec_kWh = served_kW / cop_curve
                    df["chiller_chw_kW"] = served_kW
                    df["elec_chiller_kWh"] = elec_kWh
                    df["elec_kWh"] += elec_kWh
                    df["chiller_cop"] = cop_curve
                    df["chw_rem_kW"] = 0.0
                    # finalize and return
                    cols = _finalize_columns(df, detail)
                    return df[cols]

        # scalar COP path
        served_kW = df["chw_rem_kW"].to_numpy()
        elec_kWh = served_kW / chiller_cop

        if detail:
            df["chiller_chw_kW"] = served_kW
            df["elec_chiller_kWh"] = elec_kWh
            df["chiller_cop"] = chiller_cop

        df["elec_kWh"] += elec_kWh
        df["chw_rem_kW"] = 0.0

    # ---- finalize ----
    cols = _finalize_columns(df, detail)
    return df[cols]


def _finalize_columns(df: pd.DataFrame, detail: bool) -> list[str]:
    """Return a clean column order for output."""
    base = ["t_out_C", "heating_W", "cooling_W", "elec_kWh", "gas_kWh"]
    if not detail:
        return base

    detail_cols = [
        "hhw_kW",
        "chw_kW",
        "hr_hhw_kW",
        "hr_chw_kW",
        "hr_cop",
        "elec_hr_kWh",
        "awhp_num_h",
        "awhp_cap_h_kW",
        "awhp_cop_h",
        "awhp_hhw_kW",
        "elec_awhp_h_kWh",
        "boiler_eff",
        "boiler_hhw_kW",
        "gas_boiler_kWh",
        "res_hhw_kW",
        "elec_res_kWh",
        "awhp_num_c",
        "awhp_cap_c_kW",
        "awhp_cop_c",
        "awhp_chw_kW",
        "elec_awhp_c_kWh",
        "chiller_cop",
        "chiller_chw_kW",
        "elec_chiller_kWh",
    ]
    # only include those that actually exist
    detail_cols = [c for c in detail_cols if c in df.columns]
    return base + detail_cols


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

    # Join emissions rate
    df = df.merge(
        grid_data[["elec_emissions_rate"]],
        left_index=True,
        right_index=True,
        how="left",
    )

    # # Convert elec from Wh to kWh
    # if "elec" in df.columns:
    #     df["elec"] = df["elec"] / 1000

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
