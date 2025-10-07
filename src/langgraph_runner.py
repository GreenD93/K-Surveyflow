from langgraph.graph import StateGraph, END

import asyncio
import pandas as pd

from src.constants import *
from src.core.state import GraphState
from src.core.classify import category_level1_async, category_level2_async, sentiment_and_keywords_async
    
# ---- 래퍼 노드들 (상태 키 충돌 방지 & 의존성 주입) -----------------

# L1: L1 결과만 반환
async def n_level1(state: GraphState):
    s = await category_level1_async(dict(state))
    l1 = s.get('batch_results', [])
    return {'l1_results': l1}  # ← 변경된 키만!

# L2: L1결과를 입력으로 쓰되, 반환은 L2 결과만
async def n_level2(state: GraphState):
    tmp = dict(state)
    tmp['batch_results'] = state.get('l1_results', [])
    s2 = await category_level2_async(tmp)
    return {'l2_results': s2.get('batch_results', [])}

# 감정: L1결과만 참조, 반환은 감정 결과만
async def n_sentiment(state: GraphState):
    tmp = dict(state)
    tmp['batch_results'] = state.get('l1_results', [])
    s2 = await sentiment_and_keywords_async(tmp)
    return {'sent_results': s2.get('batch_results', [])}

# merge: 최종 CSV용 결과만
async def n_merge(state: GraphState):
    import pandas as pd
    df_l2 = pd.DataFrame(state.get('l2_results', []))
    df_sk = pd.DataFrame(state.get('sent_results', []))

    if df_l2.empty and not df_sk.empty:
        out = df_sk
    elif not df_l2.empty and df_sk.empty:
        out = df_l2
    elif df_l2.empty and df_sk.empty:
        out = pd.DataFrame()
    else:
        # 공통키 있으면 그걸로 머지 (예: 'answ_id'); 없으면 인덱스 병합
        key = 'answ_id' if {'answ_id'} <= set(df_l2.columns) and {'answ_id'} <= set(df_sk.columns) else None
        if key:
            out = df_l2.merge(df_sk[[c for c in df_sk.columns if c != key]], on=key, how='left')
        else:
            out = pd.concat(
                [df_l2.reset_index(drop=True),
                 df_sk[['sentiment','keywords','summary']].reset_index(drop=True)],
                axis=1
            )

    return {'batch_results': out.to_dict(orient='records')}

# ---- 그래프 정의 -----------------------------------------------------

def define_workflow():
    g = StateGraph(GraphState)
    g.add_node('level1', n_level1)
    g.add_node('level2', n_level2)
    g.add_node('sentiment', n_sentiment)
    g.add_node('merge', n_merge)

    g.set_entry_point('level1')
    g.add_edge('level1', 'level2')      # L1 → L2
    g.add_edge('level1', 'sentiment')   # L1 → 감정
    g.add_edge('level2', 'merge')       # fan-in
    g.add_edge('sentiment', 'merge')
    g.add_edge('merge', END)
    return g.compile()

def run_langgraph(workflow, state):

    # 그래프 실행

    if USE_ASYNC_CLASSIFY or USE_ASYNC_ENRICH:
        loop = asyncio.get_event_loop()
        result = loop.run_until_complete(workflow.ainvoke(state))
    else:
        result = workflow.invoke(state)
    
    return result