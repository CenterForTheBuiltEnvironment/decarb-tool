# Testing Scheme — Berkeley Decarb Tool

## Context

`src/energy.py` runs all hourly HVAC energy simulations and is the highest-risk module in the codebase. It processes load data through up to six sequential calculation phases (HR-WWHP, AWHP heating, boiler, electric resistance, AWHP cooling, chiller) and feeds into emissions calculations. A hand-calculated spreadsheet (`testing_cases.xlsx`) was historically used for manual verification after code changes — slow, error-prone, and skipped under time pressure.

This document describes the automated test suite that replaced it. The suite has **87 tests** that run in under a second locally, with no ongoing maintenance required for the invariant-based tests. Snapshot-based tests require a one-command update when output legitimately changes.

---

## Core Philosophy

Two complementary strategies are used together:

**Strategy A — Physics invariants**: Test that mathematical identities hold, not that outputs equal a specific number. For example: `electricity = thermal output ÷ COP` must be true at every hour, for any input. These tests never need updating — they encode the laws of thermodynamics, not specific numeric results.

**Strategy B — Snapshot regression**: Capture the full engine output (all columns, all hours) as a committed file. Future runs compare against it. When a deliberate change alters output, the developer runs one command, reviews the diff (which shows exactly which values changed and by how much), and commits the updated snapshot alongside the code change.

---

## Tier Structure

### Tier 1 — Unit Tests

| Property | Value |
|---|---|
| Marker | `@pytest.mark.unit` |
| Run command | `pytest -m unit` |
| Trigger | Every `git commit` (pre-commit hook) |
| Runtime | ~0.05 seconds |
| Failure means | A low-level pure function is broken; safe to block the commit |

**What is tested:** Pure helper functions in `src/energy.py` with tiny synthetic numpy arrays (3–5 data points). No real equipment JSON, no parquet files, no I/O of any kind. Also includes the existing equipment library and load validation tests in `test_equipment.py` and `test_loads.py`.

| Function | What is asserted |
|---|---|
| `_capacity_constraints` | OAT below `min_temp_C` → capacity zeroed; above `max_temp_C` → zeroed; in range → unchanged |
| `_per_unit_heating_cop` | Interpolation at exact breakpoints returns exact values; midpoint returns linear interpolation |
| `_per_unit_heating_capacity_W` | Same as above; scalar `capacity_W` triggers fixed-capacity broadcast path |
| `_per_unit_cooling_cop` / `_per_unit_cooling_capacity_W` | Same patterns for cooling side |
| `_heat_recovery_plr_curve` | Returns DataFrame with `cap` and `cop` columns; values match inputs |
| `_constant_heating_efficiency` | Returns correct float from Equipment fixture |
| Emissions rate formula | `weighting=0.0` → pure LRMER; `weighting=1.0` → pure SRMER; `weighting=0.5` → average |
| Physics invariants | `elec = thermal / COP`; `gas = thermal / efficiency`; COP > 1 → elec < thermal |

**Test files:**
- `tests/test_energy_unit.py` — 30 tests (energy helpers + invariants)
- `tests/test_equipment.py` — 9 tests (equipment library loading and validation)
- `tests/test_loads.py` — 10 tests (StandardLoad validation and edge cases)

---

### Tier 2 — Regression Tests

| Property | Value |
|---|---|
| Marker | `@pytest.mark.regression` |
| Run command | `pytest -m regression` |
| Trigger | Every push and pull request to GitHub (GitHub Actions) |
| Runtime | ~0.10 seconds |
| Failure means | Engine output changed relative to last known-good snapshot; requires developer review |

**What is tested:** Full execution of `loads_to_site_energy()` with real equipment library data, across four scenarios that each represent a distinct equipment configuration. Load input is a fixed 24-hour synthetic profile (not random — see parameters section below).

**Scenarios covered:**

| Scenario ID | Configuration |
|---|---|
| `eq_scenario_3` | AWHP + gas boiler backup + AWHP cooling |
| `eq_scenario_4` | AWHP + electric resistance backup + AWHP cooling |
| `eq_scenario_5` | HR-WWHP + AWHP + electric resistance backup + AWHP cooling (most complex) |
| `eq_scenario_10` | HR-WWHP only, no AWHP, gas boiler backup, no AWHP cooling |

**Layer 2a — Physics invariants (16 tests):** For each scenario, verified over all 24 output rows:
- `hr_hhw_W + awhp_hhw_W + boiler_hhw_W + res_hhw_W == hhw_W` (all heating served)
- `hr_chw_W + awhp_chw_W + chiller_chw_W == chw_W` (all cooling served)
- `elec_hr_Wh + elec_awhp_h_Wh + elec_res_Wh + elec_awhp_c_Wh + elec_chiller_Wh == elec_Wh` (electricity components sum to total)
- `elec_Wh >= 0` and `gas_Wh >= 0` everywhere

