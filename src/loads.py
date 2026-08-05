from pathlib import Path

import pandas as pd

from src import paths
from src.metadata import Metadata
from utils.logging_config import get_logger

logger = get_logger(__name__)

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
            logger.warning(f"Inferred frequency = {freq}, expected hourly")

        # Enforce numeric columns, but allow NaNs
        for col in ["t_out_C", "heating_W", "cooling_W"]:
            df[col] = pd.to_numeric(df[col], errors="coerce")
            bad_count = df[col].isnull().sum()
            if bad_count > 0:
                logger.warning(f"{bad_count} invalid values in column {col}, set to NaN")

        return df

    # --------- Factory methods ---------
    @classmethod
    def from_parquet(cls, path: str | Path) -> "StandardLoad":
        df = pd.read_parquet(path, engine="pyarrow")
        return cls(df)

    @classmethod
    def from_csv(cls, path: str | Path) -> "StandardLoad":
        df = pd.read_csv(path)
        return cls(df)

    @classmethod
    def from_excel(cls, path: str | Path, sheet: str = 0) -> "StandardLoad":
        df = pd.read_excel(path, sheet_name=sheet)
        return cls(df)

    # --------- Export ---------
    def to_parquet(self, path: str | Path):
        self.df.reset_index().to_parquet(path, engine="pyarrow", index=False)

    def to_csv(self, path: str | Path):
        self.df.reset_index().to_csv(path, index=False)

    # --------- Properties ---------
    @property
    def num_hours(self) -> int:
        """Number of hours in the dataset."""
        return len(self.df)

    @property
    def has_leap_day(self) -> bool:
        """Check if data contains Feb 29 (leap day)."""
        return ((self.df.index.month == 2) & (self.df.index.day == 29)).any()

    @property
    def spans_multiple_years(self) -> bool:
        """Check if data spans more than one year from start date."""
        if len(self.df) == 0:
            return False
        start = self.df.index.min()
        end = self.df.index.max()
        one_year_later = start + pd.DateOffset(years=1)
        return end >= one_year_later

    # --------- Methods ---------
    def limit_to_one_year(self) -> "StandardLoad":
        """Trim data to first year from start date.

        Keeps the first 8760/8784 hours of data, removing any overflow
        beyond one year from the start date. This preserves seasonal
        continuity for multi-year datasets.

        Returns:
            New StandardLoad instance with trimmed data.
        """
        if len(self.df) == 0:
            return self

        start = self.df.index.min()
        one_year_later = start + pd.DateOffset(years=1)
        trimmed_df = self.df[self.df.index < one_year_later].copy()

        # Check for leap day
        has_feb_29 = ((trimmed_df.index.month == 2) & (trimmed_df.index.day == 29)).any()
        expected_hours = 8784 if has_feb_29 else 8760

        logger.info(
            f"Limited data from {len(self.df)} to {len(trimmed_df)} hours "
            f"({start.strftime('%Y-%m-%d %H:%M')} to {one_year_later.strftime('%Y-%m-%d %H:%M')}), "
            f"has_feb_29={has_feb_29}, expected={expected_hours}"
        )

        if len(trimmed_df) < expected_hours:
            logger.warning(
                f"Data has fewer hours than expected: {len(trimmed_df)} < {expected_hours} "
                f"(missing {expected_hours - len(trimmed_df)} hours)"
            )

        return StandardLoad(trimmed_df.reset_index())

    def get_data_summary(self) -> dict:
        """Return summary of load data characteristics.

        Useful for displaying data quality info to users before selection.

        Returns:
            Dictionary with data characteristics including dates, hours,
            completeness, column quality stats, and any detected issues.
        """
        if len(self.df) == 0:
            return {
                "start_date": None,
                "end_date": None,
                "num_hours": 0,
                "expected_hours": 8760,
                "is_complete": False,
                "has_leap_day": False,
                "spans_multiple_years": False,
                "missing_hours": 0,
                "column_stats": {},
                "has_missing_values": False,
                "total_missing_values": 0,
            }

        expected = 8784 if self.has_leap_day else 8760

        # Check column completeness for required data columns
        data_columns = ["t_out_C", "heating_W", "cooling_W"]
        column_stats = {}
        total_missing = 0

        for col in data_columns:
            if col in self.df.columns:
                null_count = int(self.df[col].isnull().sum())
                valid_count = int(self.num_hours - null_count)
                column_stats[col] = {
                    "valid_count": valid_count,
                    "missing_count": null_count,
                    "completeness_pct": round(100 * valid_count / self.num_hours, 1)
                    if self.num_hours > 0
                    else 0,
                }
                total_missing += null_count
            else:
                column_stats[col] = {
                    "valid_count": 0,
                    "missing_count": self.num_hours,
                    "completeness_pct": 0,
                }
                total_missing += self.num_hours

        # Determine overall completeness (hours AND data values)
        hours_complete = self.num_hours >= expected
        data_complete = total_missing == 0
        is_complete = hours_complete and data_complete

        return {
            "start_date": self.df.index.min(),
            "end_date": self.df.index.max(),
            "num_hours": self.num_hours,
            "expected_hours": expected,
            "is_complete": is_complete,
            "hours_complete": hours_complete,
            "data_complete": data_complete,
            "has_leap_day": self.has_leap_day,
            "spans_multiple_years": self.spans_multiple_years,
            "missing_hours": max(0, expected - self.num_hours),
            "column_stats": column_stats,
            "has_missing_values": total_missing > 0,
            "total_missing_values": total_missing,
        }

    def compute_load_stats(self) -> dict:
        """Compute summary statistics for LoadData fields.

        Returns dict with keys matching LoadData field names.
        Used to populate LoadData for custom uploads.
        """
        df = self.df

        heating_sum = float(df["heating_W"].sum())
        cooling_sum = float(df["cooling_W"].sum())

        return {
            "hhw_max_load": float(df["heating_W"].max()),
            "chw_max_load": float(df["cooling_W"].max()),
            "hhw_annual_load": heating_sum,
            "chw_annual_load": cooling_sum,
            "annual_heating_cooling_ratio": (
                round(heating_sum / cooling_sum, 2) if cooling_sum > 0 else None
            ),
            "max_temp": float(df["t_out_C"].max()),
            "median_temp": float(df["t_out_C"].median()),
            "min_temp": float(df["t_out_C"].min()),
        }

    # --------- Accessors ---------
    def slice_year(self, year: int) -> pd.DataFrame:
        return self.df[self.df.index.year == year]

    def stats(self) -> pd.DataFrame:
        return self.df.describe()


