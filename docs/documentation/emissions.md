---
icon: utility-pole
---

# Emissions

The Emissions page is the final step before results are calculated. The electric grid, gas, and refrigerant emissions scenarios are defined here. An explanation for each input and default scenario group is provided below.

The tool uses marginal grid emissions data from the NLR 2024 Cambium dataset. Further details for these inputs can be found in the [Cambium documentation](https://docs.nlr.gov/docs/fy25osti/93005.pdf). The raw data can be accessed [here](https://scenarioviewer.nlr.gov/?project=5c7bef16-7e38-4094-92ce-8b03dfa93380\&mode=download\&layout=Default).

### Inputs

#### Grid Scenario

From the Cambium docs:

The grid scenarios project the possible evolution of the US electricity sector through 2050. They are built around a base set of assumptions that contain median values for inputs such as technology costs and fuel prices, demand growth averaging 1.8% per year, and both state and federal electricity sector policies as they existed in August 2024. The eight scenarios are then created by varying renewable energy costs and performance, battery cost and performance, natural gas prices, and the rate of electricity demand growth.

1. **Mid-case (default)**: Central estimates for inputs such as technology costs, fuel prices, and demand growth.
2. **Low Renewable Energy and Battery Costs**: The same set of base assumptions as the first scenario but where renewable energy and battery costs are assumed to be lower and performance improvements greater.
3. **High Renewable Energy and Battery Costs**: The same set of base assumptions as the first scenario but where renewable energy and battery costs are assumed to be higher and performance improvements lesser.
4. **High Demand Growth**: The same set of base assumptions as the first scenario but where demand growth is assumed to average 2.8% from 2024 through 2050.
5. **Low Natural Gas Prices**: The same set of base assumptions as the first scenario but where natural gas prices are assumed to be lower.
6. **High Natural Gas Prices**: The same set of base assumptions as the first scenario but where natural gas prices are assumed to be higher.
7. **Low Renewable Energy and Battery Costs With High Natural Gas Prices**: The same set of base assumptions as the first scenario but with higher natural gas prices and where renewable energy and battery costs are assumed to be lower and performance improvements greater.

#### GEA Grid Region

The Generation and Emission Assessment grid region. GEA regions are based on data from the [EPA's eGRID subregions](https://www.epa.gov/green-power-markets/us-grid-regions). This input is automatically populated based on the specified building location, but can be edited by the user.

#### Emission Type

The **Combustion only** option selects the emissions rate due to direct combustion. The **Includes pre-combustion** option additionally accounts for pre-combustion processes such as fuel extraction, processing, and transport (including fugitive emissions).

#### Short-run Weighting

This input is the weight applied to the short-run marginal emissions rate (SRMER) in the total emissions rate calculation (described [here](calculations.md#calculation-1)). The default SRMER weight is 0.

SRMER accounts for marginal increases in a region's load at a specific point in time. LRMER captures the long-term shifts in electricity generation and accounts for structural changes in the grid.

#### Refrigerant Leakage

The annual refrigerant leakage rate for all equipment (heat pumps and chillers). The default leakage rate is 5%. Typical values for large equipment range from 4-15%; [ASHRAE Standard 228](https://store.accuristech.com/ashrae/standards/ashrae-228-2023?product_id=2562375) recommends 5%. The [MEP2040 Refrigerant Impact Calculator](https://refrigerant-impact.org/) is a comprehensive resource that compiles leakage rate data from various sources and can be used to determine precise values for different applications.

#### Gas Emissions Rate

The emissions rate associated with natural gas-based heating, in g/kWh (lb/kBtu). This input is automatically populated based on the emission type, but can be edited by the user.

For **combustion only**, the default carbon dioxide emission rate associated with direct combustion of natural gas is assumed to be 181 g/kWh (0.117 lb/kBtu). This is a standard and accepted value available from the EPA and other sources, and matches the [assumptions used in the Cambium dataset](https://docs.nrel.gov/docs/fy25osti/93005.pdf). This ignores all upstream leakage effects.

For **Includes pre-combustion**, the default carbon dioxide emission rate associated with natural gas delivered to a building is assumed to be 239 g/kWh (0.154 lb/kBtu), including estimated upstream leakage. This corresponds to a 2.2% natural gas leakage rate for gas delivered to city gate/power plant (which aligns with assumptions with Cambium precombustion leakage rate assumptions for natural gas taken from [Alvarez et. al. 2018](https://www.science.org/doi/10.1126/science.aar7204)) with an additional 0.7% for local distribution leakage for delivery of natural gas to building level gas appliances. This yields a total leakage rate assumption of 2.95% which aligns with a recent synthesis of subsequent field measured methane leakage rates in the US ([Kircher, 2025](https://www.sciencedirect.com/science/article/pii/S030142152500254X)). Note that methane leakage rates are multiplied by a conversion factor of 10.87 to convert them to carbon dioxide equivalent emissions. i.e. (100% + (2.95%\*10.87))\*181g/kWh = 239 g/kWh. This accounts for the fact that methane both has a much higher global warming potential than carbon dioxide but also gains mass when combusted; 1 ton of methane combusted equals 2.74 tons of carbon dioxide. Using the most recent IPCC (AR 6) factor for methane of 29.8 GWP (standard 100 year timeframe), accounting for the 2.74 difference in molar mass, this becomes a factor of 10.87 (29.8/2.74). See page 68-69 of the [CPUC 2024 Distributed Energy Resources Avoided Cost Calculator Documentation](https://www.ethree.com/wp-content/uploads/2025/02/2024-ACC-Documentation-v1b_clean.pdf) for more information and discussion on these calculations.

#### Year

The year under which the grid scenario is calculated.

### Default Scenario Groups

#### Year (2025, 2035, 2045)

With all other inputs held constant, the calculation date is varied in 10-year increments. These scenarios illustrate the reduction in electricity-based emissions as the grid infrastructure improves.

#### Refrigerant leakage (1%, 5%, 10%)

With all other inputs held constant, the equipment refrigerant leakage is varied. These scenarios illustrate the impact of refrigerant leakage assumptions.

#### Combustion vs pre-combustion

These scenarios allow comparison between the two emission types with all other inputs held constant.

### Future Development

1. Add functionality for user-uploaded emissions factors. This will allow locations outside the US (and those in Alaska, Hawaii, and Puerto Rico) to be analyzed, as they not covered by the Cambium dataset.
2. Add the option to use annual average, instead of marginal, emissions factors.
3. Use individual refrigerant leakage rates for different types of equipment.
