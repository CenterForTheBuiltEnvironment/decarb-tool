"""Centralized file path configuration."""

from pathlib import Path

# Base data directory
DATA_DIR = Path("data/input")

# Data file paths
LOCATIONS_CSV = DATA_DIR / "locations.csv"
BUILDING_METADATA_CSV = DATA_DIR / "building_metadata.csv"
LOAD_DATA_PARQUET = DATA_DIR / "load_data_full.parquet"
EMISSION_DATA_PARQUET = DATA_DIR / "emission_data.parquet"
EQUIPMENT_JSON = DATA_DIR / "equipment_data.JSON"
METADATA_INDEX_JSON = DATA_DIR / "metadata_index.json"