def get_load_data(metadata: Metadata) -> StandardLoad:
    """
    Load and filter load data based on Metadata settings.

    - simulated / measured: from a single parquet, filtered by building_id + load_type
    - custom: from user-uploaded csv at metadata.custom_load_path
    """
    load_type = metadata.load_data.load_type

    if load_type in ("simulated", "measured"):
        if metadata.building_id is None:
            raise ValueError("building_id required to load simulated/measured data")

        parquet_path = paths.LOAD_DATA_PARQUET

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
            raise ValueError(f"No {load_type} load found for building_id={metadata.building_id}")

        keep = ["timestamp", "t_out_C", "heating_W", "cooling_W"]
        missing = [c for c in keep if c not in df.columns]
        if missing:
            raise ValueError(f"Missing required columns in parquet: {missing}")

        df = df[keep]

        load = StandardLoad(df)

        # Log data characteristics
        logger.info(
            f"Loaded {load_type} data: {load.num_hours} hours, "
            f"has_leap_day={load.has_leap_day}, "
            f"spans_multiple_years={load.spans_multiple_years}, "
            f"range={load.df.index.min()} to {load.df.index.max()}"
        )

        # Auto-limit measured data to one year if it spans multiple years
        if load_type == "measured" and load.spans_multiple_years:
            logger.warning(
                f"Measured data spans multiple years "
                f"({load.df.index.min()} to {load.df.index.max()}), "
                f"limiting to first year"
            )
            load = load.limit_to_one_year()

        return load

    elif load_type == "custom":
        if not metadata.custom_load_path:
            raise ValueError("custom_load_path required for load_type='custom'")

        load = StandardLoad.from_parquet(metadata.custom_load_path)

        # Log data characteristics
        logger.info(
            f"Loaded {load_type} data: {load.num_hours} hours, "
            f"has_leap_day={load.has_leap_day}, "
            f"spans_multiple_years={load.spans_multiple_years}, "
            f"range={load.df.index.min()} to {load.df.index.max()}"
        )

        return load

    else:
        raise NotImplementedError(f"Unsupported load type: {load_type!r}")
