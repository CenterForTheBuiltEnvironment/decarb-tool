---
icon: air-conditioner
---

# Equipment

Equipment scenarios are defined on this page. An explanation for each input and default scenario group is provided below.

### Inputs

For each category of equipment noted below, the tool's equipment library defines a number of equipment models with energy and emissions characteristics, including capacity, efficiency, operating temperatures, and refrigerant type and weight. The library can be viewed in full [here](../../data/input/equipment_data.JSON).

<details>

<summary>Heat Recovery Water-to-Water Heat Pump (HR WWHP)</summary>

#### HR WWHP Model

Generic HR WWHP units are listed with efficiency values per the IECC. Performance tables for efficiency are defined over the range of operating part-loads for various heating hot water supply temperatures (HHWSTs).&#x20;

#### HR WWHP Performance Calculation Model

This input determines how the unit operating efficiency is calculated.

* **Interpolated table (HHWST fixed) (default)**: This calculation model interpolates between the performance table values with a user-specified HHWST to determine the operating efficiency for the part-load in every hour.
* _(To be implemented)_ **Fixed COP**: Fixed, user-editable efficiency at all operating conditions.
* _(To be implemented)_ **Performance curves**: Polynomial regression curves (as in EnergyPlus) with user-editable coefficients.

#### HR WWHP Heating Supply Temperature

The heating hot water supply (i.e., condenser leaving water) temperature. This value must be within the minimum and maximum HHWST constraints as defined in the equipment library. The default is equal to the lowest available operating HHWST.

</details>

<details>

<summary>Air-to-Water Heat Pump (AWHP)</summary>

#### AWHP Model

The following units are listed in the equipment library. Performance tables for efficiency and capacity are defined over the range of operating outside air temperatures (OATs) for various heating hot water supply temperatures (HHWSTs).&#x20;

