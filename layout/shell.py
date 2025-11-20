# layout/shell.py

import uuid
import dash
from dash import dcc, html, Input, Output, State, ALL, callback
import dash_mantine_components as dmc

from layout.header import cbe_header
from layout.footer import cbe_footer
from layout.input import unit_toggle

from src.config import LINKS

from src.equipment import load_library  # adjust if path differs


equipment_library = load_library("data/input/equipment_data.JSON").model_dump()


def build_shell(page_content):
    """
    Build a Dash Mantine AppShell-based layout around the current page content.
    `page_content` will be dash.page_container from app.py.
    """

    # ---- global stores ----
    global_state = [
        dcc.Store(id="metadata-store"),
        dcc.Store(id="equipment-store", data=equipment_library),
        dcc.Store(id="session-store", data={"session_id": str(uuid.uuid4())}),
    ]

    header = dmc.AppShellHeader(
        dmc.Group(
            [
                cbe_header(),
            ],
            h="100%",
            px="md",
            justify="space-between",
            align="center",
        )
    )

    navbar = dmc.AppShellNavbar(
        id="navbar",
        children=build_navbar_content(),
        p="md",
    )

    main = dmc.AppShellMain(
        dmc.Stack(
            [
                dcc.Location(id="url", refresh=False),
                *global_state,
                html.Div(page_content),
            ],
            gap="md",
        )
    )

    # ---- FOOTER: wrap your existing footer ----
    footer = dmc.AppShellFooter(
        cbe_footer(),
        p=0,
    )

    appshell = dmc.AppShell(
        [
            header,
            navbar,
            main,
            footer,
        ],
        header={"height": 120},
        # footer={"height": 120},
        navbar={
            "width": 300,
            "breakpoint": "sm",
            "collapsed": {"mobile": True, "desktop": True},  # start collapsed on both
        },
        padding="md",
        id="appshell",
    )

    return dmc.MantineProvider(appshell)


def build_navbar_content():

    pages = sorted(
        dash.page_registry.values(),
        key=lambda p: p.get("order", 0),
    )

    page_links = [
        dmc.NavLink(
            label=page["name"],
            href=page["path"],
            id={"type": "navbar-link", "path": page["path"]},
            active=False,  # will be controlled by callback
        )
        for page in pages
    ]

    docs_link = dmc.Anchor(
        "Documentation",
        href=LINKS.DOCS_URL.value,
        target="_blank",
        underline=False,
        fz="sm",
    )

    return dmc.Stack(
        children=[
            dmc.Stack(page_links, gap="sm"),
            dmc.Divider(),
            unit_toggle(),
            dmc.Divider(),
            dmc.Stack(  # external resources section
                [docs_link],
                gap="xs",
            ),
        ],
        gap="md",
    )


@callback(
    Output({"type": "navbar-link", "path": ALL}, "active"),
    Input("url", "pathname"),
    State({"type": "navbar-link", "path": ALL}, "id"),
)
def set_active_navlinks(pathname, link_ids):
    # pathname: current path, e.g. "/emissions"
    # link_ids: list of {"type": "navbar-link", "path": "..."} dicts

    if pathname is None:
        return [False] * len(link_ids)

    return [(link_id["path"] == pathname) for link_id in link_ids]


@callback(
    Output("appshell", "navbar"),
    Input("burger", "opened"),
    State("appshell", "navbar"),
)
def toggle_navbar(opened, navbar):
    # Defensive copy, in case navbar is None on first call
    navbar = dict(navbar or {})
    collapsed = dict(navbar.get("collapsed", {}))

    collapsed.update(
        {
            "mobile": not opened,
            "desktop": not opened,
        }
    )

    navbar["collapsed"] = collapsed
    return navbar
