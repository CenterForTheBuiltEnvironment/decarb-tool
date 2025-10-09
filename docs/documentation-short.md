# Berkeley Decarb Tool Documentation

## Calculation Workflow

### Loads to Site Energy

Hourly heating and cooling loads are converted to electricity & gas site energy.

#### Inputs

* Hourly heating and cooling load profile with outdoor air temperature
* Equipment library with performance curves and efficiencies
* User-specified equipment scenario (HR WWHP, AWHP, boiler, chiller, etc.)

#### Calculation

Loads are allocated in 6 steps, for each type of equipment present in the scenario:

* **Phase 1: Heat Recovery Water-to-Water Heat Pump (HR WWHP)**
  * Uses simultaneous heating and cooling demand
  * Limited by maximum capacity and minimum turndown
  * Capacity and COP vary with part load ratio (PLR)
  * Electricity use is calculated using capacity and COP curves
  * Updates remaining heating and cooling loads after heat recovery
* **Phase 2: Heating Air-to-Water Heat Pump (AWHP)**
  * Sizing logic: specified fixed number of units or calculated based on specified percentage of peak load and nominal capacity
  * Capacity and COP vary with outdoor air temperature
  * Electricity use is calculated using capacity and COP curves
  * Updates remaining heating load
* **Phase 3: Natural Gas Boiler**
  * Covers any remaining heating load, if served by gas
  * Electricity use is calculated using fixed efficiency
* **Phase 4: Electric Resistance Heating**
  * Covers any remaining heating load, if served by electricity
  * Electricity use is calculated using 100% efficiency
* **Phase 5: Cooling Air-to-Water Heat Pump (AWHP)**
  * Sizing logic: uses number of units calculated for heating in Phase 2
  * Capacity and COP vary with outdoor air temperature
  * Electricity use is calculated using capacity and COP curves
  * Updates remaining cooling load
* **Phase 6: Electric Chiller**
  * Covers any remaining cooling load
  * Electricity use is calculated using fixed COP

<img src="https://i.imgur.com/Qzux714.png" alt="Energy Calculation" width="400"/>

#### Outputs

* Per-hour electricity and gas usage totals
* Optional details:
  * Per-equipment served load, COPs, capacities, fuel use

#### Key Simplifications

* Water temperature-dependent performance is fixed at rated temperaturees for selected equipment (no temperature resets)
* AWHP COP and capacity is dependent on OAT only (no PLR, no cycling losses, no defrost derate)
* Heat recovery WWHP COP is dependent on part load
  * Equipment does not operate below turndown (no cycling modeled)
  * No auxiliary fans/pump energy use modeled
* Equipment operates ideally up to capacity limits
* Instantaneous dispatch: no control dynamics or lag
* AWHP sizing logic is simplified (fraction of peak load or fixed number of units)

### Site Energy to Source Emissions

Electricity & gas site energy are converted to CO2-equivalent source emissions.

#### Inputs

* Site energy data
* Emissions dataset filtered by scenario and region
* User-specified emissions settings (years, type, weighting)

#### Calculation

* **Step 1: Align time resolution**
  * Extract month and hour from load data timestamps
  * Collapse emissions data into monthly-hourly averages
* **Step 2: Compute electricity emissions rate**
  * Combustion only: weighted average of short-run/long-run marginal rates (CO₂e_c)
  * Includes pre-combustion: adds upstream emissions (CO₂e_p)
  * Emissions data is taken from NREL Cambium
* **Step 3: Merge and expand for each year**
  * Match load data (month/hour) with emissions rates
  * Duplicate across requested emission years
* **Step 4: Calculate emissions**
  * Electricity = elec × elec_emissions_rate
  * Gas = gas × gas_emissions_rate
    * Gas emissions rate is assumed to be 240 gCO₂e/kWh (combustion and precombustion) based on NREL Cambium and IPCC data
  * Refrigerants = GWP × charge × annual leakage / 8760 (spread evenly over time)
    * GWP is taken from the latest IPCC Assessment Report dataset based on the type of refrigerant for each equipment
    * Annual leakage rate is assumed to be fixed (user-editable, default 5%) for all equipment

#### Outputs

* Per-hour and per-year emissions totals

#### Key Simplifications

* Monthly-hourly matching (instead of true hourly time series)

## Next Steps

The following features will be added to future versions of the tool.

* Utility cost calculations
* N+1 redundancy in sizing calculations to account for additional refrigerant leakage
* Water-cooled chillers with PLR-based capacity and COP curves
* Cooling tower water use calculations
* Outdoor air temperature-based capacity and COP curves for air-cooled chillers
* Varying refrigerant leakage rates for different types of equipment
* Exhaust air heat recovery
* AWHPs with heat recovery
* Sizing AWHPs based on heating or cooling instead of heating only
* Fuel switching evaluation (based on grid emissions and equipment COP)
* Load shifting evaluation (thermal energy storage)
