"""Helpers for the app-tier tests: walk Dash layouts without a browser."""

import json
import re
from pathlib import Path

from dash.development.base_component import Component

ROOT = Path(__file__).resolve().parents[1]
_ID_IN_SOURCE = re.compile(r"""\bid\s*=\s*["']([\w\-:.]+)["']""")


def walk(node):
    """Yield every Dash component in a layout tree (children and component-valued props)."""
    if isinstance(node, Component):
        yield node
        for prop in node._prop_names:
            value = getattr(node, prop, None)
            if isinstance(value, Component | list | tuple):
                yield from walk(value)
    elif isinstance(node, list | tuple):
        for item in node:
            yield from walk(item)


def component_ids(layout) -> set[str]:
    ids = set()
    for comp in walk(layout):
        cid = getattr(comp, "id", None)
        if isinstance(cid, str):
            ids.add(cid)
    return ids


def find(layout, component_id: str) -> Component:
    for comp in walk(layout):
        if getattr(comp, "id", None) == component_id:
            return comp
    raise KeyError(component_id)


def option_values(layout, component_id: str) -> list:
    """Values of a Select/SegmentedControl's `data` options, read from the live layout."""
    return [opt["value"] for opt in find(layout, component_id).data]


def ids_declared_in_source() -> set[str]:
    """Every literal id="..." in the app source, including components built at runtime."""
    ids = set()
    for folder in ("pages", "layout"):
        for path in (ROOT / folder).glob("*.py"):
            ids.update(_ID_IN_SOURCE.findall(path.read_text()))
    ids.update(_ID_IN_SOURCE.findall((ROOT / "app.py").read_text()))
    return ids


def callback_component_ids(dependencies: list[dict]) -> set[str]:
    """String component ids referenced by /_dash-dependencies (pattern-matching ids skipped)."""
    ids = set()
    for dep in dependencies:
        if not dep.get("no_output"):
            for output in dep["output"].strip(".").split("..."):
                ids.add(output.rsplit(".", 1)[0])
        for item in dep["inputs"] + dep["state"]:
            if isinstance(item["id"], str):
                ids.add(item["id"])
    return {i for i in ids if not i.startswith("{")}


def figure_has_data(fig) -> bool:
    fig = json.loads(fig.to_json()) if hasattr(fig, "to_json") else fig
    return any(trace for trace in fig.get("data", []))
