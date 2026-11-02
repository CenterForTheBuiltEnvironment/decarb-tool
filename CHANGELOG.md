# Changelog

All notable changes to the Berkeley Decarb Tool are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project
uses [Semantic Versioning](https://semver.org/). While the version is below 1.0.0:

- **minor** (0.x.0): new features, or changes that alter calculation results or the format of
  saved/uploaded data
- **patch** (0.0.x): bug fixes and UI tweaks

Add entries under `[Unreleased]` with every pull request, grouped as Added / Changed / Fixed /
Removed. `scripts/bump_version.py` turns them into a release section.

## [Unreleased]

### Added

- Results download includes an annual summary CSV with one row per equipment and emission
  scenario combination
- Reset button in the Scale Load Profile and Modify Base Load modals to restore the load
  without scaling or base load
- Confirm button in both modals: Apply only updates the values shown in the modal, so several
  changes (e.g. heating and cooling) can be made before Confirm uses them in the calculation
- Modify Base Load modal shows peak loads without and with the base load side by side
- Status line in both modals says what is in the table and whether Apply or Confirm is needed
  next; Confirm is disabled while an entered value has not been applied or nothing changed
- Equipment Manager page, linked in the sidebar next to the documentation: browse the equipment
  library by type, search it, and inspect each item's data, data checks and performance curves
  (plot and table, SI/IP) (#171)
- Performance curve plot in the edit equipment scenario window, with the curve at the selected
  supply temperature highlighted (#171)
- Equipment validation that reports every problem in an equipment definition (errors and
  warnings), groundwork for the Equipment Manager and editable performance curves (#171)
- Optional `source`, `based_on` and `notes` fields on equipment, to tell library equipment from
  user-made copies

### Changed

- Default unit system is IP; SI can still be selected with the unit toggle
- Results download is named after the case (building, location, climate zone, load scaling,
  base load, unit system), e.g. `decarb_B3_Denver_CZ5B_scaled-h1.25-c1.25_SI_<date>.zip`, and
  unzips into a folder of the same name
- Hourly results CSV starts with readable case columns (equipment scenario number as shown on the
  Results page, emission scenario letter, name, year, grid scenario, source, emission type) so
  scenario combinations can be filtered directly; rows are grouped per combination and the
  remaining columns are ordered by topic. The load-year column was removed (it is in the timestamp)
- Settings summary lists load scaling and base load, and shows emission rates in the selected unit
  system
- Values below 1 in the results CSVs keep 4 significant figures instead of 3 decimals, so small
  hourly emissions and lb CO₂e/kWh rates no longer round to zero
- Scale Load Profile modal shows the original library values next to the scaled values instead
  of overwriting them
- Scaling by peak heating or peak cooling load only scales that load; heating and cooling
  factors are kept separately, so both peaks can be matched
- Heating and cooling can each have their own base load (floor or offset); applying a base
  load replaces the previous one for that load type instead of stacking, and base loads are
  always applied after scaling
- Heat pump curves are now also checked for strictly increasing outdoor temperature or capacity
  values, positive COP and capacity, numeric non-duplicate supply temperatures, and ordered
  min/max limits before a calculation runs

### Fixed

- Combined LRMER/SRMER/AER CO₂e rate columns in the results CSV were not converted (and had no
  unit) in IP mode
- Applying load scaling repeatedly no longer compounds the scale factor
- Input labels and the base load method description show as soon as the modals open
- The supply temperature reset now picks the lowest supply temperature curve numerically
  instead of alphabetically (no effect on the current equipment library)

## [0.1.0] - 2026-10-13

First versioned release of the tool. Earlier deployments were not versioned consistently;
this changelog starts here.

### Added

- Four-step workflow: loads, equipment, emissions, results
- Building load profiles from the library (DOE prototypes and measured data), filterable by
  location, building type and vintage, or uploaded as a custom CSV
- Load scaling and base-load adjustment for selected load profiles
- Location search to set the building location independently of the load profile
- Equipment scenarios combining heat recovery water-to-water heat pumps, air-to-water heat pumps,
  air-cooled chillers, and gas or electric boilers, with an editable equipment library
- Grid emission scenarios based on NREL Cambium data (long-run and short-run marginal rates),
  including refrigerant and natural gas leakage assumptions
- Results page comparing energy use and emissions across equipment and emission scenarios, with
  data download
- SI/IP unit toggle
- Tiered automated test suite (unit, verification, regression, integration, app)
- Versioning and changelog workflow; the footer version is read from `pyproject.toml`

### Fixed

- Summary cards on the loads page are shown empty before a load is selected, instead of
  "No metadata yet"
- Add/Reset buttons on the equipment and emissions pages stay on the right on narrow windows;
  the subtitle wraps instead
- Location set via the location search is stored correctly (#200, #201)
- Faster results download (#110)
