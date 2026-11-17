"""Unit tests for the Equipment Manager's editor helpers (display units <-> stored curves)."""

import pytest

import layout.equipment_editor as eqm
from src.equipment import apply_curve_table

pytestmark = pytest.mark.unit


@pytest.mark.parametrize("eq_id", ["hp01", "hp02", "hp04", "hp08", "hr01"])
@pytest.mark.parametrize("unit_mode", ["SI", "IP"])
def test_editor_tables_round_trip(equipment_library, eq_id, unit_mode):
    eq = equipment_library.get_equipment(eq_id)
    for mode in eq.performance:
        rows, _, lwt_rows, _ = eqm.editor_tables(eq, mode, unit_mode)
        df = eqm.tables_to_long(eq, mode, unit_mode, rows, lwt_rows)
        back = apply_curve_table(eq, mode, df)
        before, after = eq.performance[mode], back.performance[mode]
        assert set(after.leaving_supply_t) == set(before.leaving_supply_t)
        for key, curves in before.leaving_supply_t.items():
            assert after.leaving_supply_t[key].cop == pytest.approx(curves.cop)
            if curves.capacity_W:
                assert after.leaving_supply_t[key].capacity_W == pytest.approx(curves.capacity_W)
            assert (
                after.leaving_supply_t[key].constraints == pytest.approx(curves.constraints or {})
                or curves.constraints is None
            )


def test_editor_cell_edit_reaches_the_curve(equipment_library):
    hp01 = equipment_library.get_equipment("hp01")
    rows, _, lwt_rows, _ = eqm.editor_tables(hp01, "heating", "IP")
    rows[0]["cop_1"] = 1.5  # 52 °C curve, first outdoor temperature
    lwt_rows[0]["oat_min"] = 0.0  # 0 °F
    eq = apply_curve_table(
        hp01, "heating", eqm.tables_to_long(hp01, "heating", "IP", rows, lwt_rows)
    )
    assert eq.performance_heating.leaving_supply_t["52"].cop[0] == 1.5
    assert eq.performance_heating.leaving_supply_t["38"].constraints["min_temp_C"] == pytest.approx(
        -17.78, abs=0.01
    )


@pytest.mark.parametrize("unit_mode", ["SI", "IP"])
def test_form_display_values_convert_back(equipment_library, unit_mode):
    hp01 = equipment_library.get_equipment("hp01").model_dump()
    for name in ("nominal_capacity_W", "refrigerant_weight_g", "dimensions.length"):
        _, _, _, to_base, _ = eqm.field_meta(name, hp01, unit_mode)
        shown = eqm.display_value(hp01, name, unit_mode)
        assert to_base(shown) == pytest.approx(eqm.get_path(hp01, name), rel=1e-3)


def test_form_fields_follow_equipment_type(equipment_library):
    names = {
        eq_id: set(eqm.form_field_names(equipment_library.get_equipment(eq_id).model_dump()))
        for eq_id in ("hp01", "hp02", "bo01", "ch02")
    }
    assert "efficiency" in names["bo01"] and "refrigerant" not in names["bo01"]
    assert {"efficiency", "refrigerant", "capacity_W"} <= names["ch02"]
    assert "capacity_W" in names["hp02"] and "capacity_W" not in names["hp01"]
