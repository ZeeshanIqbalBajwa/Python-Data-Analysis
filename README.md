## Overview
The purpose of this script is to create a database using user-provided credentials such as username, password, host, and port. The script defines tables and columns within the database as specified in the script.

## Data Manipulation
The script manipulates data from an Excel file named "NetworkElement.xlsx." It performs various data transformations, and in some cases, it compares the data with an "Area_code_Map.xlsx" file. After data manipulation, the final dataset is stored in a MariaDB database.

## Dashboard Panels
The folder "dashboard_panels" contanins json files which you can directly import into you grafana to see the dashboard.

## Disclaimer
some libraries which you need to install before are logging, pandas, sqlalchemy and sqlalchemy-utils.
