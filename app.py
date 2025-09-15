from dash import Dash, html, dcc
import dash_bootstrap_components as dbc

from components.header import cbe_header
from components.tabs import tabs
from components.footer import cbe_footer

from src.metadata import Metadata

app = Dash(
    __name__,
    use_pages=True,
    external_stylesheets=[
        dbc.themes.LUX,
        "https://fonts.googleapis.com/css2?family=Open+Sans:wght@400;700&display=swap",
    ],
    serve_locally=True,
)

# Initialize Metadata at startup
initial_metadata = Metadata.create().model_dump()

app.layout = dbc.Container(
    fluid=True,
    style={"padding": "0"},
    children=[
        cbe_header(),
        html.Div(
            children=[
                dcc.Store(id="metadata-store", data=initial_metadata),
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
