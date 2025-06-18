import dash_bootstrap_components as dbc
from dash import html


# Example data for now
summary_data = [
    {"Label": "Building Type", "Value": "Office"},
    {"Label": "Climate Region", "Value": "5A - Cool, Humid"},
    {"Label": "Heating Load", "Value": "45,000 BTU/hr"},
    {"Label": "Cooling Load", "Value": "60,000 BTU/hr"},
]

# Create rows of table
table_rows = [
    html.Tr([html.Td(item["Label"]), html.Td(item["Value"])]) for item in summary_data
]


def summary_project_info():
    return dbc.Card(
        [
            dbc.CardHeader("Building Overview"),
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
