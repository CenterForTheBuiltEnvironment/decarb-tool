# Testing Scheme for Berkeley Decarb Tool

## Context

The Berkeley Decarb Tool performs multi-phase hourly energy simulations (heat recovery WWHP,
AWHP heating, boiler, electric resistance, AWHP cooling, chiller) and converts site energy to
emissions. The core engine in `src/energy.py` currently has **zero test coverage** despite being
the highest-risk module. A hand-calculated spreadsheet (`testing_cases.xlsx`) exists with
intermediate and final values for 7 scenarios across 3 buildings, and has historically been used
for manual verification after code changes. This is slow, error-prone, and unsustainable.

The goal is a tiered testing scheme that:
- Catches real bugs at the right level of development (push → PR → deployment)
- Requires minimal ongoing maintenance when equipment data or scenarios change
- Integrates into the existing pre-commit + Cloud Build pipeline
- Uses the spreadsheet as a one-time bootstrapping aid, then exits it from the daily loop

---

## Why Not Keep the Spreadsheet as a Test Fixture?

The obvious first instinct is to copy the hand-calculated values from `testing_cases.xlsx` into a
JSON fixture file and assert against them. This is rejected for the following reasons:

1. **Double maintenance burden**: Every equipment curve update or scenario change requires updating
   the spreadsheet AND the fixture JSON separately.
2. **Brittleness at the edges**: The spreadsheet tests 2–3 specific hours per scenario. It doesn't
   tell you whether hours 4–8760 behave correctly.
3. **Format fragility**: If someone restructures the spreadsheet, fixture generation breaks.
4. **Wrong failure signal**: When a fixture test fails, you don't know if the code is wrong or if
   the expected value was stale. You still have to go back to first principles.

The spreadsheet remains valuable as a **one-time bootstrap** (seeding initial snapshots) and as
**design documentation** for colleagues. It just shouldn't be in the critical path of every test run.

---

## Core Testing Philosophy

The scheme uses two complementary strategies:

### Strategy A — Physics Invariants
Test that **mathematical identities hold**, not that outputs equal a specific number.

Examples:
- `hr_hhw + awhp_hhw + boiler_hhw + res_hhw == heating_W` (all load served)
- `elec_awhp_h == awhp_hhw / awhp_cop_h` (electricity follows from thermal output and COP)
- `gas_boiler == boiler_hhw / efficiency` (gas input follows from thermal output and efficiency)

**Maintenance cost: zero.** These never need updating because they encode the laws of thermodynamics,
not specific numeric results. If the code violates them, something is genuinely wrong.

### Strategy B — Snapshot Regression
Capture the full output of the calculation engine (all columns, all hours) as a committed file.
Future test runs compare against it. When a deliberate change alters the output:
```bash
pytest --snapshot-update
```
The developer reviews the diff (a meaningful CSV delta showing exactly which values changed and
by how much), then commits it alongside the code change.

**Maintenance cost: one command + diff review.** This is much lighter than recalculating by hand.
The snapshot is always in sync with the code by construction, and the diff is the paper trail.

**Initial seeding**: The very first snapshot should be generated after manually verifying the
engine output against the spreadsheet. After that, the spreadsheet is no longer needed for testing.

---

## Tier Structure

### Tier 1 — Unit Tests  (`pytest -m unit`)

**Trigger**: Every push, via pre-commit hook  
**Target runtime**: < 10 seconds  
**Failure means**: A low-level pure function is broken; safe to block the commit

#### What they test

Pure helper functions in `src/energy.py`, tested with small synthetic numpy arrays (3–5 data
points). No real equipment JSON, no parquet files, no I/O of any kind.

| Function | What to assert |
|---|---|
| `_capacity_constraints` | OAT below min → capacity = 0; OAT above max → capacity = 0; OAT in range → capacity unchanged |
| `_per_unit_heating_cop` | Interpolation at exact table breakpoints returns exact table values; between points returns interpolated value |
| `_per_unit_heating_capacity_W` | Same as above; fixed-capacity fallback path returns scalar broadcast |
| `_per_unit_cooling_cop` / `_per_unit_cooling_capacity_W` | Same patterns for cooling |
| `_heating_supply_temp_performance` | With two known HHWST values, interpolation at midpoint returns midpoint performance |
| `_heat_recovery_plr_curve` | Output DataFrame has correct columns (`cap`, `cop`, `cap_h_to_cap_c`, `cap_c`, `cop_c`); values consistent with input |
| `_constant_heating_efficiency` | Returns correct float from Equipment fixture |
| Emissions rate formula in `site_to_source` | With synthetic LRMER/SRMER arrays, weighted combination at weighting=0 returns pure LRMER, at weighting=1 returns pure SRMER, at 0.5 returns average |

