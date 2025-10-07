from langchain import PromptTemplate
from langchain_core.output_parsers import StrOutputParser

import re
import asyncio
import difflib
import pandas as pd

from src.core.state import GraphState
from src.core.prompt import *
from src.constants import *

from langchain.chat_models import ChatOpenAI

# =========================
# LLM & Parser
# =========================

llm = ChatOpenAI(
    model="gpt-4o",
    temperature=0,
    model_kwargs={"top_p": 1},
    openai_api_key=OPENAI_KEY
)

parser = StrOutputParser()

# # Solar -> OpenAI
# llm = SolarLangChainLLM(
#     model="solar-pro-finance",
#     temperature=0,
#     top_p=1
# )

# =========================

def _normalize_label(s: str) -> str:
    if s is None:
        return ""
    s = re.sub(r"\s+", " ", str(s).strip().lower())
    return s

def best_match_level(new_cate: str, surv_cate_list: list[str], threshold: float = 0.5):
    if not new_cate or not surv_cate_list:
        return None, 0.0
    new_norm = _normalize_label(new_cate)
    best, best_score = None, 0.0
    for ex in surv_cate_list:
        score = difflib.SequenceMatcher(None, new_norm, _normalize_label(ex)).ratio()
        if score > best_score:
            best, best_score = ex, score
    if best_score >= threshold:
        return best, best_score
    return None, best_score

async def category_level1_async(state: GraphState):
    categories = state.get('surv_cate', [])
    surv_answ = state.get('surv_answ', pd.DataFrame())
    results = []
    batch_size = 1
    n = len(surv_answ)

    prompt = PromptTemplate(
        input_variables=["main_ttl", "qsit_ttl", "categories", "answ_list"],
        template=CATEGORY_CLASSIFICATION_PROMPT
    )
    chain = prompt | llm | parser

    batches = []
    for batch_start in range(0, n, batch_size):
        batch = surv_answ.iloc[batch_start:batch_start + batch_size].copy()
        answ_list_str = "\n".join([f"{i+1} Q: {row['answ_cntnt']}" for i, row in batch.iterrows()])
        input_vars = {
            "categories": ', '.join(categories) if categories else "기타 피드백",
            "answ_list": answ_list_str,
            "qsit_ttl": state.get('qsit_ttl', ''),
            "main_ttl": state.get('main_ttl', '')
        }
        batches.append((batch.index.tolist(), input_vars, categories))

    sem = asyncio.Semaphore(ASYNC_CONCURRENCY)
    lock = asyncio.Lock()

    async def run_one(idx_list, input_vars, categories):
        async with sem:
            response = await chain.ainvoke(input_vars)
            parsed_lines = [line for line in response.split('\n') if '분류:' in line]
            batch_results = []
            for i, idx in enumerate(idx_list):
                raw_cat = parsed_lines[i].split('분류:')[-1].strip() if i < len(parsed_lines) else None
                canon_cat, score = best_match_level(raw_cat, categories, threshold=0.5) if categories else (None, 0.0)
                if canon_cat is None:
                    canon_cat = "기타 피드백"
                batch_results.append({
                    **{col: surv_answ.at[idx, col] for col in surv_answ.columns if col in surv_answ},
                    'category_level1_raw': raw_cat,
                    'category_level1': canon_cat
                })
            async with lock:
                results.extend(batch_results)

    await asyncio.gather(*(run_one(idxs, inp, cats) for idxs, inp, cats in batches))
    state['batch_results'] = results
    return state

