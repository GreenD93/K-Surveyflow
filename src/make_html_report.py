import pandas as pd
import re

# ============================================================
# 🧩 [공통] 데이터 불러오기
# ============================================================
def load_data(filepath: str) -> pd.DataFrame:
    """CSV 파일 불러오기 및 기본 전처리"""
    df = pd.read_csv(filepath, sep=",", low_memory=False)
    for col in ["main_ttl", "qsit_ttl", "category_level1", "category_level2", "sentiment", "summary", "keywords"]:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip()
    return df


# ============================================================
# 🧩 [DATA1] 카테고리별 감정 요약 생성
# ============================================================
def create_data1(df: pd.DataFrame, main_ttl: str, qsit_ttl: str) -> pd.DataFrame:
    """카테고리별 감정요약 data1 생성"""
    filtered = df[
        (df["text_yn"] == 1) &
        (df["main_ttl"] == main_ttl) &
        (df["qsit_ttl"] == qsit_ttl) &
        (~df["category_level2"].isin([
            '단순 칭찬/불만', '욕설·무관한 피드백', '개선 의사 없음 (“없습니다”)'
        ]))
    ]

    grouped = (
        filtered
        .groupby(["category_level1", "category_level2"], dropna=False)
        .agg(
            응답건수=("sentiment", "count"),
            긍정건수=("sentiment", lambda x: (x == "긍정").sum()),
            부정건수=("sentiment", lambda x: (x == "부정").sum()),
            중립건수=("sentiment", lambda x: (x == "중립").sum())
        )
        .reset_index()
    )

    grouped["카테고리"] = grouped["category_level1"].fillna('') + ">" + grouped["category_level2"].fillna('')
    grouped = grouped.sort_values("응답건수", ascending=False).reset_index(drop=True)
    grouped["rnk"] = grouped.index + 1

    grouped["긍정비중"] = (grouped["긍정건수"] / grouped["응답건수"] * 100).round().astype(int).astype(str) + "%"
    grouped["부정비중"] = (grouped["부정건수"] / grouped["응답건수"] * 100).round().astype(int).astype(str) + "%"
    grouped["중립비중"] = (grouped["중립건수"] / grouped["응답건수"] * 100).round().astype(int).astype(str) + "%"

    data1 = grouped[[
        "rnk", "카테고리", "응답건수", "긍정건수", "부정건수", "중립건수",
        "긍정비중", "부정비중", "중립비중"
    ]].head(10)
    return data1


