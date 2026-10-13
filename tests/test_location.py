"""Tests for location handling: load profile vs. user-selected location (search)."""

import shutil
import uuid
from pathlib import Path

import pytest
from dash.exceptions import PreventUpdate

from src.metadata import Metadata

DENVER_ID = "1"  # DOE, 5B, WestConnect_North
FAIRBANKS_ID = "2"  # DOE, 8, grid region "TBD"
FRESNO_ID = "274"  # DEER, 3B, CAISO, CA climate zone 13
MIAMI_ZIP = "33129"  # FL, 1A, FRCC


def _regions(metadata: Metadata) -> set:
    return {s.gea_grid_region for s in metadata.emission_settings}


@pytest.mark.unit
class TestApplyLocation:
    def test_ca_location_adds_ca_region(self):
        m = Metadata.create()
        m.apply_location("Fresno", "CA", "3B", 13.0, "CAISO", source="load")
        assert m.location == "Fresno"
        assert m.ashrae_climate_zone == "3B"
        assert m.climate_zone_output == "3B (CA Region 13)"
        assert _regions(m) == {"CAISO"}
        assert m.location_source == "load"
        assert m.location_zip is None

    def test_ca_location_without_zone_shows_ashrae_only(self):
        m = Metadata.create()
        m.apply_location("Los Angeles", "CA", "3B", float("nan"), "CAISO", source="load")
        assert m.climate_zone_output == "3B"

    def test_non_ca_location(self):
        m = Metadata.create()
        m.apply_location("Miami", "FL", "1A", None, "FRCC", source="user", zip=MIAMI_ZIP)
        assert m.climate_zone_output == "1A"
        assert _regions(m) == {"FRCC"}
        assert m.location_source == "user"
        assert m.location_zip == MIAMI_ZIP

    def test_tbd_region_becomes_none(self):
        m = Metadata.create()
        m.apply_location("Fairbanks", None, 8, None, "TBD", source="load")
        assert m.ashrae_climate_zone == "8"
        assert _regions(m) == {None}

    def test_new_location_replaces_all_fields(self):
        m = Metadata.create()
        m.apply_location("Fresno", "CA", "3B", 13, "CAISO", source="load")
        m.apply_location("Denver", None, "5B", None, "WestConnect_North", source="load")
        assert m.climate_zone_output == "5B"
        assert _regions(m) == {"WestConnect_North"}

    def test_clear_location(self):
        m = Metadata.create()
        m.apply_location("Miami", "FL", "1A", None, "FRCC", source="user", zip=MIAMI_ZIP)
        m.clear_location()
        assert m.location is None
        assert m.climate_zone_output is None
        assert _regions(m) == {None}
        assert m.location_source is None
        assert m.location_zip is None


@pytest.mark.app
class TestLocationCallbacks:
    @pytest.fixture(scope="class", autouse=True)
    def loads_page(self):
        import app  # noqa: F401  (pages can only be imported after the Dash app exists)

        from pages import loads_page

        return loads_page

    @pytest.fixture
    def session_data(self):
        session_id = f"pytest-{uuid.uuid4().hex}"
        yield {"session_id": session_id}
        shutil.rmtree(Path(f"/tmp/{session_id}"), ignore_errors=True)

    def _select_building(self, loads_page, metadata_json, building_id, session_data):
        out = loads_page.confirm_selection(1, building_id, metadata_json, session_data)
        return out[2]

    def test_load_change_updates_all_location_fields(self, loads_page, session_data):
        m = self._select_building(loads_page, None, DENVER_ID, session_data)
        m = self._select_building(loads_page, m, FRESNO_ID, session_data)
        m = Metadata(**m)
        assert m.location == "Fresno"
        assert m.climate_zone_output == "3B (CA Region 13)"
        assert _regions(m) == {"CAISO"}
        assert m.location_source == "load"

    def test_user_location_persists_across_load_changes(self, loads_page, session_data):
        m = self._select_building(loads_page, None, DENVER_ID, session_data)
        m = loads_page.update_metadata(MIAMI_ZIP, m)
        m = self._select_building(loads_page, m, FRESNO_ID, session_data)
        m = Metadata(**m)
        assert m.location == "Miami"
        assert m.climate_zone_output == "1A"
        assert _regions(m) == {"FRCC"}
        assert m.building_id == FRESNO_ID

    def test_clearing_user_location_reverts_to_load(self, loads_page, session_data):
        m = self._select_building(loads_page, None, FRESNO_ID, session_data)
        m = loads_page.update_metadata(MIAMI_ZIP, m)
        m = Metadata(**loads_page.update_metadata(None, m))
        assert m.location == "Fresno"
        assert m.climate_zone_output == "3B (CA Region 13)"
        assert _regions(m) == {"CAISO"}
        assert m.location_source == "load"

    def test_restoring_same_zip_does_not_reapply(self, loads_page, session_data):
        m = loads_page.update_metadata(MIAMI_ZIP, Metadata.create().model_dump())
        m["emission_settings"][0]["gea_grid_region"] = "edited on emissions page"
        with pytest.raises(PreventUpdate):
            loads_page.update_metadata(MIAMI_ZIP, m)
        # restore_location_input (clientside) builds its option label from these fields
        assert m["location_zip"] == MIAMI_ZIP
        assert m["location_state"] == "FL"

    def test_tbd_building_has_no_grid_region(self, loads_page, session_data):
        m = Metadata(**self._select_building(loads_page, None, FAIRBANKS_ID, session_data))
        assert m.location == "Fairbanks"
        assert _regions(m) == {None}
        _, color = loads_page.update_location_source_note(m.model_dump())
        assert color == "orange"
