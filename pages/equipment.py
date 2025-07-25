import dash
from dash import html
import dash_bootstrap_components as dbc

from src.config import URLS

dash.register_page(__name__, path=URLS.EQUIPMENT.value, order=1)


def layout():
    return dbc.Container(html.Div("This is the equipment selection page."))
