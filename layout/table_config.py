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
    diff_row_style: dict = None

    def __post_init__(self):
        object.__setattr__(
            self,
            "active_col_style",
            {"backgroundColor": "var(--mantine-color-blue-0)", "fontWeight": 500},
        )
        object.__setattr__(self, "inactive_col_style", {})
        object.__setattr__(
            self,
            "diff_row_style",
            {
                "fontWeight": 2000,
                "borderLeft": "5px solid var(--mantine-color-pink-7)",
            },
        )


TABLE_STYLE = ScenarioTableStyle()


# --- Helpers for table value formatting and styling ---


def format_table_value(raw_value, field_name: str = None):
    """
    Normalize values for display in tables.
    - None / "None" -> em dash
    - booleans -> Yes / No
    - Equipment IDs -> model names (when field_name is provided)
    """
    if raw_value is None:
        return "—"
    if isinstance(raw_value, str) and raw_value.strip().lower() == "none":
        return "-"
    if isinstance(raw_value, bool):
        return "Yes" if raw_value else "No"

    # Map equipment IDs to display names
    if field_name is not None:
        from utils.display_registry import EQUIPMENT_ID_FIELDS, get_equipment_display_name

        if field_name in EQUIPMENT_ID_FIELDS:
            return get_equipment_display_name(raw_value)

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


def get_diff_fields(df, fields):
    """
    Identify which fields have differing values across rows in the DataFrame.

    Args:
        df: DataFrame with scenarios as rows
        fields: List of field names to check

    Returns:
        Set of field names that have more than one unique value
    """
    diff_fields = set()
    for field in fields:
        if field not in df.columns:
            continue
        # Count unique non-null values
        unique_values = df[field].dropna().unique()
        if len(unique_values) > 1:
            diff_fields.add(field)
    return diff_fields
