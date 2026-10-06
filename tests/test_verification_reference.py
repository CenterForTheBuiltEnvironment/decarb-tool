"""Verification tier, part 2: tool vs independent 8760-hour reference model.

The reference (tests/verification/reference_model.py) re-implements the
documented method without importing src/, for two library buildings
(83, 35), three scenarios and two grid emission sources. Annual electricity,
gas and emissions must agree within REL_TOL.

The only expected residual is the engine rounding hourly values to 4 decimals
(about 1e-7 relative on refrigerant emissions), so the tolerance is tight: a
real implementation change will show up here.

To print the comparison as a table:
    python -m tests.verification.report
"""

import pytest

from tests.verification.cases import ALL_CASES, METRICS, reference_result, tool_result

pytestmark = pytest.mark.verification

REL_TOL = 1e-5  # 0.001 %


@pytest.mark.parametrize("case", ALL_CASES, ids=lambda c: c.id)
def test_tool_matches_reference_model(case):
    tool, reference = tool_result(case), reference_result(case)
    mismatches = {
        metric: (round(tool[metric], 3), round(reference[metric], 3))
        for metric in METRICS
        if tool[metric] != pytest.approx(reference[metric], rel=REL_TOL, abs=1e-3)
    }
    assert not mismatches, f"{case.id}: tool vs reference {mismatches}"
