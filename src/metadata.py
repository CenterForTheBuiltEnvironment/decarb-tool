from typing import List, Literal, Optional, Any
from pydantic import BaseModel
from pathlib import Path
import json
from datetime import datetime


class EmissionsSettings(BaseModel):
    emission_scenario: str
    gea_grid_region: str
    time_zone: str
    emission_type: str
    shortrun_weighting: float
    years: List[int]


class Metadata(BaseModel):
    location: str
    building_type: str
    vintage: int
    load_type: str
    ashrae_climate_zone: str
    equipment_scenario: str
    emissions: EmissionsSettings
    units: str
    last_updated: str

    @classmethod
    def create(cls, **overrides: Any) -> "Metadata":
        """
        Factory for default session metadata.

        Parameters
        ----------
        overrides : dict
            Any field in Metadata you want to override.
            Example: Metadata.default(location="US_NY_NewYork")

        Returns
        -------
        Metadata
            A Metadata object with default values, with optional overrides applied.
        """
        defaults = dict(
            location="US_CA_SanFrancisco",
            building_type="office",
            vintage=2022,
            load_type="load_simulated",
            ashrae_climate_zone="3C",
            equipment_scenario="baseline_01",
            emissions=EmissionsSettings(
                emission_scenario="MidCase",
                gea_grid_region="CAISO",
                time_zone="America/Los_Angeles",
                emission_type="Combustion only",
                shortrun_weighting=1.0,
                years=[2025, 2030, 2040],
            ),
            units="SI",
            last_updated=datetime.utcnow().isoformat(),
        )
        defaults.update(overrides)
        return cls(**defaults)

    def save_json(self, file_path: Path):
        """Save metadata to JSON file."""
        self.last_updated = datetime.utcnow().isoformat()
        with Path(file_path).open("w") as f:
            json.dump(self.dict(), f, indent=2)

    @classmethod
    def load_json(cls, file_path: Path) -> "Metadata":
        """Load metadata from JSON file."""
        with Path(file_path).open("r") as f:
            data = json.load(f)
        return cls(**data)
