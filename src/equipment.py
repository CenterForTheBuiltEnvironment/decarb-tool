from typing import List, Optional, Union, Dict
from pydantic import BaseModel, PrivateAttr
import json
from pathlib import Path
import numpy as np


# --- Models ---
class COPCurve(BaseModel):
    temperature_C: List[float]
    cop: List[float]

    def get_cop(self, temp: float) -> float:
        return float(np.interp(temp, self.temperature_C, self.cop))


class Performance(BaseModel):
    cop_curve: Optional[COPCurve] = None
    efficiency: Optional[float] = None
    constraints: Optional[Dict[str, float]] = None


class Emissions(BaseModel):
    co2_kg_per_mwh: float


class Equipment(BaseModel):
    eq_id: str
    eq_type: str
    eq_subtype: Optional[str] = None
    model: str
    fuel: str
    capacity_kw: float
    performance: Performance
    emissions: Optional[Emissions] = None


class EquipmentScenario(BaseModel):
    eq_scen_id: str
    eq_scen_name: str
    hr_wwhp: Optional[str]
    awhp_h: Optional[str]
    awhp_c: Optional[str]
    awhp_sizing: float
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

    def add_scenario(self, scenario: EquipmentScenario):
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
