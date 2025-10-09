import numpy as np
import pandas as pd
from typing import Optional, Union

from src.loads import StandardLoad
from src.equipment import EquipmentLibrary, Equipment
from src.emissions import StandardEmissions, get_emissions_data, EmissionScenario
from src.metadata import Metadata

from utils.units import cop_h_to_cop_c
from utils.interp import interp_vector


def _heat_recovery_plr_curve(e: Equipment) -> pd.DataFrame:
    """Heat recovery COP vs part-load ratio (PLR)."""
    if e.performance and e.performance.plr_curve:
        cap = e.performance.plr_curve.capacity_W
        cop = e.performance.plr_curve.cop
        return pd.DataFrame({"cap": cap, "cop": cop})
    raise ValueError(f"Equipment '{e.eq_id}' has no plr_curve.")


def _per_unit_capacity_W(e: Equipment, t_out: np.ndarray) -> np.ndarray:
    """Per-unit thermal capacity [W] vs outdoor temperature."""
    if e.performance and e.performance.cap_curve:
        return interp_vector(
            e.performance.cap_curve.t_out_C, e.performance.cap_curve.capacity_W, t_out
        )
    # fallback to fixed capacity if provided
    if e.capacity_W is not None:
        return np.full_like(t_out, fill_value=float(e.capacity_W), dtype=float)
    raise ValueError(
        f"Equipment '{e.eq_id}' has no capacity info (cap_curve or capacity_W)."
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
    scenario_ids: Union[str, list[str]],
    detail: bool = True,
) -> pd.DataFrame:
    """
    Convert hourly heating/cooling loads to site energy (kWh_electricity and kWh_gas)
    using the selected equipment scenarios from the EquipmentLibrary.
    """
    # --- normalize input ---
    if isinstance(scenario_ids, str):
        scenario_ids = [scenario_ids]

    results = []

    for scenario_id in scenario_ids:

        # ---- pull inputs ----
        df = load.df.copy()  # index = timestamp
        temps = df["t_out_C"].to_numpy()

        df["hhw_W"] = df["heating_W"]
        df["chw_W"] = df["cooling_W"]

        # Remainders in W_th
        df["hhw_rem_W"] = df["hhw_W"].copy()
        df["chw_rem_W"] = df["chw_W"].copy()

        # Outputs
        df["elec_Wh"] = 0.0
        df["gas_Wh"] = 0.0

        # detail columns (create lazily; safer to pre-create as NaN for clarity)
        if detail:
            for c in [
                "hr_hhw_W",  # ? HR heating hot water load
                "hr_chw_W",  # ? HR chilled water load
                "elec_hr_Wh",
                "hr_cop_h",
                "awhp_hhw_W",  # ? HR heating hot water load
                "awhp_cap_h_W",  # ? HR heating capacity
                "elec_awhp_h_Wh",  # ? HR electricity use
                "awhp_cop_h",  # ? HR COP
                "boiler_hhw_W",  # ? Boiler heating hot water load
                "gas_boiler_Wh",  # ? Boiler gas use
                "boiler_eff",  # ? Boiler efficiency
                "res_hhw_W",  # ? Resistance heating hot water load
                "elec_res_Wh",
                "awhp_chw_W",
                "awhp_cap_c_W",
                "elec_awhp_c_Wh",
                "awhp_cop_c",
                "chiller_chw_W",
                "elec_chiller_Wh",
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

            plr_curve = _heat_recovery_plr_curve(hr_wwhp)
            if plr_curve.empty:
                raise ValueError(f"HR WWHP '{hr_wwhp.eq_id}' lacks a PLR curve.")

            plr_curve = plr_curve.sort_values(by="cap", ascending=False).reset_index(
                drop=True
            )
            plr_curve["cap_h_to_cap_c"] = 1 - (
                1 / plr_curve["cop"]
            )  # conversion factor cooling capacity from heating_capacity
            plr_curve["cap_c"] = (
                plr_curve["cap"] * plr_curve["cap_h_to_cap_c"]
            )  # cooling capacity from heating capacity
            plr_curve["cop_c"] = cop_h_to_cop_c(
                plr_curve["cop"]
            )  # convert heating COP → cooling COP

            num_units = 1
            least_waste_heat = plr_curve.loc[plr_curve["cop"].idxmax()]
            max_cap_h = (
                num_units * plr_curve["cap"].max()
            )  # max heating capacity required in timeframe <- allowed by unit, timeframe not relevant
            min_cap_h = plr_curve[
                "cap"
            ].min()  # min heating capacity required in timeframe <- allowed by unit, timeframe not relevant

            # Simultaneous load potential (using least-waste-heat factor)
            simult_h = np.minimum(
                df["hhw_rem_W"].to_numpy(),
                df["chw_rem_W"].to_numpy()
                / least_waste_heat[
                    "cap_h_to_cap_c"
                ],  # amount of simultaneous load that the WWHP can actually satisfy
            )

            # Actual heating served (within capacity limits)
            hr_hhw = np.where(
                np.minimum(max_cap_h, simult_h) > min_cap_h,
                np.minimum(max_cap_h, simult_h),
                0.0,
            )

            # Interpolate COP at part load
            hr_cop_h = interp_vector(plr_curve["cap"], plr_curve["cop"], hr_hhw)

            # Cooling served derived from heating & COP
            hr_chw = np.where(
                hr_cop_h > 0, hr_hhw * (1 - (1 / hr_cop_h)), 0.0
            )  # same as R

            # Electricity use
            elec_hr = np.where(hr_cop_h > 0, hr_hhw / hr_cop_h, 0.0)

            # Apply results
            df["max_cap_h_hr_W"] = max_cap_h  #! remove
            df["min_cap_h_hr_W"] = min_cap_h  #! remove
            df["simult_h_hr_W"] = simult_h  #! remove
            df["hr_hhw_W"] = hr_hhw
            df["hr_chw_W"] = hr_chw
            df["hr_cop_h"] = hr_cop_h
            df["elec_hr_Wh"] = elec_hr
            df["elec_Wh"] += elec_hr
            df["hhw_rem_W"] -= hr_hhw
            df["chw_rem_W"] -= hr_chw

        # =========================
        # Phase 2 – AWHP Heating
        # =========================
        if scen.awhp_h:
            awhp_h = library.get_equipment(scen.awhp_h)
            awhp_cap_h = _per_unit_capacity_W(awhp_h, temps)
            awhp_cop_h = _per_unit_cop(awhp_h, temps)
            if np.isnan(awhp_cop_h).all():
                raise ValueError(f"AWHP heating '{awhp_h.eq_id}' lacks a COP curve.")

            # Determine number of units
            sizing = float(scen.awhp_sizing)
            if sizing < 1.0:
                # fraction of peak HHW at a conservative temperature (e.g., 0°C)
                peak_hhw_W = float(df["hhw_W"].max())
                if awhp_h.performance and awhp_h.performance.cap_curve:
                    cap_ref = interp_vector(
                        awhp_h.performance.cap_curve.t_out_C,
                        awhp_h.performance.cap_curve.capacity_W,
                        np.array([0.0]),  # fall back / reference capacity
                    )[0]
                elif awhp_h.capacity_W:
                    cap_ref = float(awhp_h.capacity_W)
                else:
                    raise ValueError(
                        f"AWHP '{awhp_h.eq_id}' lacks a capacity reference."
                    )
                num_awhp_h = (
                    int(np.ceil((peak_hhw_W * sizing) / cap_ref)) if cap_ref > 0 else 0
                )
            else:
                num_awhp_h = int(np.ceil(sizing))

            num_awhp_h = max(num_awhp_h, 0)

            cap_total_h_W = awhp_cap_h * num_awhp_h
            served_h_W = np.minimum(df["hhw_rem_W"].to_numpy(), cap_total_h_W)
            elec_h_Wh = served_h_W / awhp_cop_h

            df["awhp_hhw_W"] = served_h_W
            df["awhp_cap_h_W"] = cap_total_h_W
            df["awhp_cop_h"] = awhp_cop_h
            df["elec_awhp_h_Wh"] = elec_h_Wh
            df["elec_Wh"] += elec_h_Wh
            df["hhw_rem_W"] -= served_h_W
            df["awhp_num_h"] = float(num_awhp_h)

        # =========================
        # Phase 3 – Boiler (optional)
        # =========================
        if scen.boiler:
            blr = library.get_equipment(scen.boiler)
            eff = _constant_efficiency(blr)
            if eff is None or eff <= 0:
                raise ValueError(
                    f"Boiler '{blr.eq_id}' requires a positive 'efficiency'."
                )

            boiler_served_W = df["hhw_rem_W"].to_numpy()
            gas_Wh = boiler_served_W / eff

            df["boiler_hhw_W"] = boiler_served_W
            df["gas_boiler_Wh"] = gas_Wh
            df["boiler_eff"] = eff
            df["gas_Wh"] += gas_Wh
            df["hhw_rem_W"] = 0.0

        # =========================
        # Phase 4 – Electric resistance (if heating remains)
        # =========================
        remaining_h_W = df["hhw_rem_W"].to_numpy()
        if np.any(remaining_h_W > 1e-9):
            elec_res_Wh = remaining_h_W  # COP = 1
            df["res_hhw_W"] = remaining_h_W
            df["elec_res_Wh"] = elec_res_Wh
            df["elec_Wh"] += elec_res_Wh
            df["hhw_rem_W"] = 0.0

        # =========================
        # Phase 5 – AWHP Cooling
        # =========================
        if scen.awhp_c:
            awhp_c = library.get_equipment(scen.awhp_c)
            awhp_cap_c = _per_unit_capacity_W(awhp_c, temps)
            awhp_cop_c = _per_unit_cop(awhp_c, temps)
            if np.isnan(awhp_cop_c).all():
                raise ValueError(f"AWHP cooling '{awhp_c.eq_id}' lacks a COP curve.")

            # Use same sizing logic as heating (from awhp_sizing)
            sizing = float(scen.awhp_sizing)
            if sizing < 1.0:
                peak_chw_W = float(df["chw_W"].max())
                if awhp_c.performance and awhp_c.performance.cap_curve:
                    cap_ref = interp_vector(
                        awhp_c.performance.cap_curve.t_out_C,
                        awhp_c.performance.cap_curve.capacity_W,
                        np.array([35.0]),  # conservative hot condition
                    )[0]
                elif awhp_c.capacity_W:
                    cap_ref = float(awhp_c.capacity_W)
                else:
                    raise ValueError(
                        f"AWHP '{awhp_c.eq_id}' lacks a capacity reference."
                    )
                awhp_num_c = (
                    int(np.ceil((peak_chw_W * sizing) / cap_ref)) if cap_ref > 0 else 0
                )
            else:
                awhp_num_c = int(np.ceil(sizing))

            awhp_num_c = max(awhp_num_c, 0)

            cap_total_c_W = awhp_cap_c * awhp_num_c
            served_c_W = np.minimum(df["chw_rem_W"].to_numpy(), cap_total_c_W)
            elec_c_Wh = served_c_W / awhp_cop_c

            df["awhp_chw_W"] = served_c_W
            df["awhp_cap_c_W"] = cap_total_c_W
            df["awhp_cop_c"] = awhp_cop_c
            df["elec_awhp_c_Wh"] = elec_c_Wh
            df["elec_Wh"] += elec_c_Wh
            df["chw_rem_W"] -= served_c_W
            df["awhp_num_c"] = float(awhp_num_c)

        # =========================
        # Phase 6 – Electric chiller fallback
        # =========================
        if df["chw_rem_W"].sum() > 1e-9:
            chiller_cop = 5.0  # default <- why fix here?
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
                        served_W = df["chw_rem_W"].to_numpy()
                        elec_Wh = served_W / cop_curve
                        df["chiller_chw_W"] = served_W
                        df["elec_chiller_Wh"] = elec_Wh
                        df["elec_Wh"] += elec_Wh
                        df["chiller_cop"] = cop_curve
                        df["chw_rem_W"] = 0.0
                        # finalize and return
                        cols = _finalize_columns(df, detail)
                        return df[cols]

            # scalar COP path
            served_W = df["chw_rem_W"].to_numpy()
            elec_Wh = served_W / chiller_cop

            if detail:
                df["chiller_chw_W"] = served_W
                df["elec_chiller_Wh"] = elec_Wh
                df["chiller_cop"] = chiller_cop

            df["elec_Wh"] += elec_Wh
            df["chw_rem_W"] = 0.0

            df = df.round(2)

        # ---- finalize ----
        cols = _finalize_columns(df, detail)

        df = df[cols]
        df["scenario_id"] = scenario_id  # tag scenario
        results.append(df)

    return pd.concat(results, axis=0, ignore_index=False)


def _finalize_columns(df: pd.DataFrame, detail: bool) -> list[str]:
    """Return a clean column order for output."""
    base = ["t_out_C", "heating_W", "cooling_W", "elec_Wh", "gas_Wh"]
    if not detail:
        return base

    detail_cols = [
        "hhw_W",
        "chw_W",
        "hr_hhw_W",
        "hr_chw_W",
        "hr_cop_h",
        "max_cap_h_hr_W",  #! remove
        "min_cap_h_hr_W",  #! remove
        "simult_h_hr_W",  #! remove
        "elec_hr_Wh",
        "awhp_num_h",
        "awhp_cap_h_W",
        "awhp_cop_h",
        "awhp_hhw_W",
        "elec_awhp_h_Wh",
        "boiler_eff",
        "boiler_hhw_W",
        "gas_boiler_Wh",
        "res_hhw_W",
        "elec_res_Wh",
        "awhp_num_c",
        "awhp_cap_c_W",
        "awhp_cop_c",
        "awhp_chw_W",
        "elec_awhp_c_Wh",
        "chiller_cop",
        "chiller_chw_W",
        "elec_chiller_Wh",
    ]
    # only include those that actually exist
    detail_cols = [c for c in detail_cols if c in df.columns]
    return base + detail_cols


def site_to_source(
    df_loads: pd.DataFrame,
    metadata: Metadata,
    gas_emissions_rate: float = 180,  # gCO2e/kWh (example default)
    annual_refrig_leakage: float = 0.02,  # fraction per year
    shortrun_weighting: float = 0.5,  # between 0 and 1
) -> pd.DataFrame:
    """
    Convert site energy data (from loads_to_site) into source emissions
    using StandardEmissions data and user EmissionsScenario settings.
    """

    results = []

    for scenario_id in metadata.list_emission_scenarios():

        emissions_data = get_emissions_data(metadata[scenario_id])

        scen = metadata[scenario_id]

        # extract month/hour from loads
        base = df_loads.copy()
        base["month"] = base.index.month
        base["day"] = base.index.day
        base["hour"] = base.index.hour
        base["doy"] = base.index.dayofyear

        # collapse emissions to month-hour averages
        emissions_data.df["month"] = emissions_data.df.index.month
        emissions_data.df["hour"] = emissions_data.df.index.hour
        group_cols = ["month", "hour"]

        if scen.emission_type == "Combustion only":
            emissions_data.df["elec_emissions_rate"] = (
                emissions_data.df["lrmer_co2e_c"] * (1 - shortrun_weighting)
                + emissions_data.df["srmer_co2e_c"] * shortrun_weighting
            )
        elif scen.emission_type == "Includes pre-combustion":
            emissions_data.df["elec_emissions_rate"] = (
                emissions_data.df["lrmer_co2e_c"] + emissions_data.df["lrmer_co2e_p"]
            ) * (1 - shortrun_weighting) + (
                emissions_data.df["srmer_co2e_c"] + emissions_data.df["srmer_co2e_p"]
            ) * shortrun_weighting
        else:
            raise ValueError(f"Invalid emissions_type: {scen.emission_type}")

        df_em = (
            emissions_data.df.groupby(group_cols)["elec_emissions_rate"]
            .mean()
            .reset_index()
        )

        # expand loads with this year's emissions
        merged = base.merge(df_em, on=["month", "hour"], how="left")
        merged["year"] = scen.year

        # electricity emissions
        merged["elec_emissions"] = (
            merged["elec_Wh"] * merged["elec_emissions_rate"] / 1_000_000
        )

        # gas emissions
        if "gas_Wh" in merged.columns:
            merged["gas_emissions"] = gas_emissions_rate * merged["gas_Wh"] / 1_000_000
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

        # result_df["year"] = result_df["emission_year"]
        merged["timestamp"] = pd.to_datetime(merged[["year", "month", "day", "hour"]])

        merged = merged.drop(columns=["month", "day", "doy", "hour"]).set_index(
            "timestamp"
        )

        merged["em_scen_id"] = scenario_id  # tag scenario

        results.append(merged)

    return pd.concat(results, axis=0, ignore_index=False)
