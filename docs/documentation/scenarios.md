---
icon: table-cells-columns
---

# Scenarios

The [Equipment](equipment.md) and [Emissions](emissions.md) pages are used to define various scenarios to compare equipment configurations and emissions calculation assumptions. This section explains how to navigate these two pages.

### Add Scenario

The `Add` button in the top-right corner can be used to add a new scenario. In the Add Scenario popup, select an existing scenario under `Base scenario` to copy as a starting point. New scenarios are automatically incrementally numbered, but the ID can be edited. Providing a scenario name is optional but recommended for ease of use.

### Reset Scenarios

The `Reset` button in the top-right corner can be used to reset all scenarios and scenario groups to the initial default assumptions.

### Scenario Groups

Users can select from predefined sets of scenarios from the `Scenario Group` dropdown under the page title. See the [Equipment](equipment.md#scenario-groups) and [Emissions](emissions.md#default-scenario-groups) pages for further information on the scenario groups.

### Views

Three views of the scenario tables are available:

* **Simple**: essential, high-level information for the scenario.
* **Advanced**: the full set of inputs for the scenario.
* **Differences**: only the inputs with values that differ between scenarios in the current group.
  * Inputs with differences are shown with bold text in all views.

### Select Scenario

The checkbox icon in the `Selected` row can be used to select a scenario for analysis. Only selected scenarios are included in the calculations. A maximum of 5 scenarios can be selected at a time.

### Edit Scenario

The pencil icon in the `Selected` row can be used to edit an individual scenario's inputs. Click `Save` in the Edit Scenario popup to incorporate edits when completed, or `Cancel` to discard changes.

### Delete Scenario

The trashcan icon in the `Selected` row can be used to delete a scenario entirely. A predefined default scenario can be restored after deletion using `Reset` or by re-selecting its parent scenario group.

### Future Development

1. Allow users to create and edit scenario groups.
2. Add functionality to save edited scenario groups for future use.
