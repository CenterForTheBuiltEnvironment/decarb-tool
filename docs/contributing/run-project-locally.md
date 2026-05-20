---
description: >-
  These instructions will get you a copy of the project up and running on your
  local machine for development and testing purposes.
metaLinks:
  alternates:
    - >-
      https://app.gitbook.com/s/-MhupA7DXRC4lRDTpJQJ/contributing/run-project-locally
---

# Run project locally

### Prerequisites <a href="#prerequisites" id="prerequisites"></a>

Python 3 installed on your machine and [pipenv](https://docs.pipenv.org/).

* If you do not have Python installed on your machine you can follow [this guide](https://wiki.python.org/moin/BeginnersGuide/Download).
* You can install `pipenv` using the following command `pip install pipenv`.

### Installation <a href="#installation" id="installation"></a>

This guide is for Mac OSX, Linux, or Windows.

1.  **Get the source code from the GitHub repository**

    <a class="button secondary">Copy</a>

    ```
    $ git clone https://github.com/CenterForTheBuiltEnvironment/decarb-tool.git
    $ cd decarb-tool
    ```
2.  **Create a virtual environment using pipenv and install dependencies:**

    <a class="button secondary">Copy</a>

    ```
     pipenv install --dev
    ```
3. **Run tool locally**

Now you should be ready to run the tool locally.

`pipenv run python app.py`

Visit [http://localhost:8050](http://localhost:8050/) in your browser to check it out. Note that whenever you want to run the tool, you have to activate the virtualenv first.