# ============================================================
# 🧩 [DATA2] 감정별 요약 데이터 생성
# ============================================================
def create_data2(df: pd.DataFrame, main_ttl: str, qsit_ttl: str) -> pd.DataFrame:
    """감정별 요약문 + 키워드분석 + keyword_hit_cnt 기반 랭킹"""
    filtered = df[
        (df["text_yn"] == 1) &
        (df["main_ttl"] == main_ttl) &
        (df["qsit_ttl"] == qsit_ttl) &
        (~df["category_level2"].isin([
            '단순 칭찬/불만', '욕설·무관한 피드백', '개선 의사 없음 (“없습니다”)'
        ]))
    ].copy()

    # ============================================================
    # 🧩 ① 상위 10개 카테고리 선정
    # ============================================================
    cat_rank = (
        filtered.groupby(["category_level1", "category_level2"])
        .size()
        .reset_index(name="cnt")
        .sort_values("cnt", ascending=False)
    )
    cat_rank["rnk_cat"] = cat_rank.index + 1
    top10 = cat_rank.head(10)
    top10["카테고리"] = top10["category_level1"].fillna('') + ">" + top10["category_level2"].fillna('')

    # ============================================================
    # 🧩 ② 키워드 분리 및 집계
    # ============================================================
    def split_keywords(k):
        if pd.isna(k): 
            return []
        return [p.strip() for p in str(k).split(",") if p.strip()][:3]

    kw_rows = []
    for _, row in filtered.iterrows():
        for kw in split_keywords(row["keywords"]):
            kw_rows.append([
                row["category_level1"], row["category_level2"],
                row["sentiment"], kw
            ])

    kw_count = (
        pd.DataFrame(kw_rows, columns=["category_level1","category_level2","sentiment","keyword"])
        .groupby(["category_level1","category_level2","sentiment","keyword"])
        .size()
        .reset_index(name="cnt")
    )

    # 감정별 상위 5개 키워드
    kw_count = (
        kw_count.sort_values(["category_level1","category_level2","sentiment","cnt"], ascending=[True,True,True,False])
        .groupby(["category_level1","category_level2","sentiment"])
        .head(5)
        .reset_index(drop=True)
    )

    # keyword_anal 문자열 (빈도 내림차순)
    kw_anal = (
        kw_count
        .sort_values(["category_level1","category_level2","sentiment","cnt"], ascending=[True,True,True,False])
        .groupby(["category_level1","category_level2","sentiment"])
        .apply(lambda x: ", ".join(f"{k}({c})" for k, c in zip(x["keyword"], x["cnt"])))
        .reset_index(name="keyword_anal")
    )

    # ✅ (추가 ①) 동일 카테고리·감정 조합 중복 제거
    kw_anal = kw_anal.drop_duplicates(subset=["category_level1","category_level2","sentiment"])

    # ============================================================
    # 🧩 ③ 요약문 + 원문 + keyword_anal 병합
    # ============================================================
    data = filtered.copy()
    data["카테고리"] = data["category_level1"].fillna('') + ">" + data["category_level2"].fillna('')
    kw_anal["카테고리"] = kw_anal["category_level1"].fillna('') + ">" + kw_anal["category_level2"].fillna('')

    data = data.merge(
        kw_anal[["카테고리","sentiment","keyword_anal"]],
        on=["카테고리","sentiment"], how="left"
    )

    data = data.drop_duplicates(subset=["카테고리","sentiment","summary","answ_cntnt"])

    # ============================================================
    # 🧩 ④ keyword_hit_cnt 계산
    # ============================================================
    def count_keyword_hits(row):
        if pd.isna(row["answ_cntnt"]) or pd.isna(row["keyword_anal"]):
            return 0
        keywords = [re.sub(r"\(.*\)", "", k.strip()) for k in row["keyword_anal"].split(",")]
        text = str(row["answ_cntnt"])
        return sum(1 for k in keywords if k and k in text)

    data["keyword_hit_cnt"] = data.apply(count_keyword_hits, axis=1)
    data["문장길이"] = data["summary"].fillna("").apply(len)

    # ============================================================
    # 🧩 ⑤ 감정별 랭킹 계산
    # ============================================================
    data["rnk"] = (
        data.sort_values(["카테고리","sentiment","keyword_hit_cnt","문장길이"], ascending=[True,True,False,False])
        .groupby(["카테고리","sentiment"])
        .cumcount() + 1
    )

    # 감정별 상위 제한 (긍/부 3, 중립 2)
    data = data[
        ((data["sentiment"].isin(["긍정","부정"])) & (data["rnk"] <= 3)) |
        ((data["sentiment"] == "중립") & (data["rnk"] <= 2))
    ].copy()

    # ============================================================
    # 🧩 ⑥ 최종 정리
    # ============================================================
    data2 = data[
        ["rnk","카테고리","sentiment","summary","keyword_anal","answ_cntnt","keyword_hit_cnt"]
    ].rename(columns={
        "sentiment":"감정분석",
        "summary":"요약"
    })

    data2 = data2[data2["카테고리"].isin(top10["카테고리"])].reset_index(drop=True)
    data2 = data2.sort_values(["카테고리","감정분석","rnk"]).reset_index(drop=True)
    
    return data2
    
