import uuid
from dash import Dash, html, dcc, callback, Input, Output
import dash_bootstrap_components as dbc

from layout.header import cbe_header
from layout.tabs import tabs
from layout.footer import cbe_footer

from src.equipment import load_library

from utils.plotly_theme import *

app = Dash(
    __name__,
    use_pages=True,
    external_stylesheets=[
        dbc.themes.LUX,
        "https://fonts.googleapis.com/css2?family=Open+Sans:wght@400;700&display=swap",
    ],
    suppress_callback_exceptions=True,
    serve_locally=True,
)


# Initialize Equipment Library at startup
equipment_library = load_library("data/input/equipment_data.JSON").model_dump()


def serve_layout():
    return dbc.Container(
        fluid=True,
        style={"padding": "0"},
        children=[
            cbe_header(),
            html.Div(
                dbc.Badge(
                    "Alpha Version",
                    color="danger",
                    className="me-1",
                    pill=True,
                    style={"borderRadius": "5px", "margin-top": "10px"},
                ),
                className="d-flex justify-content-center",
            ),
            dcc.Store(id="metadata-store"),
            dcc.Store(id="equipment-store", data=equipment_library),
            dcc.Store(id="session-store", data={"session_id": str(uuid.uuid4())}),
            html.Div(
                children=[
                    tabs(),
                ],
                style={"padding": "10px"},
            ),
            cbe_footer(),
        ],
    )


app.layout = serve_layout


@callback(
    Output("session-store", "data", allow_duplicate=True),
    Input("session-store", "data"),
    prevent_initial_call=True,
)
def print_session_id(session_data):
    print(f"[DEBUG] Session ID: {session_data['session_id']}")
    return session_data


# if __name__ == "__main__":
#     app.run(
#         debug=False,
#         host="0.0.0.0",
#         port=8080,
#     )


if __name__ == "__main__":
    app.run(
        debug=True,
        host="localhost",
        port=8050,
    )
