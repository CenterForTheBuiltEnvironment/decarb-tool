from pathlib import Path
from typing import Union
import pandas as pd
import numpy as np

from src.metadata import Metadata

STANDARD_COLUMNS = ["t_out_C", "heating_W", "cooling_W"]

default_year = 2025  # for data without datetime info


def ensure_datetime(df: pd.DataFrame, default_year: int = 2025) -> pd.DataFrame:
    if "timestamp" in df.columns:
        # User already gave datetime
        df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce", utc=True)
    elif "hour_of_year" in df.columns:
        # Convert HOY → datetime
        base = pd.Timestamp(f"{default_year}-01-01 00:00:00", tz="UTC")
        df["timestamp"] = df["hour_of_year"].apply(
            lambda h: base + pd.Timedelta(hours=h - 1)  #! adjust for 1-based index
        )
    elif {"month", "day", "hour"}.issubset(df.columns):
        df["timestamp"] = pd.to_datetime(
            {
                "year": default_year,
                "month": df["month"],
                "day": df["day"],
                "hour": df["hour"],
            },
            utc=False,
        )
    else:
        raise ValueError(
            "No valid time column found (need timestamp OR hour_of_year OR month/day/hour)"
        )

    return df


class StandardLoad:
    """
    Unified interface for load data used for calculation.
    Schema: timestamp | t_out_C | heating_W | cooling_W
    - timestamp: datetime timestamp in ISO 8601 format (UTC)
    - t_out_C: outdoor air temperature [°C]
    - heating_W, cooling_W: load in Watts
    """

    def __init__(self, df: pd.DataFrame):
        self.df = self._validate(df)

    @staticmethod
    def _validate(df: pd.DataFrame) -> pd.DataFrame:

        # Ensure required columns
        missing = [c for c in STANDARD_COLUMNS if c not in df.columns]
        if missing:
            raise ValueError(f"Missing required columns: {missing}")

        # DATETIME VERSION
        # Timestamp / datetime handling
        ensure_datetime(df)

        # Sort + set index
        df = df.sort_values("timestamp").set_index("timestamp")

        # Check hourly frequency
        freq = pd.infer_freq(df.index)
        if freq not in ("H", "h"):
            print(f"⚠️ Warning: inferred frequency = {freq}, expected hourly")

        # Enforce numeric columns
        for col in ["t_out_C", "heating_W", "cooling_W"]:
            df[col] = pd.to_numeric(df[col], errors="coerce")
            if df[col].isnull().any():
                raise ValueError(f"Invalid numeric values in column {col}")

        return df

    # --------- Factory methods ---------
    @classmethod
    def from_parquet(cls, path: Union[str, Path]) -> "StandardLoad":
        df = pd.read_parquet(path, engine="pyarrow")
        return cls(df)

    @classmethod
    def from_csv(cls, path: Union[str, Path]) -> "StandardLoad":
        df = pd.read_csv(path)
        return cls(df)

    @classmethod
    def from_excel(cls, path: Union[str, Path], sheet: str = 0) -> "StandardLoad":
        df = pd.read_excel(path, sheet_name=sheet)
        return cls(df)

    # --------- Export ---------
    def to_parquet(self, path: Union[str, Path]):
        self.df.reset_index().to_parquet(path, engine="pyarrow", index=False)

    def to_csv(self, path: Union[str, Path]):
        self.df.reset_index().to_csv(path, index=False)

    # --------- Accessors ---------
    def slice_year(self, year: int) -> pd.DataFrame:
        return self.df[self.df.index.year == year]

    def stats(self) -> pd.DataFrame:
        return self.df.describe()


def get_load_data(settings: Metadata) -> StandardLoad:
    """
    Load and filter load data based on Metadata settings.
    Currently only supports `load_simulated`.

    Parameters
    ----------
    settings : Metadata
        User/project metadata including load_type, climate zone, building type.

    Returns
    -------
    StandardLoad
        A validated, canonical load object ready for calculations.
    """
    if settings.load_type == "load_simulated":
        # Load the raw DataFrame
        df = pd.read_parquet("data/input/load_data_simulated.parquet", engine="pyarrow")

        # Filter by user metadata
        mask = (df["ashrae_climate_zone"] == settings.ashrae_climate_zone) & (
            df["building_type"] == settings.building_type
        )
        df = df.loc[mask]

        if df.empty:
            raise ValueError(
                f"No simulated load found for climate zone={settings.ashrae_climate_zone}, "
                f"building type={settings.building_type}"
            )

        # Keep only canonical columns
        df = df[["timestamp", "t_out_C", "heating_W", "cooling_W"]]

        # Wrap into StandardLoad (validation runs here)
        return StandardLoad(df)

    else:
        raise NotImplementedError(
            f"Load type {settings.load_type!r} not yet supported in get_load_data"
        )
