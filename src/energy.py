import numpy as np
import pandas as pd

from src.config import Columns as Col
from src.emissions import get_emissions_data
from src.equipment import Equipment, EquipmentLibrary, PerformanceCurves
from src.loads import StandardLoad
from src.metadata import Metadata
from utils.interp import interp_vector, multi_interp_vector
from utils.logging_config import get_logger
from utils.units import cop_h_to_cop_c
from utils.error_handling import create_warning_notification

logger = get_logger(__name__)


def _equipment_data_validation(library: EquipmentLibrary, scenario_ids: list[str]):
    """Ensure all equipment in the selected scenarios have complete data for the calculations."""

    for scenario_id in scenario_ids:
        scen = library.get_scenario(scenario_id)

        # wwhp checks
        if scen.hr_wwhp:
            hr_wwhp = library.get_equipment(scen.hr_wwhp)

            if not hr_wwhp.performance_heating:
                raise ValueError(f"Equipment '{hr_wwhp.eq_id}' lacks heating performance data.")

            hr_wwhp_supply_t = scen.hr_wwhp_h_supply_t
            if (
                hr_wwhp_supply_t < hr_wwhp.performance_heating.constraints["min_temp_C"]
                or hr_wwhp_supply_t > hr_wwhp.performance_heating.constraints["max_temp_C"]
            ):
                raise ValueError(
                    f"Supply water temperature {hr_wwhp_supply_t} is outside the bounds of the provided performance data for equipment '{hr_wwhp.eq_id}'."
                )

            if not hr_wwhp.performance_heating.capacity_W:
                raise ValueError(
                    f"Equipment '{hr_wwhp.eq_id}' lacks heating capacity info (capacity_W curve)."
                )

            hr_wwhp_supply_temps_str = list(hr_wwhp.performance_heating.leaving_supply_t.keys())

            for t in hr_wwhp_supply_temps_str:
                if not hr_wwhp.performance_heating.leaving_supply_t[t].cop:
                    raise ValueError(
                        f"Equipment '{hr_wwhp.eq_id}' lacks heating capacity info (COP curve for supply temperature {t})."
                    )

                if len(hr_wwhp.performance_heating.capacity_W) != len(
                    hr_wwhp.performance_heating.leaving_supply_t[t].cop
                ):
                    raise ValueError(
                        f"Equipment '{hr_wwhp.eq_id}' heating COP and capacity curves are of different lengths for supply temperature {t}."
                    )

            if scen.hr_wwhp_performance_model not in [
                "fixed_COP",
                "interpolate_HHWST",
                "performance_curves",
            ]:
                raise ValueError(
                    f"HR WWHP scenario '{scen.eq_scen_id}' has unrecognized performance calculation model: '{scen.hr_wwhp_performance_model}'."
                )

        if scen.awhp:
            # awhp heating checks
            awhp_h = library.get_equipment(scen.awhp)

            if not awhp_h.performance_heating:
                raise ValueError(f"Equipment '{awhp_h.eq_id}' lacks heating performance data.")

            awhp_h_supply_t = scen.awhp_h_supply_t
            if (
                awhp_h_supply_t < awhp_h.performance_heating.constraints["min_temp_C"]
                or awhp_h_supply_t > awhp_h.performance_heating.constraints["max_temp_C"]
            ):
                raise ValueError(
                    f"Supply water temperature {awhp_h_supply_t} is outside the bounds of the provided performance data for equipment '{awhp_h.eq_id}'."
                )

            if not awhp_h.performance_heating.t_out_C:
                raise ValueError(
                    f"Equipment '{awhp_h.eq_id}' lacks heating capacity info (t_out curve)."
                )

            awhp_h_supply_temps_str = list(awhp_h.performance_heating.leaving_supply_t.keys())

            for t in awhp_h_supply_temps_str:
                if not awhp_h.performance_heating.leaving_supply_t[t].capacity_W:
                    if not awhp_h.capacity_W:
                        raise ValueError(
                            f"Equipment '{awhp_h.eq_id}' lacks heating capacity info (fixed value or t_out-based curve for capacity_W at supply temperature {t})."
                        )

                else:
                    if len(awhp_h.performance_heating.t_out_C) != len(
                        awhp_h.performance_heating.leaving_supply_t[t].capacity_W
                    ):
                        raise ValueError(
                            f"Equipment '{awhp_h.eq_id}' heating capacity_W and t_out curves are of different lengths for supply temperature {t}."
                        )

                if not awhp_h.performance_heating.leaving_supply_t[t].cop:
                    raise ValueError(
                        f"Equipment '{awhp_h.eq_id}' lacks heating capacity info (COP curve for supply temperature {t})."
                    )

                if len(awhp_h.performance_heating.t_out_C) != len(
                    awhp_h.performance_heating.leaving_supply_t[t].cop
                ):
                    raise ValueError(
                        f"Equipment '{awhp_h.eq_id}' heating COP and t_out curves are of different lengths for supply temperature {t}."
                    )

                if "min_temp_C" not in awhp_h.performance_heating.leaving_supply_t[t].constraints:
                    raise ValueError(
                        f"Equipment '{awhp_h.eq_id}' lacks heating capacity info (minimum t_out constraint for supply temperature {t})."
                    )

                if "max_temp_C" not in awhp_h.performance_heating.leaving_supply_t[t].constraints:
                    raise ValueError(
                        f"Equipment '{awhp_h.eq_id}' lacks heating capacity info (maximum t_out constraint for supply temperature {t})."
                    )

            if scen.awhp_sizing_mode is None:
                raise ValueError(f"AWHP scenario '{scen.eq_scen_id}' requires 'awhp_sizing_mode'.")

            if scen.awhp_sizing_value is None:
                raise ValueError(f"AWHP scenario '{scen.eq_scen_id}' requires 'awhp_sizing_value'.")

            if scen.awhp_redundancy is None:
                raise ValueError(f"AWHP scenario '{scen.eq_scen_id}' requires 'awhp_redundancy'.")

            if scen.awhp_sizing_mode in [
                "integer_sizing_peak_load",
                "fractional_sizing_peak_load",
            ]:
                if not (0.0 <= scen.awhp_sizing_value <= 1.0):
                    raise ValueError(
                        f"AWHP scenario '{scen.eq_scen_id}' requires "
                        f"'awhp_sizing_value' between 0 and 1 for peak load percentage sizing."
                    )

            elif scen.awhp_sizing_mode == "fixed_num_units":
                if scen.awhp_sizing_value < 0:
                    raise ValueError(
                        f"AWHP scenario '{scen.eq_scen_id}' requires "
                        f"'awhp_sizing_value' to be non-negative for num_of_units mode."
                    )

            else:
                raise ValueError(
                    f"AWHP scenario '{scen.eq_scen_id}' has unrecognized sizing mode: '{scen.awhp_sizing_mode}'."
                )

            if scen.awhp_redundancy < 0:
                raise ValueError(
                    f"AWHP scenario '{scen.eq_scen_id}' requires "
                    f"'awhp_redundancy' greater than or equal to 0."
                )

            if scen.awhp_performance_model not in [
                "fixed_COP",
                "interpolate_HHWST_fixed",
                "interpolate_HHWST_reset",
                "performance_curves",
            ]:
                raise ValueError(
                    f"AWHP scenario '{scen.eq_scen_id}' has unrecognized performance calculation model: '{scen.awhp_performance_model}'."
                )

            # awhp cooling checks
            if scen.awhp_use_cooling:
                awhp_c = library.get_equipment(scen.awhp)

                if scen.awhp_sizing_priority is None:
                    raise ValueError(f"AWHP scenario '{scen.eq_scen_id}' requires 'awhp_sizing_priority'.")
                
                if not awhp_c.performance_cooling:
                    raise ValueError(f"Equipment '{awhp_c.eq_id}' lacks cooling performance data.")

                if not awhp_c.performance_cooling.t_out_C:
                    raise ValueError(
                        f"Equipment '{awhp_c.eq_id}' lacks cooling capacity info (t_out curve)."
                    )

                awhp_c_supply_temps_str = list(awhp_c.performance_cooling.leaving_supply_t.keys())

                for t in awhp_c_supply_temps_str:
                    if not awhp_c.performance_cooling.leaving_supply_t[t].capacity_W:
                        if not awhp_c.capacity_W:
                            raise ValueError(
                                f"Equipment '{awhp_c.eq_id}' lacks cooling capacity info (fixed value or t_out-based curve for capacity_W at supply temperature {t})."
                            )

                    else:
                        if len(awhp_c.performance_cooling.t_out_C) != len(
                            awhp_c.performance_cooling.leaving_supply_t[t].capacity_W
                        ):
                            raise ValueError(
                                f"Equipment '{awhp_c.eq_id}' cooling capacity_W and t_out curves are of different lengths for supply temperature {t}."
                            )

                    if not awhp_c.performance_cooling.leaving_supply_t[t].cop:
                        raise ValueError(
                            f"Equipment '{awhp_c.eq_id}' lacks cooling capacity info (COP curve for supply temperature {t})."
                        )

                    if len(awhp_c.performance_cooling.t_out_C) != len(
                        awhp_c.performance_cooling.leaving_supply_t[t].cop
                    ):
                        raise ValueError(
                            f"Equipment '{awhp_c.eq_id}' cooling COP and t_out curves are of different lengths for supply temperature {t}."
                        )

                    if (
                        "min_temp_C"
                        not in awhp_c.performance_cooling.leaving_supply_t[t].constraints
                    ):
                        raise ValueError(
                            f"Equipment '{awhp_c.eq_id}' lacks cooling capacity info (minimum t_out constraint for supply temperature {t})."
                        )

                    if (
                        "max_temp_C"
                        not in awhp_c.performance_cooling.leaving_supply_t[t].constraints
                    ):
                        raise ValueError(
                            f"Equipment '{awhp_c.eq_id}' lacks cooling capacity info (maximum t_out constraint for supply temperature {t})."
                        )

        if scen.backup_heating:
            backup_heating = library.get_equipment(scen.backup_heating)

            if backup_heating.fuel == "natural_gas":
                # boiler checks
                if not backup_heating.performance_heating:
                    raise ValueError(
                        f"Equipment '{backup_heating.eq_id}' lacks heating performance data (efficiency)."
                    )

                if (
                    backup_heating.performance_heating.efficiency is None
                    or backup_heating.performance_heating.efficiency <= 0
                ):
                    raise ValueError(
                        f"Equipment '{backup_heating.eq_id}' requires a positive 'efficiency'."
                    )


