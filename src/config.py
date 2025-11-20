from enum import Enum


class URLS(Enum):
    HOME: str = "/"
    EQUIPMENT: str = "/equipment"
    EMISSIONS: str = "/emissions"
    RESULTS: str = "/results"


class LINKS(Enum):
    DOCS_URL: str = (
        "https://github.com/CenterForTheBuiltEnvironment/decarb-tool/blob/main/docs/documentation-short.md"
    )


class Columns(str, Enum):
    # --- Core time & scenario metadata ---
    TIMESTAMP = "timestamp"
    YEAR = "year"
    MONTH = "month"
    DAY = "day"
    HOUR = "hour"
    DOY = "doy"
    EQ_SCEN_ID = "eq_scen_id"
    EQ_SCEN_NAME = "eq_scen_name"
    EM_SCEN_ID = "em_scen_id"

    # --- Environmental conditions ---
    T_OUT_C = "t_out_C"

    # --- Load data ---
    HEATING_W = "heating_W"
    COOLING_W = "cooling_W"

    # --- Heating & cooling water loops ---
    HHW_W = "hhw_W"
    CHW_W = "chw_W"
    HHW_REM_W = "hhw_rem_W"
    CHW_REM_W = "chw_rem_W"

    # --- Heat Recovery Water-to-Water Heat Pump (H+C) ---
    HR_HHW_W = "hr_hhw_W"
    HR_CHW_W = "hr_chw_W"
    HR_COP_H = "hr_cop_h"
    MAX_CAP_H_HR_W = "max_cap_h_hr_W"
    MIN_CAP_H_HR_W = "min_cap_h_hr_W"
    SIMULT_H_HR_W = "simult_h_hr_W"
    ELEC_HR_WH = "elec_hr_Wh"

    # --- Air–Water Heat Pump (Heating) ---
    AWHP_NUM_H = "awhp_num_h"
    AWHP_CAP_H_W = "awhp_cap_h_W"
    AWHP_COP_H = "awhp_cop_h"
    AWHP_HHW_W = "awhp_hhw_W"
    ELEC_AWHP_H_WH = "elec_awhp_h_Wh"

    # --- Boiler ---
    BOILER_EFF = "boiler_eff"
    BOILER_HHW_W = "boiler_hhw_W"
    GAS_BOILER_WH = "gas_boiler_Wh"

    # --- Resistance heater backup ---
    RES_HHW_W = "res_hhw_W"
    ELEC_RES_WH = "elec_res_Wh"

    # --- Air–Water Heat Pump (Cooling) ---
    AWHP_NUM_C = "awhp_num_c"
    AWHP_CAP_C_W = "awhp_cap_c_W"
    AWHP_COP_C = "awhp_cop_c"
    AWHP_CHW_W = "awhp_chw_W"
    ELEC_AWHP_C_WH = "elec_awhp_c_Wh"

    # --- Chiller backup ---
    CHILLER_COP = "chiller_cop"
    CHILLER_CHW_W = "chiller_chw_W"
    ELEC_CHILLER_WH = "elec_chiller_Wh"

    # --- Energy (general) ---
    ELEC_WH = "elec_Wh"
    GAS_WH = "gas_Wh"

    # --- Refrigerant (general) ---
    HR_WWHP_REFRIGERANT = "hr_wwhp_refrigerant"
    HR_WWHP_REFRIGERANT_WEIGHT_KG = "hr_wwhp_refrigerant_weight_kg"
    HR_WWHP_REFRIGERANT_GWP = "hr_wwhp_refrigerant_gwp_kgCO2e_per_kgRefrig"
    AWHP_REFRIGERANT = "awhp_refrigerant"
    AWHP_REFRIGERANT_WEIGHT_KG = "total_awhp_refrigerant_weight_kg"
    AWHP_REFRIGERANT_GWP = "total_awhp_refrigerant_gwp_kgCO2e_per_kgRefrig"
    CHILLER_REFRIGERANT = "chiller_refrigerant"
    CHILLER_REFRIGERANT_WEIGHT_KG = "chiller_refrigerant_weight_kg"
    CHILLER_REFRIGERANT_GWP = "chiller_refrigerant_gwp_kgCO2e_per_kgRefrig"

    # --- Emissions & energy rates ---
    LRMER_CO2E_C = "lrmer_co2e_c"
    LRMER_CO2E_P = "lrmer_co2e_p"
    LRMER_CO2E = "lrmer_co2e"
    SRMER_CO2E_C = "srmer_co2e_c"
    SRMER_CO2E_P = "srmer_co2e_p"
    SRMER_CO2E = "srmer_co2e"
    SHORTRUN_WEIGHTING = "shortrun_weighting"
    ELEC_EMISSIONS_RATE_G_PER_KWH = "elec_emissions_rate_gCO2e_per_kWh"

    # --- Resulting emissions summary ---
    ELEC_EMISSIONS_KG_CO2E = "elec_emissions"
    GAS_EMISSIONS_KG_CO2E = "gas_emissions"
    TOTAL_REFRIG_GWP_KG = "total_refrig_gwp_kg"
    TOTAL_REFRIG_EMISSIONS_KG_CO2E = "total_refrig_emissions"
    TOTAL_EMISSIONS_KG_CO2E = "total_emissions"
