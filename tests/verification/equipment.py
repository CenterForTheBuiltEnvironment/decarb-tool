"""Frozen, test-owned equipment for hand-calculated verification cases.

These definitions deliberately do NOT come from data/input/equipment_data.JSON:
editing the production library must never break the verification tier. Values
are round numbers so every expected result in test_verification_handcalc.py
can be written as a one-line formula.

AWHP "V-AWHP" heating table at HHWST 40 °C (operating range -10 … 30 °C OAT):

    OAT [°C]        -10     0     10     20
    COP             2.0   2.5    3.0    4.0
    Capacity [kW]    50    60     70     80

AWHP "V-AWHP" cooling table at CHWST 7 °C (operating range 10 … 45 °C OAT):

    OAT [°C]         20    30     40
    COP             5.0   4.0    3.0
    Capacity [kW]   100    90     80
"""

from src.equipment import EquipmentLibrary

BOILER_EFF = 0.8
BOILER_CAP_W = 100_000.0
CHILLER_COP = 4.0
CHILLER_CAP_W = 500_000.0
CHILLER_REFRIG_KG = 100.0
CHILLER_GWP = 1000.0
AWHP_REFRIG_KG = 20.0
AWHP_GWP = 500.0

AWHP_H_T = [-10.0, 0.0, 10.0, 20.0]
AWHP_H_COP = [2.0, 2.5, 3.0, 4.0]
AWHP_H_CAP_W = [50_000.0, 60_000.0, 70_000.0, 80_000.0]
AWHP_H_MIN_T, AWHP_H_MAX_T = -10.0, 30.0

AWHP_C_T = [20.0, 30.0, 40.0]
AWHP_C_COP = [5.0, 4.0, 3.0]
AWHP_C_CAP_W = [100_000.0, 90_000.0, 80_000.0]
AWHP_C_MIN_T, AWHP_C_MAX_T = 10.0, 45.0

_EQUIPMENT = [
    {
        "eq_id": "v_boiler",
        "eq_type": "backup_heating",
        "eq_calc_type": "specific",
        "model": "Verification gas boiler",
        "fuel": "natural_gas",
        "capacity_W": BOILER_CAP_W,
        "performance": {"heating": {"efficiency": BOILER_EFF}},
    },
    {
        "eq_id": "v_resistance",
        "eq_type": "backup_heating",
        "eq_calc_type": "generic",
        "model": "Verification electric resistance",
        "fuel": "electricity",
        "performance": {"heating": {"efficiency": 1.0}},
    },
    {
        "eq_id": "v_chiller",
        "eq_type": "chiller",
        "eq_calc_type": "specific",
        "model": "Verification chiller",
        "fuel": "electricity",
        "capacity_W": CHILLER_CAP_W,
        "refrigerant": "R-test",
        "refrigerant_weight_g": CHILLER_REFRIG_KG * 1000,
        "refrigerant_gwp": CHILLER_GWP,
        "performance": {"cooling": {"efficiency": CHILLER_COP}},
    },
    {
        "eq_id": "v_awhp",
        "eq_type": "heat_pump",
        "eq_calc_type": "specific",
        "model": "Verification AWHP",
        "fuel": "electricity",
        "refrigerant": "R-test",
        "refrigerant_weight_g": AWHP_REFRIG_KG * 1000,
        "refrigerant_gwp": AWHP_GWP,
        "performance": {
            "heating": {
                "t_out_C": AWHP_H_T,
                "leaving_supply_t": {
                    "40": {
                        "cop": AWHP_H_COP,
                        "capacity_W": AWHP_H_CAP_W,
                        "constraints": {"min_temp_C": AWHP_H_MIN_T, "max_temp_C": AWHP_H_MAX_T},
                    }
                },
                "constraints": {"min_temp_C": 40, "max_temp_C": 40},
            },
            "cooling": {
                "t_out_C": AWHP_C_T,
                "leaving_supply_t": {
                    "7": {
                        "cop": AWHP_C_COP,
                        "capacity_W": AWHP_C_CAP_W,
                        "constraints": {"min_temp_C": AWHP_C_MIN_T, "max_temp_C": AWHP_C_MAX_T},
                    }
                },
                "constraints": {"min_temp_C": 7, "max_temp_C": 7},
            },
        },
    },
]

_SCENARIO_DEFAULTS = {
    "hr_wwhp": None,
    "awhp": None,
    "awhp_performance_model": "interpolate_HHWST_fixed",
    "awhp_h_supply_t": 40.0,
    "awhp_sizing_mode": "integer_sizing_peak_load",
    "awhp_sizing_value": 1.0,
    "awhp_redundancy": 1,
    "awhp_use_cooling": False,
    "awhp_sizing_priority": "heating",
    "backup_heating": "v_boiler",
    "fuel_switching": False,
    "chiller": "v_chiller",
}

_SCENARIOS = {
    "v_baseline": {"eq_scen_name": "Gas boiler + chiller"},
    "v_awhp_gas": {"eq_scen_name": "AWHP (H) + gas backup + chiller", "awhp": "v_awhp"},
    "v_awhp_hc_elec": {
        "eq_scen_name": "AWHP (H+C) + electric backup + chiller",
        "awhp": "v_awhp",
        "awhp_use_cooling": True,
        "backup_heating": "v_resistance",
    },
    "v_awhp_fuel_switching": {
        "eq_scen_name": "AWHP (H) + gas backup, fuel switching",
        "awhp": "v_awhp",
        "fuel_switching": True,
    },
}


def verification_library() -> EquipmentLibrary:
    """Fresh EquipmentLibrary containing only the frozen verification equipment."""
    scenarios = [
        {"eq_scen_id": sid, **_SCENARIO_DEFAULTS, **overrides}
        for sid, overrides in _SCENARIOS.items()
    ]
    return EquipmentLibrary(equipment=_EQUIPMENT, equipment_scenarios=scenarios)
