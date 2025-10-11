# any constants used in the analysis
# unit conversions
# all are multiplied, right to left
ton_to_W = 12000 * 0.293  # refrigerant-ton to W
W_to_ton = 1 / ton_to_W
BTUh_to_W = 0.293  # BTU/hr to W
W_to_BTUh = 1 / BTUh_to_W
lbs_to_ton = 0.454 / 1000  # lbs (e.g. of CO2) to metric tons
ton_to_lbs = 1 / lbs_to_ton
lb_to_kg = 0.454  # lbs (e.g. of CO2) to metric tons
kg_to_lb = 1 / lb_to_kg
dC_to_dF = 1.8  # conversion of temperature differences (i.e. delta Ts)
dF_to_dC = 1 / dC_to_dF
cfm_to_lps = 0.47194745  # cfm to l/s
lps_to_cfm = 1 / cfm_to_lps

# fixed emissions conversions factors
# ng_combustion_to_co2e = 5.3*1000/29.3 # 5.3kg/therm to g/kWh (same unit as cambium emissions data, kg/MWh)
# from EPA: https://www.epa.gov/energy/greenhouse-gas-equivalencies-calculator-calculations-and-references
# if including pre-combustion emissions to end use that match Cambium assumptions, increase by 29% (31% reported in paper adjusted to account for newer IPCC AR6 values)
ng_combustion_to_co2e = (
    1.29 * 5.3 * 1000 / 29.3
)  # 5.3kg/therm to g/kWh (same unit as cambium emissions data, kg/MWh)


### CONVERSIONS ###
def C_to_F(c_val):
    return c_val * 1.8 + 32


def F_to_C(f_val):
    return (f_val - 32) / 1.8


def Wh_to_kWh(Wh):
    return Wh / 1000


def Wh_to_BTUh(Wh):
    return Wh * 3.412


def kg_to_lbs(kg):
    return kg * 2.20462


def lbs_to_ton(lbs):
    return lbs / 2000


def kg_to_ton(kg):  # imperial tons
    return kg / 907.185


### COP CONVERSIONS ###


def cop_c_to_cop_h(cop_c_val):
    return cop_c_val + 1


def cop_h_to_cop_c(cop_h_val):
    return cop_h_val - 1


def cop_h_to_cop_hc(cop_h_val):
    return (cop_h_val * 2) - 1


def cop_c_to_cop_hc(cop_c_val):
    return (cop_c_val * 2) + 1


def cop_hc_to_cop_c(cop_hc):
    return (cop_hc - 1) / 2


def cop_hc_to_cop_h(cop_hc):
    return ((cop_hc - 1) / 2) + 1


### MAPPING FOR CHARTS ###
unit_map = {
    "energy": {
        "SI": {
            "func": Wh_to_kWh,
            "label": 'Energy <span style="font-weight:200">| kWh</span>',
        },
        "IP": {
            "func": Wh_to_BTUh,
            "label": 'Energy <span style="font-weight:200">| BTU</span>',
        },
    },
    "temperature": {
        "SI": {
            "func": lambda x: x,
            "label": 'Temperature <span style="font-weight:200">| °C</span>',
        },
        "IP": {
            "func": C_to_F,
            "label": 'Temperature <span style="font-weight:200">| °F</span>',
        },
    },
    "emissions": {
        "SI": {
            "func": lambda x: x,
            "label": 'Emissions <span style="font-weight:200">| kgCO₂e</span>',
        },
        "IP": {
            "func": kg_to_lbs,
            "label": 'Emissions <span style="font-weight:200">| lbCO₂e</span>',
        },
    },
    "gas_emission_factor": {
        "SI": {
            "label": "gCO₂e/kWh",
            "func": lambda x: x,
            "default_value": 239.2,
        },
        "IP": {
            "label": "lbCO₂e/kBTU",
            "func": lambda x: (x / 2.20462) / (1000 * 3.412),  # lbCO₂e/kBTU → kgCO₂e/Wh
            "default_value": 0.01 * (2.20462) / (1000 * 3.412),  #! use function
        },
    },
}