async def category_level2_async(state: GraphState):
    surv_answ = state.get('surv_answ', pd.DataFrame())
    base_results = state.get('batch_results', [])
    results = []
    batch_size = 1

    level2_map = state.get('level2_map', {})  # state에서 level2_map 가져오기

    if not base_results:
        return state

    prompt = PromptTemplate(
        input_variables=["main_ttl", "qsit_ttl", "categories", "answ_list"],
        template=CATEGORY_CLASSIFICATION_PROMPT
    )
    chain = prompt | llm | parser

    def fetch_level2_list(level1_value: str) -> list[str]:
        try:
            l1 = str(level1_value).strip()
            return level2_map.get(l1, [])
        except Exception as e:
            print(f"[L2] category_level2 조회 실패: L1='{level1_value}', err={e}")
            return []

    groups = {}
    for i, row in enumerate(base_results):
        l1_value = row.get("category_level1", "기타 피드백")
        groups.setdefault(l1_value, []).append(i)

    sem = asyncio.Semaphore(ASYNC_CONCURRENCY)
    lock = asyncio.Lock()
    tasks = []

    async def run_group(l1_value: str, idxs: list[int]):
        categories = fetch_level2_list(l1_value)
        if not categories:
            async with lock:
                for idx in idxs:
                    base_results[idx]["category_level2_raw"] = None
                    base_results[idx]["category_level2"] = "기타 피드백"
                    results.append(base_results[idx])
            return

        for batch_start in range(0, len(idxs), batch_size):
            batch_idxs = idxs[batch_start:batch_start + batch_size]
            answ_list_str = "\n".join([f"{i+1} Q: {base_results[idx].get('answ_cntnt','')}" for i, idx in enumerate(batch_idxs)])
            input_vars = {
                "categories": ', '.join(categories),
                "answ_list": answ_list_str,
                "qsit_ttl": state.get('qsit_ttl', ''),
                "main_ttl": state.get('main_ttl', '')
            }

            async with sem:
                resp = await chain.ainvoke(input_vars)
                parsed_lines = [ln for ln in str(resp).splitlines() if '분류:' in ln]
                parsed = [ln.split('분류:')[-1].strip() for ln in parsed_lines]

                updates = []
                for off, idx in enumerate(batch_idxs):
                    raw_cat = parsed[off] if off < len(parsed) else None
                    canon_cat, score = best_match_level(raw_cat, categories, threshold=0.5)
                    if canon_cat is None:
                        canon_cat = "기타 피드백"
                    updates.append((idx, raw_cat, canon_cat))

                async with lock:
                    for idx, raw, canon in updates:
                        base_results[idx]["category_level2_raw"] = raw
                        base_results[idx]["category_level2"] = canon
                        results.append(base_results[idx])

    for l1, idxs in groups.items():
        tasks.append(run_group(l1, idxs))

    await asyncio.gather(*tasks)

    state['batch_results'] = results
    return state


async def sentiment_and_keywords_async(state: GraphState):

    surv_answ = state.get('surv_answ', pd.DataFrame())
    base_results = state.get('batch_results', [])

    sentiment_chain = PromptTemplate(
        input_variables=["answer"],
        template=SENTIMENT_CLASSIFICATION_PROMPT
    ) | llm | parser

    keyword_chain = PromptTemplate(
        input_variables=["answer"],
        template=KEYWORD_EXTRACTION_PROMPT
    ) | llm | parser

    summary_chain = PromptTemplate(
        input_variables=["answer"],
        template=SUMMARY_PROMPT
    ) | llm | parser

    results = []
    batch_size = 1
    n = len(base_results)

    batches = []
    for batch_start in range(0, n, batch_size):
        batch_end = min(batch_start + batch_size, n)
        idx_list = list(range(batch_start, batch_end))
        batches.append((batch_start, idx_list))

    sem = asyncio.Semaphore(ASYNC_CONCURRENCY)
    lock = asyncio.Lock()

    def parse_sentiment(text: str) -> str | None:
        if not text:
            return None
        if '-> 분류:' in text:
            return text.split('-> 분류:')[-1].strip()
        if '분류:' in text:
            return text.split('분류:')[-1].strip()
        return text.strip() or None

    def parse_keywords(text: str) -> str | None:
        if not text:
            return None
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        toks = []
        for ln in lines:
            if ':' in ln:
                head, tail = ln.split(':', 1)
                if any(h in head for h in ['키워드', 'keywords', 'Keywords']):
                    ln = tail.strip()
            ln = ln.lstrip("-•*·").strip()
            parts = [p.strip() for p in re.split(r'[,\u3001;/·、]', ln) if p.strip()]
            toks.extend(parts if parts else [ln])
        seen, dedup = set(), []
        for t in toks:
            if t and t not in seen:
                seen.add(t)
                dedup.append(t)
        return ", ".join(dedup) if dedup else None    

    async def run_one(batch_start, idx_list):
        async with sem:
            batch_no = (batch_start // batch_size) + 1
            batch_results = []
            for i in idx_list:
                base = base_results[i]
                ans = base.get('answ_cntnt')
                if ans is None and i < len(surv_answ):
                    ans = surv_answ.iloc[i]['answ_cntnt']

                if ans is None or not str(ans).strip():
                    s_val, k_val, sum_val = None, None, None
                else:
                    s_raw = await sentiment_chain.ainvoke({"answer": ans})
                    await asyncio.sleep(0.5)
                    k_raw = await keyword_chain.ainvoke({"answer": ans})
                    await asyncio.sleep(0.5)
                    sum_raw = await summary_chain.ainvoke({"answer": ans}) 
                    await asyncio.sleep(0.5)

                    s_val = parse_sentiment(s_raw)
                    k_val = parse_keywords(k_raw)
                    sum_val = str(sum_raw).strip() or None

                row = {
                    **base,
                    "sentiment": s_val,
                    "keywords": k_val,
                    "summary": sum_val
                }
                batch_results.append(row)

            async with lock:
                results.extend(batch_results)

    await asyncio.gather(*(run_one(bs, idxs) for bs, idxs in batches))
    state['batch_results'] = results
    return state