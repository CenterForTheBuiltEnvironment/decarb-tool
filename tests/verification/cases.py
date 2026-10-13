"""Tool-vs-reference comparison cases shared by the verification test and the report.

Two contrasting library buildings:
  83 - Hospital, New York (NYISO): heating-dominated, cold climate
  35 - Large office, San Francisco (CAISO): mild climate
"""

from dataclasses import dataclass
from functools import cache

import numpy as np
import pandas as pd

from src import paths
from src.config import Columns as Col
from src.emissions import EmissionScenario
from src.energy import loads_to_site_energy, site_to_source
from src.equipment import load_library
from src.loads import get_load_data
from src.metadata import LoadData, Metadata
from tests.verification import reference_model as ref

BUILDINGS = {"83": "NYISO", "35": "CAISO"}
SCENARIOS = ref.SUPPORTED_SCENARIOS
NG_RATE = 239.2  # gCO2e/kWh, app default
LEAKAGE = 0.05  # app default

GRIDS = {
    "constant_400": dict(source="constant", constant_rate=400.0),
    "cambium_lrmer_2025": dict(source="lrmer", grid_scenario="MidCase", year=2025),
}

TOOL_SOURCE = {
    "constant": "Constant (User-provided)",
    "lrmer": "Marginal (Cambium, Long-run)",
    "srmer": "Marginal (Cambium, Short-run)",
    "average": "Average (Cambium)",
}

METRICS = ("elec_kWh", "gas_kWh", "elec_kgCO2e", "gas_kgCO2e", "refrig_kgCO2e", "total_kgCO2e")


@dataclass(frozen=True)
class Case:
    building_id: str
    scenario_id: str
    grid: str

    @property
    def id(self) -> str:
        return f"b{self.building_id}-{self.scenario_id}-{self.grid}"


ALL_CASES = [Case(b, s, g) for b in BUILDINGS for s in SCENARIOS for g in GRIDS]


def _tool_metadata(case: Case) -> Metadata:
    grid = GRIDS[case.grid]
    return Metadata.create(
        building_id=case.building_id,
        load_data=LoadData(load_type="simulated"),
        emission_settings=[
            EmissionScenario(
                em_scen_id="em_verification",
                em_scen_name=case.grid,
                elec_emission_source=TOOL_SOURCE[grid["source"]],
                elec_avg_emission_rate_gCO2e_per_kWh=grid.get("constant_rate"),
                grid_scenario=grid.get("grid_scenario"),
                gea_grid_region=BUILDINGS[case.building_id],
                emission_type="Includes pre-combustion",
                annual_refrig_leakage_percent=LEAKAGE,
                ng_emission_rate_gCO2e_per_kWh=NG_RATE,
                year=grid.get("year", 2025),
            )
        ],
    )


@cache
def _tool_library():
    return load_library(paths.EQUIPMENT_JSON)


def tool_result(case: Case) -> dict[str, float]:
    """Run the tool along the same call chain the Results page uses."""
    metadata = _tool_metadata(case)
    site = loads_to_site_energy(
        get_load_data(metadata), _tool_library(), [case.scenario_id], detail=True
    )
    out = site_to_source(site, metadata=metadata)
    return {
        "elec_kWh": out[Col.ELEC_WH.value].sum() / 1000,
        "gas_kWh": out[Col.GAS_WH.value].sum() / 1000,
        "elec_kgCO2e": out[Col.ELEC_EMISSIONS_KG_CO2E.value].sum(),
        "gas_kgCO2e": out[Col.GAS_EMISSIONS_KG_CO2E.value].sum(),
        "refrig_kgCO2e": out[Col.TOTAL_REFRIG_EMISSIONS_KG_CO2E.value].sum(),
        "total_kgCO2e": out[Col.TOTAL_EMISSIONS_KG_CO2E.value].sum(),
    }


@cache
def _ref_inputs(building_id: str):
    equipment, scenarios = ref.read_library()
    return equipment, scenarios, ref.read_building_load(building_id)


def reference_result(case: Case) -> dict[str, float]:
    equipment, scenarios, load = _ref_inputs(case.building_id)
    grid = GRIDS[case.grid]
    rate = ref.hourly_grid_rate(
        load["timestamp"],
        source=grid["source"],
        constant_rate=grid.get("constant_rate"),
        grid_scenario=grid.get("grid_scenario"),
        region=BUILDINGS[case.building_id],
        year=grid.get("year"),
    )
    return ref.run(load, scenarios[case.scenario_id], equipment, rate, NG_RATE, LEAKAGE)


def relative_difference(tool: float, reference: float) -> float:
    if reference == 0:
        return 0.0 if abs(tool) < 1e-6 else np.inf
    return (tool - reference) / reference


def comparison_table(cases=ALL_CASES) -> pd.DataFrame:
    rows = []
    for case in cases:
        tool, reference = tool_result(case), reference_result(case)
        for metric in METRICS:
            rows.append(
                {
                    "building": case.building_id,
                    "scenario": case.scenario_id,
                    "grid": case.grid,
                    "metric": metric,
                    "tool": tool[metric],
                    "reference": reference[metric],
                    "rel_diff": relative_difference(tool[metric], reference[metric]),
                }
            )
    return pd.DataFrame(rows)
