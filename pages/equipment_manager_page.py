import json
import time

import dash
import dash_mantine_components as dmc
import pandas as pd
from dash import ALL, Input, Output, State, callback, ctx, dash_table, dcc, html, no_update
from dash_iconify import DashIconify

from layout.equipment_editor import (
    TYPE_LABELS,
    display_value,
    editor_tables,
    editor_units,
    field_meta,
    overview_form,
    scale_values,
    set_path,
    tables_to_long,
    to_float,
)
from src.config import LINKS, URLS
from src.equipment import (
    HEAT_PUMP_TYPES,
    Equipment,
    apply_curve_table,
    curve_table,
    delete_custom_equipment,
    duplicate_equipment,
    find_refrigerant,
    save_custom_equipment,
    scale_performance,
    validate_equipment,
)
from src.visuals import empty_figure, plot_performance_curves
from utils.logging_config import get_logger
from utils.tooltips import with_icon_and_tooltip
from utils.units import (
    format_with_auto_scale,
    get_auto_scale,
    get_converter,
    get_display_unit,
)

logger = get_logger(__name__)


dash.register_page(
    __name__,
    name="Equipment Manager",
    path=URLS.EQUIPMENT_MANAGER.value,
    order=99,  # not a workflow step; linked separately in the sidebar
)

TYPE_FILTERS = [
    {"label": "All", "value": "all"},
    {"label": "HR WWHP", "value": "hr_heat_pump"},
    {"label": "AWHP", "value": "heat_pump"},
    {"label": "Backup", "value": "backup_heating"},
    {"label": "Chiller", "value": "chiller"},
]

MODE_LABELS = {"heating": "Heating", "cooling": "Cooling"}

HIDDEN = {"display": "none"}

TABLE_STYLE = {
    "style_table": {"overflowX": "auto"},
    "style_cell": {
        "fontFamily": "inherit",
        "fontSize": 12,
        "padding": "4px 8px",
        "border": "1px solid var(--mantine-color-gray-3)",
        "minWidth": 70,
    },
    "style_header": {
        "fontWeight": 600,
        "backgroundColor": "var(--mantine-color-gray-0)",
        "whiteSpace": "normal",
        "height": "auto",
    },
}


def _action_button(label, button_id, icon, **kwargs):
    return dmc.Button(
        label,
        id=button_id,
        leftSection=DashIconify(icon=icon, width=16),
        size="xs",
        n_clicks=0,
        style=HIDDEN,
        **kwargs,
    )


def _curve_editor():
    """Scaling panel and editable curve tables, shown while a custom heat pump is edited."""
    return html.Div(
        dmc.Stack(
            [
                dmc.Paper(
                    dmc.Stack(
                        [
                            dmc.Text("Scale curves", size="sm", fw=600),
                            dmc.Group(
                                [
                                    dmc.NumberInput(
                                        id="eqm-scale-cop",
                                        label="COP factor",
                                        suffix=" %",
                                        value=100,
                                        min=1,
                                        step=1,
                                        decimalScale=1,
                                        size="xs",
                                        w=120,
                                    ),
                                    dmc.NumberInput(
                                        id="eqm-scale-cap",
                                        label="Capacity factor",
                                        suffix=" %",
                                        value=100,
                                        min=1,
                                        step=1,
                                        decimalScale=1,
                                        size="xs",
                                        w=120,
                                    ),
                                    dmc.Button(
                                        "Apply", id="eqm-scale-apply", size="xs", n_clicks=0
                                    ),
                                ],
                                align="flex-end",
                                gap="sm",
                            ),
                            dmc.Text(
                                "Factors are relative to the curves before any scaling and apply "
                                "to every supply temperature of the selected mode. Applying the "
                                "same factor again changes nothing.",
                                size="xs",
                                c="dimmed",
                            ),
                        ],
                        gap=6,
                    ),
                    withBorder=True,
                    radius="sm",
                    p="sm",
                ),
                dmc.Text("Curve points", size="sm", fw=600),
                dash_table.DataTable(
                    id="eqm-curve-editor",
                    data=[],
                    columns=[],
                    editable=True,
                    row_deletable=True,
                    **TABLE_STYLE,
                ),
                dmc.Group(
                    dmc.Button(
                        "Add point",
                        id="eqm-add-point",
                        leftSection=DashIconify(icon="tabler:row-insert-bottom", width=16),
                        size="xs",
                        variant="light",
                        n_clicks=0,
                    )
                ),
                dmc.Text("Supply temperatures", size="sm", fw=600, mt="xs"),
                dash_table.DataTable(
                    id="eqm-lwt-editor",
                    data=[],
                    columns=[],
                    editable=True,
                    **TABLE_STYLE,
                ),
                dmc.Group(
                    [
                        dmc.NumberInput(id="eqm-new-lwt", placeholder="New", size="xs", w=110),
                        dmc.Button(
                            "Add supply temperature",
                            id="eqm-add-lwt",
                            size="xs",
                            variant="light",
                            n_clicks=0,
                        ),
                        dmc.Select(id="eqm-remove-lwt-select", data=[], size="xs", w=110),
                        dmc.Button(
                            "Remove",
                            id="eqm-remove-lwt",
                            size="xs",
                            variant="light",
                            color="red",
                            n_clicks=0,
                        ),
                    ],
                    gap="xs",
                ),
                dmc.Text(
                    "A new supply temperature starts as a copy of the nearest existing curve. "
                    "The supply temperature limits of the mode follow the range of the curves.",
                    size="xs",
                    c="dimmed",
                ),
                html.Div(id="eqm-curve-editor-msg"),
            ],
            gap="xs",
        ),
        id="eqm-curve-editor-wrap",
        style=HIDDEN,
    )


