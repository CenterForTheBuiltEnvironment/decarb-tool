"""App tier, part 2: headless end-to-end workflow through the real Results callbacks.

Builds the session stores the Loads/Equipment/Emissions pages would leave
behind, then calls the Results page callbacks as plain functions, as Dash
would: the auto-calculation (initialize_results_page), every chart in SI and
IP units, and the ZIP download. One test sweeps every option of every chart
control; options are read from the live layout, so new options are covered
without editing this file.
"""

import base64
import io
import shutil
import time
import uuid
import zipfile
from pathlib import Path

import pandas as pd
import pytest

from src import paths
from src.config import DEFAULT_SELECTIONS
from src.emissions import EmissionScenario
from src.equipment import load_library
from src.metadata import LoadData, Metadata
from tests.app_helpers import figure_has_data, option_values
from tests.app_helpers import find as _find

pytestmark = pytest.mark.app

UNIT_MODES = ("SI", "IP")


@pytest.fixture(scope="module", autouse=True)
def dash_app():
    """Pages can only be imported after the Dash app exists."""
    import app

    return app


@pytest.fixture(scope="module")
def results_page():
    from pages import results_page

    return results_page


@pytest.fixture(scope="module")
def results_layout(results_page):
    return results_page.layout()


@pytest.fixture(scope="module")
def library_json():
    return load_library(paths.EQUIPMENT_JSON).model_dump()


def _all_emission_sources(region: str) -> list[EmissionScenario]:
    common = dict(
        grid_scenario="MidCase",
        gea_grid_region=region,
        emission_type="Includes pre-combustion",
        annual_refrig_leakage_percent=0.05,
        ng_emission_rate_gCO2e_per_kWh=239.2,
        year=2030,
    )
    sources = [
        ("em_scenario_a", "Marginal (Cambium, Long-run)"),
        ("em_scenario_b", "Marginal (Cambium, Short-run)"),
        ("em_scenario_c", "Average (Cambium)"),
    ]
    scenarios = [
        EmissionScenario(em_scen_id=i, em_scen_name=s, elec_emission_source=s, **common)
        for i, s in sources
    ]
    scenarios.append(
        EmissionScenario(
            em_scen_id="em_scenario_d",
            em_scen_name="Constant",
            elec_emission_source="Constant (User-provided)",
            elec_avg_emission_rate_gCO2e_per_kWh=250.0,
            **{**common, "grid_scenario": None},
        )
    )
    return scenarios


class Session:
    """The client-side stores a user would have filled in before opening Results."""

    def __init__(self, metadata: Metadata, library_json: dict, scenario_ids: list[str]):
        self.metadata_json = metadata.model_dump()
        self.equipment_json = library_json
        self.scenario_ids = scenario_ids
        self.emission_ids = metadata.list_emission_scenarios()
        self.session_data = {"session_id": f"pytest-{uuid.uuid4().hex}"}

    @property
    def folder(self) -> Path:
        return Path(f"/tmp/{self.session_data['session_id']}")


def _calculate(results_page, s: Session):
    out = results_page.initialize_results_page(
        time.time(),
        s.metadata_json,
        s.equipment_json,
        s.scenario_ids,
        s.scenario_ids,
        s.emission_ids,
        s.session_data,
        None,
        None,
        None,
        None,
        None,
    )
    notification = out[2]
    assert notification is not None and notification != dash_no_update(), "no notification"
    assert notification[0]["color"] == "green", notification[0]["message"]
    return out


def dash_no_update():
    from dash import no_update

    return no_update


def _exercise_charts(results_page, layout, s: Session, exhaustive: bool):
    """Render every Results chart. exhaustive=True also sweeps every control option."""
    eq, em = s.scenario_ids, s.emission_ids
    rp = results_page

    def options(component_id):
        values = option_values(layout, component_id)
        default = getattr(_find(layout, component_id), "value", values[0])
        return values if exhaustive else [default]

    for unit in UNIT_MODES:
        for freq in options("frequency-dropdown"):
            fig = rp.update_meter_plot(
                eq[0], em[0], ["stacked"], ["gas"], freq, unit, s.session_data
            )
            assert figure_has_data(fig), f"meter plot empty ({freq}, {unit})"
        assert figure_has_data(
            rp.update_total_emissions_plot(eq, em[0], unit, s.session_data, eq)
        ), f"energy & emissions plot empty ({unit})"
        assert figure_has_data(
            rp.update_emissions_bar_plot(em, unit, eq, eq, s.session_data)
        ), f"grouped emissions bar empty ({unit})"
        for em_type in options("heatmap-emission-type-dropdown"):
            for em_id in em if exhaustive else em[:1]:
                fig = rp.update_emissions_heatmap(eq[0], em_id, em_type, unit, s.session_data)
                assert figure_has_data(fig), f"heatmap empty ({em_id}, {em_type}, {unit})"
        for y_var in options("scatter-yvar-dropdown"):
            for freq in options("scatter-frequency-dropdown"):
                fig = rp.update_scatter_plot(eq, em[0], y_var, freq, unit, s.session_data)
                assert figure_has_data(fig), f"scatter empty ({y_var}, {freq}, {unit})"


