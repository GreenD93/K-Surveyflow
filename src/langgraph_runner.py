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

def run_langgraph(workflow, state):

    # 그래프 실행

    if USE_ASYNC_CLASSIFY or USE_ASYNC_ENRICH:
        loop = asyncio.get_event_loop()
        result = loop.run_until_complete(workflow.ainvoke(state))
    else:
        result = workflow.invoke(state)
    
    return result