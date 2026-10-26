import json
from collections.abc import Iterable
from functools import lru_cache
from itertools import pairwise
from pathlib import Path
from typing import Literal

import pandas as pd
from pydantic import BaseModel, Field, PrivateAttr

from src.mixins import DotAccessMixin

HEAT_PUMP_TYPES = ("heat_pump", "hr_heat_pump")
PLAUSIBLE_COP_RANGE = (1.0, 8.0)  # outside this range is flagged as a warning, not an error


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
    source: Literal["library", "custom"] = "library"
    based_on: str | None = None  # eq_id of the library item a custom copy was made from
    notes: str | None = None

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
    fuel_switching: bool = False
    chiller: str | None = None


class ScenarioGroup(BaseModel):
    group_id: str
    group_name: str
    scenario_ids: list[str]


# --- Validation ---
class EquipmentIssue(BaseModel):
    """A single problem found in an equipment definition. `field` is a dotted path into the model."""

    severity: Literal["error", "warning"]
    field: str
    message: str


def _curve_x_axis(eq: Equipment, perf: Performance) -> tuple[str, list[float] | None]:
    """Name and values of the x-axis the curves are defined over: part-load capacity for HR WWHPs, outdoor air temperature for AWHPs."""
    if eq.eq_type == "hr_heat_pump":
        return "capacity_W", perf.capacity_W
    return "t_out_C", perf.t_out_C


def validate_equipment(eq: Equipment, modes: Iterable[str] | None = None) -> list[EquipmentIssue]:
    """Check an equipment definition for completeness and consistency.

    Returns all issues found instead of raising, so callers can either report them
    (equipment manager) or raise on the first error (calculation engine).
    `modes` limits the checks to e.g. ("heating",); defaults to every mode present.
    """
    issues: list[EquipmentIssue] = []

    def add(severity, field, message):
        issues.append(
            EquipmentIssue(
                severity=severity, field=field, message=f"Equipment '{eq.eq_id}' {message}"
            )
        )

    modes = list(eq.performance) if modes is None else list(modes)

    if eq.eq_type in HEAT_PUMP_TYPES:
        if eq.eq_calc_type == "specific" and eq.nominal_capacity_W is None:
            add("warning", "nominal_capacity_W", "has no nominal capacity.")
        for mode in modes:
            _validate_heat_pump_mode(eq, mode, add)
    else:
        for mode in modes:
            perf = eq.performance.get(mode)
            if perf is None:
                add("error", f"performance.{mode}", f"lacks {mode} performance data.")
            elif perf.efficiency is None or perf.efficiency <= 0:
                add("error", f"performance.{mode}.efficiency", "requires a positive 'efficiency'.")

    return issues


def _validate_constraints(constraints, field, label, add):
    if not constraints or "min_temp_C" not in constraints or "max_temp_C" not in constraints:
        add("error", field, f"lacks {label} (min_temp_C and max_temp_C).")
    elif constraints["min_temp_C"] > constraints["max_temp_C"]:
        add("error", field, f"has {label} with min_temp_C above max_temp_C.")


