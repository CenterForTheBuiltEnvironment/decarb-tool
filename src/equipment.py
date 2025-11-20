from typing import List, Literal, Optional, Union, Dict
from pydantic import BaseModel, Field, PrivateAttr
import json
from pathlib import Path
import numpy as np

from utils.interp import interp_vector


# --- Models ---
class COPCurve(BaseModel):
    t_out_C: List[float]
    cop: List[float]

    def get_cop(self, temp: float) -> float:
        return float(interp_vector(self.t_out_C, self.cop, temp))


class CapCurve(BaseModel):
    t_out_C: List[float]
    capacity_W: List[float]

    def get_capacity(self, temp: float) -> float:
        return float(interp_vector(self.t_out_C, self.capacity_W, temp))


class plrCurve(BaseModel):
    capacity_W: List[float]
    cop: List[float]

    def get_cop(self, cap: float) -> float:
        return float(interp_vector(self.capacity_W, self.cop, cap))


class Performance(BaseModel):
    cop_curve: Optional[COPCurve] = None
    cap_curve: Optional[CapCurve] = None
    plr_curve: Optional[plrCurve] = None
    efficiency: Optional[float] = None
    constraints: Optional[Dict[str, float]] = None


class Emissions(BaseModel):
    co2_kg_per_mwh: float


class Equipment(BaseModel):
    eq_id: str
    eq_type: str
    eq_subtype: Optional[str] = None
    eq_manufacturer: Optional[str] = None
    model: str
    fuel: str
    refrigerant: Optional[str] = None
    refrigerant_weight_g: Optional[float] = None
    refrigerant_gwp: Optional[float] = None  # in kgCO2e per kg of refrigerant
    capacity_W: Optional[float] = None
    performance: Dict[str, Performance] = Field(default_factory=dict)
    emissions: Optional[Emissions] = (
        None  #! potentially rename to something more specific
    )

    @property
    def performance_heating(self) -> Optional[Performance]:
        return self.performance.get("heating")

    @property
    def performance_cooling(self) -> Optional[Performance]:
        return self.performance.get("cooling")


class EquipmentScenario(BaseModel):
    eq_scen_id: str
    eq_scen_name: str
    hr_wwhp: Optional[str]
    awhp: Optional[str]
    awhp_sizing_mode: Optional[Literal["peak_load_percentage_integer", "peak_load_percentage_fractional", "num_of_units"]] = None
    awhp_sizing_value: float
    awhp_use_cooling: bool
    boiler: Optional[str]
    chiller: Optional[str] = None
    resistance_heater: Optional[str] = None


# --- Dot-accessible wrapper with dynamic updates ---
class DotDict:
    def __init__(self, items: List[BaseModel], id_attr: str):
        self._id_attr = id_attr
        self._items: Dict[str, BaseModel] = {}
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
    equipment: List[Equipment]
    equipment_scenarios: List[EquipmentScenario]

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

    def add_equipment_scenario(
        self, scenario: EquipmentScenario, overwrite: bool = True
    ):
        """Add a new scenario. Overwrites existing if `overwrite=True`."""
        existing = [
            s for s in self.equipment_scenarios if s.eq_scen_id == scenario.eq_scen_id
        ]

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
        self.scenarios.remove(eq_scen_id)

    # Save back to JSON
    def to_json(self, file_path: Union[str, Path], indent: int = 2):
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
def load_library(file_path: Union[str, Path]) -> EquipmentLibrary:
    file_path = Path(file_path)
    with file_path.open("r") as f:
        data = json.load(f)
    return EquipmentLibrary(**data)
