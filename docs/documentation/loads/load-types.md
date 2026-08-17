# Load types

The **Load Data** section provides two options to define the building loads and outdoor temperature profiles: [selecting from a built-in library](load-types.md#select-from-library) or [uploading custom data](load-types.md#upload-custom-data).

## Select From Library

Expand this dropdown and select `Open Library` to access the Load Data Library popup and select from the tool's database of measured and simulated building profiles. The database can be filtered by load type (simulated or measured), ASHRAE climate zone, building type, building floor area, and peak heating hot water (HHW) and chilled water (CHW) loads.

### Simulated

#### DOE

The Simulated:DOE dataset contains loads generated using the [DOE Commercial Reference Building models](https://www.energy.gov/cmei/buildings/commercial-reference-buildings) with every combination of the following characteristics:

* 4 building types: Hospital, Large Office, Outpatient Healthcare, Large Hotel
* 2 vintages: 2004, 2022
* 16 climate zones: 1A, 2A-B, 3A-C, 4A-C, 5A-C, 6A-B, 7, 8. The representative cities used for each climate zone are listed [here](https://www.energy.gov/cmei/buildings/commercial-reference-buildings).

The heating loads in this dataset include only heating hot water (HHW) loads.

#### DEER

The Simulated:DEER dataset contains loads generated using the [CPUC Database of Energy Efficiency Resources (DEER) prototype models](https://cedars.cpuc.ca.gov/deer-resources/tools/energy-plus/) with every combination of the following characteristics:

* 5 building types: Hospital, Large Office, University, Education - Community College, Manufacturing - Biotech
* 2 vintages: 1996, 2020
* All 16 [California climate zones](https://www.energy.ca.gov/filebrowser/download/8625?fid=8625)

Further information about the DEER models is available [here](https://calbem-benchmarking.com/docs/building-energy-models). The heating loads in this dataset are the sum of heating hot water (HHW) and domestic hot water (DHW) loads.

#### Measured

The measured dataset contains loads data from 35 commercial buildings located primarily in California. It includes buildings with the following characteristics:

* Building types: Academic, Lab, Office, Medical Office, Other
* Vintages: 1963 to 2024
* Climate zones: 3B, 3C, 4A, 4C

Certain measured load profiles contain gaps or irregularities due to real-world monitoring limitations. The Data Completeness Summary is displayed when a measured load profile is selected so the user can verify the dataset quality.

## Upload Custom Data

Users can upload custom load profiles here. The upload must be a `csv` file that includes the columns listed below, named exactly in this format. Data must be aggregated hourly as the tool expects a full 8,760-hour dataset for a typical year. A blank template file in the required format can be downloaded from [here](https://github.com/CenterForTheBuiltEnvironment/decarb-tool/blob/main/data/input/upload_template.csv).

* `timestamp`: hourly datetime value
* `t_out_C`: outdoor air temperature, in degrees Celsius
* `heating_W`: heating load, in Watts
* `cooling_W`: cooling load, in Watts
