"""Equipment Manager edit helpers: the overview form and the curve editor tables.

Values are shown in display units (SI/IP, fixed scale) and converted back to the stored base
units. Kept apart from the page module so the conversions can be unit-tested without the app.
"""

import dash_mantine_components as dmc
import pandas as pd
from dash.dash_table.Format import Format, Scheme

from src.equipment import (
    HEAT_PUMP_TYPES,
    Equipment,
    curve_table,
    find_refrigerant,
    load_refrigerants,
)
from utils.units import get_converter, get_display_unit, get_inverse_converter

TYPE_LABELS = {
    "hr_heat_pump": "HR water-to-water heat pump",
    "heat_pump": "Air-to-water heat pump",
    "backup_heating": "Backup heating",
    "chiller": "Chiller",
}

CALC_TYPE_OPTIONS = [
    {"label": "Specific (sized from its capacity)", "value": "specific"},
    {"label": "Generic (unlimited capacity)", "value": "generic"},
]


def edit_unit(category: str, unit_mode: str):
    """(base -> display, display -> base, label) for edit inputs, with a fixed scale per unit system."""
    if category == "power" and unit_mode == "IP":
        to_btu, from_btu = get_converter("power", "IP"), get_inverse_converter("power", "IP")
        return (lambda v: to_btu(v) / 1000), (lambda v: from_btu(v * 1000)), "kBTU/h"
    if category == "length":
        factor = 1.0 if unit_mode == "SI" else 3.28084
        return (lambda v: v * factor), (lambda v: v / factor), "m" if unit_mode == "SI" else "ft"
    return (
        get_converter(category, unit_mode),
        get_inverse_converter(category, unit_mode),
        get_display_unit(category, unit_mode),
    )


# --- Overview form ---
# path in the equipment dict -> (label, kind, unit category, decimals, display factor)
FORM_FIELDS = {
    "model": ("Model", "text", None, None, 1),
    "eq_manufacturer": ("Manufacturer", "text", None, None, 1),
    "eq_subtype": ("Subtype", "text", None, None, 1),
    "eq_calc_type": ("Calculation type", "calc_type", None, None, 1),
    "nominal_capacity_W": ("Nominal capacity", "number", "power_cooling", 2, 1),
    "capacity_W": ("Capacity", "number", "power", 1, 1),
    "efficiency": ("Efficiency", "number", None, 2, 1),
    "refrigerant": ("Refrigerant", "refrigerant", None, None, 1),
    "refrigerant_gwp": ("Refrigerant GWP", "number", "gwp", 0, 1),
    "refrigerant_weight_g": ("Refrigerant charge", "number", "mass_g", 2, 1),
    "operating_weight_g": ("Operating weight", "number", "mass_g", 0, 1),
    "dimensions.length": ("Length", "number", "length", 2, 1),
    "dimensions.width": ("Width", "number", "length", 2, 1),
    "dimensions.height": ("Height", "number", "length", 2, 1),
    "electrical.mca": ("MCA [A]", "number", None, 1, 1),
    "electrical.voltage": ("Voltage [V]", "number", None, 0, 1),
    "electrical.phase": ("Phase", "number", None, 0, 1),
    "max_output_dba": ("Max. sound level [dBA]", "number", None, 0, 1),
    "notes": ("Notes", "textarea", None, None, 1),
}

FORM_SECTIONS = [
    ("General", ["model", "eq_manufacturer", "eq_subtype", "eq_calc_type"]),
    ("Capacity and efficiency", ["nominal_capacity_W", "capacity_W", "efficiency"]),
    ("Refrigerant", ["refrigerant", "refrigerant_gwp", "refrigerant_weight_g"]),
    (
        "Physical and electrical",
        [
            "operating_weight_g",
            "dimensions.length",
            "dimensions.width",
            "dimensions.height",
            "electrical.mca",
            "electrical.voltage",
            "electrical.phase",
            "max_output_dba",
        ],
    ),
    ("Notes", ["notes"]),
]


def form_field_names(eq: dict) -> list[str]:
    """The overview fields that apply to this kind of equipment."""
    eq_type = eq.get("eq_type")
    names = ["model", "eq_manufacturer", "eq_subtype", "eq_calc_type", "notes"]
    if eq_type in (*HEAT_PUMP_TYPES, "chiller"):
        names += ["nominal_capacity_W", "refrigerant", "refrigerant_gwp", "refrigerant_weight_g"]
        names += [n for n in FORM_FIELDS if n.startswith(("dimensions.", "electrical."))]
        names += ["operating_weight_g", "max_output_dba"]
    if eq_type in ("backup_heating", "chiller") or (
        eq_type == "heat_pump" and eq.get("capacity_W")
    ):
        names.append("capacity_W")
    if eq_type in ("backup_heating", "chiller"):
        names.append("efficiency")
    return names


