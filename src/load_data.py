import pandas as pd

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