def layout():
    return dmc.Container(
        [
            dcc.Store(id="eqm-selected-store", storage_type="session"),
            dcc.Store(id="eqm-draft-store", storage_type="memory", data=None),
            dcc.Store(id="eqm-edit-session", storage_type="memory", data=None),
            dcc.Store(id="eqm-form-version", storage_type="memory", data=0),
            dmc.Stack(
                [
                    with_icon_and_tooltip(
                        "Equipment Manager",
                        "equipment_manager.docs",
                        order=5,
                        icon="basil:book-open-outline",
                        href=LINKS.EQUIPMENT_DOCS_URL.value,
                    ),
                    dmc.Text(
                        "Browse the equipment library and inspect the data behind each item. "
                        "Duplicate an item to make an editable custom copy; library equipment "
                        "itself is never changed.",
                        size="sm",
                        c="dimmed",
                    ),
                ],
                gap=3,
                mt="md",
                mb="sm",
            ),
            dmc.Grid(
                [
                    dmc.GridCol(
                        dmc.Paper(
                            dmc.Stack(
                                [
                                    dmc.SegmentedControl(
                                        id="eqm-type-filter",
                                        data=TYPE_FILTERS,
                                        value="all",
                                        size="xs",
                                        fullWidth=True,
                                    ),
                                    dmc.TextInput(
                                        id="eqm-search",
                                        placeholder="Search model, manufacturer or ID",
                                        leftSection=DashIconify(icon="tabler:search", width=16),
                                        size="sm",
                                        debounce=300,
                                    ),
                                    dmc.ScrollArea(
                                        html.Div(id="eqm-list"),
                                        h=640,
                                        type="hover",
                                        offsetScrollbars=True,
                                    ),
                                ],
                                gap="sm",
                            ),
                            shadow="xs",
                            radius="md",
                            p="md",
                        ),
                        span={"base": 12, "md": 4},
                    ),
                    dmc.GridCol(
                        dmc.Paper(
                            dmc.Stack(
                                [
                                    html.Div(id="eqm-detail-header"),
                                    dmc.Group(
                                        [
                                            _action_button(
                                                "Duplicate to edit",
                                                "eqm-duplicate-btn",
                                                "tabler:copy",
                                                variant="light",
                                            ),
                                            _action_button("Edit", "eqm-edit-btn", "tabler:pencil"),
                                            _action_button(
                                                "Delete",
                                                "eqm-delete-btn",
                                                "tabler:trash",
                                                variant="subtle",
                                                color="red",
                                            ),
                                            _action_button(
                                                "Save", "eqm-save-btn", "tabler:device-floppy"
                                            ),
                                            _action_button(
                                                "Cancel",
                                                "eqm-cancel-btn",
                                                "tabler:x",
                                                variant="default",
                                            ),
                                        ],
                                        gap="xs",
                                    ),
                                    html.Div(id="eqm-action-msg"),
                                    dmc.Tabs(
                                        [
                                            dmc.TabsList(
                                                [
                                                    dmc.TabsTab("Performance", value="performance"),
                                                    dmc.TabsTab("Overview", value="overview"),
                                                ]
                                            ),
                                            dmc.TabsPanel(
                                                dmc.Stack(
                                                    [
                                                        dmc.SegmentedControl(
                                                            id="eqm-mode",
                                                            data=[],
                                                            value=None,
                                                            size="xs",
                                                            style={"alignSelf": "flex-start"},
                                                        ),
                                                        html.Div(id="eqm-issues"),
                                                        dcc.Graph(
                                                            id="eqm-curve-graph",
                                                            figure=empty_figure(""),
                                                            config={"displaylogo": False},
                                                        ),
                                                        html.Div(id="eqm-curve-table"),
                                                        _curve_editor(),
                                                    ],
                                                    gap="sm",
                                                    pt="sm",
                                                ),
                                                value="performance",
                                            ),
                                            dmc.TabsPanel(
                                                html.Div(
                                                    id="eqm-overview", style={"paddingTop": 8}
                                                ),
                                                value="overview",
                                            ),
                                        ],
                                        value="performance",
                                    ),
                                ],
                                gap="sm",
                            ),
                            shadow="xs",
                            radius="md",
                            p="md",
                        ),
                        span={"base": 12, "md": 8},
                    ),
                ],
                gutter="md",
            ),
        ],
        fluid=True,
    )