Physics invariant tests also belong here, written with synthetic single-hour inputs:
- `elec = thermal / COP` for all phases
- `gas = thermal / efficiency` for boiler
- Refrigerant GWP = `gwp_per_kg × weight_kg × leakage_rate`

**New file**: `tests/test_energy_unit.py`

#### Existing tests

`tests/test_equipment.py` (8 tests) and `tests/test_loads.py` (13 tests) already cover equipment
library loading and `StandardLoad` validation. These are already fast and pure. Changes needed:
- Add `@pytest.mark.unit` to all existing test classes/functions
- No logic changes required — they slot directly into Tier 1

This gives Tier 1 approximately **40–50 tests** total after adding the new energy unit tests.

---

### Tier 2 — Regression Tests  (`pytest -m regression`)

**Trigger**: Every PR (added as a step in Cloud Build before Docker build)  
**Target runtime**: 30–90 seconds  
**Failure means**: The engine output changed relative to the last known-good snapshot; requires
developer review before merge

#### What they test

Full execution of `loads_to_site_energy()` and `site_to_source()` with real equipment library
data, across a representative set of 3–4 scenarios (one per distinct equipment configuration:
HR-WWHP+AWHP, AWHP-only, AWHP+boiler, AWHP-only with cooling). These use minimal load DataFrames
(a few dozen synthetic hours) rather than full 8760-hour runs to keep runtime short.

**Two layers within Tier 2:**

**Layer 2a — Physics invariant checks** (over the full output DataFrame):
- `hhw_rem_W == 0` for every row (all heating served)
- `chw_rem_W == 0` for every row (all cooling served)
- `elec_Wh >= 0` for every row
- `gas_Wh >= 0` for every row
- `elec_Wh == elec_hr_Wh + elec_awhp_h_Wh + elec_res_Wh + elec_awhp_c_Wh + elec_chiller_Wh`
- `elec_awhp_h_Wh ≈ awhp_hhw_W / awhp_cop_h` (within floating point tolerance) wherever AWHP is running
- Emission totals are non-negative and correctly sum components

These catch logic bugs that break the energy balance without needing a golden reference number.

**Layer 2b — Snapshot regression** (output must match prior run):
Uses `syrupy` to persist the output DataFrame and compare on each run.
Test structure:
```python
@pytest.mark.regression
def test_scenario_awhp_only_snapshot(snapshot):
    result = loads_to_site_energy(load=sample_load, library=library, scenario_ids=["hp01_res"])
    snapshot.assert_match(result.to_csv(), "awhp_only.csv")
```

When the output legitimately changes (e.g., a bug fix or equipment data update):
```bash
pytest -m regression --snapshot-update
```
The developer reviews the diff with `git diff tests/snapshots/`. The diff shows exactly which
values changed, in which columns, at which hours. This makes the review fast and auditable.

**Snapshot seeding**: On first run, snapshots are generated from the current engine. Before
committing them, manually cross-check a few key values against the spreadsheet to confirm the
engine was already correct. After that, the spreadsheet is no longer needed as a test dependency.

**New files**:
- `tests/test_energy_regression.py`
- `tests/snapshots/` directory (auto-populated by syrupy on first run)

**New dependency**: `syrupy` (lightweight snapshot testing library for pytest)

---

### Tier 3 — Integration / Smoke Tests  (`pytest -m integration`)

**Trigger**: Before production deployment (Cloud Build release step, or manually on a release branch)  
**Target runtime**: 2–5 minutes  
**Failure means**: Something is fundamentally broken end-to-end; block the deployment

#### What they test

Full 8760-hour runs (or 8784 for leap years) using real parquet load data for one representative
building per building type (office, lab, academic). All scenarios for that building are run.

**What is checked:**
1. **No NaNs** in any output column across all 8760 rows
2. **Load conservation**: `hhw_rem_W == 0` and `chw_rem_W == 0` for every hour — meaning no
   heating or cooling load was silently dropped
3. **Energy positivity**: `elec_Wh ≥ 0` and `gas_Wh ≥ 0` everywhere
4. **Component electricity sum** matches total (no phantom energy)
5. **Emissions positivity** and correct summation: total = elec + gas + refrigerant
6. **Annual snapshot**: Total annual kWh electricity and kgCO2e emissions match a stored golden
   value within ±0.1%. This catches silent regressions from changes to equipment JSON or parquet
   data that otherwise wouldn't be noticed until someone reads a result and finds it implausible.

The annual snapshot is stored as a small JSON file (`tests/snapshots/integration_annual_totals.json`).
It is updated manually and intentionally, not automatically, because it represents a "this is what
the tool produces" statement that deserves deliberate sign-off.

