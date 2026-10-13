"""App tier, part 1: server smoke tests (no browser).

Catches broken imports, page layouts that raise, and callbacks wired to
component ids that no longer exist. The app runs with
suppress_callback_exceptions=True, so Dash itself stays silent about the last
category: a renamed id simply makes a control stop working.
"""

import json

import dash
import plotly
import pytest

from tests.app_helpers import callback_component_ids, component_ids, ids_declared_in_source

pytestmark = pytest.mark.app

# Callbacks whose target component no longer exists anywhere in the app.
# Keep this list honest: the test below fails if an entry is fixed or removed.
KNOWN_ORPHAN_IDS = {
    # pages/results_page.py::show_project_summary writes here, but nothing renders it.
    "summary-project-info",
}


@pytest.fixture(scope="module")
def app():
    import app as app_module

    return app_module


@pytest.fixture(scope="module")
def client(app):
    return app.app.server.test_client()


@pytest.fixture(scope="module")
def dependencies(client):
    return client.get("/_dash-dependencies").get_json()


def _page_paths():
    import app  # noqa: F401  (registers pages)

    return [page["path"] for page in dash.page_registry.values()]


@pytest.mark.parametrize("path", ["/", "/_dash-layout", "/_dash-dependencies"])
def test_server_endpoints_respond(client, path):
    assert client.get(path).status_code == 200


@pytest.mark.parametrize("path", _page_paths())
def test_every_page_path_responds(client, path):
    assert client.get(path).status_code == 200


def test_every_page_layout_renders_and_serialises(app):
    for page in dash.page_registry.values():
        layout = page["layout"]() if callable(page["layout"]) else page["layout"]
        json.dumps(layout, cls=plotly.utils.PlotlyJSONEncoder)


def test_callbacks_only_reference_existing_components(app, dependencies):
    """Every id a callback reads or writes must exist in a layout or be built at runtime."""
    static = component_ids(app.serve_layout())
    for page in dash.page_registry.values():
        static |= component_ids(page["layout"]() if callable(page["layout"]) else page["layout"])
    known = static | ids_declared_in_source()

    missing = callback_component_ids(dependencies) - known
    assert missing == KNOWN_ORPHAN_IDS, (
        f"Callbacks reference unknown component ids: {sorted(missing - KNOWN_ORPHAN_IDS)}; "
        f"no longer orphaned (remove from KNOWN_ORPHAN_IDS): {sorted(KNOWN_ORPHAN_IDS - missing)}"
    )


def test_no_output_written_by_two_callbacks_without_allow_duplicate(dependencies):
    seen = {}
    for dep in dependencies:
        for output in dep["output"].strip(".").split("..."):
            if "@" in output:  # allow_duplicate outputs carry a hash suffix
                continue
            assert output not in seen, f"{output} written by two callbacks"
            seen[output] = dep