# ---------------------------------------- Helpers ----------------------------------------


def _resolve_selected_id(equipment_list, selected_id):
    """The selected eq_id if it still exists, otherwise the first heat pump in the library."""
    ids = [e.get("eq_id") for e in equipment_list]
    if selected_id in ids:
        return selected_id
    first_hp = next(
        (e["eq_id"] for e in equipment_list if e.get("eq_type") in HEAT_PUMP_TYPES), None
    )
    return first_hp or (ids[0] if ids else None)


def _find_equipment(equipment_data, eq_id) -> Equipment | None:
    eq = next(
        (e for e in (equipment_data or {}).get("equipment", []) if e.get("eq_id") == eq_id), None
    )
    return Equipment(**eq) if eq else None


def _editing(session, draft, selected_id) -> bool:
    """Whether the selected item is open in the editor."""
    return bool(session and draft and session.get("eq_id") == selected_id)


def _capacity_label(eq: Equipment, unit_mode: str) -> str:
    """Capacity as shown in the scenario dropdowns (see equipment_page._build_equipment_options)."""
    if eq.eq_calc_type != "specific":
        return "Infinite capacity"
    if eq.eq_type == "backup_heating":
        return format_with_auto_scale(eq.capacity_W, "power", unit_mode)
    return format_with_auto_scale(eq.nominal_capacity_W, "power_cooling", unit_mode)


def _source_badge(eq: Equipment):
    if eq.source == "custom":
        return dmc.Badge("Custom", color="grape", variant="light", size="sm")
    return dmc.Badge("Library", color="gray", variant="light", size="sm")


def _scaling_text(eq: Equipment) -> str | None:
    if not eq.scaling:
        return None
    return "; ".join(
        f"{MODE_LABELS.get(m, m)}: COP {f.get('cop', 1) * 100:.0f} %, "
        f"capacity {f.get('capacity', 1) * 100:.0f} %"
        for m, f in eq.scaling.items()
    )


def _list_item(eq: Equipment, selected: bool, unit_mode: str):
    title = f"{eq.eq_manufacturer} {eq.model}" if eq.eq_manufacturer else eq.model
    return dmc.UnstyledButton(
        dmc.Paper(
            dmc.Group(
                [
                    dmc.Stack(
                        [
                            dmc.Text(title, size="sm", fw=600),
                            dmc.Text(
                                f"{eq.eq_id} · {_capacity_label(eq, unit_mode)}",
                                size="xs",
                                c="dimmed",
                            ),
                        ],
                        gap=0,
                    ),
                    _source_badge(eq),
                ],
                justify="space-between",
                wrap="nowrap",
            ),
            p="xs",
            radius="sm",
            withBorder=True,
            style={
                "borderColor": "var(--mantine-color-blue-6)" if selected else None,
                "backgroundColor": "var(--mantine-color-blue-0)" if selected else None,
            },
        ),
        id={"type": "eqm-item", "eq_id": eq.eq_id},
        n_clicks=0,
        w="100%",
    )


def _overview_table(eq: Equipment, unit_mode: str):
    def fmt(value, category=None, decimals=1):
        if value is None:
            return "—"
        if category:
            return format_with_auto_scale(value, category, unit_mode, decimals=decimals)
        return str(value)

    rows = [
        ("ID", eq.eq_id),
        ("Type", TYPE_LABELS.get(eq.eq_type, eq.eq_type)),
        ("Subtype", fmt(eq.eq_subtype)),
        ("Manufacturer", fmt(eq.eq_manufacturer)),
        ("Model", eq.model),
        (
            "Source",
            "Custom" + (f" (based on {eq.based_on})" if eq.based_on else "")
            if eq.source == "custom"
            else "Library",
        ),
        ("Fuel", eq.fuel.replace("_", " ")),
        ("Capacity", _capacity_label(eq, unit_mode)),
    ]
    if eq.eq_type == "heat_pump" and eq.capacity_W:
        rows.append(("Fixed unit capacity", fmt(eq.capacity_W, "power")))
    for mode, perf in eq.performance.items():
        if perf.efficiency is not None:
            label = "Efficiency" if eq.eq_type == "backup_heating" else "COP"
            value = (
                f"{perf.efficiency * 100:.0f} %"
                if eq.eq_type == "backup_heating"
                else f"{perf.efficiency:.2f}"
            )
            rows.append((f"{label} ({mode})", value))
    if eq.scaling:
        rows.append(("Curve scaling", _scaling_text(eq)))
    if eq.eq_type in HEAT_PUMP_TYPES or eq.refrigerant:
        rows += [
            ("Refrigerant", fmt(eq.refrigerant)),
            ("Refrigerant GWP", fmt(eq.refrigerant_gwp, "gwp", decimals=0)),
            ("Refrigerant charge", fmt(eq.refrigerant_weight_g, "mass_g")),
            ("Operating weight", fmt(eq.operating_weight_g, "mass_g", decimals=0)),
        ]
    if eq.dimensions:
        d = eq.dimensions
        factor, unit = (1, "m") if unit_mode == "SI" else (3.28084, "ft")
        dims = [v for v in (d.length, d.width, d.height) if v is not None]
        rows.append(
            ("Dimensions (L x W x H)", " x ".join(f"{v * factor:.1f}" for v in dims) + f" {unit}")
        )
    if eq.electrical:
        e = eq.electrical
        rows.append(
            ("Electrical", f"MCA {fmt(e.mca)} A · {fmt(e.voltage)} V · {fmt(e.phase)} phase")
        )
    if eq.max_output_dba is not None:
        rows.append(("Max. sound level", f"{eq.max_output_dba:.0f} dBA"))
    if eq.notes:
        rows.append(("Notes", eq.notes))

    # Explicit rows: components inside Table's `data` prop are not rendered by Dash
    return dmc.Table(
        dmc.TableTbody(
            [
                dmc.TableTr(
                    [
                        dmc.TableTd(dmc.Text(k, size="sm", c="dimmed")),
                        dmc.TableTd(dmc.Text(v, size="sm")),
                    ]
                )
                for k, v in rows
            ]
        ),
        withRowBorders=True,
        verticalSpacing=6,
    )


