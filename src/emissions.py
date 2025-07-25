import pandas as pd


def load_cambium_data(file_path, emissions_scenario: dict) -> pd.DataFrame:
    """
    Load and filter Cambium data based on emissions_scenario dictionary.

    Parameters:
    - file_path (str): Path to the Cambium CSV file (multi-scenario).
    - emissions_scenario (dict): Metadata used to filter the relevant scenario. Keys:
        - 'grid_region': e.g., 'CAISO'
        - 'grid_scenario': e.g., 'MidCase'
        - 'grid_year': e.g., 2040
        - 'emissions_type': 'Combustion only' or 'Includes pre-combustion'

    Returns:
    - pd.DataFrame with columns:
        ['grid_region', 'grid_scenario', 'grid_year', 'month', 'hour',
        'lrmer_co2e_c', 'lrmer_co2e_p', 'srmer_co2e_c', 'srmer_co2e_p']
    """
    # --- Step 1: Load file (skip metadata rows if needed) ---
    df = pd.read_csv(file_path)

    # --- Step 2: Filter by emissions_scenario ---
    scenario = emissions_scenario["grid_scenario"]
    region = emissions_scenario["grid_region"]
    year = emissions_scenario["grid_year"]

    df_filtered = df[
        (df["scenario"] == scenario) & (df["gea"] == region) & (df["t"] == year)
    ].copy()

    # --- Step 3: Select emissions type ---
    if emissions_scenario["emissions_type"] == "Combustion only":
        lrmer_c = "lrmer_co2e_c"
        lrmer_p = "lrmer_co2e_p"
        srmer_c = "srmer_co2e_c"
        srmer_p = "srmer_co2e_p"
    elif emissions_scenario["emissions_type"] == "Includes pre-combustion":
        lrmer_c = "lrmer_co2e"
        lrmer_p = "lrmer_co2e"
        srmer_c = "srmer_co2e"
        srmer_p = "srmer_co2e"
    else:
        raise ValueError(
            "Invalid emissions_type. Choose 'Combustion only' or 'Includes pre-combustion'."
        )

    # --- Step 4: Timestamp processing ---
    df_filtered["datetime"] = pd.to_datetime(
        df_filtered["timestamp_local"], format="%m/%d/%y %H:%M", errors="coerce"
    )

    # --- Step 5: Assemble result ---
    result = pd.DataFrame(
        {
            "grid_region": region,
            "grid_scenario": scenario,
            "grid_year": year,
            "datetime": df_filtered["datetime"].astype("datetime64[ns]"),
            "lrmer_co2e_c": df_filtered[lrmer_c],
            "lrmer_co2e_p": df_filtered[lrmer_p],
            "srmer_co2e_c": df_filtered[srmer_c],
            "srmer_co2e_p": df_filtered[srmer_p],
        }
    )

    result.set_index("datetime", inplace=True)

    return result
