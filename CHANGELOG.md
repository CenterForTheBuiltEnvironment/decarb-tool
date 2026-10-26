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

- Optional exhaust air coil for the HR WWHP, with rejection and recovery capacities and a control option for each side (#122)

### Fixed

- The HR WWHP can now run exactly at its minimum turndown


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