def _issues_block(eq: Equipment, mode: str):
    issues = validate_equipment(eq, (mode,))
    if not issues:
        return dmc.Text(
            [
                DashIconify(icon="tabler:circle-check", width=14, style={"verticalAlign": "-2px"}),
                " Data checks passed",
            ],
            size="xs",
            c="green",
        )
    return dmc.Stack(
        [
            dmc.Alert(
                i.message,
                color="red" if i.severity == "error" else "yellow",
                variant="light",
                p="xs",
                title="Error" if i.severity == "error" else "Warning",
            )
            for i in issues
        ],
        gap=4,
    )


def _curve_data_table(eq: Equipment, mode: str, unit_mode: str):
    """Wide table: one row per curve point, a COP (and capacity) column per supply temperature."""
    df = curve_table(eq, mode)
    if df.empty:
        return None

    to_temp = get_converter("temperature", unit_mode)
    t_unit = get_display_unit("temperature", unit_mode)
    cap_category = "power_cooling" if mode == "cooling" else "power"
    is_awhp = df["x_kind"].iloc[0] == "t_out_C"

    # one scale for the whole table, matching the plot axis
    cap_scale, cap_unit = get_auto_scale(
        df["capacity_W"].dropna().tolist() or [eq.capacity_W or 0], cap_category, unit_mode
    )

    def cap(v):
        return "—" if pd.isna(v) else f"{v / cap_scale:,.1f}"

    lwts = sorted(df["lwt_C"].unique())
    x_points = sorted(df["x"].unique())
    has_cap = is_awhp and df["capacity_W"].notna().any()

    head = [f"OAT [{t_unit}]" if is_awhp else f"Capacity [{cap_unit}]"]
    for lwt in lwts:
        head.append(f"COP @ {to_temp(lwt):.1f} {t_unit}")
        if has_cap:
            head.append(f"Capacity @ {to_temp(lwt):.1f} {t_unit} [{cap_unit}]")

    body = []
    for x in x_points:
        row = [f"{to_temp(x):.1f}" if is_awhp else cap(x)]
        for lwt in lwts:
            point = df[(df["lwt_C"] == lwt) & (df["x"] == x)].iloc[0]
            row.append(f"{point['cop']:.2f}")
            if has_cap:
                row.append(cap(point["capacity_W"]))
        body.append(row)

    caption = None
    if is_awhp:
        limits = df.groupby("lwt_C")[["oat_min_C", "oat_max_C"]].first().sort_index().itertuples()
        caption = "Outdoor air temperature limits: " + "; ".join(
            f"{to_temp(r.Index):.1f} {t_unit}: {to_temp(r.oat_min_C):.1f} to {to_temp(r.oat_max_C):.1f} {t_unit}"
            for r in limits
        )
        if not has_cap and eq.capacity_W:
            caption += f". Fixed unit capacity: {format_with_auto_scale(eq.capacity_W, cap_category, unit_mode)}"

    return dmc.Stack(
        [
            dmc.TableScrollContainer(
                dmc.Table(
                    data={"head": head, "body": body},
                    striped=True,
                    highlightOnHover=True,
                    fz="xs",
                    verticalSpacing=4,
                ),
                minWidth=400,
            ),
            dmc.Text(caption, size="xs", c="dimmed") if caption else None,
        ],
        gap=4,
    )


def _message(text, color="blue"):
    return dmc.Alert(text, color=color, variant="light", p="xs", withCloseButton=True)


# ---------------------------------------- Callbacks ----------------------------------------


