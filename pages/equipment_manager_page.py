import dash
import dash_mantine_components as dmc
import pandas as pd
from dash import ALL, Input, Output, State, callback, ctx, dcc, html, no_update
from dash_iconify import DashIconify

from src.config import LINKS, URLS
from src.equipment import HEAT_PUMP_TYPES, Equipment, curve_table, validate_equipment
from src.visuals import empty_figure, plot_performance_curves
from utils.logging_config import get_logger
from utils.tooltips import with_icon_and_tooltip
from utils.units import format_with_auto_scale, get_auto_scale, get_converter, get_display_unit

logger = get_logger(__name__)


dash.register_page(
    __name__,
    name="Equipment Manager",
    path=URLS.EQUIPMENT_MANAGER.value,
    order=99,  # not a workflow step; linked separately in the sidebar
)

TYPE_LABELS = {
    "hr_heat_pump": "HR water-to-water heat pump",
    "heat_pump": "Air-to-water heat pump",
    "backup_heating": "Backup heating",
    "chiller": "Chiller",
}

TYPE_FILTERS = [
    {"label": "All", "value": "all"},
    {"label": "HR WWHP", "value": "hr_heat_pump"},
    {"label": "AWHP", "value": "heat_pump"},
    {"label": "Backup", "value": "backup_heating"},
    {"label": "Chiller", "value": "chiller"},
]

MODE_LABELS = {"heating": "Heating", "cooling": "Cooling"}


def layout():
    return dmc.Container(
        [
            dcc.Store(id="eqm-selected-store", storage_type="session"),
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
                        "Browse the equipment library and inspect the data behind each item, including the performance curves of heat pumps.",
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
    for mode, perf in eq.performance.items():
        if perf.efficiency is not None:
            label = "Efficiency" if eq.eq_type == "backup_heating" else "COP"
            value = (
                f"{perf.efficiency * 100:.0f} %"
                if eq.eq_type == "backup_heating"
                else f"{perf.efficiency:.2f}"
            )
            rows.append((f"{label} ({mode})", value))
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
    Input({"type": "eqm-item", "eq_id": ALL}, "n_clicks"),
    prevent_initial_call=True,
)
def select_equipment(n_clicks):
    # The list is re-rendered on every selection, which re-fires this with n_clicks=0
    if not ctx.triggered_id or not any(n_clicks or []):
        return no_update
    return ctx.triggered_id["eq_id"]


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
    Output("eqm-detail-header", "children"),
    Output("eqm-overview", "children"),
    Output("eqm-issues", "children"),
    Output("eqm-curve-graph", "figure"),
    Output("eqm-curve-graph", "style"),
    Output("eqm-curve-table", "children"),
    Input("eqm-selected-store", "data"),
    Input("eqm-mode", "value"),
    Input("equipment-store", "data"),
    Input("unit-toggle", "value"),
)
def render_equipment_detail(selected_id, mode, equipment_data, unit_mode):
    unit_mode = unit_mode or "SI"
    equipment_list = (equipment_data or {}).get("equipment", [])
    eq = _find_equipment(equipment_data, _resolve_selected_id(equipment_list, selected_id))
    if eq is None:
        return None, None, None, empty_figure("No equipment selected"), {"display": "none"}, None

    if mode not in eq.performance:
        mode = next(iter(eq.performance), None)

    title = f"{eq.eq_manufacturer} {eq.model}" if eq.eq_manufacturer else eq.model
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
            _source_badge(eq),
        ],
        justify="space-between",
    )

    overview = _overview_table(eq, unit_mode)
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
        note = dmc.Text(f"{text} This equipment has no performance curves.", size="sm")
        return header, overview, issues, empty_figure(""), {"display": "none"}, note

    fig = plot_performance_curves(eq, mode, unit_mode)
    return header, overview, issues, fig, {}, _curve_data_table(eq, mode, unit_mode)
