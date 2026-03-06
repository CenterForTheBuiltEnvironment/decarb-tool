import dash_bootstrap_components as dbc
from dash import html

import dash_mantine_components as dmc
from dash_iconify import DashIconify

from src.metadata import Metadata

from src.equipment import EquipmentLibrary, EquipmentScenario
from utils.units import format_with_units, get_unit_label


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


def make_metadata_card(metadata: Metadata, fields, title="", unit_mode="SI"):
    """Build a card displaying metadata fields with optional unit conversion.

    Args:
        metadata: Object with get_value() method
        fields: List of tuples. Each tuple can be:
            - (key, label) for plain text fields
            - (key, label, var_type) for unit-aware fields (var_type: "power", "area", "temperature")
        title: Card title
        unit_mode: "SI" or "IP" for unit conversion
    """
    rows = []
    for field in fields:
        # Unpack field definition
        if len(field) == 3:
            key, base_label, var_type = field
        else:
            key, base_label = field
            var_type = None

        value = metadata.get_value(key)  # ← uses Metadata.get_value

        # Format value and label based on variable type
        if var_type and value is not None:
            # Apply unit conversion and formatting
            display_value = format_with_units(value, var_type, unit_mode)
            # Append unit to label
            unit_label = get_unit_label(var_type, unit_mode)
            label = f"{base_label} [{unit_label}]"
        else:
            display_value = str(value) if value is not None else "-"
            label = base_label

        rows.append(
            dmc.Group(
                [
                    dmc.Text(label, fw=200),
                    dmc.Text(display_value, c="dimmed"),
                ],
                justify="space-between",
            )
        )

    return dmc.Card(
        [
            dmc.CardSection(
                dmc.Text(title, fw=500, p="md"),
            ),
            dmc.Stack(rows, gap="sm"),
        ],
        withBorder=False,
        radius="md",
        shadow="sm",
        p="lg",
    )


def building_characteristics_card(metadata: Metadata, unit_mode="SI"):
    fields = [
        ("location", "Location"),
        ("building_type", "Building Type"),
        ("vintage", "Vintage"),
        ("climate_zone_output", "Climate Region"),
        ("base_gea_grid_region", "GEA Grid Region"),
        ("area_sqm", "Building Area", "area"),
    ]
    return make_metadata_card(metadata, fields, title="Building Characteristics", unit_mode=unit_mode)


def load_characteristics_card(metadata: Metadata, unit_mode="SI"):
    load_fields = [
        ("load_data.load_type", "Load Type"),
        ("load_data.annual_heating_cooling_ratio", "Annual H/C Ratio"),
        ("load_data.hhw_max_load", "Peak Heating Load", "power"),
        ("load_data.chw_max_load", "Peak Cooling Load", "power"),
        ("load_data.max_temp", "Max. Outdoor Temp.", "temperature"),
        ("load_data.median_temp", "Median Outdoor Temp.", "temperature"),
        ("load_data.min_temp", "Min. Outdoor Temp.", "temperature"),
    ]

    return make_metadata_card(metadata, load_fields, title="Load Characteristics", unit_mode=unit_mode)


