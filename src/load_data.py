import pandas as pd


def load_data(data_path):

    # "data/isb_surv_rpt_info.csv"
    df = pd.read_csv(data_path)
    df = df.astype(str)

    grouped = df.groupby("SURV_ID").agg({
        'EMPNO': lambda x: list(x),
        'EMAIL': lambda x: list(x),
        'SNDG_YN': 'first',
        'SNDG_START_DT': 'first',
        'SNDG_END_DT': 'first',
        'SNDG_CTCL_CD': 'first',
        'DTWK_CD': 'first',
        'DAY_CD': 'first',
        'DATA_RNG_CD': 'first',
        'FRST_RGST_USER_ID': 'first',
        'FRST_RGST_DTTM': 'first',
        'LAST_CHNG_USER_ID': 'first',
        'LAST_CHNG_DTTM': 'first'
    }).reset_index()

    return grouped

def load_category_map(category_file):

    # "data/category.csv"
    df = pd.read_csv(category_file)

    tmp = (
        df.dropna(subset=['l_cate', 'm_cate'])      # NULL 제거
        .assign(
            l_cate=lambda d: d['l_cate'].astype(str).str.strip(),
            m_cate=lambda d: d['m_cate'].astype(str).str.strip(),
        )
    )

    category_map = (
        tmp.groupby('l_cate')['m_cate']
        .apply(lambda s: sorted(set(s.tolist())))  # 중복 제거 + 정렬
        .to_dict()
    )

    return category_map