def _heat_recovery_plr_curve(e: Equipment, performance: PerformanceCurves) -> pd.DataFrame:
    """Heat recovery COP vs part-load ratio (PLR)."""
    cap = e.performance_heating.capacity_W
    cop = performance.cop[0]
    return pd.DataFrame({"cap": cap, "cop": cop})


def _heating_supply_temp_performance(
    e: Equipment, supply_t: np.ndarray, t_out: np.ndarray, perf_model: str
) -> PerformanceCurves:
    """Heat pump performance data (COP, capacity, operating constraints) interpolated based on supply water temperature"""
    # extract list of supply temperatures
    equip_supply_temps_str = list(e.performance_heating.leaving_supply_t.keys())
    equip_supply_temps = np.array(equip_supply_temps_str, dtype="float")

    if perf_model == "interpolate_HHWST_reset":
        # define reset bounds
        supply_temp_lim = [
            max(equip_supply_temps),
            min(equip_supply_temps),
        ]  # highest HHWST at lowest OAT
        t_out_lim = [np.nan, 20]
        # set low limit to the minimum operating OAT at the lowest supply temperature
        t_out_lim[0] = e.performance_heating.leaving_supply_t[
            min(equip_supply_temps_str)
        ].constraints["min_temp_C"]
        logger.debug(
            f"AWHP heating water supply temperature reset: "
            f"HHWST {supply_temp_lim[0]}°C at OAT {t_out_lim[0]}°C, "
            f"HHWST {supply_temp_lim[1]}°C at OAT {t_out_lim[1]}°C."
        )

        supply_t = interp_vector(
            t_out_lim, supply_temp_lim, t_out
        )  # creates an array of HHWST at every OAT
        logger.debug(
            f"AWHP heating water supply temperature array: "
            f"length {len(supply_t)} ({np.sum(np.isnan(supply_t))} NaNs), "
            f"minimum {np.nanmin(supply_t):.1f}°C, "
            f"maximum {np.nanmax(supply_t):.1f}°C."
        )

    else:  # edit later when fixed COP/curves are added; for now, this is for fixed HHWST
        logger.debug(f"Equipment {e.eq_id} heating water supply temperature: {supply_t[0]}°C")

    interp_perf = PerformanceCurves()

    # extract performance data into separate lists
    cops = [e.performance_heating.leaving_supply_t[t].cop for t in equip_supply_temps_str]
    if e.eq_type == "heat_pump":  # only COP needed for WWHPs
        caps = [
            e.performance_heating.leaving_supply_t[t].capacity_W for t in equip_supply_temps_str
        ]
        constraints = {
            "min": [
                e.performance_heating.leaving_supply_t[t].constraints["min_temp_C"]
                for t in equip_supply_temps_str
            ],
            "max": [
                e.performance_heating.leaving_supply_t[t].constraints["max_temp_C"]
                for t in equip_supply_temps_str
            ],
        }

    # interpolate and store results
    interp_perf.cop = np.array(
        [interp_vector(equip_supply_temps, x, supply_t) for x in zip(*cops, strict=False)]
    ).T
    if e.eq_type == "heat_pump":
        if not all(caps):  # in case fixed capacity is used
            interp_perf.capacity_W = e.capacity_W
        else:
            interp_perf.capacity_W = np.array(
                [interp_vector(equip_supply_temps, x, supply_t) for x in zip(*caps, strict=False)]
            ).T
        interp_perf.constraints = {
            "min_temp_C": interp_vector(equip_supply_temps, constraints["min"], supply_t),
            "max_temp_C": interp_vector(equip_supply_temps, constraints["max"], supply_t),
        }
    else:
        # for WWHPs
        interp_perf.capacity_W = np.array(e.performance_heating.capacity_W)

    return interp_perf