def summary_equipment_selection(equipment_library: EquipmentLibrary, active_tab=None):
    """
    Build a tabbed summary of all equipment scenarios.
    - `equipment_library` is an EquipmentLibrary instance (not a dict)
    - `active_tab` is the previously selected tab id (e.g. "eq_scenario_1")
    """

    # Map eq_id -> human-readable label (e.g. model name)
    eq_lookup = {eq.eq_id: f"{eq.model}".strip() for eq in equipment_library.equipment}

    # Helper: wrapper that resolves equipment IDs to model names for display
    class ScenarioView:
        def __init__(self, scenario: EquipmentScenario, lookup: dict[str, str]):
            self._scenario = scenario
            self._lookup = lookup

        def get_value(self, path: str):
            # only need simple attributes here (no deep nesting)
            val = getattr(self._scenario, path, None)

            # For equipment-id fields, map id -> model name if available
            if path in ("hr_wwhp", "awhp", "boiler", "chiller") and val is not None:
                return self._lookup.get(val, val)

            return val

    # Sort scenarios by id for stable ordering
    scenarios = sorted(
        equipment_library.equipment_scenarios,
        key=lambda s: s.eq_scen_id,
    )

    if not scenarios:
        return dmc.Text("No equipment scenarios available.", c="dimmed")

    # Build tabs
    tabs_list_items = []
    tabs_panels = []

    fields = [
        ("eq_scen_name", "Scenario"),
        ("hr_wwhp", "HR WWHP"),
        ("awhp", "AWHP"),
        ("awhp_sizing_mode", "AWHP Sizing Mode"),
        ("awhp_sizing_value", "AWHP Sizing Value"),
        ("awhp_redundancy", "AWHP Redundancy"),
        ("awhp_use_cooling", "AWHP Use Cooling"),
        ("backup_heating", "Backup Heating"),
        ("chiller", "Chiller"),
    ]

    for scen in scenarios:
        scen_view = ScenarioView(scen, eq_lookup)

        card = make_metadata_card(
            scen_view,  # 👈 object with .get_value()
            fields,
            title="Summary",
        )

        tab_label = (
            f"Scen. {scen.eq_scen_id[-1].upper()}" if scen.eq_scen_id else "Scenario"
        )

        tabs_list_items.append(
            dmc.TabsTab(
                tab_label,  # children (text label)
                value=scen.eq_scen_id,
            )
        )

        tabs_panels.append(
            dmc.TabsPanel(
                children=card,
                value=scen.eq_scen_id,
            )
        )

    # Default active tab
    default_tab = active_tab or scenarios[0].eq_scen_id

    return dmc.Tabs(
        value=default_tab,
        id="equipment-scenario-tabs",
        children=[
            dmc.TabsList(tabs_list_items, grow=True),
            *tabs_panels,
        ],
        orientation="horizontal",
        variant="outline",
        keepMounted=False,
    )


def summary_emissions_selection(metadata: Metadata, active_tab=None):
    """
    Build a tabbed summary of all emission scenarios.
    `metadata` is a Metadata instance (not a dict).
    """

    scenarios = metadata.emission_settings or []
    if not scenarios:
        return dmc.Text("No emission scenarios available.", c="dimmed")

    # Sort for stable ordering (e.g. by year then id)
    scenarios = sorted(scenarios, key=lambda s: (s.year, s.em_scen_id))

    emission_fields = [
        ("grid_scenario", "Grid Scenario"),
        ("gea_grid_region", "GEA Grid Region"),
        ("emission_type", "Emission Type"),
        ("shortrun_weighting", "Short-Run Weighting"),
        ("annual_refrig_leakage_percent", "Refrig. Leakage, p.a."),
        ("year", "Year"),
    ]

    tabs_list_items = []
    tabs_panels = []

    for scen in scenarios:
        # scen is an EmissionScenario with .get_value
        card = make_metadata_card(
            scen,
            emission_fields,
            title="Summary",
        )

        # label similar to your original: "Scenario A", "Scenario B", ...
        label_suffix = scen.em_scen_id[-1].upper() if scen.em_scen_id else "?"
        tab_label = f"Scenario {label_suffix}"

        tabs_list_items.append(
            dmc.TabsTab(
                tab_label,  # children (no 'label=' kwarg in dmc)
                value=scen.em_scen_id,
            )
        )

        tabs_panels.append(
            dmc.TabsPanel(
                children=card,
                value=scen.em_scen_id,
            )
        )

    # Default active tab: stored one or first scenario
    default_tab = active_tab or scenarios[0].em_scen_id

    return dmc.Tabs(
        value=default_tab,
        id="emission-scenario-tabs",  # keep your original id
        children=[
            dmc.TabsList(tabs_list_items, grow=True),
            *tabs_panels,
        ],
        orientation="horizontal",
        variant="outline",
        keepMounted=False,
    )


def summary_project_info(metadata: Metadata, unit_mode="SI"):

    overview_fields = [
        ("location", "Location"),
        ("climate_zone_output", "Climate Region"),
        ("building_type", "Building Type"),
        ("area_sqm", "Building Area", "area"),
        # Load-side fields (from LoadData)
        ("load_data.hhw_max_load", "Peak HHW Load", "power"),
        ("load_data.chw_max_load", "Peak CHW Load", "power"),
        ("load_data.annual_heating_cooling_ratio", "Annual Heating/Cooling Ratio"),
    ]

    return make_metadata_card(
        metadata,
        overview_fields,
        title="Project Overview",
        unit_mode=unit_mode,
    )


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
