import numpy as np
import pandas as pd
from typing import Optional, Union

from src.loads import StandardLoad
from src.equipment import EquipmentLibrary, Equipment
from src.emissions import StandardEmissions, get_emissions_data, EmissionScenario
from src.metadata import Metadata
from src.config import Columns as Col

from utils.units import cop_h_to_cop_c
from utils.interp import interp_vector


def _heat_recovery_plr_curve(e: Equipment) -> pd.DataFrame:
    """Heat recovery COP vs part-load ratio (PLR)."""
    if e.performance and e.performance_heating.plr_curve:
        cap = e.performance_heating.plr_curve.capacity_W
        cop = e.performance_heating.plr_curve.cop
        return pd.DataFrame({"cap": cap, "cop": cop})
    raise ValueError(f"Equipment '{e.eq_id}' has no plr_curve.")


def _per_unit_heating_capacity_W(e: Equipment, t_out: np.ndarray) -> np.ndarray:
    """Per-unit thermal capacity [W] vs outdoor temperature."""
    if e.performance and e.performance_heating.cap_curve:
        cap_h = interp_vector(
            e.performance_heating.cap_curve.t_out_C,
            e.performance_heating.cap_curve.capacity_W,
            t_out,
        )
    elif e.capacity_W is not None: # fallback to fixed capacity if provided 
        cap_h = np.full_like(t_out, fill_value=float(e.capacity_W), dtype=float)
    else: 
        raise ValueError(
            f"Equipment '{e.eq_id}' has no heating capacity info (cap_curve or capacity_W)."
        )
    cap_h = _capacity_constraints(e, t_out, cap_h, True)
    return cap_h

def _per_unit_heating_cop(e: Equipment, t_out: np.ndarray) -> np.ndarray:
    """Per-unit COP vs outdoor temperature."""
    # If the device has a COP curve, use it
    if e.performance and e.performance_heating.cop_curve:
        return interp_vector(
            e.performance_heating.cop_curve.t_out_C,
            e.performance_heating.cop_curve.cop,
            t_out,
        )
    # Some devices (boiler/resistance) use efficiency instead (not COP).
    # We'll not use COP for them here.
    return np.full_like(t_out, fill_value=np.nan, dtype=float)


def _per_unit_cooling_capacity_W(e: Equipment, t_out: np.ndarray) -> np.ndarray:
    """Per-unit thermal capacity [W] vs outdoor temperature."""
    if e.performance and e.performance_cooling.cap_curve:
        cap_c = interp_vector(
            e.performance_cooling.cap_curve.t_out_C,
            e.performance_cooling.cap_curve.capacity_W,
            t_out,
        )
    elif e.capacity_W is not None: # fallback to fixed capacity if provided
        cap_c = np.full_like(t_out, fill_value=float(e.capacity_W), dtype=float)
    else:
        raise ValueError(
            f"Equipment '{e.eq_id}' has no cooling capacity info (cap_curve or capacity_W)."
        )
    cap_c = _capacity_constraints(e, t_out, cap_c, False)
    return cap_c

def _per_unit_cooling_cop(e: Equipment, t_out: np.ndarray) -> np.ndarray:
    """Per-unit COP vs outdoor temperature."""
    # If the device has a COP curve, use it
    if e.performance and e.performance_cooling.cop_curve:
        return interp_vector(
            e.performance_cooling.cop_curve.t_out_C,
            e.performance_cooling.cop_curve.cop,
            t_out,
        )
    # Some devices (boiler/resistance) use efficiency instead (not COP).
    # We'll not use COP for them here.
    return np.full_like(t_out, fill_value=np.nan, dtype=float)


def _constant_heating_efficiency(e: Equipment) -> Optional[float]:
    if e.performance and e.performance_heating.efficiency is not None:
        return float(e.performance_heating.efficiency)
    return None


