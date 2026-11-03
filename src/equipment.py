import copy
import json
import math
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
    # total factors applied to the curves of a custom copy, e.g. {"heating": {"cop": 0.95, "capacity": 1.1}};
    # informational only, the scaled values are stored in `performance`
    scaling: dict[str, dict[str, float]] | None = None

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
    hr_eac_rejection_cap_W: float | None = None
    hr_eac_recovery_cap_W: float | None = None
    hr_eac_rejection_control: Literal["min_turndown", "max_heat_rejection"] | None = None
    hr_eac_recovery_control: Literal["min_turndown", "max_heat_recovery"] | None = None
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
    elif not all(math.isfinite(v) for v in x):
        add("error", f"{prefix}.{x_name}", f"has a missing {mode} {x_name} value.")
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
        elif not all(math.isfinite(v) for v in curves.cop):
            add("error", f"{field}.cop", f"has a missing {mode} COP value for {label}.")
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
            if not all(math.isfinite(v) for v in curves.capacity_W):
                add(
                    "error",
                    f"{field}.capacity_W",
                    f"has a missing {mode} capacity value for {label}.",
                )
            elif x and len(curves.capacity_W) != len(x):
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


SCENARIO_EQUIPMENT_FIELDS = ("hr_wwhp", "awhp", "backup_heating", "chiller")


def scenarios_using(equipment_data: dict, eq_id: str) -> list[str]:
    """Names of the equipment scenarios in `equipment_data` that use `eq_id`."""
    return [
        s.get("eq_scen_name") or s.get("eq_scen_id")
        for s in (equipment_data or {}).get("equipment_scenarios", [])
        if any(s.get(f) == eq_id for f in SCENARIO_EQUIPMENT_FIELDS)
    ]


def save_custom_equipment(equipment_data: dict, eq: Equipment, library_ids: Iterable[str]) -> dict:
    """Return `equipment_data` with the custom item `eq` added or replaced.

    Refuses anything that would overwrite library equipment: `eq` must be a custom item
    whose id is not one of `library_ids`.
    """
    if eq.source != "custom" or eq.eq_id in set(library_ids):
        raise ValueError(f"Equipment '{eq.eq_id}' is library equipment and cannot be overwritten.")
    item = eq.model_dump()
    equipment = list((equipment_data or {}).get("equipment", []))
    index = next((i for i, e in enumerate(equipment) if e.get("eq_id") == eq.eq_id), None)
    if index is None:
        equipment.append(item)
    else:
        equipment[index] = item
    return {**(equipment_data or {}), "equipment": equipment}


def delete_custom_equipment(equipment_data: dict, eq_id: str) -> dict:
    """Return `equipment_data` without the custom item `eq_id`; refuses library items and items in use."""
    equipment = (equipment_data or {}).get("equipment", [])
    item = next((e for e in equipment if e.get("eq_id") == eq_id), None)
    if item is None or item.get("source") != "custom":
        raise ValueError(f"Equipment '{eq_id}' is not custom equipment and cannot be deleted.")
    used_by = scenarios_using(equipment_data, eq_id)
    if used_by:
        raise ValueError(
            f"Equipment '{eq_id}' is used by {', '.join(used_by)}. "
            "Choose other equipment in these scenarios first."
        )
    return {**equipment_data, "equipment": [e for e in equipment if e.get("eq_id") != eq_id]}


def keep_custom_equipment(initial_data: dict, current_data: dict | None) -> dict:
    """`initial_data` (the library) plus the custom equipment in `current_data`, used when resetting."""
    custom = [e for e in (current_data or {}).get("equipment", []) if e.get("source") == "custom"]
    if not custom:
        return initial_data
    return {**initial_data, "equipment": [*initial_data.get("equipment", []), *custom]}


# --- Import / export of custom equipment ---
CUSTOM_EQUIPMENT_FORMAT = "decarb-tool/custom-equipment"
CUSTOM_EQUIPMENT_FORMAT_VERSION = "1.0"


def export_custom_equipment(equipment_data: dict, tool_version: str | None = None) -> dict:
    """The custom equipment in `equipment_data` as an export file (see `import_custom_equipment`)."""
    import datetime

    return {
        "format": CUSTOM_EQUIPMENT_FORMAT,
        "format_version": CUSTOM_EQUIPMENT_FORMAT_VERSION,
        "tool_version": tool_version,
        "exported_at": datetime.datetime.now().isoformat(timespec="seconds"),
        "equipment": [
            copy.deepcopy(e)
            for e in (equipment_data or {}).get("equipment", [])
            if e.get("source") == "custom"
        ],
    }


