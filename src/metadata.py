import json
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from src.emissions import EmissionScenario
from src.mixins import DotAccessMixin


class LoadData(BaseModel):
    load_type: str | None = None
    max_temp: float | None = None
    median_temp: float | None = None
    min_temp: float | None = None
    annual_heating_cooling_ratio: float | None = None
    chw_annual_load: float | None = None
    chw_data_coverage: float | None = None
    chw_max_load: float | None = None
    chw_max_load_per_area: float | None = None
    chw_mean_load: float | None = None
    chw_median_load: float | None = None
    chw_min_load: float | None = None
    chw_pct_below_10pct_max: float | None = None
    chw_pct_below_20pct_max: float | None = None
    chw_pct_below_30pct_max: float | None = None
    chw_pct_below_40pct_max: float | None = None
    chw_pct_below_50pct_max: float | None = None
    chw_pct_below_60pct_max: float | None = None
    chw_pct_below_70pct_max: float | None = None
    chw_pct_below_80pct_max: float | None = None
    chw_pct_below_90pct_max: float | None = None
    chw_q25_load: float | None = None
    chw_q75_load: float | None = None
    chw_valid_hours: int | None = None
    heat_recovery_heating_fraction: float | None = None
    hhw_annual_load: float | None = None
    hhw_data_coverage: float | None = None
    hhw_max_load: float | None = None
    hhw_max_load_per_area: float | None = None
    hhw_mean_load: float | None = None
    hhw_median_load: float | None = None
    hhw_min_load: float | None = None
    hhw_pct_below_10pct_max: float | None = None
    hhw_pct_below_20pct_max: float | None = None
    hhw_pct_below_30pct_max: float | None = None
    hhw_pct_below_40pct_max: float | None = None
    hhw_pct_below_50pct_max: float | None = None


class Metadata(DotAccessMixin, BaseModel):
    building_id: str | None = None
    location: str | None = None
    building_type: str | None = None
    vintage: str | None = None
    ashrae_climate_zone: str | None = None
    climate_zone_output: str | None = None
    area_sqm: float | None
    load_data: LoadData
    equipment_scenarios: str | list[str]
    emission_settings: list[EmissionScenario]
    units: str
    last_updated: str
    custom_load_path: str | None = None  # Path to custom load data file if load_type='load_custom'

    @property
    def base_gea_grid_region(self) -> str | None:
        """Assumes all emission scenarios share the same grid region."""
        if not self.emission_settings:
            return None
        return self.emission_settings[0].gea_grid_region

    # ---------- Factory ----------
    @classmethod
    def create(cls, **overrides: Any) -> "Metadata":
        defaults = dict(
            location=None,
            building_type=None,
            vintage=None,
            ashrae_climate_zone=None,
            area_sqm=None,
            load_data=LoadData(
                load_type=None,
                # All other fields default to None
            ),
            equipment_scenarios=[
                "eq_scenario_1",
                "eq_scenario_2",
                "eq_scenario_3",
                "eq_scenario_4",
                "eq_scenario_5",
            ],
            emission_settings=[
                EmissionScenario(
                    em_scen_id="em_scenario_a",
                    em_scen_name="2025",
                    grid_scenario="MidCase",
                    gea_grid_region=None,
                    time_zone="America/Los_Angeles",
                    emission_type="Includes pre-combustion",
                    shortrun_weighting=0,
                    annual_refrig_leakage_percent=0.05,
                    ng_emission_rate_gCO2e_per_kWh=239.2,
                    year=2025,
                ),
                EmissionScenario(
                    em_scen_id="em_scenario_b",
                    em_scen_name="2035",
                    grid_scenario="MidCase",
                    gea_grid_region=None,
                    time_zone="America/Los_Angeles",
                    emission_type="Includes pre-combustion",
                    shortrun_weighting=0,
                    annual_refrig_leakage_percent=0.05,
                    ng_emission_rate_gCO2e_per_kWh=239.2,
                    year=2035,
                ),
                EmissionScenario(
                    em_scen_id="em_scenario_c",
                    em_scen_name="2045",
                    grid_scenario="MidCase",
                    gea_grid_region=None,
                    time_zone="America/Los_Angeles",
                    emission_type="Includes pre-combustion",
                    shortrun_weighting=0,
                    annual_refrig_leakage_percent=0.05,
                    ng_emission_rate_gCO2e_per_kWh=239.2,
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

    def list_emission_scenarios(self) -> list[str]:
        return [s.em_scen_id for s in self.emission_settings]

    def add_emission_scenario(self, scenario: EmissionScenario, overwrite: bool = True):
        """Add a new scenario. Overwrites existing if `overwrite=True`."""
        existing = [s for s in self.emission_settings if s.em_scen_id == scenario.em_scen_id]
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

    def set_gea_grid_region_for_all(self, region: str) -> None:
        for scen in self.emission_settings:
            scen.gea_grid_region = region

    # ---------- Dict-like interface ----------
    def __getitem__(self, em_scen_id: str) -> EmissionScenario:
        return self.get_emission_scenario(em_scen_id)

    def __contains__(self, em_scen_id: str) -> bool:
        return any(s.em_scen_id == em_scen_id for s in self.emission_settings)

    def __iter__(self):
        return iter(self.emission_settings)