def _per_unit_heating_capacity_W(
    e: Equipment, t_out: np.ndarray, performance: PerformanceCurves, perf_model: str
) -> np.ndarray:
    """Per-unit thermal capacity [W] vs outdoor temperature."""
    if isinstance(performance.capacity_W, np.ndarray):
        if perf_model == "interpolate_HHWST_fixed":
            cap_h = interp_vector(
                e.performance_heating.t_out_C,
                performance.capacity_W[0],
                t_out,
            )
        elif perf_model == "interpolate_HHWST_reset":
            cap_h = multi_interp_vector(
                e.performance_heating.t_out_C,
                performance.capacity_W,
                t_out,
            )
    else:  # fallback to fixed capacity
        cap_h = np.full_like(t_out, fill_value=float(performance.capacity_W), dtype=float)

    cap_h = _capacity_constraints(t_out, cap_h, performance, "heating")
    return cap_h


def _per_unit_heating_cop(
    e: Equipment, t_out: np.ndarray, performance: PerformanceCurves, perf_model: str
) -> np.ndarray:
    """Per-unit COP vs outdoor temperature."""
    if perf_model == "interpolate_HHWST_fixed":
        return interp_vector(
            e.performance_heating.t_out_C,
            performance.cop[0],
            t_out,
        )
    elif perf_model == "interpolate_HHWST_reset":
        return multi_interp_vector(
            e.performance_heating.t_out_C,
            performance.cop,
            t_out,
        )


