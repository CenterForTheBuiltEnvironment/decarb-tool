import dash
from dash import callback, ctx, html, dcc, dash_table, Input, Output, State
import dash_bootstrap_components as dbc

from dash_iconify import DashIconify

from layout.output import summary_equipment_selection
from src.config import URLS

from layout.input import select_equipment, equipment_scenario_saving_buttons
from src.equipment import EquipmentLibrary, EquipmentScenario

dash.register_page(
    __name__,
    name="Equipment",
    path=URLS.EQUIPMENT.value,
    order=1,
)


def layout():
    return dbc.Container(
        children=[
            dcc.Store(id="active-equipment-tab"),
            dbc.Row(
                [
                    dbc.Col(
                        [
                            html.H5("Specify Equipment"),
                            html.Div(id="select-equipment-options"),
                            html.Hr(),
                            equipment_scenario_saving_buttons(),
                        ],
                        width=7,
                    ),
                    dbc.Col(
                        [
                            html.H5("Overview"),
                            html.P(
                                "We use integers to identify equipment scenarios. Below a summary of all equipment scenarios currently considered."
                            ),
                            html.Hr(),
                            html.Div(
                                id="summary-equipment-info",
                            ),
                            dbc.Button(
                                [
                                    "Specify Grid Scenarios ",
                                    DashIconify(
                                        icon="tabler:arrow-narrow-right-dashed",
                                        width=20,
                                    ),
                                ],
                                color="primary",
                                id="button-specify-grid-scenarios",
                                n_clicks=0,
                                style={"float": "right"},
                            ),
                        ],
                        width=5,
                    ),
                ]
            ),
        ]
    )


@callback(
    Output("url", "href", allow_duplicate=True),
    Input("button-specify-grid-scenarios", "n_clicks"),
    prevent_initial_call=True,
)
def navigate_to_equipment(n_clicks):
    if not n_clicks:  # ignore None or 0
        raise dash.exceptions.PreventUpdate
    return "/emissions"


@callback(
    Output("select-equipment-options", "children"),
    Input("equipment-store", "data"),
)
def update_equipment_options(equipment_library):
    if not equipment_library:
        return html.Div("No equipment data available.")

    return select_equipment(equipment_library)


@callback(
    Output("summary-equipment-info", "children"),
    Input("equipment-store", "data"),
    State("active-equipment-tab", "data"),  # <- keep track of last active tab
)
def show_equipment_scenarios(data, active_tab):
    if not data:
        return "No equipment data available."
    return summary_equipment_selection(data, active_tab)


@callback(
    Output("scenario-name-modal", "is_open"),
    Output("scenario-name-input", "value"),
    Output("scenario-trigger-store", "data"),
    Input("update-eq-scen-1", "n_clicks"),
    Input("update-eq-scen-2", "n_clicks"),
    Input("update-eq-scen-3", "n_clicks"),
    Input("update-eq-scen-4", "n_clicks"),
    Input("update-eq-scen-5", "n_clicks"),
    Input("confirm-scenario-name", "n_clicks"),
    State("scenario-name-modal", "is_open"),
    prevent_initial_call=True,
)
def toggle_modal(n1, n2, n3, n4, n5, confirm, is_open):
    trigger = ctx.triggered_id
    if trigger and trigger.startswith("update-eq-scen"):
        # Open modal, clear input, and remember which button was clicked
        return True, "", trigger
    elif trigger == "confirm-scenario-name":
        # Close modal, don’t clear input, don’t overwrite trigger store
        return False, dash.no_update, dash.no_update
    return is_open, dash.no_update, dash.no_update


@callback(
    Output("equipment-store", "data", allow_duplicate=True),
    Input("confirm-scenario-name", "n_clicks"),
    State("scenario-name-input", "value"),
    State("scenario-trigger-store", "data"),
    State("equipment-store", "data"),
    State("hr-wwhp-input", "value"),
    State("awhp-input", "value"),
    State("awhp-sizing-radio", "value"),
    State("awhp-sizing-slider", "value"),
    State("boiler-input", "value"),
    State("chiller-input", "value"),
    prevent_initial_call=True,
)
def save_scenario(
    confirm,
    scenario_name,
    trigger,
    equipment_data,
    selected_hr_wwhp,
    selected_awhp,
    selected_awhp_sizing_mode,
    selected_awhp_sizing_value,
    selected_boiler,
    selected_chiller,
):

    if not confirm or not trigger:
        return equipment_data

    equipment_data = EquipmentLibrary(**equipment_data)

    # Map button IDs to scenario IDs
    mapping = {
        "update-eq-scen-1": "eq_scenario_1",
        "update-eq-scen-2": "eq_scenario_2",
        "update-eq-scen-3": "eq_scenario_3",
        "update-eq-scen-4": "eq_scenario_4",
        "update-eq-scen-5": "eq_scenario_5",
    }

    scen_id = mapping.get(trigger)
    if not scen_id:
        return equipment_data

    try:
        scenario = equipment_data.get_scenario(scen_id)
    except KeyError:
        scenario = EquipmentScenario(
            eq_scen_id=scen_id,
            eq_scen_name="Basic Scenario",
            hr_wwhp="hr01",
            awhp="hp01",
            awhp_sizing_mode="peak_load_percentage",
            awhp_sizing_value=0.5,
            boiler="bo01",
            chiller="ch01",
            resistance_heater=None,
        )

    # Update scenario name from user input
    if scenario_name and scenario_name.strip():
        scenario.eq_scen_name = scenario_name.strip()

    if selected_hr_wwhp is not None:
        scenario.hr_wwhp = selected_hr_wwhp
    if selected_awhp is not None:
        scenario.awhp = selected_awhp
    if selected_awhp_sizing_mode is not None:
        scenario.awhp_sizing_mode = selected_awhp_sizing_mode
    if selected_awhp_sizing_value is not None:
        scenario.awhp_sizing_value = selected_awhp_sizing_value
    if selected_boiler is not None:
        scenario.boiler = selected_boiler
    if selected_chiller is not None:
        scenario.chiller = selected_chiller

    equipment_data.add_equipment_scenario(scenario, overwrite=True)

    return equipment_data.model_dump()


@callback(
    Output("active-equipment-tab", "data"),
    Input("equipment-scenario-tabs", "active_tab"),
    prevent_initial_call=True,
)
def store_active_equipment_tab(active_tab):
    return active_tab


@callback(
    Output("awhp-sizing-slider", "min"),
    Output("awhp-sizing-slider", "max"),
    Output("awhp-sizing-slider", "step"),
    Output("awhp-sizing-slider", "marks"),
    Output("awhp-sizing-slider", "value"),
    Input("awhp-sizing-radio", "value"),
)
def update_awhp_slider(mode):
    if mode == "peak_load_percentage":
        return (
            0,  # min
            1,  # max
            0.05,  # step
            {i: f"{i * 100}" for i in range(0, 21, 5)},  # marks
            0.85,  # default value
        )
    elif mode == "num_of_units":
        return (
            1,
            5,  # max 5 units (adjust as needed)
            1,
            {i: str(i) for i in range(1, 6)},
            1,
        )
    return dash.no_update
