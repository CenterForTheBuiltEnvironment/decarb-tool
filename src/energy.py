import numpy as np
import pandas as pd
from typing import Optional

from src.loads import StandardLoad
from src.equipment import EquipmentLibrary, Equipment
from src.emissions import StandardEmissions, EmissionsSettings

from utils.conversions import cop_h_to_cop_c
from utils.interp import interp_vector


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
            "hr_hhw_kW",  # ? HR heating hot water load
            "hr_chw_kW",  # ? HR chilled water load
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
        hr_wwhp = library.get_equipment(scen.hr_wwhp)

        hr_wwhp_cap_h = _per_unit_capacity_kw(
            hr_wwhp, temps
        )  # heating capacity [kW_th]
        hr_wwhp_cop_h = _per_unit_cop(hr_wwhp, temps)  # heating COP
        if np.isnan(hr_wwhp_cop_h).all():
            raise ValueError(f"HR WWHP '{hr_wwhp.eq_id}' lacks a COP curve.")

        # Conversion factor: how much cooling per heating capacity
        cap_h_to_cap_c = 1 - (1 / hr_wwhp_cop_h)  # same as in R
        cap_c = hr_wwhp_cap_h * cap_h_to_cap_c  # cooling capacity from heating capacity
        cop_c = cop_h_to_cop_c(hr_wwhp_cop_h)  # convert heating COP → cooling COP

        # Capacity limits
        max_cap_h = np.nanmax(
            hr_wwhp_cap_h
        )  # max heating capacity required in timeframe
        min_cap_h = np.nanmin(
            hr_wwhp_cap_h
        )  # min heating capacity required in timeframe

        # Least-waste-heat point (max COP) for HR
        idx_best = np.nanargmax(
            hr_wwhp_cop_h
        )  # index of maximum heating COP (smallest fraction of recovered heat wasted)
        least_waste_heat_factor = cap_h_to_cap_c[idx_best]

        # Simultaneous load potential (using least-waste-heat factor)
        simult_h = np.minimum(
            df["hhw_rem_kW"].to_numpy(),
            df["chw_rem_kW"].to_numpy() / least_waste_heat_factor,
        )

        # Actual heating served (within capacity limits)
        hr_hhw = np.where(
            np.minimum(max_cap_h, simult_h) > min_cap_h,
            np.minimum(max_cap_h, simult_h),
            0.0,
        )

        # Interpolate COP at part load
        hr_cop_h = interp_vector(hr_wwhp_cap_h, hr_wwhp_cop_h, hr_hhw)

        # Cooling served derived from heating & COP
        hr_chw = np.where(hr_cop_h > 0, hr_hhw * (1 - (1 / hr_cop_h)), 0.0)  # same as R

        # Electricity use
        elec_hr = np.where(hr_cop_h > 0, hr_hhw / hr_cop_h, 0.0)

        # Apply results
        df["hr_hhw_kW"] = hr_hhw
        df["hr_chw_kW"] = hr_chw
        df["hr_cop_h"] = hr_cop_h
        df["elec_hr_kWh"] = elec_hr
        df["elec_kWh"] += elec_hr
        df["hhw_rem_kW"] -= hr_hhw
        df["chw_rem_kW"] -= hr_chw

    # =========================
    # Phase 2 – AWHP Heating
    # =========================
    if scen.awhp_h:
        awhp_h = library.get_equipment(scen.awhp_h)
        awhp_cap_h = _per_unit_capacity_kw(awhp_h, temps)
        awhp_cop_h = _per_unit_cop(awhp_h, temps)
        if np.isnan(awhp_cop_h).all():
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
                    np.array([0.0]),  # fall back / reference capacity
                )[0]
            elif awhp_h.capacity_kw:
                cap_ref = float(awhp_h.capacity_kw)
            else:
                raise ValueError(f"AWHP '{awhp_h.eq_id}' lacks a capacity reference.")
            num_awhp_h = (
                int(np.ceil((peak_hhw_kW * sizing) / cap_ref)) if cap_ref > 0 else 0
            )
        else:
            num_awhp_h = int(np.ceil(sizing))

        num_awhp_h = max(num_awhp_h, 0)

        cap_total_h_kW = awhp_cap_h * num_awhp_h
        served_h_kW = np.minimum(df["hhw_rem_kW"].to_numpy(), cap_total_h_kW)
        elec_h_kWh = served_h_kW / awhp_cop_h

        df["awhp_hhw_kW"] = served_h_kW
        df["awhp_cap_h_kW"] = cap_total_h_kW
        df["awhp_cop_h"] = awhp_cop_h
        df["elec_awhp_h_kWh"] = elec_h_kWh
        df["elec_kWh"] += elec_h_kWh
        df["hhw_rem_kW"] -= served_h_kW
        df["awhp_num_h"] = float(num_awhp_h)

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
        awhp_cap_c = _per_unit_capacity_kw(awhp_c, temps)
        awhp_cop_c = _per_unit_cop(awhp_c, temps)
        if np.isnan(awhp_cop_c).all():
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
            awhp_num_c = (
                int(np.ceil((peak_chw_kW * sizing) / cap_ref)) if cap_ref > 0 else 0
            )
        else:
            awhp_num_c = int(np.ceil(sizing))

        awhp_num_c = max(awhp_num_c, 0)

        cap_total_c_kW = awhp_cap_c * awhp_num_c
        served_c_kW = np.minimum(df["chw_rem_kW"].to_numpy(), cap_total_c_kW)
        elec_c_kWh = served_c_kW / awhp_cop_c

        df["awhp_chw_kW"] = served_c_kW
        df["awhp_cap_c_kW"] = cap_total_c_kW
        df["awhp_cop_c"] = awhp_cop_c
        df["elec_awhp_c_kWh"] = elec_c_kWh
        df["elec_kWh"] += elec_c_kWh
        df["chw_rem_kW"] -= served_c_kW
        df["awhp_num_c"] = float(awhp_num_c)

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

        df = df.round(2)

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
    df_loads: pd.DataFrame,
    emissions: StandardEmissions,
    settings: EmissionsSettings,
    gas_emissions_rate: float = 180_000,  # gCO2e/kWh (example default)
    annual_refrig_leakage: float = 0.02,  # fraction per year
    shortrun_weighting: float = 0.5,  # between 0 and 1
) -> pd.DataFrame:
    """
    Convert site energy data (from loads_to_site) into source emissions
    using StandardEmissions data and user EmissionsSettings.

    Parameters
    ----------
    df_loads : DataFrame
        Hourly site load data with index = datetime and columns:
          - elec [kWh]
          - gas [kWh] (optional)
          - total_refrig_emissions_inventory [kgCO₂e] (optional)

    emissions : StandardEmissions
        Canonical emissions dataset, already filtered to requested scenario/region.

    settings : EmissionsSettings
        User settings with years, emission_type, etc.

    gas_emissions_rate : float
        Default gCO₂e/kWh for gas.

    annual_refrig_leakage : float
        Annual refrigerant leakage fraction.

    shortrun_weighting : float
        Weighting factor for SR vs LR marginal emissions.

    Returns
    -------
    DataFrame
        Loads dataframe expanded across all requested emissions years,
        with added columns:
          - emission_year
          - elec_emissions_rate [g/kWh]
          - elec_emissions [kgCO₂e]
          - gas_emissions [kgCO₂e]
          - total_refrig_emissions [kgCO₂e]
    """
    results = []

    # extract month/hour from loads
    base = df_loads.copy()
    base["month"] = base.index.month
    base["hour"] = base.index.hour

    for year in settings.emissions.years:
        df_year = emissions.slice_year(year).copy()

        # collapse emissions to month-hour averages
        df_year["month"] = df_year.index.month
        df_year["hour"] = df_year.index.hour
        group_cols = ["month", "hour"]

        if settings.emissions.emission_type == "Combustion only":
            df_year["elec_emissions_rate"] = (
                df_year["lrmer_co2e_c"] * (1 - shortrun_weighting)
                + df_year["srmer_co2e_c"] * shortrun_weighting
            )
        elif settings.emissions.emission_type == "Includes pre-combustion":
            df_year["elec_emissions_rate"] = (
                df_year["lrmer_co2e_c"] + df_year["lrmer_co2e_p"]
            ) * (1 - shortrun_weighting) + (
                df_year["srmer_co2e_c"] + df_year["srmer_co2e_p"]
            ) * shortrun_weighting
        else:
            raise ValueError(
                f"Invalid emissions_type: {settings.emissions.emission_type}"
            )

        df_em = df_year.groupby(group_cols)["elec_emissions_rate"].mean().reset_index()

        # expand loads with this year's emissions
        merged = base.merge(df_em, on=["month", "hour"], how="left")
        merged["emission_year"] = year

        # electricity emissions
        merged["elec_emissions"] = (
            merged["elec"] * merged["elec_emissions_rate"] / 1_000_000
        )

        # gas emissions
        if "gas" in merged.columns:
            merged["gas_emissions"] = gas_emissions_rate * merged["gas"] / 1_000_000
        else:
            merged["gas_emissions"] = 0.0

        # refrigerant emissions
        if "total_refrig_emissions_inventory" in merged.columns:
            merged["total_refrig_emissions"] = (
                merged["total_refrig_emissions_inventory"]
                * annual_refrig_leakage
                / 8760
            )
        else:
            merged["total_refrig_emissions"] = 0.0

        results.append(merged)

    return pd.concat(results, ignore_index=True)
