import dash
from dash import html
import dash_bootstrap_components as dbc

from utils.config import URLS

dash.register_page(__name__, path=URLS.HOME.value, order=0)


def layout():
    return dbc.Container(html.Div("This is the starting/input page."))
