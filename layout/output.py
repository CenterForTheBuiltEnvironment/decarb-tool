import dash_bootstrap_components as dbc
from dash import html

import dash_bootstrap_components as dbc


### Bootstrap Card with Table for Metadata Summary ###


def get_nested_value(obj, attr_path):
    """Helper to get nested attributes or dict keys using dot notation."""
    parts = attr_path.split(".")
    val = obj
    for p in parts:
        if isinstance(val, dict):
            val = val.get(p, None)
        else:
            val = getattr(val, p, None)
        if val is None:
            break
    return val


def make_metadata_card(metadata, fields, title="Summary"):
    """
    Create a Bootstrap card with a table of selected metadata fields.

    Args:
        metadata: object or dict with metadata info
        fields: list of (attr_path, label) pairs. Example:
                [("location", "Location"),
                 ("building_type", "Building Type"),
                 ("emissions.emission_scenario", "Emission Scenario")]
        title: header title of the card
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
                        style={"fontSize": "12px"},
                    )
                ]
            ),
        ]
    )


def summary_selection_info(metadata):

    # building information

    building_fields = [
        ("location", "Location"),
        ("building_type", "Building Type"),
        ("vintage", "Vintage"),
        ("ashrae_climate_zone", "Climate Region"),
    ]

    building_card = make_metadata_card(
        metadata, building_fields, title="Building Information"
    )

    # emission information

    emission_fields = [
        ("emissions.emission_scenario", "Emission Scenario"),
        ("emissions.gea_grid_region", "GEA Grid Region"),
    ]

    emission_card = make_metadata_card(
        metadata, emission_fields, title="Emission Information"
    )

    return building_card, emission_card


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