# ============================================================
# 🧩 [HTML 리포트 생성]
# ============================================================
def make_html_report(data1, data2):
    """카테고리별 감정분석 + 주요 키워드 HTML 리포트 (인라인 스타일 버전)"""
    html = """
<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<title>카테고리별 주요 키워드 리포트</title>
</head>
<body style="font-family:-apple-system,BlinkMacSystemFont,Segoe UI,Roboto,'Noto Sans KR',sans-serif;color:#111827;font-size:13px;margin:20px;">
<h2 style="font-size:18px;font-weight:700;margin-bottom:12px;">카테고리별 주요 키워드 리포트</h2>

<table style="width:100%;border-collapse:collapse;border:1px solid #E5E7EB;">
  <thead>
    <tr>
      <th style="background:#F3F4F6;color:#374151;font-size:12px;padding:8px;border:1px solid #E5E7EB;width:260px;">카테고리</th>
      <th style="background:#F3F4F6;color:#374151;font-size:12px;padding:8px;border:1px solid #E5E7EB;width:180px;">감정분석</th>
      <th style="background:#F3F4F6;color:#374151;font-size:12px;padding:8px;border:1px solid #E5E7EB;">주요 키워드</th>
    </tr>
  </thead>
  <tbody>
"""

    # 행별로 데이터 구성
    for _, row in data1.iterrows():
        cat = row["카테고리"]
        resp = row["응답건수"]
        pos_cnt, neg_cnt, neu_cnt = row["긍정건수"], row["부정건수"], row["중립건수"]
        pos_pct, neg_pct, neu_pct = row["긍정비중"], row["부정비중"], row["중립비중"]

        subset = data2[data2["카테고리"] == cat]
        pos_summary = subset[subset["감정분석"] == "긍정"]["요약"].head(3).tolist()
        neg_summary = subset[subset["감정분석"] == "부정"]["요약"].head(3).tolist()
        neu_summary = subset[subset["감정분석"] == "중립"]["요약"].head(2).tolist()

        html += f"""
    <tr>
      <td style="border:1px solid #E5E7EB;padding:8px;vertical-align:top;font-weight:700;font-size:12px;width:260px;">
        {cat} <span style="color:#6B7280;font-size:11px;">({resp}건)</span>
      </td>
      <td style="border:1px solid #E5E7EB;padding:8px;vertical-align:top;width:180px;">
        <div style="margin-bottom:4px;height:12px;background:#E5E7EB;border-radius:4px;overflow:hidden;">
          <div style="width:{pos_pct};background:#324AFB;height:100%;"></div>
        </div>
        <div style="font-size:11px;margin-bottom:3px;">긍정 {pos_pct}</div>
        <div style="margin-bottom:4px;height:12px;background:#E5E7EB;border-radius:4px;overflow:hidden;">
          <div style="width:{neg_pct};background:#EF4444;height:100%;"></div>
        </div>
        <div style="font-size:11px;margin-bottom:3px;">부정 {neg_pct}</div>
        <div style="margin-bottom:4px;height:12px;background:#E5E7EB;border-radius:4px;overflow:hidden;">
          <div style="width:{neu_pct};background:#9CA3AF;height:100%;"></div>
        </div>
        <div style="font-size:11px;">중립 {neu_pct}</div>
      </td>
      <td style="border:1px solid #E5E7EB;padding:8px;vertical-align:top;font-size:11px;line-height:1.3;">
        <div style="background:#E8EDFF;color:#2539E9;font-weight:700;border-radius:4px;padding:2px 6px;margin-bottom:3px;display:inline-block;">긍정 ({pos_cnt}건)</div>
        <ul style="margin:2px 0 4px 14px;padding:0;">
          {''.join(f'<li>{x}</li>' for x in pos_summary)}
        </ul>
        <div style="background:#FEF2F2;color:#991B1B;font-weight:700;border-radius:4px;padding:2px 6px;margin-bottom:3px;display:inline-block;">부정 ({neg_cnt}건)</div>
        <ul style="margin:2px 0 4px 14px;padding:0;">
          {''.join(f'<li>{x}</li>' for x in neg_summary)}
        </ul>
        <div style="background:#ECFDF5;color:#065F46;font-weight:700;border-radius:4px;padding:2px 6px;margin-bottom:3px;display:inline-block;">중립 ({neu_cnt}건)</div>
        <ul style="margin:2px 0 4px 14px;padding:0;">
          {''.join(f'<li>{x}</li>' for x in neu_summary)}
        </ul>
      </td>
    </tr>
"""

    html += """
  </tbody>
</table>
</body>
</html>
"""
    return html

# ============================================================
# 🧩 [실행부]
# ============================================================
if __name__ == "__main__":
    main_ttl = "[홈개편] 홈탭 설문조사"
    qsit_ttl = "추가로 다른 의견이 있다면 알려주세요"

    df = load_data("20251010_sample_data.csv")
    data1 = create_data1(df, main_ttl, qsit_ttl)
    data2 = create_data2(df, main_ttl, qsit_ttl)

    html_report = make_html_report(data1, data2)
    output_name = f"{main_ttl}_주관식분석.html"
    with open(output_name, "w", encoding="utf-8") as f:
        f.write(html_report)

    print(f"✅ {output_name} 생성 완료")