**Layer 2b — Snapshot tests (4 tests):** Full CSV output for each scenario is compared against a committed snapshot. Any deviation fails the test.

**Test files:**
- `tests/test_energy_regression.py`
- `tests/__snapshots__/test_energy_regression.ambr` (auto-managed by syrupy)

---

### Tier 3 — Integration Tests

| Property | Value |
|---|---|
| Marker | `@pytest.mark.integration` |
| Run command | `pytest -m integration` |
| Trigger | Every deployment (Cloud Build, before Docker build) |
| Runtime | ~0.5 seconds |
| Failure means | Something is fundamentally broken on real data; block the deployment |

**What is tested:** Full 8,760-hour runs using real parquet load data, checking physics invariants across all hours and comparing annual totals against committed golden values.

**Cases covered:**

| Building | Scenario | Location | Climate |
|---|---|---|---|
| Building 5 (Office) | `eq_scenario_3` | Port Angeles, WA | Zone 5C (mild) |
| Building 5 (Office) | `eq_scenario_5` | Port Angeles, WA | Zone 5C (mild) |
| Building 1 (Hospital) | `eq_scenario_3` | Denver, CO | Zone 5B (cold) |

**What is checked per case:**
1. Core columns (`t_out_C`, `heating_W`, `cooling_W`, `hhw_W`, `chw_W`, `elec_Wh`, `gas_Wh`) have no NaN values across all 8,760 hours. Detail columns (e.g., `hr_hhw_W`) are allowed to be NaN when the corresponding phase does not run for a given scenario.
2. All heating load served (component sum ≈ total, tolerance ±1 W)
3. All cooling load served (component sum ≈ total, tolerance ±1 W)
4. Electricity ≥ 0 and gas ≥ 0 everywhere
5. Component electricity sum matches total
6. Annual electricity and gas totals match golden values within **±0.1%**

**Current golden values** (`tests/snapshots/integration_annual_totals.json`):

| Case | Annual electricity (kWh) | Annual gas (kWh) |
|---|---|---|
| Building 5, `eq_scenario_3` | 177,772 | 57,646 |
| Building 5, `eq_scenario_5` | 183,876 | 0 (all-electric) |
| Building 1, `eq_scenario_3` | 1,049,487 | 206,452 |

**Test files:**
- `tests/test_energy_integration.py`
- `tests/snapshots/integration_annual_totals.json` (manually seeded, reviewed before committing)

---

## CI Integration

### GitHub Actions (`.github/workflows/tests.yml`)

Runs **Tier 1 + 2** on every push and pull request to any branch. Results appear directly in the GitHub PR interface.

```
push / pull_request → install dependencies → pytest -m "unit or regression"
```

### Pre-commit hook (`.pre-commit-config.yaml`)

Runs **Tier 1 only** on every local `git commit`, before the commit is accepted. Takes ~0.05 seconds.

Requires one-time setup per machine: `pre-commit install`

### Cloud Build (`cloudbuild.yaml`)

Runs **Tier 3** before building and deploying to Cloud Run. If integration tests fail, the Docker build does not start.

```
deploy trigger → pytest -m integration → docker build → docker push → cloud run deploy
```

---

## Parameters and Where to Change Them

### Tier 2: Scenarios tested

**File:** `tests/test_energy_regression.py`, top of file

```python
SCENARIOS = [
    "eq_scenario_3",
    "eq_scenario_4",
    "eq_scenario_5",
    "eq_scenario_10",
]
```

Add, remove, or swap scenario IDs here. All IDs must exist in `data/input/equipment_data.JSON`. Adding a scenario automatically adds it to both the physics invariant tests and the snapshot tests — no other changes required. New snapshots are generated on the next `--snapshot-update` run.

### Tier 2: Synthetic load profile

**File:** `tests/test_energy_regression.py`, `synthetic_load` fixture

```python
t_out = np.array([
    -20.0, -15.0, -10.0, -5.0,   # below and at AWHP heating min
      0.0,   4.4,  10.0,  15.0,
     ...
])
heating_W = np.clip((-t_out + 25) * 10_000, 0, None).astype(float)
cooling_W = np.clip((t_out - 15) * 8_000, 0, None).astype(float)
```

The profile deliberately sweeps from -20°C to +45°C to exercise capacity-constraint zeroing (below/above AWHP operating limits), simultaneous heating and cooling, and heating-only and cooling-only hours. It is deterministic (not random) so snapshots are stable. The number of hours is 24 — increasing to 48 gives more coverage at negligible runtime cost.

After changing this, run `pytest -m regression --snapshot-update` to regenerate snapshots.

### Tier 3: Buildings and scenarios tested

**File:** `tests/test_energy_integration.py`, top of file