@callback(
    Output("eqm-list", "children"),
    Input("equipment-store", "data"),
    Input("eqm-type-filter", "value"),
    Input("eqm-search", "value"),
    Input("eqm-selected-store", "data"),
    Input("unit-toggle", "value"),
)
def render_equipment_list(equipment_data, type_filter, search, selected_id, unit_mode):
    equipment_list = (equipment_data or {}).get("equipment", [])
    if not equipment_list:
        return dmc.Text("No equipment available.", size="sm", c="dimmed")

    selected_id = _resolve_selected_id(equipment_list, selected_id)
    query = (search or "").strip().lower()

    groups = []
    for eq_type, label in TYPE_LABELS.items():
        if type_filter not in (None, "all", eq_type):
            continue
        items = []
        for e in equipment_list:
            if e.get("eq_type") != eq_type:
                continue
            haystack = " ".join(str(e.get(k) or "") for k in ("eq_id", "model", "eq_manufacturer"))
            if query and query not in haystack.lower():
                continue
            items.append(_list_item(Equipment(**e), e["eq_id"] == selected_id, unit_mode or "SI"))
        if items:
            groups.append(dmc.Text(label, size="xs", fw=700, c="dimmed", tt="uppercase", mt="xs"))
            groups.extend(items)

    if not groups:
        return dmc.Text("No equipment matches the filter.", size="sm", c="dimmed")
    return dmc.Stack(groups, gap=6)


@callback(
    Output("eqm-selected-store", "data"),
    Output("eqm-draft-store", "data", allow_duplicate=True),
    Output("eqm-edit-session", "data", allow_duplicate=True),
    Output("eqm-action-msg", "children", allow_duplicate=True),
    Input({"type": "eqm-item", "eq_id": ALL}, "n_clicks"),
    State("eqm-edit-session", "data"),
    prevent_initial_call=True,
)
def select_equipment(n_clicks, session):
    # The list is re-rendered on every selection, which re-fires this with n_clicks=0
    if not ctx.triggered_id or not any(n_clicks or []):
        return no_update, no_update, no_update, no_update
    eq_id = ctx.triggered_id["eq_id"]
    if session and session.get("eq_id") != eq_id:
        # selecting another item discards unsaved edits
        return eq_id, None, None, None
    return eq_id, no_update, no_update, no_update


@callback(
    Output("eqm-mode", "data"),
    Output("eqm-mode", "value"),
    Output("eqm-mode", "style"),
    Input("eqm-selected-store", "data"),
    Input("equipment-store", "data"),
    State("eqm-mode", "value"),
)
def update_mode_options(selected_id, equipment_data, current_mode):
    equipment_list = (equipment_data or {}).get("equipment", [])
    eq = _find_equipment(equipment_data, _resolve_selected_id(equipment_list, selected_id))
    modes = list(eq.performance) if eq else []
    data = [{"label": MODE_LABELS.get(m, m.title()), "value": m} for m in modes]
    value = current_mode if current_mode in modes else (modes[0] if modes else None)
    style = {"alignSelf": "flex-start", "display": "flex" if len(modes) > 1 else "none"}
    return data, value, style


@callback(
    Output("eqm-duplicate-btn", "style"),
    Output("eqm-duplicate-btn", "children"),
    Output("eqm-edit-btn", "style"),
    Output("eqm-delete-btn", "style"),
    Output("eqm-save-btn", "style"),
    Output("eqm-cancel-btn", "style"),
    Input("eqm-selected-store", "data"),
    Input("equipment-store", "data"),
    Input("eqm-edit-session", "data"),
    Input("eqm-draft-store", "data"),
)
def update_action_buttons(selected_id, equipment_data, session, draft):
    show = {}
    equipment_list = (equipment_data or {}).get("equipment", [])
    selected_id = _resolve_selected_id(equipment_list, selected_id)
    eq = _find_equipment(equipment_data, selected_id)
    if eq is None:
        return HIDDEN, no_update, HIDDEN, HIDDEN, HIDDEN, HIDDEN
    if _editing(session, draft, selected_id):
        return HIDDEN, no_update, HIDDEN, HIDDEN, show, show
    if eq.source == "custom":
        return show, "Duplicate", show, show, HIDDEN, HIDDEN
    return show, "Duplicate to edit", HIDDEN, HIDDEN, HIDDEN, HIDDEN


