import dash
from dash import (
    callback,
    ctx,
    html,
    dcc,
    dash_table,
    Input,
    Output,
    State,
    callback_context,
    no_update,
)
import dash_mantine_components as dmc

from dash_iconify import DashIconify

from layout.output import summary_equipment_selection
from src.config import URLS

from layout.input import (
    build_equipment_table,
    select_equipment,
    equipment_scenario_saving_buttons,
)
from src.equipment import EquipmentLibrary, EquipmentScenario

dash.register_page(
    __name__,
    name="Equipment",
    path=URLS.EQUIPMENT.value,
    order=1,
)


def layout():
    return dmc.Container(
        [
            dcc.Store(id="active-equipment-tab"),
            dmc.Group(
                [
                    dmc.Text("Specify Equipment", fw=500, size="lg"),
                    dmc.Group(
                        [
                            dmc.Button(
                                "Add",
                                id="button-add-equipment",
                                variant="outline",
                            ),
                            dmc.Button(
                                "Remove",
                                id="button-remove-equipment",
                                variant="outline",
                                color="red",
                            ),
                        ],
                    ),
                ],
                justify="space-between",
                mt="md",
                mb="sm",
            ),
            dmc.Divider(),
            html.Div(
                id="equipment-table",
                style={
                    "minHeight": "300px",  # just to make the area visible while empty
                    "marginTop": "16px",
                },
            ),
            # Use Mantine spacing prop instead of marginTop
            dmc.Divider(mt="md"),
            dmc.Group(
                [
                    dmc.Button(
                        "Confirm",
                        id="button-confirm-equipment",
                        variant="filled",
                    )
                ],
                justify="flex-end",
                mt="md",
                mb="md",
            ),
            dmc.Modal(
                id="equipment-confirm-modal",
                opened=False,  # controlled via callback
                title="Confirm selected scenarios",
                children=[
                    dmc.Text(
                        id="equipment-modal-content",
                        size="sm",
                    ),
                    dmc.Group(
                        [
                            dmc.Button(
                                "OK",
                                id="equipment-modal-ok-btn",
                            )
                        ],
                        justify="flex-end",
                        mt="md",
                    ),
                ],
            ),
        ],
        fluid=True,
    )


@callback(
    Output("equipment-table", "children"),
    Input("equipment-store", "data"),
    Input("selected-equipment-store", "data"),
)
def update_equipment_table(equipment_store_data, selected_equipment_data):
    """
    Populate the equipment table from the data in equipment-store,
    and pre-check rows based on selected-equipment-store.
    """
    if not equipment_store_data:
        return dmc.Text("No equipment scenarios defined yet.")

    scenarios = equipment_store_data.get("equipment_scenarios", [])
    if not scenarios:
        return dmc.Text("No equipment scenarios defined yet.")

    selected_ids = selected_equipment_data or []

    # Build the table with the current selections
    table_component = build_equipment_table(scenarios, selected_ids=selected_ids)

    return table_component


@callback(
    Output("selected-equipment-store", "data"),
    Output("equipment-confirm-modal", "opened"),
    Output("equipment-modal-content", "children"),
    Input("button-confirm-equipment", "n_clicks"),
    Input("equipment-modal-ok-btn", "n_clicks"),
    State("equipment-checkbox-group", "value"),
    State("selected-equipment-store", "data"),
    prevent_initial_call=True,
)
def confirm_equipment_selection(
    confirm_clicks,
    ok_clicks,
    current_selected_values,
    current_store_values,
):
    """
    - Confirm:
        * DO NOT update selected-equipment-store (use no_update)
        * Open modal with summary (based on current checkboxes, capped to 5)
    - OK:
        * Write capped selection into selected-equipment-store
        * Close modal
    """
    ctx = callback_context
    if not ctx.triggered:
        return current_store_values, False, ""

    trigger_id = ctx.triggered[0]["prop_id"].split(".")[0]

    raw_selected = current_selected_values or []
    capped_selected = raw_selected[:5]

    # Shared summary text
    if capped_selected:
        base_summary = (
            "You selected the following equipment scenarios (up to 5 stored): "
            + ", ".join(capped_selected)
        )
    else:
        base_summary = "No equipment scenarios selected."

    # Case 1: Confirm clicked -> preview only
    if trigger_id == "button-confirm-equipment":
        # Don't touch the store at all; keep UI checkbox state untouched
        return no_update, True, base_summary

    # Case 2: OK clicked -> commit to store, close modal
    if trigger_id == "equipment-modal-ok-btn":
        return capped_selected, False, base_summary
