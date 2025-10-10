<!-- PROJECT LOGO -->
<br />
<div align="center">
  <a href="https://github.com/CenterForTheBuiltEnvironment/cbe-tool-template">
    <img src="assets/img/logo-preliminary.png" alt="Decarb Tool Logo" width="auto" height="80">
  </a>

  <h2 align="center">Berkeley Decarb Web Tool</h2>

  <p align="center">
    <br />
    <a href="https://github.com/CenterForTheBuiltEnvironment/decarb-tool/blob/main/docs/documentation-short.md"><strong>Explore the docs »</strong></a>
    <br />
    <br />
    <a href="https://github.com/CenterForTheBuiltEnvironment/cbe-tool-template">View Demo</a>
    ·
    <a href="https://github.com/CenterForTheBuiltEnvironment/decarb-tool/issues/new?labels=bug&template=issue--bug-report.md">Report Bug</a>
    ·
    <a href="https://github.com/CenterForTheBuiltEnvironment/decarb-tool/issues/new?labels=enhancement&template=feature-request.md">Request Feature</a>


  </p>
</div>



<!-- TABLE OF CONTENTS -->
<details>
  <summary>Table of Contents</summary>
  <ol>
    <li>
      <a href="#about-the-tool">About the Tool</a>
      <ul>
        <li><a href="#built-with">Built With</a></li>
      </ul>
    </li>
    <li>
      <a href="#getting-started">Getting Started</a>
      <ul>
        <li><a href="#prerequisites">Prerequisites</a></li>
        <li><a href="#installation">Installation</a></li>
      </ul>
    </li>
    <li><a href="#usage">Usage</a></li>
    <li><a href="#roadmap">Roadmap</a></li>
    <li><a href="#contributing">Contributing</a></li>
    <li><a href="#license">License</a></li>
    <li><a href="#contact">Contact</a></li>
    <li><a href="#acknowledgments">Acknowledgments</a></li>
  </ol>
</details>


## About the Tool
<!-- [![Tool Banner](link-to-your-banner-image)](link-to-your-banner-image) -->

The **Berkeley Decarb Tool** is an open-source web application developed by the [Center for the Built Environment (CBE)](https://cbe.berkeley.edu) at the University of California, Berkeley.

It supports building decarbonization planning by enabling users to assess and compare the long-term operational carbon emissions of HVAC systems under different configurations and grid emission scenarios.

### Key Features (Current Version)

* Location-based load profiles: Select representative building heating and cooling load profiles by climate zone, building type, and vintage — or upload your own.

* HVAC equipment comparison: Build and customize multiple system configurations using an expanding library of common equipment types (e.g., water-to-water heat pumps, air-to-water heat pumps, boilers, chillers, and hybrid systems).

* Emission scenario modeling: Evaluate performance across multiple grid scenarios (e.g., MidCase, High RE) and years using NREL Cambium data.

* Flexible emissions accounting: Incorporate short-run marginal weighting, refrigerant leakage, and gas leakage assumptions.

* Interactive results: Compare energy use, emissions, and key performance indicators across equipment and emission scenarios to support early-stage decision-making and sensitivity analyses.

### Purpose
The tool is designed to bring consistency, transparency, and scientific robustness to HVAC decarbonization studies — reducing reliance on proprietary or ad hoc internal modeling approaches.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

### Built With

![Python](https://img.shields.io/badge/python-3670A0?style=for-the-badge&logo=python&logoColor=ffdd54) ![Plotly Dash](https://img.shields.io/badge/plotly-3F4F75.svg?style=for-the-badge&logo=plotly&logoColor=white)


<p align="right">(<a href="#readme-top">back to top</a>)</p>


<!-- GETTING STARTED
## Getting Started
This is an example of how you may give instructions on setting up your project locally.
To get a local copy up and running follow these simple example steps.


### Prerequisites
Software or tools required before installation. <br>
Make sure `requirements.txt` is up-to-date.

<!-- INSTALLATION CODE BLOCK -->
<!-- 


### Installation
Step-by-step guide on how to install and set up the tool, incl. code blocks.

```python
def welcome(tool-name):
    print(f"Welcome to the {tool-name} GitHub page!")

welcome("cbe-webtool-name")
```


<p align="right">(<a href="#readme-top">back to top</a>)</p> -->


<!-- USAGE EXAMPLES -->
## Documentation
While the tool is still under development, we have set up a short documentation outlining underlying calculations [here](). <br>

<!-- - All larger tools should have a dedicated Documentation, ideally set up using GitBook and linked to the `docs` folder. -->

<p align="right">(<a href="#readme-top">back to top</a>)</p>



## Roadmap
In the near future, we are planning to add the following features or improvements to the tool. <br>

- [ ] Utility cost calculations
- [ ] N+1 redundancy in sizing calculations to account for additional refrigerant leakage
- [ ] Water-cooled chillers with PLR-based capacity and COP curves
- [ ] Cooling tower water use calculations
- [ ] Outdoor air temperature-based capacity and COP curves for air-cooled chillers
- [ ] Varying refrigerant leakage rates for different types of equipment
- [ ] Exhaust air heat recovery
- [ ] AWHPs with heat recovery
- [ ] Sizing AWHPs based on heating or cooling instead of heating only
- [ ] Fuel switching evaluation (based on grid emissions and equipment COP)
- [ ] Load shifting evaluation (thermal energy storage)


Please find open [issues](https://github.com/CenterForTheBuiltEnvironment/decarb-tool/issues) for a full list of proposed features (and known issues).

<p align="right">(<a href="#readme-top">back to top</a>)</p>



## Contributing
Contributions are what make the open source community such an amazing place to learn, inspire, and create. Any contributions you make are **greatly appreciated**.

If you have a suggestion that would make this better, please fork the repo and create a pull request. You can also simply open an issue with the tag "enhancement".
Thanks!

1. Fork the Project
2. Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3. Commit your Changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the Branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

<p align="right">(<a href="#readme-top">back to top</a>)</p>



## License
Distributed under the MIT License. See `LICENSE.txt` for more information.

<p align="right">(<a href="#readme-top">back to top</a>)</p>



## Feedback
For general feedback and anything related to the codebase, the tool functionality or underlying calculations, please check the documentation, review/add issues or use the [Discussions](https://github.com/CenterForTheBuiltEnvironment/decarb-tool/discussions) page.

<p align="right">(<a href="#readme-top">back to top</a>)</p>


## Authors

* [Toby Kramer](https://www.linkedin.com/in/tobias-kramer-69684611b/)
* [Paul Raftery](https://www.linkedin.com/in/paul-raftery-578b0721/)
* [Urwa Irfan](https://www.linkedin.com/in/urwa-irfan/)

<p align="right">(<a href="#readme-top">back to top</a>)</p>



## Acknowledgements
Credits to those who have contributed to the tool or resources (e.g. libraries) that were helpful.

<p align="right">(<a href="#readme-top">back to top</a>)</p>