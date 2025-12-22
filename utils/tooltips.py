import dash_mantine_components as dmc

# --- Global settings ---
TOOLTIP_DEFAULTS = {
    "position": "top",
    "withArrow": True,
    "arrowSize": 10,
    "radius": "lg",
    "transitionProps": {"transition": "fade", "duration": 500},
    "color": "blue.1",
    "multiline": True,
    "w": 250,  # width
}

TEXT_DEFAULTS = {
    "size": "sm",
    "fw": 400,
    "c": "grey",
    "lh": 1.2,  # line-height
}


# --- Tooltip Definitions, organized by page/section ---
TOOLTIPS = {
    # --- Loads Page ---
    "loads": {
        "specify_equipment_button": "Specify equipment configurations for this load scenario.",
    },
    # --- Equipment Page ---
    "equipment": {
        "add_eq_scenario": "Create a new equipment configuration based on an existing scenario.",
        "select_eq_scenario": "Consider this equipment scenario for calculation.",
        "edit_eq_scenario": "Edit the equipment configuration for this scenario.",
        "delete_eq_scenario": "Delete this equipment scenario.",
        "reset_eq_scenario": "Reset all equipment scenarios to default.",
    },
}


def with_tooltip(component, text: str, text_props: dict = None, **overrides):
    """Wrap a Dash Mantine Component with a Tooltip.
    Args:
        component: Dash Mantine Component to wrap.
        text (str): Tooltip text or key to resolve from TOOLTIPS dict.
        text_props (dict, optional): Additional styling props for the tooltip text.
        **overrides: Additional props to override default tooltip settings.
    Returns:
        dmc.Tooltip: Component wrapped with tooltip.
    """

    if "." in text:
        parts = text.split(".", 1)
        resolved_text = TOOLTIPS.get(parts[0], {}).get(parts[1], text)
    else:
        resolved_text = text

    final_text_props = {**TEXT_DEFAULTS, **(text_props or {})}
    styled_label = dmc.Text(resolved_text, **final_text_props)

    props = {**TOOLTIP_DEFAULTS, **overrides}

    return dmc.Tooltip(children=component, label=styled_label, **props)
