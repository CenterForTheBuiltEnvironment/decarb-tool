"""Independent reference implementation of the documented calculation method.

Written from docs/documentation/calculations.md and equipment.md, NOT from
src/energy.py, and deliberately imports nothing from src/. It reads the raw
equipment JSON, load parquet and Cambium parquet directly with json/pandas.
Agreement between this model and the tool therefore checks that the tool
implements its documented method correctly (an N-version comparison). It does
not validate the method itself against measured or EnergyPlus results.

Scope (kept narrow to limit maintenance): scenarios without heat recovery,
fixed HHWST at a catalogue supply temperature, integer peak-load sizing,
gas or electric resistance backup, constant-COP chiller, no fuel switching.
That covers eq_scenario_1, eq_scenario_3 and eq_scenario_4.

Method details the user docs leave implicit, taken from the equipment
specification and listed here so they can be reviewed:
  * AWHP heating sizing reference capacity is the catalogue capacity at 0 °C OAT;
    cooling reference is at 30 °C OAT.
  * Performance tables are interpolated linearly in OAT and held constant
    beyond the first/last table point; capacity is zero outside the unit's
    operating OAT limits.
  * Each AWHP has two compressors (50 % turndown). Compressors needed for
    heating in an hour = ceil(2 n * heat_served / heat_capacity); the rest cool.
  * Refrigerant charge counts all AWHP units including redundancy, and chiller
    units = ceil(peak chiller load / unit capacity) when the chiller runs.
  * Cambium rates are averaged to month x hour and mapped onto the load's
    month and hour.
"""

import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

DATA = Path(__file__).resolve().parents[2] / "data" / "input"
EQUIPMENT_JSON = DATA / "equipment_data.JSON"
LOAD_PARQUET = DATA / "load_data_full.parquet"
EMISSION_PARQUET = DATA / "emission_data.parquet"

SUPPORTED_SCENARIOS = ("eq_scenario_1", "eq_scenario_3", "eq_scenario_4")


def read_library(path: Path = EQUIPMENT_JSON) -> tuple[dict, dict]:
    raw = json.loads(Path(path).read_text())
    equipment = {e["eq_id"]: e for e in raw["equipment"]}
    scenarios = {s["eq_scen_id"]: s for s in raw["equipment_scenarios"]}
    return equipment, scenarios


def read_building_load(building_id: str, source: str = "simulated") -> pd.DataFrame:
    df = pd.read_parquet(
        LOAD_PARQUET,
        columns=["building_id", "source", "timestamp", "t_out_C", "heating_W", "cooling_W"],
        filters=[("building_id", "=", building_id), ("source", "=", source)],
    )
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    return df.sort_values("timestamp").reset_index(drop=True)


def hourly_grid_rate(
    timestamps: pd.Series,
    source: str,
    constant_rate: float | None = None,
    grid_scenario: str | None = None,
    region: str | None = None,
    year: int | None = None,
    include_precombustion: bool = True,
) -> np.ndarray:
    """Electricity emission rate [gCO2e/kWh] for each load hour."""
    if source == "constant":
        return np.full(len(timestamps), float(constant_rate))

    prefix = {"lrmer": "lrmer_co2e", "srmer": "srmer_co2e", "average": "aer_load_co2e"}[source]
    cols = [f"{prefix}_c"] + ([f"{prefix}_p"] if include_precombustion else [])
    em = pd.read_parquet(
        EMISSION_PARQUET,
        columns=["emission_scenario", "gea_grid_region", "year", "month", "hour", *cols],
        filters=[
            ("emission_scenario", "=", grid_scenario),
            ("gea_grid_region", "=", region),
            ("year", "=", year),
        ],
    )
    em["rate"] = em[cols].sum(axis=1)
    month_hour = em.groupby(["month", "hour"])["rate"].mean()
    keys = pd.MultiIndex.from_arrays([timestamps.dt.month, timestamps.dt.hour])
    return month_hour.reindex(keys).to_numpy()


def _table(perf: dict, supply_t: float) -> tuple[np.ndarray, np.ndarray, np.ndarray, float, float]:
    """(t_out, cop, capacity, min_t, max_t) for an exact catalogue supply temperature."""
    match = [k for k in perf["leaving_supply_t"] if math.isclose(float(k), float(supply_t))]
    if not match:
        raise NotImplementedError(
            f"Reference model needs a catalogue supply temperature, got {supply_t}"
        )
    curve = perf["leaving_supply_t"][match[0]]
    t = np.asarray(perf["t_out_C"], dtype=float)
    order = np.argsort(t)
    return (
        t[order],
        np.asarray(curve["cop"], dtype=float)[order],
        np.asarray(curve["capacity_W"], dtype=float)[order],
        float(curve["constraints"]["min_temp_C"]),
        float(curve["constraints"]["max_temp_C"]),
    )


