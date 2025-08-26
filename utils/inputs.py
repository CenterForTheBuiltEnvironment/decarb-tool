from dataclasses import dataclass
import pandas as pd


@dataclass
class Location:
    city: str
    state_id: str
    ashrae_climate_zone: str
    time_zone: str
    gea_grid_region: str | None = None


def get_city_and_zone(zip_code: str, df: pd.DataFrame) -> Location | None:
    zip_code = str(zip_code).zfill(5)
    mask = df["zips"].str.contains(rf"\b{zip_code}\b", na=False)
    match = df[mask]

    if match.empty:
        return None

    row = match.iloc[0]

    return Location(
        city=row["city"],
        state_id=row["state_id"],
        ashrae_climate_zone=row["ASHRAE"],
        time_zone=row["timezone"],
        gea_grid_region=row.get("gea_grid_region"),
    )


# Data source: https://www.kaggle.com/datasets/bambroot/us-cities-and-ashre-climate-zone?resource=download