def _constant_cooling_efficiency(e: Equipment) -> Optional[float]:
    if e.performance and e.performance_cooling.efficiency is not None:
        return float(e.performance_cooling.efficiency)
    return None

def _capacity_constraints(e: Equipment, t_out: np.ndarray, cap: np.ndarray, heating: bool) -> np.ndarray:
    """Per-unit thermal capacity [W] vs outdoor temperature, limited by OAT constraints."""
    temps = np.asarray(t_out, dtype=float)
    if heating:
        high_t = np.nonzero(temps>e.performance_heating.constraints['max_temp_C'])
        low_t = np.nonzero(temps<e.performance_heating.constraints['min_temp_C'])
    else:
        high_t = np.nonzero(temps>e.performance_cooling.constraints['max_temp_C'])
        low_t = np.nonzero(temps<e.performance_cooling.constraints['min_temp_C'])
    np.put(cap, high_t[0], [0]) # replace capacities where temps are outside the HP's operating bounds with 0
    np.put(cap, low_t[0], [0])
    return cap

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
        temps = df[Col.T_OUT_C.value].to_numpy()

        df[Col.HHW_W.value] = df[Col.HEATING_W.value]
        df[Col.CHW_W.value] = df[Col.COOLING_W.value]

        # Remainders in W_th
        df[Col.HHW_REM_W.value] = df[Col.HHW_W.value].copy()
        df[Col.CHW_REM_W.value] = df[Col.CHW_W.value].copy()

        # Outputs
        df[Col.ELEC_WH.value] = 0.0
        df[Col.GAS_WH.value] = 0.0

        # detail columns (create lazily; safer to pre-create as NaN for clarity)
        if detail:
            for c in [
                # HR WWHP
                Col.HR_HHW_W.value,
                Col.HR_CHW_W.value,
                Col.HR_COP_H.value,
                Col.ELEC_HR_WH.value,
                # AWHP Heating
                Col.AWHP_HHW_W.value,
                Col.AWHP_COP_H.value,
                Col.AWHP_CAP_H_W.value,
                Col.AWHP_NUM_H.value,
                Col.ELEC_AWHP_H_WH.value,
                # Boiler
                Col.BOILER_HHW_W.value,
                Col.BOILER_EFF.value,
                Col.GAS_BOILER_WH.value,
                # Resistance heater
                Col.RES_HHW_W.value,
                Col.ELEC_RES_WH.value,
                # AWHP Cooling
                Col.AWHP_CHW_W.value,
                Col.AWHP_COP_C.value,
                Col.AWHP_CAP_C_W.value,
                Col.AWHP_NUM_C.value,
                Col.ELEC_AWHP_C_WH.value,
                # Electric chiller
                Col.CHILLER_CHW_W.value,
                Col.CHILLER_COP.value,
                Col.ELEC_CHILLER_WH.value,
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
                df[Col.HHW_REM_W.value].to_numpy(),
                df[Col.CHW_REM_W.value].to_numpy()
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

            # add refrigerant information
            hr_wwhp_refrigerant = (
                hr_wwhp.refrigerant if hr_wwhp.refrigerant else "Unknown"
            )
            hr_wwhp_refrigerant_weight_kg = (
                (hr_wwhp.refrigerant_weight_g * 0.001) / 8760
                if hr_wwhp.refrigerant_weight_g
                else 0.0
            )

            # GWP in kgCO2e/kgRefrig * weightRefrig in kg = kgCO2e Emissions (potential)
            hr_wwhp_refrigerant_gwp_kg = (  #! this is not effective emissions, just potential if leaked
                hr_wwhp.refrigerant_gwp * hr_wwhp_refrigerant_weight_kg
                if hr_wwhp.refrigerant_gwp
                else 0.0
            )

            # Apply results
            df[Col.MAX_CAP_H_HR_W.value] = max_cap_h  #! remove
            df[Col.MIN_CAP_H_HR_W.value] = min_cap_h  #! remove
            df[Col.SIMULT_H_HR_W.value] = simult_h  #! remove
            df[Col.HR_HHW_W.value] = hr_hhw
            df[Col.HR_CHW_W.value] = hr_chw
            df[Col.HR_COP_H.value] = hr_cop_h
            df[Col.ELEC_HR_WH.value] = elec_hr
            df[Col.ELEC_WH.value] += elec_hr
            df[Col.HHW_REM_W.value] -= hr_hhw
            df[Col.CHW_REM_W.value] -= hr_chw
            df[Col.HR_WWHP_REFRIGERANT.value] = hr_wwhp_refrigerant
            df[Col.HR_WWHP_REFRIGERANT_WEIGHT_KG.value] = hr_wwhp_refrigerant_weight_kg
            df[Col.HR_WWHP_REFRIGERANT_GWP.value] = hr_wwhp_refrigerant_gwp_kg

        # =========================
        # Phase 2 – AWHP Heating
        # =========================
        if scen.awhp:
            awhp_h = library.get_equipment(scen.awhp)
            awhp_cap_h = _per_unit_heating_capacity_W(awhp_h, temps)
            awhp_cop_h = _per_unit_heating_cop(awhp_h, temps)
            if np.isnan(awhp_cop_h).all():
                raise ValueError(f"AWHP heating '{awhp_h.eq_id}' lacks a COP curve.")

            # Determine number of units
            sizing_mode = scen.awhp_sizing_mode
            sizing_value = scen.awhp_sizing_value

            if sizing_mode is None or sizing_value is None:
                raise ValueError(
                    f"AWHP scenario '{scen.eq_scen_id}' requires both "
                    f"'awhp_sizing_mode' and 'awhp_sizing_value'."
                )

            ref_temp_C = 0.0  # Conservative outdoor temperature for sizing

            if awhp_h.performance and getattr(
                awhp_h.performance_heating, "cap_curve", None
            ):
                cap_ref = interp_vector(
                    awhp_h.performance_heating.cap_curve.t_out_C,
                    awhp_h.performance_heating.cap_curve.capacity_W,
                    np.array([ref_temp_C]),
                )[0]
            elif getattr(awhp_h, "capacity_W", None):
                cap_ref = float(awhp_h.capacity_W)
            else:
                raise ValueError(
                    f"AWHP '{awhp_h.eq_id}' lacks a valid capacity reference."
                )

            # --- Sizing Logic ---
            if "peak_load_percentage" in sizing_mode:
                if not (0.0 <= sizing_value <= 1.0):
                    raise ValueError(
                        f"AWHP scenario '{scen.eq_scen_id}' requires "
                        f"'awhp_sizing_value' between 0 and 1 for peak_load_percentage mode."
                    )

                # Fraction of peak HHW load at reference temperature
                peak_hhw_W = float(df["hhw_W"].max())
                target_load_W = peak_hhw_W * sizing_value

                if "integer" in sizing_mode:
                    awhp_num_h = np.ceil(target_load_W / cap_ref)
                    awhp_num_h = int(max(1, awhp_num_h))  # Ensure at least one unit
                elif "fractional" in sizing_mode:
                    awhp_num_h = target_load_W / cap_ref

            elif sizing_mode == "num_of_units":
                if sizing_value < 0:
                    raise ValueError(
                        f"AWHP scenario '{scen.eq_scen_id}' requires "
                        f"'awhp_sizing_value' to be non-negative for num_of_units mode."
                    )
                awhp_num_h = np.ceil(sizing_value)
                awhp_num_h = int(max(1, awhp_num_h))  # Ensure at least one unit

            else:
                raise ValueError(
                    f"AWHP scenario '{scen.eq_scen_id}' has unrecognized sizing mode: '{sizing_mode}'."
                )

            awhp_num_h = max(awhp_num_h, 0)

            cap_total_h_W = awhp_cap_h * awhp_num_h
            served_h_W = np.minimum(df[Col.HHW_REM_W.value].to_numpy(), cap_total_h_W)
            elec_h_Wh = served_h_W / awhp_cop_h

            # add refrigerant information
            awhp_refrigerant = awhp_h.refrigerant if awhp_h.refrigerant else "Unknown"
            total_awhp_refrigerant_weight_kg = (
                awhp_h.refrigerant_weight_g * 0.001 * awhp_num_h / 8760
                if awhp_h.refrigerant_weight_g
                else 0.0
            )

            total_awhp_refrigerant_gwp_kg = (
                awhp_h.refrigerant_gwp * total_awhp_refrigerant_weight_kg / 1000
                if awhp_h.refrigerant_gwp
                else 0.0
            )

            df[Col.AWHP_HHW_W.value] = served_h_W
            df[Col.AWHP_CAP_H_W.value] = cap_total_h_W
            df[Col.AWHP_COP_H.value] = awhp_cop_h
            df[Col.ELEC_AWHP_H_WH.value] = elec_h_Wh
            df[Col.ELEC_WH.value] += elec_h_Wh
            df[Col.HHW_REM_W.value] -= served_h_W
            df[Col.AWHP_NUM_H.value] = float(awhp_num_h)
            df[Col.AWHP_REFRIGERANT.value] = awhp_refrigerant
            df[Col.AWHP_REFRIGERANT_WEIGHT_KG.value] = total_awhp_refrigerant_weight_kg
            df[Col.AWHP_REFRIGERANT_GWP.value] = total_awhp_refrigerant_gwp_kg

        # =========================
        # Phase 3 – Boiler (optional)
        # =========================
        if scen.boiler:
            blr = library.get_equipment(scen.boiler)
            eff = _constant_heating_efficiency(blr)
            if eff is None or eff <= 0:
                raise ValueError(
                    f"Boiler '{blr.eq_id}' requires a positive 'efficiency'."
                )

            boiler_served_W = df[Col.HHW_REM_W].to_numpy()
            gas_Wh = boiler_served_W / eff

            df[Col.BOILER_HHW_W.value] = boiler_served_W
            df[Col.GAS_BOILER_WH.value] = gas_Wh
            df[Col.BOILER_EFF.value] = eff
            df[Col.GAS_WH.value] += gas_Wh
            df[Col.HHW_REM_W.value] = 0.0

        # =========================
        # Phase 4 – Electric resistance (if heating remains)
        # =========================
        remaining_h_W = df[Col.HHW_REM_W.value].to_numpy()
        if np.any(remaining_h_W > 1e-9):
            elec_res_Wh = remaining_h_W  # COP = 1
            df[Col.RES_HHW_W.value] = remaining_h_W
            df[Col.ELEC_RES_WH.value] = elec_res_Wh
            df[Col.ELEC_WH.value] += elec_res_Wh
            df[Col.HHW_REM_W.value] = 0.0

        # =========================
        # Phase 5 – AWHP Cooling
        # =========================
        if scen.awhp and scen.awhp_use_cooling:
            awhp_c = library.get_equipment(scen.awhp)
            awhp_cap_c = _per_unit_cooling_capacity_W(awhp_c, temps)
            awhp_cop_c = _per_unit_cooling_cop(awhp_c, temps)
            if np.isnan(awhp_cop_c).all():
                raise ValueError(f"AWHP cooling '{awhp_c.eq_id}' lacks a COP curve.")

            awhp_num_c = awhp_num_h  # use same number of units as heating

            cap_total_c_W = awhp_cap_c * awhp_num_c

            mask = (
                df[Col.AWHP_HHW_W.value] == 0
            )  # create a mask for hours when no heating is served by AWHP
            served_c_W = np.zeros(len(df))  # Initialize served_c_W as zeros
            served_c_W[mask] = np.minimum(
                df.loc[mask, Col.CHW_REM_W.value].to_numpy(), cap_total_c_W[mask]
            )  # Compute only where mask is True

            # Compute electricity only where cooling is served
            elec_c_Wh = served_c_W / awhp_cop_c
            df[Col.AWHP_CHW_W.value] = served_c_W
            df[Col.AWHP_CAP_C_W.value] = cap_total_c_W
            df[Col.AWHP_COP_C.value] = awhp_cop_c
            df[Col.ELEC_AWHP_C_WH.value] = elec_c_Wh
            df[Col.ELEC_WH.value] += elec_c_Wh
            df[Col.CHW_REM_W.value] -= served_c_W
            df[Col.AWHP_NUM_C] = float(awhp_num_c)

        # =========================
        # Phase 6 – Electric chiller fallback
        # =========================
        if df[Col.CHW_REM_W.value].sum() > 1e-9:
            chiller_cop = 5.0  # default <- why fix here?
            if scen.chiller:
                chl = library.get_equipment(scen.chiller)
                # prefer explicit efficiency (treat as COP for chiller), otherwise try COP curve
                eff = _constant_cooling_efficiency(chl)
                if eff and eff > 0:
                    chiller_cop = eff
                else:
                    cop_curve = _per_unit_cooling_cop(chl, temps)  # could be array
                    if not np.isnan(cop_curve).all():
                        # if a curve exists, use the hourly values
                        served_W = df[Col.CHW_REM_W.value].to_numpy()
                        elec_Wh = served_W / cop_curve
                        df[Col.CHILLER_CHW_W.value] = served_W
                        df[Col.ELEC_CHILLER_WH.value] = elec_Wh
                        df[Col.ELEC_WH.value] += elec_Wh
                        df[Col.CHILLER_COP.value] = cop_curve
                        df[Col.CHW_REM_W.value] = 0.0
                        # finalize and return
                        cols = _finalize_columns(df, detail)
                        return df[cols]

            # scalar COP path
            served_W = df[Col.CHW_REM_W.value].to_numpy()
            elec_Wh = served_W / chiller_cop

            # add refrigerant information
            chiller_refrigerant = chl.refrigerant if chl.refrigerant else "Unknown"

            chiller_refrigerant_weight_kg = (
                chl.refrigerant_weight_g * 0.001 / 8760
                if chl.refrigerant_weight_g
                else 0.0
            )

            chiller_refrigerant_gwp_kg = (
                chl.refrigerant_gwp * chiller_refrigerant_weight_kg
                if chl.refrigerant_gwp
                else 0.0
            )

            if detail:
                df[Col.CHILLER_CHW_W.value] = served_W
                df[Col.ELEC_CHILLER_WH.value] = elec_Wh
                df[Col.CHILLER_COP.value] = chiller_cop

            df[Col.ELEC_WH.value] += elec_Wh
            df[Col.CHW_REM_W.value] = 0.0
            df[Col.CHILLER_REFRIGERANT.value] = chiller_refrigerant
            df[Col.CHILLER_REFRIGERANT_WEIGHT_KG.value] = chiller_refrigerant_weight_kg
            df[Col.CHILLER_REFRIGERANT_GWP.value] = chiller_refrigerant_gwp_kg

            df = df.round(4)

        # ---- finalize ----
        cols = _finalize_columns(df, detail)

        df = df[cols]
        df[Col.EQ_SCEN_ID.value] = scenario_id  # tag scenario
        df[Col.EQ_SCEN_NAME.value] = library.get_scenario(scenario_id).eq_scen_name
        results.append(df)

    return pd.concat(results, axis=0, ignore_index=False)


def _finalize_columns(df: pd.DataFrame, detail: bool) -> list[str]:
    """Return a clean column order for output."""
    base = [
        Col.T_OUT_C.value,
        Col.HEATING_W.value,
        Col.COOLING_W.value,
        Col.ELEC_WH.value,
        Col.GAS_WH.value,
    ]
    if not detail:
        return base

    detail_cols = [
        Col.HHW_W.value,
        Col.CHW_W.value,
        Col.HR_HHW_W.value,
        Col.HR_CHW_W.value,
        Col.HR_COP_H.value,
        Col.MAX_CAP_H_HR_W.value,
        Col.MIN_CAP_H_HR_W.value,
        Col.SIMULT_H_HR_W.value,
        Col.ELEC_HR_WH.value,
        Col.HR_WWHP_REFRIGERANT.value,
        Col.HR_WWHP_REFRIGERANT_WEIGHT_KG.value,
        Col.HR_WWHP_REFRIGERANT_GWP.value,
        Col.AWHP_NUM_H.value,
        Col.AWHP_CAP_H_W.value,
        Col.AWHP_COP_H.value,
        Col.AWHP_HHW_W.value,
        Col.ELEC_AWHP_H_WH.value,
        Col.AWHP_REFRIGERANT.value,
        Col.AWHP_REFRIGERANT_WEIGHT_KG.value,
        Col.AWHP_REFRIGERANT_GWP.value,
        Col.BOILER_EFF.value,
        Col.BOILER_HHW_W.value,
        Col.GAS_BOILER_WH.value,
        Col.RES_HHW_W.value,
        Col.ELEC_RES_WH.value,
        Col.AWHP_NUM_C.value,
        Col.AWHP_CAP_C_W.value,
        Col.AWHP_COP_C.value,
        Col.AWHP_CHW_W.value,
        Col.ELEC_AWHP_C_WH.value,
        Col.CHILLER_COP.value,
        Col.CHILLER_CHW_W.value,
        Col.ELEC_CHILLER_WH.value,
        Col.CHILLER_REFRIGERANT.value,
        Col.CHILLER_REFRIGERANT_WEIGHT_KG.value,
        Col.CHILLER_REFRIGERANT_GWP.value,
    ]
    # only include those that actually exist
    detail_cols = [c for c in detail_cols if c in df.columns]
    return base + detail_cols


def site_to_source(
    df_loads: pd.DataFrame,
    metadata: Metadata,
    gas_emissions_rate: float = 239.2,  # gCO2e/kWh (example default)
) -> pd.DataFrame:
    """
    Convert site energy data (from loads_to_site) into source emissions
    using StandardEmissions data and user EmissionsScenario settings.
    """

    results = []

    for em_scen_id in metadata.list_emission_scenarios():

        emissions_data = get_emissions_data(metadata[em_scen_id])

        em_scen = metadata[em_scen_id]

        shortrun_weighting = float(em_scen.shortrun_weighting)
        annual_refrig_leakage_percent = float(em_scen.annual_refrig_leakage_percent)

        # extract month/hour from loads
        base = df_loads.copy()
        base[Col.MONTH.value] = base.index.month
        base[Col.DAY.value] = base.index.day
        base[Col.HOUR.value] = base.index.hour
        base[Col.DOY.value] = base.index.dayofyear

        # collapse emissions to month-hour averages
        emissions_data.df[Col.MONTH.value] = emissions_data.df.index.month
        emissions_data.df[Col.HOUR.value] = emissions_data.df.index.hour
        emissions_data.df[Col.SHORTRUN_WEIGHTING.value] = shortrun_weighting
        group_cols = [Col.MONTH.value, Col.HOUR.value]

        # all rates are in gCO2e/kWh
        if em_scen.emission_type == "Combustion only":
            emissions_data.df[Col.ELEC_EMISSIONS_RATE_G_PER_KWH] = (
                emissions_data.df[Col.LRMER_CO2E_C.value] * (1 - shortrun_weighting)
            ) + (emissions_data.df[Col.SRMER_CO2E_C.value] * shortrun_weighting)
        elif em_scen.emission_type == "Includes pre-combustion":
            emissions_data.df[Col.ELEC_EMISSIONS_RATE_G_PER_KWH] = (
                (
                    emissions_data.df[Col.LRMER_CO2E_C.value]
                    + emissions_data.df[Col.LRMER_CO2E_P.value]
                )
                * (1 - shortrun_weighting)
            ) + (
                (
                    emissions_data.df[Col.SRMER_CO2E_C.value]
                    + emissions_data.df[Col.SRMER_CO2E_P.value]
                )
                * shortrun_weighting
            )
        else:
            raise ValueError(f"Invalid emissions_type: {em_scen.emission_type}")

        df_em = (
            emissions_data.df.groupby(group_cols)[
                [
                    Col.ELEC_EMISSIONS_RATE_G_PER_KWH,
                    Col.LRMER_CO2E_C.value,
                    Col.LRMER_CO2E_P.value,
                    Col.LRMER_CO2E.value,
                    Col.SRMER_CO2E_C.value,
                    Col.SRMER_CO2E_P.value,
                    Col.SRMER_CO2E.value,
                    Col.SHORTRUN_WEIGHTING.value,
                ]
            ]
            .mean()
            .reset_index()
        )

        # expand loads with this year's emissions
        merged = base.merge(df_em, on=[Col.MONTH.value, Col.HOUR.value], how="left")
        merged[Col.YEAR.value] = em_scen.year

        # electricity emissions
        merged[Col.ELEC_EMISSIONS_KG_CO2E.value] = (
            merged[Col.ELEC_WH.value]
            * merged[Col.ELEC_EMISSIONS_RATE_G_PER_KWH.value]
            / 1_000_000  #! make cleaner
        )

        # gas emissions
        if Col.GAS_WH.value in merged.columns:
            merged[Col.GAS_EMISSIONS_KG_CO2E.value] = (
                gas_emissions_rate * merged[Col.GAS_WH.value] / 1_000_000
            )
        else:
            merged[Col.GAS_EMISSIONS_KG_CO2E.value] = 0.0

        # refrigerant emissions
        refrig_cols = [
            Col.HR_WWHP_REFRIGERANT_GWP.value,
            Col.AWHP_REFRIGERANT_GWP.value,
            Col.CHILLER_REFRIGERANT_GWP.value,
        ]

        existing_refrig_cols = [c for c in refrig_cols if c in merged.columns]

        if existing_refrig_cols:
            # Compute the total refrigerant emissions inventory by summing available columns
            merged[Col.TOTAL_REFRIG_GWP_KG.value] = merged[existing_refrig_cols].sum(
                axis=1
            )
        else:
            # If none exist, default to zero
            merged[Col.TOTAL_REFRIG_GWP_KG.value] = 0.0

        merged[Col.TOTAL_REFRIG_EMISSIONS_KG_CO2E.value] = (
            merged[Col.TOTAL_REFRIG_GWP_KG.value] * annual_refrig_leakage_percent
        )

        merged[Col.TIMESTAMP.value] = pd.to_datetime(
            merged[[Col.YEAR.value, Col.MONTH.value, Col.DAY.value, Col.HOUR.value]]
        )

        merged = merged.drop(
            columns=[Col.MONTH.value, Col.DAY.value, Col.DOY.value, Col.HOUR.value]
        ).set_index(Col.TIMESTAMP.value)

        merged[Col.TOTAL_EMISSIONS_KG_CO2E.value] = (
            merged[Col.ELEC_EMISSIONS_KG_CO2E.value]
            + merged[Col.GAS_EMISSIONS_KG_CO2E.value]
            + merged[Col.TOTAL_REFRIG_EMISSIONS_KG_CO2E.value]
        )

        merged[Col.EM_SCEN_ID.value] = em_scen_id  # tag scenario

        results.append(merged)

    return pd.concat(results, axis=0, ignore_index=False)
