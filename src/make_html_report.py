import pandas as pd

# ============================================================
# 🧩 설문 정의
# ============================================================

main_ttl = '[홈개편] 홈탭 설문조사'
qsit_ttl = '추가로 다른 의견이 있다면 알려주세요'

# ============================================================
# 🧩 [DATA1] 카테고리별 감정 요약 데이터 생성
# ============================================================

# 1️⃣ 데이터 불러오기
df = pd.read_csv("20251010_sample_data.csv", sep=",")

# 2️⃣ 조건 필터링
filtered = df[
    (df["text_yn"] == 1) &
    (df["main_ttl"] == main_ttl) &
    (df["qsit_ttl"] == qsit_ttl) &
    (~df["category_level2"].isin([
        '단순 칭찬/불만', '욕설·무관한 피드백', '개선 의사 없음 (“없습니다”)'
    ]))
]

# 3️⃣ 감정별 카운트 집계
grouped = (
    filtered
    .groupby(["main_ttl", "qsit_ttl", "category_level1", "category_level2"], dropna=False)
    .agg(
        cnt=("sentiment", "count"),
        positive=("sentiment", lambda x: (x == "긍정").sum()),
        negative=("sentiment", lambda x: (x == "부정").sum()),
        neutral=("sentiment", lambda x: (x == "중립").sum())
    )
    .reset_index()
)

# 4️⃣ 카테고리별 랭킹 계산 (응답 건수 기준)
grouped["no_1"] = (
    grouped
    .sort_values(["main_ttl", "qsit_ttl", "cnt"], ascending=[True, True, False])
    .groupby(["main_ttl", "qsit_ttl"])
    .cumcount() + 1
)

# 5️⃣ 상위 10개 카테고리 추출
data1 = (
    grouped[grouped["no_1"] <= 10]
    .sort_values(by="cnt", ascending=False)
    .reset_index(drop=True)
)

# ============================================================
# 🧩 [DATA2] 주요 키워드 및 감정별 요약 데이터 생성
# ============================================================

# 6️⃣ 키워드 분리 (최대 3개)
def split_keywords(k):
    if pd.isna(k):
        return []
    parts = [p.strip() for p in str(k).split(",")]
    return parts[:3]

kw_rows = []
for _, row in filtered.iterrows():
    for kw in split_keywords(row["keywords"]):
        if kw:
            kw_rows.append([
                row["main_ttl"], row["qsit_ttl"],
                row["category_level1"], row["category_level2"],
                row["sentiment"], kw
            ])

keywords_df = pd.DataFrame(kw_rows, columns=[
    "main_ttl", "qsit_ttl", "category_level1", "category_level2", "sentiment", "keyword"
])

# 7️⃣ 키워드별 등장 횟수 계산
kw_count = (
    keywords_df
    .groupby(["main_ttl","qsit_ttl","category_level1","category_level2","sentiment","keyword"])
    .size()
    .reset_index(name="cnt")
)

# 8️⃣ 감정별 상위 5개 키워드 추출
kw_count["rank"] = (
    kw_count
    .sort_values(["main_ttl","qsit_ttl","category_level1","category_level2","sentiment","cnt"],
                 ascending=[True,True,True,True,True,False])
    .groupby(["main_ttl","qsit_ttl","category_level1","category_level2","sentiment"])
    .cumcount() + 1
)
top_kw = kw_count[kw_count["rank"] <= 5]

# 9️⃣ 키워드 문자열 생성 (예: "편리(10), 빠름(7), 오류(3)")
def join_keywords(sub):
    return ", ".join(f"{k}({c})" for k, c in zip(sub["keyword"], sub["cnt"]))

kw_summary = (
    top_kw.groupby(["main_ttl","qsit_ttl","category_level1","category_level2","sentiment"])
    .apply(join_keywords)
    .reset_index(name="keyword_anal")
)

# 🔟 원본 filtered 데이터와 병합
result = filtered.merge(
    kw_summary,
    on=["main_ttl","qsit_ttl","category_level1","category_level2","sentiment"],
    how="left"
)

# 11️⃣ 감정별 랭크 제한 (긍/부 3개, 중립 2개)
result["rnk"] = (
    result
    .sort_values(["main_ttl","qsit_ttl","category_level1","category_level2","sentiment"])
    .groupby(["main_ttl","qsit_ttl","category_level1","category_level2","sentiment"])
    .cumcount() + 1
)
filtered_result = result[
    ((result["sentiment"].isin(["긍정","부정"])) & (result["rnk"] <= 3)) |
    ((result["sentiment"] == "중립") & (result["rnk"] <= 2))
]

# 12️⃣ 상위 10개 카테고리와 병합 (data2 완성)
cat_count = (
    filtered.groupby(["main_ttl","qsit_ttl","category_level1","category_level2"])
    .size().reset_index(name="cnt")
)
cat_count["no_1"] = (
    cat_count
    .sort_values(["main_ttl","qsit_ttl","cnt"], ascending=[True,True,False])
    .groupby(["main_ttl","qsit_ttl"])
    .cumcount() + 1
)
top10 = cat_count[cat_count["no_1"] <= 10]

data2 = filtered_result.merge(
    top10,
    on=["main_ttl","qsit_ttl","category_level1","category_level2"],
    how="inner"
)

# ============================================================
# 🧩 [HTML] 리포트 생성
# ============================================================

# 13️⃣ 기존 CSV 불러오기 (카테고리 요약 & 키워드 요약)
data1 = pd.read_csv("survey_cat_anal.csv", sep="\t")
data2 = pd.read_csv("survey_cat_summary.csv", sep="\t")

# 14️⃣ HTML 생성 함수
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

# 16️⃣ HTML 저장
html_report = make_html_report(data1, data2)
with open(f"{main_ttl}_주관식분석.html", "w", encoding="utf-8") as f:
    f.write(html_report)

print(f"✅ {main_ttl}_주관식분석.html 생성 완료")