class ImportReport(BaseModel):
    """What `import_custom_equipment` did with each item of a file."""

    added: list[str] = []
    updated: list[str] = []
    renamed: dict[str, str] = {}  # id in the file -> new id (the file's id is a library id)
    unchanged: list[str] = []
    rejected: dict[str, str] = {}  # id (or position) in the file -> reason

    @property
    def imported(self) -> list[str]:
        return [*self.added, *self.updated, *self.renamed.values()]


def _items_in_file(payload) -> list:
    """Equipment items of an export file, a results settings file or a bare list."""
    if isinstance(payload, list):
        return payload
    if not isinstance(payload, dict):
        raise ValueError("The file does not contain equipment.")
    if isinstance(payload.get("equipment"), list):
        return payload["equipment"]
    library = payload.get("equipment_library")
    if isinstance(library, dict) and isinstance(library.get("equipment"), list):
        # results settings file: only the custom items, the library is already in the tool
        return [
            e for e in library["equipment"] if isinstance(e, dict) and e.get("source") == "custom"
        ]
    raise ValueError("The file does not contain equipment.")


def import_custom_equipment(
    equipment_data: dict, payload, library_ids: Iterable[str]
) -> tuple[dict, ImportReport]:
    """Add the equipment of an imported file to `equipment_data` as custom equipment.

    Library equipment is never overwritten: an item with a library id is imported under a new
    custom id. An item with the id of a custom item replaces it (or is skipped when identical).
    Items that cannot be read or have validation errors are rejected.
    """
    library_ids = set(library_ids)
    report = ImportReport()
    data = equipment_data or {}

    for n, item in enumerate(_items_in_file(payload), start=1):
        label = item.get("eq_id") if isinstance(item, dict) and item.get("eq_id") else f"item {n}"
        try:
            eq = Equipment(**item)
        except (TypeError, ValueError) as err:
            reason = err.errors()[0]["msg"] if hasattr(err, "errors") else str(err)
            report.rejected[label] = f"not a valid equipment definition ({reason})"
            continue
        stored = _stored_item(data, eq.eq_id)
        if stored is not None and eq.model_dump() == stored:
            report.unchanged.append(
                eq.eq_id
            )  # e.g. a library item, or a custom item imported twice
            continue
        errors = [i.message for i in validate_equipment(eq) if i.severity == "error"]
        if errors:
            report.rejected[label] = errors[0]
            continue

        if eq.eq_id in library_ids:
            # a changed library item: keep it as a custom copy, never overwrite the library
            existing_ids = [e.get("eq_id") for e in data.get("equipment", [])]
            duplicate = duplicate_equipment(
                eq.model_copy(update={"source": "library"}), existing_ids
            )
            eq = duplicate.model_copy(update={"model": eq.model})
            report.renamed[label] = eq.eq_id
        else:
            eq = eq.model_copy(update={"source": "custom"})
            (report.updated if stored is not None else report.added).append(eq.eq_id)
        data = save_custom_equipment(data, eq, library_ids)

    return data, report


def _stored_item(equipment_data: dict, eq_id: str) -> dict | None:
    """The stored item with `eq_id`, normalised through the model so it compares with an import."""
    item = next((e for e in equipment_data.get("equipment", []) if e.get("eq_id") == eq_id), None)
    return Equipment(**item).model_dump() if item else None


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


def apply_curve_table(eq: Equipment, mode: str, df: pd.DataFrame) -> Equipment:
    """Return a copy of `eq` with the `mode` curves replaced by a long table in `curve_table` format.

    The inverse of `curve_table`: rows are grouped by `lwt_C` and sorted by `x`. Every supply
    temperature must share the same x points. AWHP capacity columns that are all NaN mean the
    item uses its fixed unit capacity. The mode's supply temperature limits are set to the
    range of the curves.
    """
    eq = eq.model_copy(deep=True)
    perf = eq.performance.get(mode) or Performance()
    x_name = "capacity_W" if eq.eq_type == "hr_heat_pump" else "t_out_C"
    df = df.sort_values(["lwt_C", "x"])

    x_points = None
    curves = {}
    for lwt, d in df.groupby("lwt_C", sort=True):
        x = [float(v) for v in d["x"]]
        if x_points is None:
            x_points = x
        elif x != x_points:
            raise ValueError("All supply temperatures need the same curve points.")
        cap = d["capacity_W"]
        constraints = None
        if x_name == "t_out_C" and d[["oat_min_C", "oat_max_C"]].iloc[0].notna().all():
            constraints = {
                "min_temp_C": float(d["oat_min_C"].iloc[0]),
                "max_temp_C": float(d["oat_max_C"].iloc[0]),
            }
        curves[_lwt_key(lwt)] = PerformanceCurves(
            cop=[float(v) for v in d["cop"]],
            capacity_W=(
                [float(v) for v in cap] if x_name == "t_out_C" and cap.notna().all() else None
            ),
            constraints=constraints,
        )

    setattr(perf, x_name, x_points)
    perf.leaving_supply_t = curves
    if curves:
        # supply temperature limits follow the range of the curves
        lwts = [float(k) for k in curves]
        perf.constraints = {
            **(perf.constraints or {}),
            "min_temp_C": min(lwts),
            "max_temp_C": max(lwts),
        }
    eq.performance[mode] = perf
    return eq


