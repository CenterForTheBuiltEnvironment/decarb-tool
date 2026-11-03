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

from tests.app_helpers import (
    callback_component_ids,
    component_ids,
    components_in_dict_props,
    ids_declared_in_source,
    walk,
)

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


def test_equipment_manager_is_not_a_numbered_workflow_step(app):
    from layout.shell import build_navbar_content
    from src.config import URLS

    navbar = list(walk(build_navbar_content()))
    step_paths = {
        c.id["path"]
        for c in navbar
        if isinstance(getattr(c, "id", None), dict) and c.id.get("type") == "navbar-link"
    }
    assert "/equipment" in step_paths
    assert URLS.EQUIPMENT_MANAGER.value not in step_paths
    assert URLS.EQUIPMENT_MANAGER.value in {getattr(c, "href", None) for c in navbar}


def test_page_layouts_have_no_components_inside_dict_props(app):
    for page in dash.page_registry.values():
        layout = page["layout"]() if callable(page["layout"]) else page["layout"]
        assert components_in_dict_props(layout) == [], page["path"]


@pytest.mark.parametrize("eq_id", ["hr01", "hp01", "hp02", "bo01", "ch02"])
@pytest.mark.parametrize("unit_mode", ["SI", "IP"])
def test_equipment_manager_output_renders_in_browser(app, eq_id, unit_mode):
    """Rendered list and detail must serialise and contain no components inside dict props."""
    import pages.equipment_manager_page as eqm
    from layout.shell import _get_equipment_library

    library = _get_equipment_library()
    _, mode, _ = eqm.update_mode_options(eq_id, library, None)
    outputs = [
        eqm.render_equipment_list(library, "all", None, eq_id, unit_mode),
        eqm.render_overview(eq_id, library, unit_mode, None, 0, None),
        *eqm.render_equipment_detail(eq_id, mode, library, unit_mode, None, None),
    ]
    for output in outputs:
        json.dumps(output, cls=plotly.utils.PlotlyJSONEncoder)
        assert components_in_dict_props(output) == []


@pytest.mark.parametrize("eq_id", ["hr01", "hp01", "hp02", "bo01", "ch02"])
@pytest.mark.parametrize("unit_mode", ["SI", "IP"])
def test_equipment_manager_edit_mode_renders_in_browser(app, eq_id, unit_mode):
    """The overview form and curve editor tables of a custom copy must serialise."""
    import pages.equipment_manager_page as eqm
    from layout.shell import _get_equipment_library
    from src.equipment import Equipment, duplicate_equipment, save_custom_equipment

    library = _get_equipment_library()
    library_ids = [e["eq_id"] for e in library["equipment"]]
    source = next(Equipment(**e) for e in library["equipment"] if e["eq_id"] == eq_id)
    copy = duplicate_equipment(source, library_ids)
    data = save_custom_equipment(library, copy, library_ids)
    draft, session = copy.model_dump(), {"eq_id": copy.eq_id, "started": 0}
    _, mode, _ = eqm.update_mode_options(copy.eq_id, data, None)

    outputs = [
        eqm.render_overview(copy.eq_id, data, unit_mode, session, 0, draft),
        *eqm.render_equipment_detail(copy.eq_id, mode, data, unit_mode, draft, session),
    ]
    if copy.eq_type in ("heat_pump", "hr_heat_pump"):
        from layout.equipment_editor import editor_tables

        outputs += list(editor_tables(copy, mode, unit_mode))
    for output in outputs:
        json.dumps(output, cls=plotly.utils.PlotlyJSONEncoder)
        assert components_in_dict_props(output) == []
