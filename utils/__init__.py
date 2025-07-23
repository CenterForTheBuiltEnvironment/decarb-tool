import numpy as np
import pandas as pd
from utils.interp import interp1_zero


def loads_to_site_energy(
    equip_scenario: pd.Series, df: pd.DataFrame, detail: bool = True
) -> pd.DataFrame:
    """
    Convert heating/cooling loads into site energy consumption based on equipment scenario.
    """
    s = equip_scenario.copy()

    df = df.copy()

    # Initialize new columns
    df = df.assign(
        hhw_remainder=df["hhw"],
        chw_remainder=df["chw"],
        hr_hhw=np.nan,
        hr_chw=np.nan,
        simult_h=np.nan,
        hr_cop_h=np.nan,
        awhp_num=np.nan,
        awhp_hhw=np.nan,
        awhp_cop_h=np.nan,
        awhp_cap_h=np.nan,
        elec=0.0,
        elec_hr=np.nan,
        elec_awhp_h=np.nan,
        elec_awhp_c=np.nan,
        elec_res=np.nan,
        gas=0.0,
    )

    # More logic will be added in later steps...
    return df