def _lookup(t_tab, values, t_out):
    return np.interp(t_out, t_tab, values)  # np.interp holds end values constant


def _capacity(t_tab, cap_tab, t_min, t_max, t_out):
    cap = _lookup(t_tab, cap_tab, t_out)
    cap[(t_out < t_min) | (t_out > t_max)] = 0.0
    return cap


def run(
    load: pd.DataFrame,
    scenario: dict,
    equipment: dict,
    grid_rate_g_per_kWh: np.ndarray,
    ng_rate_g_per_kWh: float,
    leakage_fraction: float,
) -> dict[str, float]:
    """Annual site energy [kWh] and emissions [kgCO2e] for one scenario."""
    if scenario.get("hr_wwhp") or scenario.get("fuel_switching"):
        raise NotImplementedError("Reference model excludes heat recovery and fuel switching")
    if scenario.get("awhp") and scenario["awhp_sizing_mode"] != "integer_sizing_peak_load":
        raise NotImplementedError("Reference model supports integer peak-load sizing only")

    t_out = load["t_out_C"].to_numpy(dtype=float)
    heat = load["heating_W"].to_numpy(dtype=float)
    cool = load["cooling_W"].to_numpy(dtype=float)

    elec_Wh = np.zeros_like(heat)
    gas_Wh = np.zeros_like(heat)
    heat_rem = heat.copy()
    cool_rem = cool.copy()
    refrigerant_kg_co2e = 0.0  # full charge x GWP, before leakage

    # --- AWHP heating ---
    if scenario.get("awhp"):
        hp = equipment[scenario["awhp"]]
        t_h, cop_h_tab, cap_h_tab, h_min, h_max = _table(
            hp["performance"]["heating"], scenario["awhp_h_supply_t"]
        )
        ref_cap = float(np.interp(0.0, t_h, cap_h_tab))
        units = max(1, math.ceil(heat_rem.max() * scenario["awhp_sizing_value"] / ref_cap))

        cap_h = units * _capacity(t_h, cap_h_tab, h_min, h_max, t_out)
        served_h = np.minimum(heat_rem, cap_h)
        elec_Wh += served_h / _lookup(t_h, cop_h_tab, t_out)
        heat_rem -= served_h

        total_units = units + scenario["awhp_redundancy"]
        refrigerant_kg_co2e += (
            hp["refrigerant_weight_g"] / 1000 * total_units * hp["refrigerant_gwp"]
        )

    # --- backup heating ---
    backup = equipment[scenario["backup_heating"]]
    if backup["fuel"] == "natural_gas":
        gas_Wh += heat_rem / backup["performance"]["heating"]["efficiency"]
    else:
        elec_Wh += heat_rem  # electric resistance, 100 % efficient
    heat_rem[:] = 0.0

    # --- AWHP cooling with the compressors not needed for heating ---
    if scenario.get("awhp") and scenario["awhp_use_cooling"]:
        cperf = hp["performance"]["cooling"]
        chwst = next(iter(cperf["leaving_supply_t"]))
        t_c, cop_c_tab, cap_c_tab, c_min, c_max = _table(cperf, float(chwst))

        compressors = 2 * units
        with np.errstate(divide="ignore", invalid="ignore"):
            used = np.where(cap_h > 0, np.ceil(compressors * served_h / cap_h), 0.0)
        cooling_units = (compressors - used) / 2
        served_c = np.minimum(
            cool_rem, cooling_units * _capacity(t_c, cap_c_tab, c_min, c_max, t_out)
        )
        elec_Wh += served_c / _lookup(t_c, cop_c_tab, t_out)
        cool_rem -= served_c

    # --- chiller ---
    chiller = equipment[scenario["chiller"]]
    if cool_rem.sum() > 0:
        elec_Wh += cool_rem / chiller["performance"]["cooling"]["efficiency"]
        if chiller.get("eq_calc_type") == "specific" and chiller.get("refrigerant_weight_g"):
            n_chillers = max(1, math.ceil(cool_rem.max() / chiller["capacity_W"]))
            refrigerant_kg_co2e += (
                chiller["refrigerant_weight_g"] / 1000 * n_chillers * chiller["refrigerant_gwp"]
            )

    elec_kWh = elec_Wh.sum() / 1000
    gas_kWh = gas_Wh.sum() / 1000
    elec_kg = float((elec_Wh / 1000 * grid_rate_g_per_kWh).sum() / 1000)
    gas_kg = gas_kWh * ng_rate_g_per_kWh / 1000
    refrig_kg = refrigerant_kg_co2e * leakage_fraction
    return {
        "elec_kWh": float(elec_kWh),
        "gas_kWh": float(gas_kWh),
        "elec_kgCO2e": elec_kg,
        "gas_kgCO2e": float(gas_kg),
        "refrig_kgCO2e": float(refrig_kg),
        "total_kgCO2e": elec_kg + float(gas_kg) + float(refrig_kg),
    }