```python
INTEGRATION_CASES = [
    ("5",  "eq_scenario_3"),
    ("5",  "eq_scenario_5"),
    ("1",  "eq_scenario_3"),
]
```

Each tuple is `(building_id, scenario_id)`. Building IDs correspond to rows in `data/input/building_metadata.csv` and loads in `data/input/load_data_full.parquet`. After changing, regenerate golden values (see below).

### Tier 3: Annual total tolerance

**File:** `tests/test_energy_integration.py`

```python
TOLERANCE = 0.001  # ±0.1%
```

Change to `0.005` for ±0.5% if floating-point differences across Python versions or platforms cause spurious failures.

---

## Operational Playbook

### Updating regression snapshots (Tier 2)

Run after any deliberate change that alters `loads_to_site_energy()` output (bug fix, equipment data update, scenario parameter change).

**Step 1 — Review first, update second.** Run the tests without updating to see syrupy's diff in the terminal:

```bash
pytest -m regression
```

Syrupy prints a readable diff of what changed (which rows, which columns, which values). This is the review step. If the changes look correct and proportionate to what you changed, proceed.

**Step 2 — Update and commit.**

```bash
pytest -m regression --snapshot-update
git add tests/__snapshots__/ tests/test_energy_regression.py  # plus your code change
git commit -m "fix: <description of fix>; update regression snapshots"
```

> Note: `git diff tests/__snapshots__/` is not useful for review — syrupy stores snapshots as a single long string, making the raw diff illegible. Always use the pytest terminal output (step 1) to review changes.

Never update snapshots without reviewing the diff.

### Regenerating integration golden values (Tier 3)

Run after any change that legitimately alters annual totals (bug fix, equipment data update, new building/scenario added):

```bash
pytest -m integration --generate-golden
cat tests/snapshots/integration_annual_totals.json
```

Review the new values. Cross-check 1–2 numbers manually against the hand-calculated spreadsheet if the change is significant. If they look correct, commit:

```bash
git add tests/snapshots/integration_annual_totals.json
git commit -m "fix: <description>; update integration golden values"
```

### Adding a new equipment scenario to the regression suite

1. Add the scenario ID to `SCENARIOS` in `tests/test_energy_regression.py`
2. Run `pytest -m regression` — the new scenario will fail with "snapshot does not exist"; inspect the printed output to confirm it looks sensible
3. Run `pytest -m regression --snapshot-update` to write the new snapshot
4. Commit both files

### Adding a new building/scenario to the integration suite

1. Add the `(building_id, scenario_id, source)` tuple to `SIMULATION_CASES` or `MEASURED_CASES` in `tests/test_energy_integration.py`
2. Run `pytest -m integration --generate-golden`
3. Review the new entry in `tests/snapshots/integration_annual_totals.json`
4. Commit both files

### Adding a new calculation phase to the engine

1. Add unit tests for the new helper functions in `tests/test_energy_unit.py`
2. Add the new output columns to the physics invariant checks in `test_energy_regression.py` and `test_energy_integration.py`
3. Run `pytest -m regression --snapshot-update` (new columns will appear in snapshots)
4. Commit all changes together

### If a snapshot update looks wrong

The diff is the signal. If the changed values are larger than expected, or wrong columns changed, or the sign flipped — roll back the code change and investigate before touching the snapshots. Never update snapshots to make a failing test pass without understanding why it failed.

---

## Dependency

`syrupy==5.5.3` — snapshot testing library for pytest. Manages storage, comparison, and updating of snapshot files. Snapshots are stored as `.ambr` files (plain text, human-readable, git-diffable).

---

## File Inventory

| File | Purpose |
|---|---|
| `tests/test_energy_unit.py` | Tier 1 — 30 unit tests for pure helpers and invariants |
| `tests/test_equipment.py` | Tier 1 — 9 tests for equipment library loading |
| `tests/test_loads.py` | Tier 1 — 10 tests for StandardLoad validation |
| `tests/test_energy_regression.py` | Tier 2 — 20 tests: physics invariants + snapshot tests |
| `tests/test_energy_integration.py` | Tier 3 — 18 tests: physics invariants + annual golden values |
| `tests/conftest.py` | Shared fixtures and `--generate-golden` CLI flag |
| `tests/__snapshots__/test_energy_regression.ambr` | Tier 2 snapshot files (auto-managed by syrupy) |
| `tests/snapshots/integration_annual_totals.json` | Tier 3 golden values (manually updated) |
| `pyproject.toml` | Pytest marker definitions (`unit`, `regression`, `integration`) |
| `requirements.txt` | Includes `syrupy==5.5.3` |
| `.pre-commit-config.yaml` | Pre-commit hook: runs Tier 1 on every local commit |
| `.github/workflows/tests.yml` | GitHub Actions: runs Tier 1+2 on every push and PR |
| `cloudbuild.yaml` | Cloud Build: runs Tier 3, then builds and deploys |