@callback(
    Output("equipment-store", "data", allow_duplicate=True),
    Output("eqm-selected-store", "data", allow_duplicate=True),
    Output("eqm-draft-store", "data", allow_duplicate=True),
    Output("eqm-edit-session", "data", allow_duplicate=True),
    Output("eqm-action-msg", "children"),
    Input("eqm-duplicate-btn", "n_clicks"),
    Input("eqm-edit-btn", "n_clicks"),
    Input("eqm-delete-btn", "n_clicks"),
    Input("eqm-save-btn", "n_clicks"),
    Input("eqm-cancel-btn", "n_clicks"),
    State("eqm-selected-store", "data"),
    State("equipment-store", "data"),
    State("equipment-initial-store", "data"),
    State("eqm-draft-store", "data"),
    prevent_initial_call=True,
)
def handle_actions(
    _dup, _edit, _delete, _save, _cancel, selected_id, equipment_data, initial_data, draft
):
    trigger = ctx.triggered_id
    if not trigger or not ctx.triggered[0]["value"]:
        return (no_update,) * 5

    equipment_list = (equipment_data or {}).get("equipment", [])
    selected_id = _resolve_selected_id(equipment_list, selected_id)
    eq = _find_equipment(equipment_data, selected_id)
    library_ids = [e["eq_id"] for e in (initial_data or {}).get("equipment", [])]

    if trigger == "eqm-cancel-btn":
        return no_update, no_update, None, None, None

    if eq is None:
        return (no_update,) * 4 + (_message("No equipment selected.", "red"),)

    if trigger == "eqm-duplicate-btn":
        copy = duplicate_equipment(eq, [e["eq_id"] for e in equipment_list])
        updated = save_custom_equipment(equipment_data, copy, library_ids)
        logger.info("Created custom equipment '%s' from '%s'", copy.eq_id, eq.eq_id)
        return (
            updated,
            copy.eq_id,
            copy.model_dump(),
            {"eq_id": copy.eq_id, "started": time.time()},
            _message(f"Created the custom copy {copy.eq_id}. Edit it below, then Save."),
        )

    if trigger == "eqm-edit-btn":
        if eq.source != "custom":
            return (no_update,) * 4 + (_message("Library equipment cannot be edited.", "red"),)
        return (
            no_update,
            no_update,
            eq.model_dump(),
            {"eq_id": eq.eq_id, "started": time.time()},
            None,
        )

    if trigger == "eqm-delete-btn":
        try:
            updated = delete_custom_equipment(equipment_data, eq.eq_id)
        except ValueError as err:
            return (no_update,) * 4 + (_message(str(err), "red"),)
        logger.info("Deleted custom equipment '%s'", eq.eq_id)
        return updated, eq.based_on, None, None, _message(f"Deleted {eq.eq_id}.")

    # save
    if not draft:
        return (no_update,) * 5
    edited = Equipment(**draft)
    errors = [i for i in validate_equipment(edited) if i.severity == "error"]
    if errors:
        return (no_update,) * 4 + (
            _message(
                [
                    dmc.Text("Fix these problems before saving:", size="sm"),
                    dmc.List([dmc.ListItem(i.message) for i in errors], size="sm"),
                ],
                "red",
            ),
        )
    try:
        updated = save_custom_equipment(equipment_data, edited, library_ids)
    except ValueError as err:
        return (no_update,) * 4 + (_message(str(err), "red"),)
    logger.info("Saved custom equipment '%s'", edited.eq_id)
    return updated, no_update, None, None, _message(f"Saved {edited.eq_id}.", "green")


@callback(
    Output("eqm-overview", "children"),
    Input("eqm-selected-store", "data"),
    Input("equipment-store", "data"),
    Input("unit-toggle", "value"),
    Input("eqm-edit-session", "data"),
    Input("eqm-form-version", "data"),
    State("eqm-draft-store", "data"),
)
def render_overview(selected_id, equipment_data, unit_mode, session, _version, draft):
    # Rendered from the draft only when editing starts or the units change, so that typing
    # in the form is not interrupted by re-rendering it
    unit_mode = unit_mode or "SI"
    equipment_list = (equipment_data or {}).get("equipment", [])
    selected_id = _resolve_selected_id(equipment_list, selected_id)
    if _editing(session, draft, selected_id):
        return overview_form(draft, unit_mode)
    eq = _find_equipment(equipment_data, selected_id)
    return _overview_table(eq, unit_mode) if eq else None


@callback(
    Output("eqm-draft-store", "data", allow_duplicate=True),
    Input({"type": "eqm-field", "name": ALL}, "value"),
    State({"type": "eqm-field", "name": ALL}, "id"),
    State("eqm-draft-store", "data"),
    State("eqm-edit-session", "data"),
    State("unit-toggle", "value"),
    prevent_initial_call=True,
)
def update_draft_from_form(values, ids, draft, session, unit_mode):
    if not draft or not session or not ids:
        return no_update
    unit_mode = unit_mode or "SI"
    triggered = {t["prop_id"].rsplit(".", 1)[0] for t in ctx.triggered}
    changed = False
    for field_id, value in zip(ids, values, strict=True):
        name = field_id["name"]
        if _id_str(field_id) not in triggered:
            continue
        if value == display_value(draft, name, unit_mode):
            continue  # keep the stored value instead of its rounded display value
        _, kind, _, to_base, _ = field_meta(name, draft, unit_mode)
        if kind in ("text", "textarea", "calc_type", "refrigerant"):
            new = (value or "").strip() or None
            if name == "model" and new is None:
                continue  # the model name is required
        elif value in (None, ""):
            new = None
        else:
            new = to_base(float(value))
            if name in ("nominal_capacity_W", "electrical.phase"):
                new = round(new)
        set_path(draft, name, new)
        if name == "refrigerant" and (match := find_refrigerant(new)) is not None:
            draft["refrigerant_gwp"] = match.gwp
        changed = True
    return draft if changed else no_update


def _id_str(field_id: dict) -> str:
    """A pattern-matching id as it appears in ctx.triggered prop ids."""
    return json.dumps(field_id, sort_keys=True, separators=(",", ":"))


