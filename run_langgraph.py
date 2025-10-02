import os
from typing import Optional
import pandas as pd

import argparse

from src.load_data import load_data
from src.langgraph_runner import *
from src.constants import *

def main():

    parser = argparse.ArgumentParser()
    parser.add_argument("--survey_info_file", default="data/isb_surv_rpt_info.csv")
    parser.add_argument("--raw_data_file", default="data/20250916_raw_data.csv")
    args = parser.parse_args()

    survey_info_path: Optional[str] = args.survey_info_file
    raw_data_file: Optional[str] = args.raw_data_file

    survey_info_df = load_data(survey_info_path)
    raw_df = pd.read_csv(
        raw_data_file,
        dtype={
            "surv_id": str,
            "qsit_type_ds_cd": str,
            "text_yn": str,
            "surv_date": str,
        },
    ).fillna("")

    print(survey_info_df)

    # 확인 : 발송여부, 발송주기코드. 


if __name__ == "__main__":
    main()