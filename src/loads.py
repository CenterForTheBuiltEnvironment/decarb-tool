import pandas as pd


def get_simulation_data(file_path: str) -> pd.DataFrame:
    """
    Load and preprocess simulation results from a CSV file.

    Returns:
        pd.DataFrame: DataFrame with datetime index and cleaned columns.
    """
    # Load the simulation results
    simulation_results = pd.read_csv(file_path)

    # Clean the timestamp column
    simulation_results["timestamp_clean"] = (
        simulation_results["timestamp"].str.strip().str.replace(r"\s+", " ", regex=True)
    )

    # Convert to datetime
    simulation_results["datetime"] = pd.to_datetime(
        "2040/" + simulation_results["timestamp_clean"],
        format="%Y/%m/%d %H:%M:%S",
        errors="coerce",
    )

    # Set datetime as index and drop unnecessary columns
    simulation_results.set_index("datetime", inplace=True)
    simulation_results.drop(columns=["timestamp", "timestamp_clean"], inplace=True)

    return simulation_results
