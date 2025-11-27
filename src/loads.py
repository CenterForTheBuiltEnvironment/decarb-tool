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
        df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce", utc=False)
    elif "hour_of_year" in df.columns:
        # Convert HOY → datetime
        base = pd.Timestamp(f"{default_year}-01-01 00:00:00", tz=None)
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

        # Enforce numeric columns, but allow NaNs
        for col in ["t_out_C", "heating_W", "cooling_W"]:
            df[col] = pd.to_numeric(df[col], errors="coerce")
            bad_count = df[col].isnull().sum()
            if bad_count > 0:
                print(
                    f"⚠️ Warning: {bad_count} invalid values in column {col}, set to NaN"
                )

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


def get_load_data(metadata: Metadata) -> StandardLoad:
    """
    Load and filter load data based on Metadata settings.

    - simulation / measured: from a single parquet, filtered by building_id + load_type
    - custom: from user-uploaded csv at metadata.custom_load_path
    """
    load_type = metadata.load_data.load_type

    if load_type in ("simulation", "measured"):
        if metadata.building_id is None:
            raise ValueError("building_id required to load simulation/measured data")

        parquet_path = Path("data/input/load_data_full.parquet")

        # filter at read-time for speed
        df = pd.read_parquet(
            parquet_path,
            engine="pyarrow",
            filters=[
                ("building_id", "=", metadata.building_id),
                ("source", "=", load_type),
            ],
        )

        if df.empty:
            raise ValueError(
                f"No {load_type} load found for building_id={metadata.building_id}"
            )

        keep = ["timestamp", "t_out_C", "heating_W", "cooling_W"]
        missing = [c for c in keep if c not in df.columns]
        if missing:
            raise ValueError(f"Missing required columns in parquet: {missing}")

        df = df[keep]

        return StandardLoad(df)

    elif load_type == "custom":
        if not metadata.custom_load_path:
            raise ValueError("custom_load_path required for load_type='custom'")

        return StandardLoad.from_parquet(metadata.custom_load_path)

    else:
        raise NotImplementedError(f"Unsupported load type: {load_type!r}")