def field_meta(name: str, eq: dict, unit_mode: str):
    """Label, unit converters and decimals of a form field for this item and unit system."""
    label, kind, category, decimals, factor = FORM_FIELDS[name]
    eq_type = eq.get("eq_type")
    if name == "capacity_W":
        category = "power_cooling" if eq_type == "chiller" else "power"
        label = "Fixed unit capacity" if eq_type == "heat_pump" else "Capacity"
    if name == "efficiency":
        label, factor = ("Efficiency [%]", 100) if eq_type == "backup_heating" else ("COP", 1)
    if category:
        to_display, to_base, unit = edit_unit(category, unit_mode)
        label = f"{label} [{unit}]"
    else:
        to_display, to_base = (lambda v: v * factor), (lambda v: v / factor)
    return label, kind, to_display, to_base, decimals


def get_path(eq: dict, name: str):
    if name == "efficiency":
        perf = next(iter((eq.get("performance") or {}).values()), None) or {}
        return perf.get("efficiency")
    value = eq
    for part in name.split("."):
        value = (value or {}).get(part)
    return value


def set_path(eq: dict, name: str, value):
    if name == "efficiency":
        mode = next(iter(eq.get("performance") or {}), None)
        if mode:
            eq["performance"][mode]["efficiency"] = value
        return
    parts = name.split(".")
    target = eq
    for part in parts[:-1]:
        if target.get(part) is None:
            target[part] = {}
        target = target[part]
    target[parts[-1]] = value


def display_value(eq: dict, name: str, unit_mode: str):
    """A field's value as shown in the form (converted and rounded)."""
    _, kind, to_display, _, decimals = field_meta(name, eq, unit_mode)
    value = get_path(eq, name)
    if kind in ("text", "textarea", "calc_type", "refrigerant"):
        return value or ""
    if value is None:
        return ""
    return round(to_display(value), decimals)


def _form_input(name: str, eq: dict, unit_mode: str):
    label, kind, _, _, decimals = field_meta(name, eq, unit_mode)
    field_id = {"type": "eqm-field", "name": name}
    value = display_value(eq, name, unit_mode)
    if kind == "text":
        return dmc.TextInput(id=field_id, label=label, value=value, size="xs", debounce=400)
    if kind == "textarea":
        return dmc.Textarea(
            id=field_id, label=label, value=value, size="xs", autosize=True, minRows=2, debounce=400
        )
    if kind == "calc_type":
        return dmc.Select(
            id=field_id, label=label, data=CALC_TYPE_OPTIONS, value=value or None, size="xs"
        )
    if kind == "refrigerant":
        return dmc.Autocomplete(
            id=field_id,
            label=label,
            data=[r.name for r in load_refrigerants()],
            value=value,
            size="xs",
            placeholder="Pick or type a refrigerant",
            debounce=400,
        )
    known = name == "refrigerant_gwp" and find_refrigerant(eq.get("refrigerant")) is not None
    return dmc.NumberInput(
        id=field_id,
        label=label,
        value=value,
        decimalScale=decimals,
        size="xs",
        debounce=400,
        disabled=known,
        description="From the refrigerant database" if name == "refrigerant_gwp" else None,
    )


def overview_form(eq: dict, unit_mode: str):
    names = set(form_field_names(eq))
    sections = []
    for title, fields in FORM_SECTIONS:
        inputs = [_form_input(n, eq, unit_mode) for n in fields if n in names]
        if not inputs:
            continue
        sections.append(dmc.Text(title, size="xs", fw=700, c="dimmed", tt="uppercase", mt="xs"))
        sections.append(
            inputs[0] if title == "Notes" else dmc.SimpleGrid(inputs, cols={"base": 1, "sm": 2})
        )
    header = dmc.Text(
        f"{eq['eq_id']} · {TYPE_LABELS.get(eq.get('eq_type'), eq.get('eq_type'))} · "
        f"{(eq.get('fuel') or '').replace('_', ' ')}"
        + (f" · based on {eq['based_on']}" if eq.get("based_on") else ""),
        size="xs",
        c="dimmed",
    )
    return dmc.Stack([header, *sections], gap="xs")


