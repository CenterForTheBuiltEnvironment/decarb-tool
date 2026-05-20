---
icon: temperature-list
---

# Loads

The Loads page is the first step in the tool workflow. All energy and emissions calculations depend on the climate and loads information defined here. The page is divided into three sections described below.

### Loads

Users should start by selecting a building location, using the search field to filter by location name or ZIP code. Next, specify the building loads and outdoor temperature profile from one of the two options under **Load Data**. See the [Load types](load-types.md) page for more information.

### Summary

The center section of the page displays key details about the building and summary statistics about the selected heating and cooling load and outdoor temperature profiles.

#### Building Characteristics

* **Location**: The selected building location. This determines the climate region and grid region.
* **Building Type**: The building type associated with the load profile. This will remain blank if not specified when uploading custom data.
* **Vintage**: The construction year of the building. This will remain blank if not specified when uploading custom data.
* **Climate Region**: The ASHRAE climate zone, as defined by [Standard 169-2020, Climatic Data For Building Design Standards](https://webstore.ansi.org/standards/ashrae/ansiashrae1692020), [Addendum a](https://www.ashrae.org/file%20library/technical%20resources/standards%20and%20guidelines/standards%20addenda/169_2020_a_20211029.pdf), which references the 2021 ASHRAE Handbook of Fundamentals.
  * For locations in California, the CA climate region as defined by the [California Energy Commission](https://www.energy.ca.gov/programs-and-topics/programs/building-energy-efficiency-standards/climate-zone-tool-maps-and) is also shown.
* **GEA Grid Region**: The Generation and Emission Assessment grid region, as defined by NLR's [2024 Cambium](https://docs.nlr.gov/docs/fy25osti/93005.pdf) dataset. GEA regions are based on data from the [EPA's eGRID subregions](https://www.epa.gov/green-power-markets/us-grid-regions). This input identifies the region used to select emissions factors.
* **Building Area**: The net floor area of the building.

#### Load Characteristics

* [**Load Type**](load-types.md)
* **Annual H/C Ratio**: The ratio of the total annual heating load to cooling load. A value well below 1 indicates a cooling-dominant building, and a value well above 1 indicates a heating-dominant building. A building with evenly balanced annual loads will have an H/C ratio close to 1.
* **Peak Heating/Cooling Load**: The largest hourly heating/cooling load in the profile.
* **Max/Median/Min Outdoor Temperature**: The maximum, median, and minimum outdoor air temperature in the profile.

### Load Visualization

This section includes graphics of the provided heating and cooling loads and outdoor temperature profiles to help review and verify the input dataset.

The first chart shows the annual trend in heating and cooling loads by plotting the peak hourly load for each month.

The second chart illustrates the distribution of heating and cooling loads over the range of outdoor air temperatures in the profile. The average load across each 5°C (or 10°F) temperature bin is shown.