def _per_unit_cooling_capacity_W(
    e: Equipment, t_out: np.ndarray, performance: PerformanceCurves
) -> np.ndarray:
    """Per-unit thermal capacity [W] vs outdoor temperature."""
    if isinstance(performance.capacity_W, list):
        cap_c = interp_vector(
            e.performance_cooling.t_out_C,
            performance.capacity_W,
            t_out,
        )
    else:  # fallback to fixed capacity
        cap_c = np.full_like(t_out, fill_value=float(e.capacity_W), dtype=float)

    cap_c = _capacity_constraints(t_out, cap_c, performance, "cooling")

    return cap_c


def _per_unit_cooling_cop(
    e: Equipment, t_out: np.ndarray, performance: PerformanceCurves
) -> np.ndarray:
    """Per-unit COP vs outdoor temperature."""
    return interp_vector(
        e.performance_cooling.t_out_C,
        performance.cop,
        t_out,
    )


def _constant_heating_efficiency(e: Equipment) -> float | None:
    return float(e.performance_heating.efficiency)


def _constant_cooling_efficiency(e: Equipment) -> float | None:
    if e.performance and e.performance_cooling.efficiency is not None:
        return float(e.performance_cooling.efficiency)
    return None


def _capacity_constraints(
    t_out: np.ndarray,
    cap: np.ndarray,
    performance: PerformanceCurves,
    load_type: str,
) -> np.ndarray:
    """Per-unit thermal capacity [W] vs outdoor temperature, limited by OAT constraints."""
    temps = np.asarray(t_out, dtype=float)
    high_t = np.nonzero(temps > performance.constraints["max_temp_C"])
    low_t = np.nonzero(temps < performance.constraints["min_temp_C"])

    logger.debug(
        f"{len(high_t[0])} hours above AWHP {load_type} operating limit; "
        f"{len(low_t[0])} hours below AWHP {load_type} operating limit "
    )

    # replace capacities where temps are outside the HP's operating bounds with 0
    np.put(cap, high_t[0], [0])
    np.put(cap, low_t[0], [0])

    return cap

def _awhp_reference_capacity(
    e: Equipment,
    performance: PerformanceCurves,
    supply_t: float,
    load_type: str,
) -> float:
    """AWHP reference capacity [W] for sizing."""

    cap_type = {"heating": np.ndarray, "cooling": list}

    if isinstance(performance.capacity_W, cap_type[load_type]):
        if load_type == "heating":
            ref_temp_C = 0.0  # Conservative outdoor temperature for sizing

            # closest supply temperature to input (for reset, this defaults to the lowest)
            awhp_h_supply_temps_str = list(e.performance_heating.leaving_supply_t.keys())
            awhp_h_supply_temps = np.array(awhp_h_supply_temps_str, dtype=float)
            ref_supply_temp = awhp_h_supply_temps_str[
                np.argmin(np.abs(awhp_h_supply_temps - supply_t))
            ]

        elif load_type == "cooling":
            ref_temp_C = 30.0  # Conservative outdoor temperature for sizing
            ref_supply_temp = supply_t

        ref_capacity_W = e.performance[load_type].leaving_supply_t[
            ref_supply_temp
        ].capacity_W
        
        cap_ref = interp_vector(
            e.performance[load_type].t_out_C,
            ref_capacity_W,
            np.array([ref_temp_C]),
        )[0]
    else:
        cap_ref = float(e.capacity_W)

    return cap_ref