def _validate_heat_pump_mode(eq: Equipment, mode: str, add):
    prefix = f"performance.{mode}"
    perf = eq.performance.get(mode)
    if perf is None:
        add("error", prefix, f"lacks {mode} performance data.")
        return
    if not perf.leaving_supply_t:
        add("error", f"{prefix}.leaving_supply_t", f"has no {mode} performance curves.")
        return

    x_name, x = _curve_x_axis(eq, perf)
    if not x:
        add("error", f"{prefix}.{x_name}", f"lacks {mode} capacity info ({x_name} curve).")
    elif any(b <= a for a, b in pairwise(x)):
        add("error", f"{prefix}.{x_name}", f"{mode} {x_name} values must be strictly increasing.")

    _validate_constraints(
        perf.constraints, f"{prefix}.constraints", f"{mode} supply temperature limits", add
    )

    supply_temps: dict[float, str] = {}
    for key in perf.leaving_supply_t:
        try:
            t = float(key)
        except ValueError:
            add(
                "error",
                f"{prefix}.leaving_supply_t",
                f"has a {mode} supply temperature '{key}' that is not a number.",
            )
            continue
        if t in supply_temps:
            add(
                "error",
                f"{prefix}.leaving_supply_t",
                f"lists {mode} supply temperature {key} more than once.",
            )
        supply_temps[t] = key

    c = perf.constraints or {}
    if (
        supply_temps
        and "min_temp_C" in c
        and "max_temp_C" in c
        and (min(supply_temps) != c["min_temp_C"] or max(supply_temps) != c["max_temp_C"])
    ):
        add(
            "warning",
            f"{prefix}.constraints",
            f"{mode} supply temperature limits do not match the range of the curves "
            f"({min(supply_temps)} to {max(supply_temps)} °C).",
        )

    for key, curves in perf.leaving_supply_t.items():
        field = f"{prefix}.leaving_supply_t.{key}"
        label = f"supply temperature {key}"

        if not curves.cop:
            add("error", f"{field}.cop", f"lacks {mode} capacity info (COP curve for {label}).")
        else:
            if x and len(curves.cop) != len(x):
                add(
                    "error",
                    f"{field}.cop",
                    f"{mode} COP and {x_name} curves are of different lengths for {label}.",
                )
            if any(v <= 0 for v in curves.cop):
                add("error", f"{field}.cop", f"has a non-positive {mode} COP for {label}.")
            elif any(not PLAUSIBLE_COP_RANGE[0] <= v <= PLAUSIBLE_COP_RANGE[1] for v in curves.cop):
                add(
                    "warning",
                    f"{field}.cop",
                    f"has a {mode} COP outside the typical range "
                    f"{PLAUSIBLE_COP_RANGE[0]} to {PLAUSIBLE_COP_RANGE[1]} for {label}.",
                )

        if eq.eq_type != "heat_pump":
            continue

        # AWHP: capacity per supply temperature, or a fixed capacity for the unit
        if curves.capacity_W:
            if x and len(curves.capacity_W) != len(x):
                add(
                    "error",
                    f"{field}.capacity_W",
                    f"{mode} capacity_W and t_out curves are of different lengths for {label}.",
                )
            if any(v <= 0 for v in curves.capacity_W):
                add(
                    "error",
                    f"{field}.capacity_W",
                    f"has a non-positive {mode} capacity for {label}.",
                )
        elif not eq.capacity_W:
            add(
                "error",
                f"{field}.capacity_W",
                f"lacks {mode} capacity info (fixed value or t_out-based curve for capacity_W at {label}).",
            )

        _validate_constraints(
            curves.constraints,
            f"{field}.constraints",
            f"{mode} outdoor air temperature limits for {label}",
            add,
        )


# --- Helpers for user-defined equipment ---
def duplicate_equipment(eq: Equipment, existing_ids: Iterable[str]) -> Equipment:
    """Return an editable custom copy of `eq` with an id not in `existing_ids`."""
    existing_ids = set(existing_ids)
    base_id = eq.based_on if eq.source == "custom" and eq.based_on else eq.eq_id
    n = 1
    while f"custom_{base_id}_{n}" in existing_ids:
        n += 1
    return eq.model_copy(
        deep=True,
        update={
            "eq_id": f"custom_{base_id}_{n}",
            "model": f"{eq.model} (copy)",
            "source": "custom",
            "based_on": base_id,
        },
    )


CURVE_TABLE_COLUMNS = ["x", "x_kind", "lwt_C", "cop", "capacity_W", "oat_min_C", "oat_max_C"]


def curve_table(eq: Equipment, mode: str) -> pd.DataFrame:
    """Heat pump performance curves for one mode as a long table, one row per (supply temperature, x) point.

    `x` is outdoor air temperature (AWHP) or part-load capacity (HR WWHP), named in `x_kind`.
    Supply temperatures are sorted numerically. `capacity_W` is NaN where an AWHP only has a
    fixed unit capacity. Expects equipment without validation errors.
    """
    perf = eq.performance.get(mode)
    if eq.eq_type not in HEAT_PUMP_TYPES or perf is None or not perf.leaving_supply_t:
        return pd.DataFrame(columns=CURVE_TABLE_COLUMNS)

    x_name, x = _curve_x_axis(eq, perf)
    frames = []
    for key, curves in sorted(perf.leaving_supply_t.items(), key=lambda item: float(item[0])):
        constraints = curves.constraints or {}
        # HR WWHP curves are defined over capacity; AWHPs may only have a fixed unit capacity
        capacity = x if x_name == "capacity_W" else curves.capacity_W or [float("nan")] * len(x)
        frames.append(
            pd.DataFrame(
                {
                    "x": x,
                    "x_kind": x_name,
                    "lwt_C": float(key),
                    "cop": curves.cop,
                    "capacity_W": capacity,
                    "oat_min_C": constraints.get("min_temp_C", float("nan")),
                    "oat_max_C": constraints.get("max_temp_C", float("nan")),
                }
            )
        )
    return pd.concat(frames, ignore_index=True)[CURVE_TABLE_COLUMNS]


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

    def validation_issues(self) -> dict[str, list[EquipmentIssue]]:
        """Validation issues per equipment id (empty list when an item is fine)."""
        return {e.eq_id: validate_equipment(e) for e in self.equipment}

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