@callback(
    Output({"type": "eqm-field", "name": "refrigerant_gwp"}, "value"),
    Output({"type": "eqm-field", "name": "refrigerant_gwp"}, "disabled"),
    Input({"type": "eqm-field", "name": "refrigerant"}, "value"),
    prevent_initial_call=True,
)
def fill_refrigerant_gwp(refrigerant):
    match = find_refrigerant(refrigerant)
    if match is None:
        return no_update, False  # unknown refrigerant: enter the GWP manually
    return match.gwp, True


@callback(
    Output("eqm-detail-header", "children"),
    Output("eqm-issues", "children"),
    Output("eqm-curve-graph", "figure"),
    Output("eqm-curve-graph", "style"),
    Output("eqm-curve-table", "children"),
    Output("eqm-curve-editor-wrap", "style"),
    Input("eqm-selected-store", "data"),
    Input("eqm-mode", "value"),
    Input("equipment-store", "data"),
    Input("unit-toggle", "value"),
    Input("eqm-draft-store", "data"),
    Input("eqm-edit-session", "data"),
)
def render_equipment_detail(selected_id, mode, equipment_data, unit_mode, draft, session):
    unit_mode = unit_mode or "SI"
    equipment_list = (equipment_data or {}).get("equipment", [])
    selected_id = _resolve_selected_id(equipment_list, selected_id)
    editing = _editing(session, draft, selected_id)
    eq = Equipment(**draft) if editing else _find_equipment(equipment_data, selected_id)
    if eq is None:
        return None, None, empty_figure("No equipment selected"), HIDDEN, None, HIDDEN

    if mode not in eq.performance:
        mode = next(iter(eq.performance), None)

    title = f"{eq.eq_manufacturer} {eq.model}" if eq.eq_manufacturer else eq.model
    badges = [_source_badge(eq)]
    if editing:
        badges.insert(0, dmc.Badge("Editing", color="orange", variant="filled", size="sm"))
    header = dmc.Group(
        [
            dmc.Stack(
                [
                    dmc.Title(title, order=4),
                    dmc.Text(
                        f"{TYPE_LABELS.get(eq.eq_type, eq.eq_type)} · {eq.eq_id}",
                        size="sm",
                        c="dimmed",
                    ),
                ],
                gap=0,
            ),
            dmc.Group(badges, gap=4),
        ],
        justify="space-between",
    )

    issues = _issues_block(eq, mode) if mode else None

    if eq.eq_type not in HEAT_PUMP_TYPES:
        perf = eq.performance.get(mode) if mode else None
        if perf and perf.efficiency is not None:
            text = (
                f"Constant efficiency of {perf.efficiency * 100:.0f} %."
                if eq.eq_type == "backup_heating"
                else f"Constant COP of {perf.efficiency:.2f}."
            )
        else:
            text = "No performance data."
        note = f"{text} This equipment has no performance curves."
        if editing:
            note += " Edit its efficiency in the Overview tab."
        return header, issues, empty_figure(""), HIDDEN, dmc.Text(note, size="sm"), HIDDEN

    compare_to = None
    if editing or eq.source == "custom":
        compare_to = _find_equipment(equipment_data, eq.based_on) if eq.based_on else None
    if not editing or _plottable(eq, mode):
        fig = plot_performance_curves(eq, mode, unit_mode, compare_to=compare_to)
    else:
        fig = empty_figure("Fix the errors above to see the curves")
    if editing:
        return header, issues, fig, {}, None, {}
    return header, issues, fig, {}, _curve_data_table(eq, mode, unit_mode), HIDDEN


def _plottable(eq: Equipment, mode: str) -> bool:
    """Whether a draft's curves can be drawn: errors in limits or values still plot, broken shapes do not."""
    try:
        df = curve_table(eq, mode)
    except (ValueError, TypeError):
        return False
    return not df.empty and df["x"].notna().all()


