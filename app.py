import dash
from dash import Dash, callback, Input, Output, State
import dash_bootstrap_components as dbc

from layout.shell import build_shell

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


def serve_layout():
    return build_shell(dash.page_container)


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