def _lwt_key(lwt: float) -> str:
    """Supply temperature as a dict key in the library's style: '38', '32.2'."""
    return f"{float(lwt):g}"


def scale_performance(
    eq: Equipment, mode: str, cop_factor: float = 1.0, capacity_factor: float = 1.0
) -> Equipment:
    """Return a copy of `eq` with the `mode` curves scaled to the given total factors.

    The factors are relative to the unscaled curves: the curves are multiplied by the new
    factor divided by the one already applied (`eq.scaling`), so applying 110 % twice stays
    at 110 %. Scales COP and capacity (AWHP per supply temperature or fixed unit capacity,
    HR WWHP part-load capacity points, and the nominal capacity).
    """
    if cop_factor <= 0 or capacity_factor <= 0:
        raise ValueError("Scaling factors must be positive.")
    eq = eq.model_copy(deep=True)
    perf = eq.performance.get(mode)
    if perf is None or not perf.leaving_supply_t:
        return eq

    previous = (eq.scaling or {}).get(mode, {})
    cop_step = cop_factor / previous.get("cop", 1.0)
    cap_step = capacity_factor / previous.get("capacity", 1.0)

    for curves in perf.leaving_supply_t.values():
        curves.cop = [v * cop_step for v in curves.cop or []]
        if curves.capacity_W:
            curves.capacity_W = [v * cap_step for v in curves.capacity_W]
    if eq.eq_type == "hr_heat_pump" and perf.capacity_W:
        perf.capacity_W = [v * cap_step for v in perf.capacity_W]
    elif eq.eq_type == "heat_pump" and eq.capacity_W:
        eq.capacity_W *= cap_step
    if eq.nominal_capacity_W:
        eq.nominal_capacity_W = round(eq.nominal_capacity_W * cap_step)

    scaling = dict(eq.scaling or {})
    scaling[mode] = {"cop": cop_factor, "capacity": capacity_factor}
    eq.scaling = {m: f for m, f in scaling.items() if f != {"cop": 1.0, "capacity": 1.0}} or None
    return eq


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


# --- Refrigerants ---
class Refrigerant(BaseModel):
    """A refrigerant and its global warming potential (100-year, IPCC AR4 where listed)."""

    name: str
    aliases: list[str] = []
    gwp: float
    type: str | None = None
    safety_class: str | None = None
    note: str | None = None


def _refrigerant_key(name: str) -> str:
    """Name normalised for matching: 'R-134A', 'r134a' and 'R 134a' are the same refrigerant."""
    return "".join(c for c in name.upper() if c.isalnum())


@lru_cache(maxsize=4)
def load_refrigerants(file_path: str | Path | None = None) -> tuple[Refrigerant, ...]:
    """Refrigerant database from CSV (columns name, aliases, gwp, type, safety_class, note)."""
    from src import paths

    df = pd.read_csv(file_path or paths.REFRIGERANTS_CSV, dtype=str, keep_default_na=False)
    return tuple(
        Refrigerant(
            name=r["name"],
            aliases=[a.strip() for a in r["aliases"].split(";") if a.strip()],
            gwp=float(r["gwp"]),
            type=r["type"] or None,
            safety_class=r["safety_class"] or None,
            note=r["note"] or None,
        )
        for r in df.to_dict("records")
    )


def find_refrigerant(name: str | None, refrigerants: Iterable[Refrigerant] | None = None):
    """The database entry matching `name` (or one of its aliases), or None."""
    if not name:
        return None
    key = _refrigerant_key(name)
    for r in refrigerants if refrigerants is not None else load_refrigerants():
        if key in {_refrigerant_key(n) for n in (r.name, *r.aliases)}:
            return r
    return None


# --- Loader ---
@lru_cache(maxsize=4)
def load_library(file_path: str | Path) -> EquipmentLibrary:
    """Load equipment library from JSON file with caching."""
    file_path = Path(file_path)
    with file_path.open("r") as f:
        data = json.load(f)
    return EquipmentLibrary(**data)
