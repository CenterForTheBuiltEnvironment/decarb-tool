import dash_bootstrap_components as dbc
from dash import html

import dash_mantine_components as dmc
from dash_iconify import DashIconify


def get_nested_value(obj, attr_path):
    """Fetch nested values using dot-separated path.
    Handles dicts, objects, and lists of dicts/objects."""
    parts = attr_path.split(".")

    # Walk down each level
    for part in parts:
        if isinstance(obj, list):
            # Apply recursively to each item
            obj = [
                get_nested_value(o, ".".join(parts[parts.index(part) :])) for o in obj
            ]
            # Stop recursion once we’ve handled list expansion
            return obj
        elif isinstance(obj, dict):
            obj = obj.get(part)
        else:
            obj = getattr(obj, part, None)
    return obj


def make_metadata_card(metadata, fields, title="Summary"):
    """
    Create a Bootstrap card with a table of selected metadata fields.
    """
    # Normalize to dict if object has __dict__
    meta_dict = metadata.__dict__ if hasattr(metadata, "__dict__") else metadata

    table_rows = []
    for attr_path, label in fields:
        value = get_nested_value(meta_dict, attr_path)
        if isinstance(value, list):
            value = ", ".join(map(str, value))
        table_rows.append(html.Tr([html.Td(label), html.Td(str(value))]))

    return dbc.Card(
        [
            dbc.CardHeader(title),
            dbc.CardBody(
                [
                    dbc.Table(
                        [html.Tbody(table_rows)],
                        bordered=True,
                        hover=True,
                        responsive=True,
                        size="sm",
                        style={"fontSize": "14px"},
                    )
                ]
            ),
        ]
    )


def building_characteristics_card(metadata):

    building_fields = [
        ("location", "Location"),
        ("building_type", "Building Type"),
        ("vintage", "Vintage"),
        ("ashrae_climate_zone", "Climate Region"),
    ]

    building_characteristics_card = make_metadata_card(
        metadata, building_fields, title="Building characteristics"
    )

    return building_characteristics_card


def load_characteristics_card(metadata):

    load_fields = [
        ("location", "Location"),
        ("building_type", "Building Type"),
        ("vintage", "Vintage"),
        ("ashrae_climate_zone", "Climate Region"),
    ]

    load_characteristics_card = make_metadata_card(
        metadata, load_fields, title="Load characteristics"
    )

    return load_characteristics_card


def summary_equipment_selection(equipment_library, active_tab=None):
    eq_lookup = {
        eq["eq_id"]: f"{eq['model']}".strip() for eq in equipment_library["equipment"]
    }

    tabs = []
    for scen in equipment_library["equipment_scenarios"]:
        scen_display = scen.copy()
        for field, _ in [
            ("eq_scen_name", "Scenario"),
            ("hr_wwhp", "HR WWHP"),
            ("awhp", "AWHP"),
            ("awhp_sizing_mode", "AWHP Sizing Mode"),
            ("awhp_sizing_value", "AWHP Sizing Value"),
            ("awhp_use_cooling", "AWHP Use Cooling"),
            ("boiler", "Boiler"),
            ("chiller", "Chiller"),
        ]:
            eq_id = scen.get(field)
            if eq_id in eq_lookup:
                scen_display[field] = eq_lookup[eq_id]

        card = make_metadata_card(
            scen_display,
            [
                ("eq_scen_name", "Scenario"),
                ("hr_wwhp", "HR WWHP"),
                ("awhp", "AWHP"),
                ("awhp_sizing_mode", "AWHP Sizing Mode"),
                ("awhp_sizing_value", "AWHP Sizing Value"),
                ("awhp_use_cooling", "AWHP Use Cooling"),
                ("boiler", "Boiler"),
                ("chiller", "Chiller"),
            ],
            # title="Summary | Scenario " + scen["eq_scen_id"][-1].upper(),
            title="Summary",
        )

        tabs.append(
            dbc.Tab(
                label="Scen. " + scen["eq_scen_id"][-1].upper(),
                tab_id=scen["eq_scen_id"],
                children=[card],
                tab_style={"margin": "0.2rem"},
            )
        )

    # If no tab stored, default to first one
    default_tab = equipment_library["equipment_scenarios"][0]["eq_scen_id"]

    return dbc.Tabs(
        tabs,
        id="equipment-scenario-tabs",
        active_tab=active_tab if active_tab else default_tab,
    )


def summary_emissions_selection(metadata, active_tab=None):
    tabs = []
    for scen in metadata["emission_settings"]:
        emission_fields = [
            ("grid_scenario", "Grid Scenario"),
            ("gea_grid_region", "GEA Grid Region"),
            ("emission_type", "Emission Type"),
            ("shortrun_weighting", "Short-Run Weighting"),
            ("annual_refrig_leakage_percent", "Refrig. Leakage, p.a."),
            ("year", "Year"),
        ]
        card = make_metadata_card(
            scen,
            emission_fields,
            # title="Summary | Scenario " + scen["em_scen_id"][-1].upper(),
            title="Summary",
        )

        tabs.append(
            dbc.Tab(
                label="Scenario "
                + scen["em_scen_id"][-1].upper(),  # Tab label, e.g. "Scenario A"
                tab_id=scen["em_scen_id"],  # needed to control active tab
                children=[card],
            )
        )

    default_tab = metadata["emission_settings"][0]["em_scen_id"]  # default first one

    return (
        dbc.Tabs(
            tabs,
            id="emission-scenario-tabs",
            active_tab=active_tab if active_tab else default_tab,
        ),  #! more style in custom css
    )


def summary_project_info(metadata):

    building_fields = [
        ("location", "Location"),
        ("building_type", "Building Type"),
        ("vintage", "Vintage"),
        ("ashrae_climate_zone", "Climate Region"),
    ]

    building_card = make_metadata_card(
        metadata, building_fields, title="Building Information"
    )

    return building_card


def summary_scenario_results():
    return dbc.Card(
        [
            dbc.CardHeader("Scenario Results"),
            dbc.CardBody(
                [
                    html.P(
                        "This section will display the results of the selected scenario."
                    ),
                    html.P(
                        "More detailed results will be added here in future updates."
                    ),
                ]
            ),
        ]
    )


def empty_state(
    title="Nothing selected :(",
    description="Please make a selection to continue.",
    icon="ph:info",
    icon_size=40,
    padding=40,
):
    """
    Reusable empty-state component for placeholder panels.

    Parameters
    ----------
    title : str
        Main title text, e.g. "No load selected :(".
    description : str
        Supporting hint text shown below the title.
    icon : str
        Iconify icon name, e.g. "ph:chart-line-up".
    icon_size : int
        Icon size in pixels.
    padding : int
        Vertical padding (top + bottom) in pixels.
    """

    return dmc.Stack(
        [
            dmc.Center(
                DashIconify(icon=icon, width=icon_size),
            ),
            dmc.Text(title, fw=500),
            dmc.Text(
                description,
                size="sm",
                c="dimmed",
                ta="center",
            ),
        ],
        align="center",
        gap="xs",
        style={"padding": f"{padding}px 0"},
    )
