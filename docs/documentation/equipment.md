---
icon: air-conditioner
---

# Equipment

Equipment scenarios are defined on this page. An explanation for each input and default scenario group is provided below.

### Inputs

For each category of equipment noted below, the tool's equipment library defines a number of equipment models with energy and emissions characteristics, including capacity, efficiency, operating temperatures, and refrigerant type and weight. The library can be viewed in full [here](https://github.com/CenterForTheBuiltEnvironment/decarb-tool/blob/development/data/input/equipment_data.JSON).

<details>

<summary>Heat Recovery Water-to-Water Heat Pump (HR WWHP)</summary>

**HR WWHP Model**

Generic HR WWHP units are listed with efficiency values per the IECC. Performance tables for efficiency are defined over the range of operating part-loads for various heating hot water supply temperatures (HHWSTs).

**HR WWHP Performance Calculation Model**

This input determines how the unit operating efficiency is calculated.

* **Interpolated table (HHWST fixed) (default)**: This calculation model interpolates between the performance table values with a user-specified HHWST to determine the operating efficiency for the part-load in every hour.
* _(To be implemented)_ **Fixed COP**: Fixed, user-editable efficiency at all operating conditions.
* _(To be implemented)_ **Performance curves**: Polynomial regression curves (as in EnergyPlus) with user-editable coefficients.

**HR WWHP Heating Supply Temperature**

The heating hot water supply (i.e., condenser leaving water) temperature. This value must be within the minimum and maximum HHWST constraints as defined in the equipment library. The default is equal to the lowest available operating HHWST.

</details>

<details>

<summary>Air-to-Water Heat Pump (AWHP)</summary>

**AWHP Model**

The following units are listed in the equipment library. Performance tables for efficiency and capacity are defined over the range of operating outside air temperatures (OATs) for various heating hot water supply temperatures (HHWSTs).

