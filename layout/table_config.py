from dataclasses import dataclass


@dataclass(frozen=True)
class ScenarioTableStyle:
    # Column sizing
    property_col_width: int = 300
    scenario_col_width: int = 200

    # Layout
    # height: int = 600 not using fixed height for now
    horizontal_spacing: str = "lg"
    vertical_spacing: str = "sm"
    scrollbar_size: int = 10

    # Behaviors
    sticky_property_col: bool = True

    # Styles
    active_col_style: dict = None
    inactive_col_style: dict = None

    def __post_init__(self):
        object.__setattr__(
            self,
            "active_col_style",
            {"backgroundColor": "var(--mantine-color-blue-0)", "fontWeight": 500},
        )
        object.__setattr__(self, "inactive_col_style", {})


TABLE_STYLE = ScenarioTableStyle()


# --- Helpers for table value formatting and styling ---


def format_table_value(raw_value):
    """
    Normalize values for display in tables.
    - None / "None" -> em dash
    - booleans -> Yes / No
    """
    if raw_value is None:
        return "—"
    if isinstance(raw_value, str) and raw_value.strip().lower() == "none":
        return "-"
    if isinstance(raw_value, bool):
        return "Yes" if raw_value else "No"
    return str(raw_value)


def value_deemphasis_style(raw_value):
    """
    De-emphasize values that indicate 'not present' or 'disabled'.
    We treat None/"None" and False/"False" as de-emphasis candidates.
    """
    is_none_like = raw_value is None or (
        isinstance(raw_value, str) and raw_value.strip().lower() == "none"
    )
    is_false_like = raw_value is False or (
        isinstance(raw_value, str) and raw_value.strip().lower() == "false"
    )

    if is_none_like or is_false_like:
        return {
            "color": "var(--mantine-color-gray-6)",
            "fontStyle": "italic",
        }

    return {}
