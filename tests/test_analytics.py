"""Tests for the analytics snippets injected into the Dash index string."""

import pytest
from dash import Dash

from utils.analytics import SITEIMPROVE_SRC, add_analytics

pytestmark = pytest.mark.unit

DASH_PLACEHOLDERS = [
    "{%metas%}",
    "{%title%}",
    "{%favicon%}",
    "{%css%}",
    "{%app_entry%}",
    "{%config%}",
    "{%scripts%}",
    "{%renderer%}",
]


@pytest.fixture(scope="module")
def default_index():
    return Dash(__name__).index_string


def test_enabled_with_id_adds_gtag_and_siteimprove(default_index):
    html = add_analytics(default_index, enabled=True, ga_id="G-TEST123")
    head = html.split("</head>")[0]
    assert "googletagmanager.com/gtag/js?id=G-TEST123" in head
    assert "gtag('config', 'G-TEST123')" in head
    assert SITEIMPROVE_SRC in head
    for placeholder in DASH_PLACEHOLDERS:
        assert placeholder in html


def test_enabled_without_id_adds_only_siteimprove(default_index):
    html = add_analytics(default_index, enabled=True, ga_id="")
    assert "gtag" not in html
    assert SITEIMPROVE_SRC in html


def test_disabled_leaves_index_unchanged(default_index):
    assert add_analytics(default_index, enabled=False, ga_id="G-TEST123") == default_index