* Generic units with efficiency values per the IECC
* [Aermec NRB](https://global.aermec.com/en/focus-prodotto/series-nrb-nrbh/)
* [Trane AXM](https://www.trane.com/commercial/north-america/us/en/products-systems/chillers/modular-chillers/thermafit-air-to-water-heat-pump-axm.html)
* [Trane ACX](https://www.trane.com/commercial/north-america/us/en/products-systems/chillers/air-cooled-chillers/ascend-air-to-water-heat-pump.html)

**AWHP Performance Calculation Model**

This input determines how the unit operating heating capacity and efficiency is calculated.

* **Interpolated table (HHWST fixed) (default)**: This calculation model interpolates between the performance table values with a user-specified HHWST to determine the operating efficiency and capacity for every OAT in the load profile.
* **Interpolated table (HHWST reset)**: An OAT-based HHWST reset is automatically defined with the following bounds: lowest available HHWST at 20°C OAT, and highest available HHWST at minimum operating OAT. This calculation model interpolates between the table values with the calculated HHWST to determine the operating efficiency and capacity for every OAT in the load profile.
* _(To be implemented)_ **Fixed COP**: Fixed, user-editable efficiency at all operating conditions.
* _(To be implemented)_ **Performance curves**: Polynomial regression curves (as in EnergyPlus) with user-editable coefficients.

**AWHP Heating Supply Temperature**

The heating hot water supply (i.e., condenser leaving water) temperature. This value must be within the minimum and maximum HHWST constraints as defined in the equipment library. The default is equal to the lowest available operating HHWST. Not editable if the Performance Calculation Model is set to **Interpolated table (HHWST reset)**.

**AWHP Sizing Mode / Value**

These two inputs determine how the total number of AWHP units, not including redundancy, is calculated.

* **Integer sizing (peak load) (default)**: The number of units required to meet the user-specified percentage of annual peak heating or cooling load, rounded up to the nearest integer.
* **Fractional sizing (peak load)**: The number of units required to meet the user-specified percentage of annual peak heating or cooling load, unrounded.
* **Fixed number of units**: User-specified actual number of units.

**AWHP Redundancy**

An integer number of additional units for redundancy. The default value is 1, i.e., N+1 redundancy. The total number of AWHP units, including redundancy, is used in refrigerant leakage calculations.

**Use AWHP for Cooling**

This input determines if the AWHPs serve cooling loads. The tool prioritizes heating loads, so the cooling capacity in a given hour is calculated using the number of units not used to serve heating load.

**AWHP Sizing Priority**

This input determines which load profile (heating, cooling, or both) is used to calculate the number of units per the sizing mode and value inputs. The default is heating load. Not editable if Use AWHP for Cooling is unchecked.

</details>

<details>

<summary>Backup Equipment</summary>

Backup heating and cooling equipment are defined in two types:

* Specific: equipment models with nominal capacity and associated refrigerant data
* Generic: equipment with infinite capacity and no associated refrigerant data

The default equipment types are all specific equipment models.

**Backup Heating**

Two types of backup heating equipment are defined: gas boilers and electric resistance heaters. Both are assumed to have fixed efficiency over all operating conditions. A range of typical gas boiler efficiencies are provided; the default is 80% efficiency.

**Use Optimal Heating Fuel**

Dynamically switch between electric and gas heating based on emissions (see [Calculations](calculations.md#calculation-1) for further detail). Only selectable if the scenario contains both AWHP and gas boiler backup heating.

**Backup Cooling**

The backup cooling equipment is assumed to be an air-cooled chiller with fixed efficiency over all operating conditions. Generic units are defined with efficiency values per the IECC.

</details>

### Default Scenario Groups

A summary of the significant inputs in each scenario group is provided below. The full list of inputs for each default scenario can be viewed in the tool or [here](https://github.com/CenterForTheBuiltEnvironment/decarb-tool/blob/development/data/input/equipment_data.JSON#L729).

#### Default

This scenario group consists of some typical equipment configurations to provide an overview of the equipment options in the tool.

#### Partial AWHP

This scenario group varies the AWHP sizing percentage, holding all other inputs constant, to provide a comparison of partial electrification options.

#### Heat Recovery

This scenario group evaluates the impact of heat recovery with different configurations of equipment to serve the remaining loads.

#### HHW Supply Temps

This scenario group varies the WWHP and AWHP heating hot water supply temperature and performance calculation model (fixed vs OAT-based reset), holding all other inputs constant.

#### Dynamic Fuel Switching

This scenario group compares fully gas and fully electric heating plants with a partial AWHP scenario and a fuel switching scenario.

### Equipment Manager

The Equipment Manager, linked in the sidebar, lists all equipment with its data checks, performance curves and properties. Library equipment is never changed. To customise an item, select it and click **Duplicate to edit**. This creates a custom copy that you can then edit:

- **Overview**: name, manufacturer, capacities, efficiency (backup heating and chillers), refrigerant, charge, weight, dimensions, electrical data and notes. Pick a refrigerant from the list to fill in its GWP (IPCC AR4, 100-year). For a refrigerant that is not listed, type its name and enter the GWP yourself.
- **Performance** (heat pumps): edit any curve point in the table, add or remove curve points and supply temperatures, and change the outdoor air temperature limits of each curve. **Scale curves** multiplies all COP and/or capacity values of the selected mode by a percentage. The factors are relative to the unscaled curves, so applying 90 % twice still gives 90 %. While you edit, the original curves are shown in grey for comparison.

Click **Save** to store the copy. Saving is blocked while the data checks report errors; warnings, such as a COP outside 1 to 8, are allowed. Custom equipment appears in the equipment selections of the scenario edit window, marked "custom". It is kept for the browser session, also when the equipment scenarios are reset, and is included in the settings file of the results download. A custom item cannot be deleted while a scenario uses it.

### Future Development

1. Import and export custom equipment as a file, to reuse it across sessions.
2. Display equipment sizing outputs, such as total capacity required, total number of units, and total refrigerant weight.
3. Allow users to edit the HHWST reset bounds.
