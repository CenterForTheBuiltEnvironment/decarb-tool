from dash import Dash, html, dcc
import dash_bootstrap_components as dbc

from layout.header import cbe_header
from layout.tabs import tabs
from layout.footer import cbe_footer

from src.metadata import Metadata
from src.equipment import load_library

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

# Initialize Metadata and Equipment Library at startup
initial_metadata = Metadata.create().model_dump()
equipment_library = load_library("data/input/equipment_data.json").model_dump()

app.layout = dbc.Container(
    fluid=True,
    style={"padding": "0"},
    children=[
        cbe_header(),
        html.Div(
            children=[
                dcc.Store(id="metadata-store", data=initial_metadata),
                dcc.Store(id="equipment-store", data=equipment_library),
                dcc.Store(id="site-energy-store"),
                dcc.Store(id="source-energy-store"),
                tabs(),
            ],
            style={"padding": "10px"},
        ),
        cbe_footer(),
    ],
)

if __name__ == "__main__":
    app.run(
        debug=True,
        host="localhost",
        port=8050,
    )
