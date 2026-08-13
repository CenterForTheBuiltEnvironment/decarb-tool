import json
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, PrivateAttr

from src.mixins import DotAccessMixin


# --- Models ---
class PerformanceCurves(BaseModel):
    """Equipment performance curves: coefficient of performance (COP), capacity, and outdoor air temperature constraints."""

    cop: list[float] | None = None
    capacity_W: list[float] | None = None
    constraints: dict[str, float] | None = None


class Performance(BaseModel):
    """Equipment performance data:
    Leaving supply water temperatures, associated performance curves, and supply water temperature constraints.
    Outdoor air temperature curve for AWHPs, capacity curve for WWHPs, constant efficiency for boilers/chillers.
    """

    t_out_C: list[float] | None = None
    capacity_W: list[float] | None = None
    leaving_supply_t: dict[str, PerformanceCurves] | None = None
    efficiency: float | None = None
    constraints: dict[str, float] | None = None


class Emissions(BaseModel):
    """ "Equipment emissions data."""

    co2_kg_per_mwh: float


class Dimensions(BaseModel):
    """Equipment physical dimensions in metres."""

    length: float | None = None
    height: float | None = None
    width: float | None = None


class Electrical(BaseModel):
    """Equipment electrical characteristics: minimum circuit amperage (MCA), voltage, and phase."""

    mca: float | None = None
    voltage: float | None = None
    phase: int | None = None


class Equipment(BaseModel):
    eq_id: str
    eq_type: str
    eq_subtype: str | None = None
    eq_calc_type: str | None = None
    eq_manufacturer: str | None = None
    model: str
    nominal_capacity_W: int | None = None
    fuel: str
    refrigerant: str | None = None
    refrigerant_weight_g: float | None = None
    refrigerant_gwp: float | None = None  # in kgCO2e per kg of refrigerant
    capacity_W: float | None = None
    dimensions: Dimensions | None = None
    operating_weight_g: float | None = None
    electrical: Electrical | None = None
    max_output_dba: float | None = None
    performance: dict[str, Performance] = Field(default_factory=dict)
    emissions: Emissions | None = None  #! potentially rename to something more specific

    @property
    def performance_heating(self) -> Performance | None:
        return self.performance.get("heating")

    @property
    def performance_cooling(self) -> Performance | None:
        return self.performance.get("cooling")


class EquipmentScenario(DotAccessMixin, BaseModel):
    eq_scen_id: str
    eq_scen_name: str
    hr_wwhp: str | None = None
    hr_wwhp_performance_model: (
        Literal["fixed_COP", "interpolate_HHWST", "performance_curves"] | None
    ) = None
    hr_wwhp_h_supply_t: float | None = None
    awhp: str | None = None
    awhp_performance_model: (
        Literal[
            "fixed_COP", "interpolate_HHWST_fixed", "interpolate_HHWST_reset", "performance_curves"
        ]
        | None
    ) = None
    awhp_h_supply_t: float | None = None
    awhp_sizing_mode: (
        Literal["integer_sizing_peak_load", "fractional_sizing_peak_load", "fixed_num_units"] | None
    ) = None
    awhp_sizing_value: float
    awhp_redundancy: int
    awhp_use_cooling: bool
    awhp_sizing_priority: Literal["heating", "cooling", "larger"] | None = None
    backup_heating: str | None = None
    fuel_switching: bool
    chiller: str | None = None


class ScenarioGroup(BaseModel):
    group_id: str
    group_name: str
    scenario_ids: list[str]


# --- Dot-accessible wrapper with dynamic updates ---
class DotDict:
    def __init__(self, items: list[BaseModel], id_attr: str):
        self._id_attr = id_attr
        self._items: dict[str, BaseModel] = {}
        for item in items:
            self.add(item)

    def add(self, item: BaseModel):
        key = getattr(item, self._id_attr)
        self._items[key] = item
        setattr(self, key, item)

    def remove(self, key: str):
        if key in self._items:
            del self._items[key]
            if hasattr(self, key):
                delattr(self, key)

    def update(self, item: BaseModel):
        key = getattr(item, self._id_attr)
        self._items[key] = item
        setattr(self, key, item)

    def __getitem__(self, key):
        return self._items[key]

    def __iter__(self):
        return iter(self._items.values())

    def keys(self):
        return self._items.keys()

    def values(self):
        return self._items.values()


# --- Library ---
class EquipmentLibrary(BaseModel):
    equipment: list[Equipment]
    equipment_scenarios: list[EquipmentScenario]
    scenario_groups: list[ScenarioGroup] = []

    # Private (non-validated) attributes
    _equipment_dict: DotDict = PrivateAttr()
    _scenarios: DotDict = PrivateAttr()

    def __init__(self, **data):
        super().__init__(**data)
        self._equipment_dict = DotDict(self.equipment, id_attr="eq_id")
        self._scenarios = DotDict(self.equipment_scenarios, id_attr="eq_scen_id")

    def get_equipment(self, eq_id: str) -> Equipment:
        return self._equipment_dict[eq_id]

    def get_scenario(self, eq_scen_id: str) -> EquipmentScenario:
        return self._scenarios[eq_scen_id]

    # Dynamic updates
    def add_equipment(self, equipment: Equipment):
        self.equipment.append(equipment)
        self._equipment_dict.add(equipment)

    def remove_equipment(self, eq_id: str):
        self.equipment = [e for e in self.equipment if e.eq_id != eq_id]
        self._equipment_dict.remove(eq_id)

    def add_equipment_scenario(self, scenario: EquipmentScenario, overwrite: bool = True):
        """Add a new scenario. Overwrites existing if `overwrite=True`."""
        existing = [s for s in self.equipment_scenarios if s.eq_scen_id == scenario.eq_scen_id]

        if existing:
            if overwrite:
                # Replace in list
                self.equipment_scenarios = [
                    scenario if s.eq_scen_id == scenario.eq_scen_id else s
                    for s in self.equipment_scenarios
                ]
                # Replace in DotDict
                self._scenarios.remove(scenario.eq_scen_id)
                self._scenarios.add(scenario)
            else:
                raise ValueError(f"Scenario {scenario.eq_scen_id!r} already exists")
        else:
            self.equipment_scenarios.append(scenario)
            self._scenarios.add(scenario)

    def remove_scenario(self, eq_scen_id: str):
        self.equipment_scenarios = [
            s for s in self.equipment_scenarios if s.eq_scen_id != eq_scen_id
        ]
        self._scenarios.remove(eq_scen_id)

    # Save back to JSON
    def to_json(self, file_path: str | Path, indent: int = 2):
        """
        Save the current library state to a JSON file.

        Parameters
        ----------
        file_path : str or Path
            Path to save the JSON file.
        indent : int
            Number of spaces for JSON indentation (default=2)
        """
        file_path = Path(file_path)
        data = {
            "equipment": [e.dict() for e in self.equipment],
            "equipment_scenarios": [s.dict() for s in self.equipment_scenarios],
        }
        with file_path.open("w") as f:
            json.dump(data, f, indent=indent)


# --- Loader ---
@lru_cache(maxsize=4)
def load_library(file_path: str | Path) -> EquipmentLibrary:
    """Load equipment library from JSON file with caching."""
    file_path = Path(file_path)
    with file_path.open("r") as f:
        data = json.load(f)
    return EquipmentLibrary(**data)
