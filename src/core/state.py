import pandas as pd
from typing import List, TypedDict

class GraphState(TypedDict):
    surv_id: str
    qsit_sqn: int
    main_ttl: str
    qsit_ttl: str
    response: str
    surv_cate: List[str]
    surv_answ: pd.DataFrame
    batch_results: List[dict]
    level2_map: dict[str, List[str]]  # 추가된 필드