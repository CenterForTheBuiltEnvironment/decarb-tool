from typing import Dict, List, Literal, Optional, Any, Union
from pydantic import BaseModel
from pathlib import Path
import json
from datetime import datetime


class EmissionScenario(BaseModel):
    em_scen_id: str
    grid_scenario: str
    gea_grid_region: str
    time_zone: str
    emission_type: str
    shortrun_weighting: float
    annual_refrig_leakage: float
    annual_ng_leakage: float
    year: int


class Metadata(BaseModel):
    location: str
    building_type: str
    vintage: int
    load_type: str
    ashrae_climate_zone: str
    equipment_scenarios: Union[str, List[str]]
    emission_settings: List[EmissionScenario]
    units: str
    last_updated: str

    # ---------- Factory ----------
    @classmethod
    def create(cls, **overrides: Any) -> "Metadata":
        defaults = dict(
            location="Berkeley",
            building_type="OfficeLarge",
            vintage=2022,
            load_type="load_simulated",
            ashrae_climate_zone="3C",
            equipment_scenarios="baseline_01",
            emission_settings=[
                EmissionScenario(
                    em_scen_id="em_scenario_a",
                    grid_scenario="MidCase",
                    gea_grid_region="CAISO",
                    time_zone="America/Los_Angeles",
                    emission_type="Combustion only",
                    shortrun_weighting=1.0,
                    annual_refrig_leakage=0.01,
                    annual_ng_leakage=0.005,
                    year=2025,
                ),
                EmissionScenario(
                    em_scen_id="em_scenario_b",
                    grid_scenario="MidCase",
                    gea_grid_region="CAISO",
                    time_zone="America/Los_Angeles",
                    emission_type="Combustion only",
                    shortrun_weighting=0.5,
                    annual_refrig_leakage=0.01,
                    annual_ng_leakage=0.005,
                    year=2035,
                ),
                EmissionScenario(
                    em_scen_id="em_scenario_c",
                    grid_scenario="MidCase",
                    gea_grid_region="CAISO",
                    time_zone="America/Los_Angeles",
                    emission_type="Combustion only",
                    shortrun_weighting=0.5,
                    annual_refrig_leakage=0.01,
                    annual_ng_leakage=0.005,
                    year=2045,
                ),
            ],
            units="SI",
            last_updated=datetime.utcnow().isoformat(),
        )
        defaults.update(overrides)
        return cls(**defaults)

    # ---------- JSON I/O ----------
    def save_json(self, file_path: Path):
        """Save metadata to JSON file."""
        self.last_updated = datetime.utcnow().isoformat()
        data = self.model_dump()
        with Path(file_path).open("w") as f:
            json.dump(data, f, indent=2)

    @classmethod
    def load_json(cls, file_path: Path) -> "Metadata":
        with Path(file_path).open("r") as f:
            data = json.load(f)
        return cls(**data)

    # ---------- Scenario helpers ----------
    def get_emission_scenario(self, scen_id: str) -> EmissionScenario:
        for scen in self.emission_settings:
            if scen.em_scen_id == scen_id:
                return scen
        raise KeyError(f"EmissionScenario {scen_id!r} not found")

    def list_emission_scenarios(self) -> List[str]:
        return [s.em_scen_id for s in self.emission_settings]

    def add_emission_scenario(self, scenario: EmissionScenario, overwrite: bool = True):
        """Add a new scenario. Overwrites existing if `overwrite=True`."""
        existing = [
            s for s in self.emission_settings if s.em_scen_id == scenario.em_scen_id
        ]
        if existing:
            if overwrite:
                self.emission_settings = [
                    scenario if s.em_scen_id == scenario.em_scen_id else s
                    for s in self.emission_settings
                ]
            else:
                raise ValueError(f"Scenario {scenario.em_scen_id!r} already exists")
        else:
            self.emission_settings.append(scenario)

    # ---------- Dict-like interface ----------
    def __getitem__(self, em_scen_id: str) -> EmissionScenario:
        return self.get_emission_scenario(em_scen_id)

    def __contains__(self, em_scen_id: str) -> bool:
        return any(s.em_scen_id == em_scen_id for s in self.emission_settings)

    def __iter__(self):
        return iter(self.emission_settings)
