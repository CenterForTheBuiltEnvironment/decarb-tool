from dash import Dash, html
import dash_bootstrap_components as dbc

from components.header import cbe_header
from components.tabs import tabs
from components.footer import cbe_footer

app = Dash(
    __name__,
    use_pages=True,
    external_stylesheets=[
        dbc.themes.LUX,
        "https://fonts.googleapis.com/css2?family=Open+Sans:wght@400;700&display=swap",
    ],
    serve_locally=True,
)

app.layout = dbc.Container(
    fluid=True,
    style={"padding": "0"},
    children=[
        cbe_header(),
        html.Div(
            children=[
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