def _download(results_page, s: Session, unit: str) -> pd.DataFrame:
    payload = results_page.download_results(
        1,
        s.session_data,
        unit,
        s.metadata_json,
        s.equipment_json,
        s.scenario_ids,
        s.emission_ids,
    )
    with zipfile.ZipFile(io.BytesIO(base64.b64decode(payload["content"]))) as zf:
        csv_name = next(n for n in zf.namelist() if n.startswith("results_"))
        return pd.read_csv(zf.open(csv_name), low_memory=False)


def _run_workflow(results_page, layout, session: Session, exhaustive=False, download_units=()):
    try:
        _calculate(results_page, session)
        _exercise_charts(results_page, layout, session, exhaustive)
        for unit in download_units:  # the export is slow (~7 s), so only where it adds coverage
            df = _download(results_page, session, unit)
            hours = len(df) / len(session.scenario_ids) / len(session.emission_ids)
            assert hours in (8760, 8784), f"download has {len(df)} rows"
    finally:
        shutil.rmtree(session.folder, ignore_errors=True)


def _scenario_groups():
    library = load_library(paths.EQUIPMENT_JSON)
    return {g.group_id: g.scenario_ids for g in library.scenario_groups}


@pytest.mark.parametrize("group_id", list(_scenario_groups()))
def test_library_building_every_scenario_group(
    results_page, results_layout, library_json, group_id
):
    """Building 83 (hospital, New York) with each predefined equipment scenario group."""
    metadata = Metadata.create(building_id="83", load_data=LoadData(load_type="simulated"))
    metadata.set_gea_grid_region_for_all("NYISO")
    session = Session(metadata, library_json, _scenario_groups()[group_id])
    _run_workflow(results_page, results_layout, session)


def test_every_emission_source_every_chart_option(results_page, results_layout, library_json):
    """Long-run, short-run, average and constant grid factors; every chart control; export."""
    metadata = Metadata.create(
        building_id="35",
        load_data=LoadData(load_type="simulated"),
        emission_settings=_all_emission_sources("CAISO"),
    )
    session = Session(metadata, library_json, list(DEFAULT_SELECTIONS.EQUIPMENT_SCENARIO.value))
    _run_workflow(results_page, results_layout, session, exhaustive=True, download_units=UNIT_MODES)


def test_measured_building(results_page, results_layout, library_json):
    """Real measured data: gaps, a leap year and two calendar years."""
    metadata = Metadata.create(building_id="182", load_data=LoadData(load_type="measured"))
    metadata.set_gea_grid_region_for_all("NorthernGrid_West")
    session = Session(metadata, library_json, list(DEFAULT_SELECTIONS.EQUIPMENT_SCENARIO.value))
    _run_workflow(results_page, results_layout, session, download_units=("SI",))


def test_custom_csv_upload(results_page, results_layout, library_json):
    """Upload path: CSV -> parse_custom_load_data -> custom load -> results."""
    from pages.loads_page import parse_custom_load_data

    source = pd.read_parquet(
        paths.LOAD_DATA_PARQUET,
        columns=["timestamp", "t_out_C", "heating_W", "cooling_W"],
        filters=[("building_id", "=", "35"), ("source", "=", "simulated")],
    )
    contents = "data:text/csv;base64," + base64.b64encode(
        source.to_csv(index=False).encode()
    ).decode("ascii")

    session_id = f"pytest-{uuid.uuid4().hex}"
    try:
        parsed = parse_custom_load_data(contents, "upload.csv", session_id)
        assert parsed["status"] == "success", parsed["message"]

        metadata = Metadata.create(
            load_data=LoadData(load_type="custom"), custom_load_path=parsed["filepath"]
        )
        metadata.set_gea_grid_region_for_all("CAISO")
        session = Session(metadata, library_json, ["eq_scenario_1", "eq_scenario_4"])
        session.session_data = {"session_id": session_id}
        _run_workflow(results_page, results_layout, session)
    finally:
        shutil.rmtree(Path(f"/tmp/{session_id}"), ignore_errors=True)


def test_upload_with_negative_loads_is_rejected_cleanly():
    from pages.loads_page import parse_custom_load_data

    csv = (
        "timestamp,t_out_C,heating_W,cooling_W\n"
        "2025-01-01 00:00,5,100,0\n2025-01-01 01:00,5,-100,0\n2025-01-01 02:00,5,100,0\n"
    )
    contents = "data:text/csv;base64," + base64.b64encode(csv.encode()).decode("ascii")
    result = parse_custom_load_data(contents, "bad.csv", f"pytest-{uuid.uuid4().hex}")
    assert result["status"] == "error"
    assert "negative" in result["message"]