**New file**: `tests/test_energy_integration.py`

#### Why not run integration tests on every PR?
Full-year runs over multiple buildings/scenarios take meaningful time and hit the parquet files.
PRs should be unblocked quickly. The physics invariant checks in Tier 2 already catch most logic
errors; Tier 3 is a final safety net before production exposure.

---

## CI Integration

### Pre-commit (`.pre-commit-config.yaml`)

Add a new hook that runs Tier 1 only. This is fast enough to not annoy developers:

```yaml
- repo: local
  hooks:
    - id: pytest-unit
      name: pytest (unit tests)
      entry: python -m pytest -m unit -x -q --tb=short
      language: system
      pass_filenames: false
      stages: [pre-commit]
```

If the unit suite grows beyond ~15 seconds, restrict it further with
`--ignore=tests/test_energy_integration.py` etc.

### Cloud Build (`cloudbuild.yaml`)

Add a test step before the Docker build step. This runs Tiers 1 + 2 on every PR/main push:

```yaml
- name: 'python:3.12-slim'
  entrypoint: bash
  args:
    - '-c'
    - 'pip install -r requirements.txt && pytest -m "unit or regression" -q --tb=short'
  id: 'run-tests'
  waitFor: ['-']   # run immediately; build step should waitFor: ['run-tests']
```

For deployment (tagged releases), add a second step running Tier 3:
```yaml
- name: 'python:3.12-slim'
  entrypoint: bash
  args:
    - '-c'
    - 'pip install -r requirements.txt && pytest -m integration -q --tb=short'
  id: 'run-integration-tests'
  waitFor: ['run-tests']
```

### `pyproject.toml` — pytest markers

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
markers = [
  "unit: fast, pure function and invariant tests, no I/O (<10s total)",
  "regression: snapshot + invariant tests using real equipment library (~60s)",
  "integration: full 8760-hour end-to-end runs with real load data (2-5min)",
]
addopts = ["-v", "--tb=short", "-ra"]
```

---

## Maintenance Playbook

| Situation | Action |
|---|---|
| Bug fix in `energy.py` | Tests should fail if the fix changes output. Run `pytest -m regression --snapshot-update`, review diff, commit snapshot alongside the fix. |
| Equipment performance curve updated in JSON | Run `pytest -m regression --snapshot-update`. Review which values changed and by how much. If plausible, commit. |
| New equipment or scenario added to JSON | Existing tests unaffected. Add a new scenario ID to the regression test's scenario list if you want it covered. |
| New calculation phase added to the engine | Add unit tests for the new helper functions, add the new column to physics invariant checks, and update snapshot. |
| Spreadsheet updated with new hand-calculated values | Optionally use it to cross-check the current snapshot values, but no code or fixture change is required. |
| Snapshot update looks wrong | The diff is the signal. Roll back the code change and investigate before updating. Never update snapshots blindly. |

---

## File Summary

| File | Status | Purpose |
|---|---|---|
| `tests/test_equipment.py` | Edit (add markers) | Tier 1 — slot into unit suite |
| `tests/test_loads.py` | Edit (add markers) | Tier 1 — slot into unit suite |
| `tests/test_energy_unit.py` | New | Tier 1 — pure helper function + invariant tests |
| `tests/test_energy_regression.py` | New | Tier 2 — physics invariants + snapshot tests |
| `tests/test_energy_integration.py` | New | Tier 3 — full-year smoke tests |
| `tests/snapshots/` | New (auto-populated) | Snapshot files managed by syrupy |
| `tests/snapshots/integration_annual_totals.json` | New (manual) | Annual totals golden values |
| `pyproject.toml` | Edit | Add markers |
| `.pre-commit-config.yaml` | Edit | Add pytest-unit hook |
| `cloudbuild.yaml` | Edit | Add test steps (Tier 1+2 on PR, Tier 3 on release) |

---

## Recommended Implementation Order

1. **Add markers to existing tests** — zero risk, zero behavior change, immediately makes the
   existing 21 tests part of the formal Tier 1 suite
2. **Add pytest markers to `pyproject.toml`** — infrastructure only
3. **Write `test_energy_unit.py`** — pure functions, no dependencies on real data
4. **Add pre-commit hook** — gates pushes on Tier 1
5. **Write `test_energy_regression.py`** — seed the initial snapshots, cross-check against
   spreadsheet values for a few scenarios, commit
6. **Update Cloud Build** — Tier 1+2 now run on every PR/push to main
7. **Write `test_energy_integration.py`** — generate annual total golden values, commit
8. **Add integration step to Cloud Build release** — Tier 3 gates deployment
