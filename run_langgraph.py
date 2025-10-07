from datetime import datetime
from typing import Optional
import pandas as pd

import argparse

from src.core.state import GraphState
from src.load_data import load_data, load_category_map
from src.langgraph_runner import define_workflow, run_langgraph
from src.constants import *

from src.utils import _get_timezone, _parse_input_datetime

# 오늘(서울) 날짜가 종료일 '이전 또는 같은 날'이면 True
def should_run_until(inclusive_end_str: str) -> bool:
    now_kr = datetime.now(_get_timezone())
    end_dt = _parse_input_datetime(inclusive_end_str)
    # 요구사항대로 '일 단위'로 비교 (시각 무시)
    return now_kr.date() <= end_dt.date()

def main():

    parser = argparse.ArgumentParser()
    parser.add_argument("--survey_info_file", default="data/isb_surv_rpt_info.csv")
    parser.add_argument("--raw_data_file", default="data/20250916_raw_data.csv")
    parser.add_argument("--category_file", default="data/category.csv")

    args = parser.parse_args()

    survey_info_path: Optional[str] = args.survey_info_file
    raw_data_file: Optional[str] = args.raw_data_file
    category_file: Optional[str] = args.category_file

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

    l2m_cate = load_category_map(category_file)
    surv_cate_list = sorted(l2m_cate.keys())

    items = survey_info_df.to_dict("records")

    # langgraph workflow
    workflow = define_workflow()

    for item in items:

        # 확인 : 발송여부, 발송주기코드.
        surv_id = item['SURV_ID']
        sndg_yn = item['SNDG_YN'] # 발송 여부
        sndg_end_dt = item['SNDG_END_DT'] # 종료 일자

        # check logic
        if not should_run_until(sndg_end_dt) and sndg_yn != "Y":
            continue

        # surv_id에 해당하는 설문 응답 가져오기
        surv_answ = raw_df[raw_df['surv_id'] == surv_id]
        qsit_sqns = surv_answ['qsit_sqn'].unique()
        qsit_sqns = sorted(qsit_sqns)

        for qsit_sqn in qsit_sqns:

            # surv_id & qsit_sqn에 해당하는 설문 응답 가져오기
            filtered_surv_answ = surv_answ[surv_answ['qsit_sqn'] == qsit_sqn]
            filtered_surv_answ = filtered_surv_answ[:20] # test sample

            if len(filtered_surv_answ) == 0:
                continue

            main_ttl = filtered_surv_answ['main_ttl'].iloc[0]
            qsit_ttl = filtered_surv_answ['qsit_ttl'].iloc[0]

            state: GraphState = {
                "surv_id": str(surv_id),
                "qsit_sqn": int(qsit_sqn),
                "main_ttl": main_ttl,
                "qsit_ttl": qsit_ttl,
                "response": "",
                "surv_cate": surv_cate_list,  
                "surv_answ": filtered_surv_answ,  
                "batch_results": [],
                "level2_map": l2m_cate
            }
            
            result = run_langgraph(workflow, state)

            # result -> category_level1, category_level2, sentiment, keywords, summary

            survey_classify_mart = result.get('batch_results', [])
            df_cls = pd.DataFrame(
                survey_classify_mart,
                columns=['surv_date', 'surv_id', 'main_ttl', 'qsit_ttl', 'qsit_sqn', 'cust_id', 'answ_id', 'answ_cntnt', 'category_level1', 'category_level2', 'sentiment', 'keywords', 'summary']
            )
            df_cls["qsit_sqn"] = df_cls["qsit_sqn"].astype(int)

            df_cls.to_csv("result.csv", index=False)

            break

if __name__ == "__main__":
    main()