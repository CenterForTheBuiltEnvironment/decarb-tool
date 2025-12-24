import os
import logging

import dash
from dash import Dash, callback, Input, Output, State
import dash_bootstrap_components as dbc

from utils.logging_config import setup_logging, get_logger
from layout.shell import build_shell
from utils.plotly_theme import *

# Read level from environment variable (or default to INFO)
log_level_name = os.environ.get("LOG_LEVEL", "INFO")
log_level = getattr(logging, log_level_name.upper(), logging.INFO)
setup_logging(level=log_level)

# Get a logger for this module
logger = get_logger(__name__)
logger.info("Starting Decarb Tool application")


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
def log_session_id(session_data):
    logger.debug(f"Session initialized: {session_data['session_id']}")
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