# --- Curve editor tables ---
def _num_col(col_id, name, decimals):
    return {
        "id": col_id,
        "name": name,
        "type": "numeric",
        "format": Format(precision=decimals, scheme=Scheme.fixed),
    }


def editor_units(mode: str, unit_mode: str):
    temp = edit_unit("temperature", unit_mode)
    cap = edit_unit("power_cooling" if mode == "cooling" else "power", unit_mode)
    return temp, cap


def editor_tables(eq: Equipment, mode: str, unit_mode: str):
    """Rows and columns of the curve and supply temperature tables, in display units.

    Curve table: one row per curve point, `cop_i` (and `cap_i` for AWHPs with capacity curves)
    per supply temperature i. Supply temperature table: one row per supply temperature i.
    """
    df = curve_table(eq, mode)
    (t_disp, _, t_unit), (c_disp, _, c_unit) = editor_units(mode, unit_mode)
    is_awhp = eq.eq_type == "heat_pump"
    lwts = sorted(df["lwt_C"].unique())
    has_cap = is_awhp and df["capacity_W"].notna().any()

    columns = [
        _num_col("x", f"OAT [{t_unit}]", 1) if is_awhp else _num_col("x", f"Capacity [{c_unit}]", 2)
    ]
    for i, lwt in enumerate(lwts):
        columns.append(_num_col(f"cop_{i}", f"COP @ {t_disp(lwt):.1f} {t_unit}", 2))
        if has_cap:
            columns.append(
                _num_col(f"cap_{i}", f"Capacity @ {t_disp(lwt):.1f} {t_unit} [{c_unit}]", 2)
            )

    rows = []
    for x, d in df.groupby("x", sort=True):
        d = d.set_index("lwt_C")
        row = {"x": float(t_disp(x) if is_awhp else c_disp(x))}
        for i, lwt in enumerate(lwts):
            row[f"cop_{i}"] = float(d.loc[lwt, "cop"])
            if has_cap:
                row[f"cap_{i}"] = float(c_disp(d.loc[lwt, "capacity_W"]))
        rows.append(row)

    lwt_columns = [_num_col("lwt", f"Supply temperature [{t_unit}]", 1)]
    if is_awhp:
        lwt_columns += [
            _num_col("oat_min", f"OAT min [{t_unit}]", 1),
            _num_col("oat_max", f"OAT max [{t_unit}]", 1),
        ]
    limits = df.groupby("lwt_C")[["oat_min_C", "oat_max_C"]].first()
    lwt_rows = []
    for lwt in lwts:
        row = {"lwt": float(t_disp(lwt))}
        if is_awhp:
            row["oat_min"] = _nan_to_none(t_disp(limits.loc[lwt, "oat_min_C"]))
            row["oat_max"] = _nan_to_none(t_disp(limits.loc[lwt, "oat_max_C"]))
        lwt_rows.append(row)
    return rows, columns, lwt_rows, lwt_columns


def _nan_to_none(v):
    return None if pd.isna(v) else float(v)


def to_float(v):
    """A table cell as float; blank or invalid cells become NaN and fail validation."""
    try:
        return float(v)
    except (TypeError, ValueError):
        return float("nan")


def tables_to_long(eq: Equipment, mode: str, unit_mode: str, rows, lwt_rows) -> pd.DataFrame:
    """Curve and supply temperature tables (display units) as a `curve_table` long table (SI)."""
    (_, t_base, _), (_, c_base, _) = editor_units(mode, unit_mode)
    is_awhp = eq.eq_type == "heat_pump"
    records = []
    for i, lwt_row in enumerate(lwt_rows):
        lwt = t_base(to_float(lwt_row.get("lwt")))
        for row in rows:
            x = to_float(row.get("x"))
            cap_key = f"cap_{i}"
            records.append(
                {
                    "x": t_base(x) if is_awhp else c_base(x),
                    "lwt_C": lwt,
                    "cop": to_float(row.get(f"cop_{i}")),
                    "capacity_W": (
                        c_base(to_float(row.get(cap_key)))
                        if is_awhp and cap_key in row
                        else (c_base(x) if not is_awhp else float("nan"))
                    ),
                    "oat_min_C": t_base(to_float(lwt_row.get("oat_min"))) if is_awhp else None,
                    "oat_max_C": t_base(to_float(lwt_row.get("oat_max"))) if is_awhp else None,
                }
            )
    return pd.DataFrame(records)


def scale_values(eq: Equipment, mode: str):
    factors = (eq.scaling or {}).get(mode, {})
    return round(factors.get("cop", 1.0) * 100, 1), round(factors.get("capacity", 1.0) * 100, 1)
