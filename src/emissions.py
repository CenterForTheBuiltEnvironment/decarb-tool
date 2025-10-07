from pprint import pprint
import pandas as pd
from pathlib import Path
from typing import Union
from src.metadata import Metadata, EmissionScenario


class StandardEmissions:
    """
    Unified interface for emissions data.
    Canonical schema:
        emission_scenario | gea_grid_region | time_zone | year | timestamp | lrmer_co2e_c | lrmer_co2e_p | srmer_co2e_c | srmer_co2e_p
    """

    def __init__(self, df: pd.DataFrame):
        self.df = self._validate(df)

    @staticmethod
    def _validate(df: pd.DataFrame) -> pd.DataFrame:
        required = [
            "emission_scenario",
            "gea_grid_region",
            "year",
            "time_zone",
            "timestamp",
            "lrmer_co2e_c",
            "lrmer_co2e_p",
            "srmer_co2e_c",
            "srmer_co2e_p",
        ]
        missing = [c for c in required if c not in df.columns]
        if missing:
            raise ValueError(f"Missing required columns in emissions data: {missing}")

        df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce", utc=False)
        if df["timestamp"].isnull().any():
            raise ValueError("Invalid or missing timestamps in emissions data")

        df = df.sort_values("timestamp").set_index("timestamp")

        # enforce numeric
        for col in ["lrmer_co2e_c", "lrmer_co2e_p", "srmer_co2e_c", "srmer_co2e_p"]:
            df[col] = pd.to_numeric(df[col], errors="coerce")
            if df[col].isnull().any():
                raise ValueError(f"Invalid numeric values in column {col}")

        return df

    # --------- Export ---------
    def to_parquet(self, path: Union[str, Path]):
        self.df.reset_index().to_parquet(path, engine="pyarrow", index=False)

    def to_csv(self, path: Union[str, Path]):
        self.df.reset_index().to_csv(path, index=False)

    # --------- Accessors ---------
    def slice_year(self, year: int) -> pd.DataFrame:
        return self.df[self.df["year"] == year]

    def stats(self) -> pd.DataFrame:
        return self.df.describe()


def get_emissions_data(
    scenario: EmissionScenario,
    path: Union[str, Path] = "data/input/emission_data.parquet",
) -> StandardEmissions:
    """
    Load emissions data filtered by user-provided EmissionsScenario.
    Handles selection of 'Combustion only' vs. 'Includes pre-combustion'.
    """

    df = pd.read_parquet(path, engine="pyarrow")

    # --- Filter by scenario, region, and years ---
    df = df[
        (df["emission_scenario"] == scenario.grid_scenario)
        & (df["gea_grid_region"] == scenario.gea_grid_region)
        & (df["year"] == scenario.year)
    ].copy()

    if df.empty:
        raise ValueError(
            f"No emissions data found for scenario={scenario.grid_scenario}, region={scenario.gea_grid_region}, year={scenario.year}"
        )

    # --- Handle emissions type mapping ---
    if scenario.emission_type == "Combustion only":
        lrmer_c = "lrmer_co2e_c"
        lrmer_p = "lrmer_co2e_p"
        srmer_c = "srmer_co2e_c"
        srmer_p = "srmer_co2e_p"
    elif scenario.emission_type == "Includes pre-combustion":
        lrmer_c = lrmer_p = "lrmer_co2e"
        srmer_c = srmer_p = "srmer_co2e"
    else:
        raise ValueError(
            "Invalid emissions_type. Use 'Combustion only' or 'Includes pre-combustion'."
        )

    # --- Build canonical schema ---
    result = pd.DataFrame(
        {
            "em_scen_id": scenario.em_scen_id,
            "emission_scenario": scenario.grid_scenario,
            "gea_grid_region": scenario.gea_grid_region,
            "time_zone": scenario.time_zone,
            "emission_type": scenario.emission_type,
            "year": df["year"],
            "timestamp": df["timestamp"],
            "lrmer_co2e_c": df[lrmer_c],
            "lrmer_co2e_p": df[lrmer_p],
            "srmer_co2e_c": df[srmer_c],
            "srmer_co2e_p": df[srmer_p],
        }
    )

    return StandardEmissions(result)