@callback(
    Output("eqm-draft-store", "data", allow_duplicate=True),
    Output("eqm-curve-editor", "data"),
    Output("eqm-curve-editor", "columns"),
    Output("eqm-lwt-editor", "data"),
    Output("eqm-lwt-editor", "columns"),
    Output("eqm-remove-lwt-select", "data"),
    Output("eqm-remove-lwt-select", "value"),
    Output("eqm-scale-cop", "value"),
    Output("eqm-scale-cap", "value"),
    Output("eqm-curve-editor-msg", "children"),
    Output("eqm-form-version", "data"),
    Input("eqm-edit-session", "data"),
    Input("eqm-mode", "value"),
    Input("unit-toggle", "value"),
    Input("eqm-curve-editor", "data_timestamp"),
    Input("eqm-lwt-editor", "data_timestamp"),
    Input("eqm-scale-apply", "n_clicks"),
    Input("eqm-add-point", "n_clicks"),
    Input("eqm-add-lwt", "n_clicks"),
    Input("eqm-remove-lwt", "n_clicks"),
    State("eqm-curve-editor", "data"),
    State("eqm-lwt-editor", "data"),
    State("eqm-draft-store", "data"),
    State("eqm-scale-cop", "value"),
    State("eqm-scale-cap", "value"),
    State("eqm-new-lwt", "value"),
    State("eqm-remove-lwt-select", "value"),
    State("eqm-form-version", "data"),
    prevent_initial_call=True,
)
def edit_curves(
    session,
    mode,
    unit_mode,
    _curve_ts,
    _lwt_ts,
    _scale,
    _add_point,
    _add_lwt,
    _remove_lwt,
    rows,
    lwt_rows,
    draft,
    cop_pct,
    cap_pct,
    new_lwt,
    remove_lwt,
    form_version,
):
    """All edits of the curves of the draft; the tables are re-rendered after structural changes."""
    unit_mode = unit_mode or "SI"
    if not session or not draft or draft.get("eq_type") not in HEAT_PUMP_TYPES:
        return (no_update,) * 11
    eq = Equipment(**draft)
    if mode not in eq.performance:
        mode = next(iter(eq.performance), None)
    if mode is None:
        return (no_update,) * 11

    trigger = ctx.triggered_id
    message = None
    rerender_form = False

    def render(eq, new_draft):
        tables = editor_tables(eq, mode, unit_mode)
        lwt_options = [
            {"label": f"{r['lwt']:.1f}", "value": str(i)} for i, r in enumerate(tables[2])
        ]
        cop, cap = scale_values(eq, mode)
        return (
            new_draft,
            *tables,
            lwt_options,
            None,
            cop,
            cap,
            message,
            form_version + 1 if rerender_form else no_update,
        )

    if trigger in ("eqm-edit-session", "eqm-mode", "unit-toggle"):
        return render(eq, no_update)

    try:
        if trigger == "eqm-curve-editor":
            # plain value edits: update the draft, keep the table as typed
            df = tables_to_long(eq, mode, unit_mode, rows or [], lwt_rows or [])
            if df.empty:
                return (no_update,) * 9 + (
                    _message("Keep at least one curve point.", "red"),
                    no_update,
                )
            eq = apply_curve_table(eq, mode, df)
            return (eq.model_dump(),) + (no_update,) * 10

        if trigger == "eqm-lwt-editor":
            lwts = [to_float(r.get("lwt")) for r in lwt_rows or []]
            if any(pd.isna(t) for t in lwts) or len({round(t, 1) for t in lwts}) < len(lwts):
                return (no_update,) * 9 + (
                    _message("Each supply temperature needs a value, and no value twice.", "red"),
                    no_update,
                )
            df = tables_to_long(eq, mode, unit_mode, rows or [], lwt_rows or [])
            eq = apply_curve_table(eq, mode, df)

        elif trigger == "eqm-scale-apply":
            eq = scale_performance(eq, mode, (cop_pct or 100) / 100, (cap_pct or 100) / 100)
            rerender_form = True  # nominal and fixed capacity are shown in the form

        elif trigger == "eqm-add-point":
            rows = [dict(r) for r in rows or []]
            if not rows:
                return (no_update,) * 11
            xs = [to_float(r.get("x")) for r in rows]
            step = xs[-1] - xs[-2] if len(xs) > 1 else 5.0
            rows.append({**rows[-1], "x": xs[-1] + step})
            eq = apply_curve_table(eq, mode, tables_to_long(eq, mode, unit_mode, rows, lwt_rows))

        elif trigger == "eqm-add-lwt":
            if new_lwt in (None, ""):
                return (no_update,) * 9 + (
                    _message("Enter the new supply temperature.", "red"),
                    no_update,
                )
            (_, t_base, _), _ = editor_units(mode, unit_mode)
            lwt_C = t_base(float(new_lwt))
            df = curve_table(eq, mode)
            if (df["lwt_C"] - lwt_C).abs().min() < 0.05:
                return (no_update,) * 9 + (
                    _message("This supply temperature already exists.", "red"),
                    no_update,
                )
            nearest = df.loc[(df["lwt_C"] - lwt_C).abs().idxmin(), "lwt_C"]
            new_curve = df[df["lwt_C"] == nearest].assign(lwt_C=lwt_C)
            eq = apply_curve_table(eq, mode, pd.concat([df, new_curve], ignore_index=True))
            message = _message(
                "Added a copy of the nearest curve. Adjust its values in the table above."
            )

        elif trigger == "eqm-remove-lwt":
            df = curve_table(eq, mode)
            lwts = sorted(df["lwt_C"].unique())
            if remove_lwt is None:
                return (no_update,) * 9 + (
                    _message("Pick the supply temperature to remove.", "red"),
                    no_update,
                )
            if len(lwts) < 2:
                return (no_update,) * 9 + (
                    _message("Keep at least one supply temperature.", "red"),
                    no_update,
                )
            eq = apply_curve_table(eq, mode, df[df["lwt_C"] != lwts[int(remove_lwt)]])

        else:
            return (no_update,) * 11
    except (ValueError, TypeError, KeyError) as err:
        return (no_update,) * 9 + (_message(f"Could not apply the change: {err}", "red"), no_update)

    return render(eq, eq.model_dump())
