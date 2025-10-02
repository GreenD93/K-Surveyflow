from langgraph.graph import StateGraph, END

import asyncio
import pandas as pd

from src.constants import *
from src.core.state import GraphState
from src.core.classify import category_level1_async, category_level2_async, sentiment_and_keywords_async
    
def define_workflow():

    workflow = StateGraph(GraphState)
    workflow.add_node('category_level1', category_level1_async)
    workflow.add_node('classify_level2', category_level2_async)
    workflow.add_node('sentiment_and_keywords', sentiment_and_keywords_async)

    workflow.set_entry_point('category_level1')
    workflow.add_edge('category_level1', 'classify_level2')
    workflow.add_edge('classify_level2', 'sentiment_and_keywords')
    workflow.add_edge('sentiment_and_keywords', END)

    graph_app = workflow.compile()

    return graph_app

def run_langgraph(workflow, item, l2m_cate):

    surv_id = item["surv_id"]
    qsit_sqn = item["qsit_sqn"]
    main_ttl = item["main_ttl"]
    qsit_ttl = item["qsit_ttl"]
    filtered_surv_answ = item["filtered_surv_answ"]
    level2_map = l2m_cate
    surv_cate_list = list(level2_map.keys())

    # 상태 구성
    state: GraphState = {
        "surv_id": str(surv_id),
        "qsit_sqn": int(qsit_sqn),
        "main_ttl": main_ttl,
        "qsit_ttl": qsit_ttl,
        "response": "",
        "surv_cate": surv_cate_list,  
        "surv_answ": filtered_surv_answ,  
        "batch_results": [],
        "level2_map": level2_map,  
    }

    # 그래프 실행

    if USE_ASYNC_CLASSIFY or USE_ASYNC_ENRICH:
        loop = asyncio.get_event_loop()
        result = loop.run_until_complete(workflow.ainvoke(state))
    else:
        result = workflow.invoke(state)
    
    return result

def main():

    workflow = define_workflow()
    result = run_langgraph(workflow, item, l2m_cate)

    # 분류 결과 저장
    survey_classify_mart = result.get('batch_results', [])

    if survey_classify_mart:

        df_cls = pd.DataFrame(
            survey_classify_mart,
            columns=['surv_date', 'surv_id', 'main_ttl', 'qsit_ttl', 'qsit_sqn', 'cust_id', 'answ_id', 'answ_cntnt', 'category_level1', 'category_level2', 'sentiment', 'keywords', 'summary']
        )

        df_cls["qsit_sqn"] = df_cls["qsit_sqn"].astype(int)
        path = "survey_classify_mart.parquet"
        df_cls.to_parquet(path, index=False, engine="pyarrow")

        print(" - 분류 업로드 완료")