def loads_to_site_energy(
    load: StandardLoad,
    library: EquipmentLibrary,
    scenario_ids: str | list[str],
    detail: bool = True,
) -> pd.DataFrame:
    """
    Convert hourly heating/cooling loads to site energy (kWh_electricity and kWh_gas)
    using the selected equipment scenarios from the EquipmentLibrary.
    """
    # --- normalize input ---
    if isinstance(scenario_ids, str):
        scenario_ids = [scenario_ids]

    logger.info(
        f"Starting loads_to_site_energy: {len(scenario_ids)} scenarios, "
        f"{len(load.df)} hours, detail={detail}"
    )

    # ---- input data validation ----
    _equipment_data_validation(library, scenario_ids)

    results = []

    for scenario_id in scenario_ids:
        logger.info(f"Processing scenario: {scenario_id}")

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
                Col.AWHP_NUM.value,
                Col.AWHP_NUM_R.value,
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
        # Phase 1 - HR WWHP (optional)
        # =========================
        if scen.hr_wwhp:
            logger.debug(f"Phase 1: HR WWHP using equipment '{scen.hr_wwhp}'")
            hr_wwhp = library.get_equipment(scen.hr_wwhp)

            hr_wwhp_h_performance_model = scen.hr_wwhp_performance_model
            logger.debug(f"HR WWHP performance calculation model: {hr_wwhp_h_performance_model}")

            hr_wwhp_supply_t = np.array([scen.hr_wwhp_h_supply_t])

            hr_wwhp_h_performance = _heating_supply_temp_performance(
                hr_wwhp, hr_wwhp_supply_t, temps, hr_wwhp_h_performance_model
            )

            plr_curve = _heat_recovery_plr_curve(hr_wwhp, hr_wwhp_h_performance)

            plr_curve = plr_curve.sort_values(by="cap", ascending=False).reset_index(drop=True)
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
            max_cap_h = num_units * plr_curve["cap"].max()  # max heating capacity allowed by unit
            min_cap_h = plr_curve["cap"].min()  # min heating capacity allowed by unit

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
            hr_chw = np.where(hr_cop_h > 0, hr_hhw * (1 - (1 / hr_cop_h)), 0.0)  # same as R

            # Electricity use
            elec_hr = np.where(hr_cop_h > 0, hr_hhw / hr_cop_h, 0.0)

            # add refrigerant information
            hr_wwhp_refrigerant = hr_wwhp.refrigerant if hr_wwhp.refrigerant else "Unknown"
            num_hours = len(df)  # Use actual data length (handles leap years)
            hr_wwhp_refrigerant_weight_kg = (
                (hr_wwhp.refrigerant_weight_g * 0.001) / num_hours
                if hr_wwhp.refrigerant_weight_g
                else 0.0
            )

            # GWP in kgCO2e/kgRefrig * weightRefrig in kg = kgCO2e Emissions (potential)
            hr_wwhp_refrigerant_gwp_kg = (  #! this is not effective emissions, just potential if leaked
                hr_wwhp.refrigerant_gwp * hr_wwhp_refrigerant_weight_kg
                if hr_wwhp.refrigerant_gwp
                else 0.0
            )

            if hr_wwhp_refrigerant_gwp_kg == 0:
                if hr_wwhp_refrigerant_weight_kg == 0:
                    logger.warning("HR WWHP refrigerant charge is 0.")
                else:
                    logger.warning("HR WWHP refrigerant GWP is 0.")

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

            hr_coverage_heating = (
                (np.nansum(hr_hhw) / np.nansum(df[Col.HHW_W.value])) * 100
                if np.nansum(df[Col.HHW_W.value]) > 0
                else 0
            )
            hr_coverage_cooling = (
                (np.nansum(hr_chw) / np.nansum(df[Col.CHW_W.value])) * 100
                if np.nansum(df[Col.CHW_W.value]) > 0
                else 0
            )
            logger.debug(
                f"Phase 1 complete: HR WWHP covers {hr_coverage_heating:.1f}% of heating load"
                f" and {hr_coverage_cooling:.1f}% of cooling load"
            )

        # =========================
        # Phase 2 - AWHP Heating
        # =========================
        if scen.awhp:
            logger.debug(f"Phase 2: AWHP Heating using equipment '{scen.awhp}'")
            awhp_h = library.get_equipment(scen.awhp)

            awhp_h_performance_model = scen.awhp_performance_model
            logger.debug(f"AWHP performance calculation model: {awhp_h_performance_model}")

            awhp_h_supply_t = np.array([scen.awhp_h_supply_t])

            awhp_h_performance = _heating_supply_temp_performance(
                awhp_h, awhp_h_supply_t, temps, awhp_h_performance_model
            )

            awhp_cap_h = _per_unit_heating_capacity_W(
                awhp_h, temps, awhp_h_performance, awhp_h_performance_model
            )
            awhp_cop_h = _per_unit_heating_cop(
                awhp_h, temps, awhp_h_performance, awhp_h_performance_model
            )

            # --- Sizing Logic ---
            sizing_mode = scen.awhp_sizing_mode
            sizing_value = scen.awhp_sizing_value
            redundancy = scen.awhp_redundancy

            if scen.awhp_use_cooling:
                sizing_priority = scen.awhp_sizing_priority

                awhp_c = library.get_equipment(scen.awhp)
                # we don't have any HPs with >1 CHWST, this can be edited later to match HHWST if needed
                # this extracts the first value and uses that performance data
                awhp_c_supply_t = next(iter(awhp_c.performance_cooling.leaving_supply_t.keys()))
                # logger.debug(f"AWHP cooling water supply temperature: {awhp_c_supply_t}°C")
                awhp_c_performance = awhp_c.performance_cooling.leaving_supply_t[awhp_c_supply_t]
            else:
                sizing_priority = "heating"

            # Determine reference capacity
            if sizing_priority == "heating":
                sizing_load = "hhw_W"
                cap_ref = _awhp_reference_capacity(awhp_h, awhp_h_performance, awhp_h_supply_t, "heating")
                
            elif sizing_priority == "cooling":
                sizing_load = "chw_W"
                cap_ref = _awhp_reference_capacity(awhp_c, awhp_c_performance, awhp_c_supply_t, "cooling")
            
            elif sizing_priority == "larger" and sizing_mode in [
                "integer_sizing_peak_load",
                "fractional_sizing_peak_load",
            ]:
                cap_ref = {
                    "hhw_W": _awhp_reference_capacity(awhp_h, awhp_h_performance, awhp_h_supply_t, "heating"),
                    "chw_W": _awhp_reference_capacity(awhp_c, awhp_c_performance, awhp_c_supply_t, "cooling")
                }
                num = {
                    "hhw_W": float(df["hhw_W"].max()) * sizing_value / cap_ref["hhw_W"],
                    "chw_W": float(df["chw_W"].max()) * sizing_value / cap_ref["chw_W"]
                }
                sizing_load = max(num, key = num.get)
                cap_ref = cap_ref[sizing_load]

                logger.debug(f"{sizing_load} drives AWHP sizing.")


            # Determine number of units
            if sizing_mode in [
                "integer_sizing_peak_load",
                "fractional_sizing_peak_load",
            ]:
                # Fraction of peak load at reference temperature
                peak_load_W = float(df[sizing_load].max())
                target_load_W = peak_load_W * sizing_value

                if sizing_mode == "integer_sizing_peak_load":
                    awhp_num = np.ceil(target_load_W / cap_ref)
                    awhp_num = int(max(1, awhp_num))  # Ensure at least one unit
                else:
                    awhp_num = target_load_W / cap_ref

            elif sizing_mode == "fixed_num_units":
                awhp_num = np.ceil(sizing_value)
                awhp_num = int(max(1, awhp_num))  # Ensure at least one unit

            awhp_num = max(awhp_num, 0)

            # --- Redundancy Logic ---
            awhp_num_r = awhp_num + redundancy

            logger.debug(
                f"AWHP sizing: priority={sizing_priority}, mode={sizing_mode}, value={sizing_value}, "
                f"units={awhp_num:.2f}, with {redundancy} redundant = {awhp_num_r:.2f} total"
            )

            # capacity calculations use the original sizing number
            cap_total_h_W = awhp_cap_h * awhp_num
            served_h_W = np.minimum(df[Col.HHW_REM_W.value].to_numpy(), cap_total_h_W)
            elec_h_Wh = served_h_W / awhp_cop_h

            # add refrigerant information
            awhp_refrigerant = awhp_h.refrigerant if awhp_h.refrigerant else "Unknown"
            num_hours = len(df)  # Use actual data length (handles leap years)
            total_awhp_refrigerant_weight_kg = (
                awhp_h.refrigerant_weight_g
                * 0.001
                * awhp_num_r
                / num_hours  # emissions calculations use the redundancy sizing number
                if awhp_h.refrigerant_weight_g
                else 0.0
            )

            total_awhp_refrigerant_gwp_kg = (
                awhp_h.refrigerant_gwp * total_awhp_refrigerant_weight_kg
                if awhp_h.refrigerant_gwp
                else 0.0
            )

            if total_awhp_refrigerant_gwp_kg == 0:
                if total_awhp_refrigerant_weight_kg == 0:
                    logger.warning("AWHP refrigerant charge is 0.")
                else:
                    logger.warning("AWHP refrigerant GWP is 0.")

            df[Col.AWHP_HHW_W.value] = served_h_W
            df[Col.AWHP_CAP_H_W.value] = cap_total_h_W
            df[Col.AWHP_COP_H.value] = awhp_cop_h
            df[Col.ELEC_AWHP_H_WH.value] = elec_h_Wh
            df[Col.ELEC_WH.value] += elec_h_Wh
            df[Col.HHW_REM_W.value] -= served_h_W
            df[Col.AWHP_NUM.value] = float(awhp_num)
            df[Col.AWHP_NUM_R.value] = float(awhp_num_r)
            df[Col.AWHP_REFRIGERANT.value] = awhp_refrigerant
            df[Col.AWHP_REFRIGERANT_WEIGHT_KG.value] = total_awhp_refrigerant_weight_kg
            df[Col.AWHP_REFRIGERANT_GWP.value] = total_awhp_refrigerant_gwp_kg

            awhp_h_coverage = (
                (np.nansum(served_h_W) / np.nansum(df[Col.HHW_W.value])) * 100
                if np.nansum(df[Col.HHW_W.value]) > 0
                else 0
            )
            logger.debug(f"Phase 2 complete: AWHP covers {awhp_h_coverage:.1f}% of heating load")

        # =========================
        # Phase 3 - Boiler (optional)
        # =========================
        if scen.backup_heating and scen.backup_heating.fuel == "natural_gas":
            backup_heating = library.get_equipment(scen.backup_heating)

            eff = _constant_heating_efficiency(backup_heating)
            logger.debug(f"Phase 3: Boiler '{backup_heating.eq_id}' with efficiency={eff}")

            boiler_served_W = df[Col.HHW_REM_W].to_numpy()
            gas_Wh = boiler_served_W / eff

            boiler_peak_served_W = np.nanmax(boiler_served_W)
            # sizing logic
            if backup_heating.eq_calc_type == "generic":
                # generic equipment - do not account for space, electric capacity, etc.
                boiler_num = 0
            else:
                # specific equipment model
                boiler_cap = backup_heating.capacity_W
                boiler_num = np.ceil(boiler_peak_served_W / boiler_cap)
                boiler_num = max(boiler_num, 1)  # ensure at least one unit

                logger.debug(f"Gas boiler sizing: {boiler_num:.0f} units")

            df[Col.BOILER_HHW_W.value] = boiler_served_W
            df[Col.GAS_BOILER_WH.value] = gas_Wh
            df[Col.BOILER_EFF.value] = eff
            df[Col.GAS_WH.value] += gas_Wh
            df[Col.HHW_REM_W.value] = 0.0

            boiler_coverage = (
                (np.nansum(boiler_served_W) / np.nansum(df[Col.HHW_W.value])) * 100
                if np.nansum(df[Col.HHW_W.value]) > 0
                else 0
            )
            logger.debug(f"Phase 3 complete: Boiler covers {boiler_coverage:.1f}% of heating load")

        # =========================
        # Phase 4 - Electric resistance (if heating remains)
        # =========================
        remaining_h_W = df[Col.HHW_REM_W.value].to_numpy()
        if np.any(remaining_h_W > 1e-9):
            elec_res_Wh = remaining_h_W  # COP = 1
            remaining_kWh = np.nansum(remaining_h_W) / 1000
            elec_res_coverage = (
                (np.nansum(remaining_h_W) / np.nansum(df[Col.HHW_W.value])) * 100
                if np.nansum(df[Col.HHW_W.value]) > 0
                else 0
            )
            logger.warning(
                f"Phase 4: Electric resistance backup required - "
                f"{remaining_kWh:.1f} kWh ({elec_res_coverage:.1f}% of heating load) unmet by HR/AWHP/Boiler"
            )
            if np.nansum(df[Col.GAS_BOILER_WH.value]) != 0:
                logger.warning("Both gas and electric backup heating equipment are being used.")

            if scen.backup_heating:
                backup_heating = library.get_equipment(scen.backup_heating)
            else:
                generic_backup_heat_id = "res01"
                backup_heating = library.get_equipment(generic_backup_heat_id)

                logger.warning(f"{remaining_kWh:.1f} kWh remaining heating load not served. "
                             f"Generic resistance heater {generic_backup_heat_id} added to equipment scenario {scen.eq_scen_id}.")

            resheater_peak_served_W = np.nanmax(elec_res_Wh)
            # sizing logic
            if backup_heating.eq_calc_type == "generic":
                # generic equipment - do not account for space, electric capacity, etc.
                resheater_num = 0
            else:
                # specific equipment model
                resheater_cap = backup_heating.capacity_W
                resheater_num = np.ceil(resheater_peak_served_W / resheater_cap)
                resheater_num = max(resheater_num, 1)  # ensure at least one unit

                logger.debug(f"Electric resistance heater sizing: {resheater_num:.0f} units")

            df[Col.RES_HHW_W.value] = remaining_h_W
            df[Col.ELEC_RES_WH.value] = elec_res_Wh
            df[Col.ELEC_WH.value] += elec_res_Wh
            df[Col.HHW_REM_W.value] = 0.0

        # =========================
        # Phase 5 - AWHP Cooling
        # =========================
        if scen.awhp and scen.awhp_use_cooling:
            awhp_cap_c = _per_unit_cooling_capacity_W(awhp_c, temps, awhp_c_performance)
            awhp_cop_c = _per_unit_cooling_cop(awhp_c, temps, awhp_c_performance)

            logger.debug(f"Phase 5: AWHP Cooling with {awhp_num:.2f} units")

            # assuming that AWHPs all have 50% turndown (2 compressors)
            awhp_turndown = 0.5
            num_compressors = awhp_num / awhp_turndown
            # calculate number of "compressors" used to serve heating load
            num_compressors_h = np.maximum(0,
                                    np.ceil(
                                        num_compressors
                                        * df[Col.AWHP_HHW_W.value] 
                                        / df[Col.AWHP_CAP_H_W.value]
                                    )
                                )
            num_compressors_h[np.isnan(num_compressors_h)] = 0 # for hours where AWHP heating capacity is 0
            # remaining compressors can serve cooling load
            num_compressors_c = np.maximum(0, num_compressors - num_compressors_h)
            awhp_num_c = num_compressors_c * awhp_turndown # number of compressors available to operate in cooling

            cap_total_c_W = awhp_cap_c * awhp_num_c
            served_c_W = np.minimum(df[Col.CHW_REM_W.value].to_numpy(), cap_total_c_W)

            # Compute electricity only where cooling is served
            elec_c_Wh = served_c_W / awhp_cop_c
            df[Col.AWHP_CHW_W.value] = served_c_W
            df[Col.AWHP_CAP_C_W.value] = cap_total_c_W
            df[Col.AWHP_COP_C.value] = awhp_cop_c
            df[Col.ELEC_AWHP_C_WH.value] = elec_c_Wh
            df[Col.ELEC_WH.value] += elec_c_Wh
            df[Col.CHW_REM_W.value] -= served_c_W
            df[Col.AWHP_NUM_C] = awhp_num_c

            awhp_c_coverage = (
                (np.nansum(served_c_W) / np.nansum(df[Col.CHW_W.value])) * 100
                if np.nansum(df[Col.CHW_W.value]) > 0
                else 0
            )
            logger.debug(f"Phase 5 complete: AWHP covers {awhp_c_coverage:.1f}% of cooling load")

        # =========================
        # Phase 6 - Electric chiller fallback
        # =========================
        if df[Col.CHW_REM_W.value].sum() > 1e-9:
            remaining_c_kWh = df[Col.CHW_REM_W.value].sum() / 1000
            chiller_cop = 5.0  # default

            if scen.chiller:
                logger.debug(
                    f"Phase 6: Chiller '{scen.chiller}' handling {remaining_c_kWh:.1f} kWh remaining cooling"
                )
                chl = library.get_equipment(scen.chiller)
            else:
                generic_chiller_id = "ch01"
                chl = library.get_equipment(generic_chiller_id)

                logger.warning(f"{remaining_c_kWh:.1f} kWh remaining cooling load not served. "
                             f"Generic chiller {generic_chiller_id} added to equipment scenario {scen.eq_scen_id}.")
                # create_warning_notification(
                #     "Unserved Cooling Load",
                #     f"Generic chiller {generic_chiller_id} added to equipment scenario {scen.eq_scen_id}."
                # )
                
            # prefer explicit efficiency (treat as COP for chiller), otherwise try COP curve
            eff = _constant_cooling_efficiency(chl)
            if eff and eff > 0:
                chiller_cop = eff
            else: 
                # not addressing for now but
                # i think this logic skips the sizing/refrigerant calcs below
                # which is not right. fix when curves are added for chillers
                logger.warning(
                    f"Phase 6: Using default chiller COP={chiller_cop} for {remaining_c_kWh:.1f} kWh - no chiller specified"
                )
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

            chl_peak_served_W = np.nanmax(served_W)
            # sizing logic
            if chl.eq_calc_type == "generic":
                # generic equipment - do not account for refrigerant, space, electric capacity, etc.
                chl_num = 0
            else:
                # specific equipment model
                # assumes fixed capacity, edit for curves later
                chl_cap = chl.capacity_W
                chl_num = np.ceil(chl_peak_served_W / chl_cap)
                chl_num = max(chl_num, 1)  # ensure at least one unit

                logger.debug(f"Chiller sizing: {chl_num:.0f} units")

            # add refrigerant information
            chiller_refrigerant = chl.refrigerant if chl.refrigerant else "Unknown"
            num_hours = len(df)  # Use actual data length (handles leap years)

            chiller_refrigerant_weight_kg = (
                chl.refrigerant_weight_g * 0.001 * chl_num / num_hours
                if chl.refrigerant_weight_g
                else 0.0
            )

            chiller_refrigerant_gwp_kg = (
                chl.refrigerant_gwp * chiller_refrigerant_weight_kg if chl.refrigerant_gwp else 0.0
            )

            # this will produce a warning if generic equipment is used
            if chiller_refrigerant_gwp_kg == 0:
                if chiller_refrigerant_weight_kg == 0:
                    logger.warning("Chiller refrigerant charge is 0.")
                else:
                    logger.warning("Chiller refrigerant GWP is 0.")

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

        logger.info(f"Completed loads_to_site for {scenario_id}")

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
        Col.AWHP_NUM.value,
        Col.AWHP_NUM_R.value,
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
) -> pd.DataFrame:
    """
    Convert site energy data (from loads_to_site) into source emissions
    using StandardEmissions data and user EmissionsScenario settings.
    """

    logger.info(
        f"Starting site_to_source: {len(df_loads)} rows of site energy data, "
        f"{len(metadata.list_emission_scenarios())} emission scenarios"
    )

    results = []

    for em_scen_id in metadata.list_emission_scenarios():
        logger.debug(
            f"Processing emission scenario: {em_scen_id}, year={metadata[em_scen_id].year}"
        )

        emissions_data = get_emissions_data(metadata[em_scen_id])
        logger.debug(f"Loaded {len(emissions_data.df)} emission data rows")

        em_scen = metadata[em_scen_id]

        shortrun_weighting = float(em_scen.shortrun_weighting)
        annual_refrig_leakage_percent = float(em_scen.annual_refrig_leakage_percent)
        gas_emissions_rate = float(em_scen.ng_emission_rate_gCO2e_per_kWh)

        # extract date components from loads (keep original year for timestamp reconstruction)
        base = df_loads.copy()
        base[Col.YEAR.value] = base.index.year  # Keep original load data year
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

        nan_count = merged[Col.ELEC_EMISSIONS_RATE_G_PER_KWH].isna().sum()
        if nan_count > 0:
            logger.warning(f"Merge produced {nan_count} rows with missing emission rates")

        # Note: Keep original load data year (already extracted above) for timestamp
        # reconstruction. This avoids Feb 29 errors when leap year load data is
        # used with non-leap emission scenario years. Emissions are still correct
        # because they're matched by month+hour pattern.

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
            merged[Col.TOTAL_REFRIG_GWP_KG.value] = merged[existing_refrig_cols].sum(axis=1)
        else:
            # If none exist, default to zero
            merged[Col.TOTAL_REFRIG_GWP_KG.value] = 0.0

        merged[Col.TOTAL_REFRIG_EMISSIONS_KG_CO2E.value] = (
            merged[Col.TOTAL_REFRIG_GWP_KG.value] * annual_refrig_leakage_percent
        )

        # DEBUGGING CODE TO IDENTIFY BAD TIMESTAMPS
        # # 1. Build the same argument you pass into to_datetime
        # arg = merged[["year", "month", "day", "hour"]].copy()  # adjust cols as needed

        # # 2. Try converting with errors="coerce" to get NaT for bad rows
        # ts = pd.to_datetime(arg, errors="coerce")

        # # 3. Find the rows that failed
        # bad_rows = merged[ts.isna()]

        # print(bad_rows[["year", "month", "day", "hour"]].head())

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

        total_emissions_kg = sum(r[Col.TOTAL_EMISSIONS_KG_CO2E.value].sum() for r in results)
        logger.info(
            f"Completed site_to_source for {em_scen_id}, "
            f"total emissions={total_emissions_kg:.0f} kg CO2e"
        )

    return pd.concat(results, axis=0, ignore_index=False)