* Generic units with efficiency values per the IECC
* [Aermec NRB](https://global.aermec.com/en/focus-prodotto/series-nrb-nrbh/)
* [Trane AXM](https://www.trane.com/commercial/north-america/us/en/products-systems/chillers/modular-chillers/thermafit-air-to-water-heat-pump-axm.html)
* [Trane ACX](https://www.trane.com/commercial/north-america/us/en/products-systems/chillers/air-cooled-chillers/ascend-air-to-water-heat-pump.html)

#### AWHP Performance Calculation Model

This input determines how the unit operating capacity and efficiency is calculated.

* **Interpolated table (HHWST fixed) (default)**: This calculation model interpolates between the performance table values with a user-specified HHWST to determine the operating efficiency and capacity for every OAT in the load profile.
* **Interpolated table (HHWST reset)**: An OAT-based HHWST reset is automatically defined with the following bounds: lowest available HHWST at 20°C OAT, and highest available HHWST at minimum operating OAT. This calculation model interpolates between the table values with the calculated HHWST to determine the operating efficiency and capacity for every OAT in the load profile.
* _(To be implemented)_ **Fixed COP**: Fixed, user-editable efficiency at all operating conditions.
* _(To be implemented)_ **Performance curves**: Polynomial regression curves (as in EnergyPlus) with user-editable coefficients.

#### AWHP Heating Supply Temperature

The heating hot water supply (i.e., condenser leaving water) temperature. This value must be within the minimum and maximum HHWST constraints as defined in the equipment library. The default is equal to the lowest available operating HHWST. Not editable if the Performance Calculation Model is set to **Interpolated table (HHWST reset)**.

#### AWHP Sizing Mode / Value

These two inputs determine how the total number of AWHP units, not including redundancy, is calculated.

* **Integer sizing (peak load) (default)**: The number of units required to meet the user-specified percentage of annual peak heating load, rounded up to the nearest integer.
* **Fractional sizing (peak load)**: The number of units required to meet the user-specified percentage of annual peak heating load, unrounded.
* **Fixed number of units**: User-specified actual number of units.

#### AWHP Sizing Priority

This input determines which load profile is used to calculate the number of units per the sizing mode and value inputs.

#### AWHP Redundancy

An integer number of additional units for redundancy. The default value is 1, i.e., N+1 redundancy. The total number of AWHP units, including redundancy, is used in refrigerant leakage calculations.

#### AWHP Use Cooling

This input determines if the AWHPs serve cooling loads. The tool prioritizes heating loads, so the cooling load in a given hour is served by the AWHPs only if their heating load is zero.

</details>

<details>

<summary>Backup Equipment</summary>

Backup heating and cooling equipment are defined in two types:

* Specific: equipment models with nominal capacity and associated refrigerant data
* Generic: equipment with infinite capacity and no associated refrigerant data

The default equipment types are all specific equipment models.&#x20;

#### Backup Heating

Two types of backup heating equipment are defined: gas boilers and electric resistance heaters. Both are assumed to have fixed efficiency over all operating conditions. A range of typical gas boiler efficiencies are provided; the default is 80% efficiency.

#### Backup Cooling

The backup cooling equipment is assumed to be an air-cooled chiller with fixed efficiency over all operating conditions. Generic units are defined with efficiency values per the IECC.



</details>

### Default Scenario Groups

A summary of the significant inputs in each scenario group is provided below. The full list of inputs for each default scenario can be viewed in the tool or [here](../../data/input/equipment_data.JSON#L729).

#### Default

This scenario group consists of some typical equipment configurations to provide an overview of the equipment options in the tool.

* **Gas Boiler + AC Chiller** (eq\_scenario\_1): gas boiler; air-cooled chiller
* **Elec Boiler + AC Chiller** (eq\_scenario\_2): electric resistance boiler; air-cooled chiller
* **20% AWHP (H+C) + Gas Backup** (eq\_scenario\_3): heating and cooling AWHP, sized for 20% peak heating load; gas boiler; air-cooled chiller
* **100% AWHP (H+C) + Elec Backup** (eq\_scenario\_4): heating and cooling AWHP, sized for 100% peak heating load; electric resistance boiler; air-cooled chiller
* **HR WWHP + 100% AWHP (H+C) + Elec Backup** (eq\_scenario\_5): HR WWHP; heating and cooling AWHP, sized for 100% peak heating load; electric resistance boiler; air-cooled chiller

#### Partial AWHP

This scenario group varies the AWHP sizing percentage, holding all other inputs constant, to provide a comparison of partial electrification options.

* **Gas Boiler + AC Chiller** (eq\_scenario\_1): gas boiler; air-cooled chiller
* **20% (Frac) AWHP (H+C) + Gas Backup** (eq\_scenario\_6): heating and cooling AWHP, sized for 20% peak heating load, fractional; gas boiler; air-cooled chiller
* **40% (Frac) AWHP (H+C) + Gas Backup** (eq\_scenario\_7): heating and cooling AWHP, sized for 40% peak heating load, fractional; gas boiler; air-cooled chiller
* **60% (Frac) AWHP (H+C) + Gas Backup** (eq\_scenario\_8): heating and cooling AWHP, sized for 60% peak heating load, fractional; gas boiler; air-cooled chiller
* **100% (Frac) AWHP (H+C) + Gas Backup** (eq\_scenario\_6): heating and cooling AWHP, sized for 100% peak heating load, fractional; gas boiler; air-cooled chiller

#### Heat Recovery

This scenario group evaluates the impact of heat recovery with different configurations of equipment to serve the remaining loads.

* **HR WWHP + Gas Boiler + AC Chiller** (eq\_scenario\_10): HR WWHP; gas boiler; air-cooled chiller
* **HR WWHP + Elec Boiler + AC Chiller** (eq\_scenario\_11): HR WWHP; electric resistance boiler; air-cooled chiller
* **HR WWHP + 20% AWHP (H+C) + Elec Backup** (eq\_scenario\_12): HR WWHP; heating and cooling AWHP, sized for 20% peak heating load; electric resistance boiler; air-cooled chiller
* **HR WWHP + 100% AWHP (H+C) + Elec Backup** (eq\_scenario\_5): HR WWHP; heating and cooling AWHP, sized for 100% peak heating load; electric resistance boiler; air-cooled chiller

### Future Development

1. Allow users to edit the equipment library and add new equipment models.
2. Add non-energy and emissions characteristics for equipment, such as dimensions, weight, and electrical requirements.
3. Display equipment sizing outputs, such as total capacity required, total number of units, and total refrigerant weight.
4. Allow users to edit the HHWST reset bounds.

