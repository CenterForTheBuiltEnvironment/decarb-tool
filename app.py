import logging
import os

import dash
import dash_bootstrap_components as dbc
from dash import Dash, Input, Output, callback

import utils.plotly_theme  # noqa: F401 - imports for side effect (sets default Plotly theme)
from layout.shell import build_shell
from utils.logging_config import get_logger, setup_logging

# Read level from environment variable (or default to INFO)
log_level_name = os.environ.get("LOG_LEVEL", "DEBUG")
log_level = getattr(logging, log_level_name.upper(), logging.DEBUG)
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

# Expose Flask server for gunicorn
server = app.server


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


if __name__ == "__main__":
    # Development mode
    debug = os.environ.get("DEBUG", "true").lower() == "true"
    port = int(os.environ.get("PORT", 8050))
    host = "localhost" if debug else "0.0.0.0"

    app.run(debug=debug, host=host, port=port)
