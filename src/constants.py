import os
from typing import Dict, List

# =========================
# 파일 경로 설정
# =========================
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")  # 데이터 파일이 저장된 디렉토리

# =========================
# 보고서 레이아웃 설정
# =========================
# 보고서 최소/최대 폭 설정
REPORT_MIN_WIDTH = 840  # 최소 폭 (px)
REPORT_MAX_WIDTH = 980  # 최대 폭 (px)

# =========================
# 문항타입별 보고서 컴포넌트 구성
# =========================

# 사용 가능한 컴포넌트 타입들
COMPONENT_TYPES = {
    "general_stats": "일반형 응답통계",                                  # 기본 응답 통계 (비율, 응답수 등)
    "general_heatmap": "일반형 히트맵",                                  # 세그먼트별 교차분석 히트맵 (히트맵만)
    "general_heatmap_with_cross_analysis": "일반형 히트맵+교차분석",      # 일반형 히트맵 + 교차분석 엣지케이스
    "evaluation_heatmap": "평가형 히트맵",                               # 평가형 전용 히트맵 (순만족도 포함, 히트맵만)
    "evaluation_heatmap_with_cross_analysis": "평가형 히트맵+교차분석",   # 평가형 히트맵 + 교차분석 엣지케이스
    "ranking_stats": "순위형 응답통계",                                  # 순위별 응답 통계
    "ranking_chart": "순위형 차트",                                     # 순위 시각화 차트
    "subjective_summary": "주관식 요약",                                # 키워드 분석 및 요약
}

# 문항 타입별 컴포넌트 구성 설정
QUESTION_TYPE_COMPONENTS: Dict[str, List[str]] = {
    "objective": ["general_stats", "general_heatmap_with_cross_analysis"],           # 객관식: 일반형 응답통계 + 일반형 히트맵+교차분석
    "evaluation": ["general_stats", "evaluation_heatmap_with_cross_analysis"],       # 평가형: 일반형 응답통계 + 평가형 히트맵+교차분석
    "card": ["general_stats", "general_heatmap_with_cross_analysis"],                # 카드형: 일반형 응답통계 + 일반형 히트맵+교차분석
    "binary": ["general_stats", "general_heatmap_with_cross_analysis"],              # 이분형: 일반형 응답통계 + 일반형 히트맵+교차분석
    "ranking": ["ranking_stats", "ranking_chart"],               # 순위형: 순위형 응답통계 + 순위형 차트
    "subjective": ["subjective_summary"],                        # 주관식: 주관식 요약
    "content": ["general_stats", "general_heatmap_with_cross_analysis"],             # 콘텐츠형: 일반형 응답통계 + 일반형 히트맵+교차분석
    "list": ["general_stats", "general_heatmap_with_cross_analysis"],                # 목록형: 일반형 응답통계 + 일반형 히트맵+교차분석
}

# =========================
# 평가형 히트맵 분석 설정
# =========================
# 평가형 문항의 표준 라벨 순서 (매우 만족 → 매우 불만족)
EVAL_LABELS = ["매우 만족해요", "만족해요", "보통이에요", "불만족해요", "매우 불만족해요"]

# 평가형 히트맵으로 분류할 문항을 판단하는 키워드
EVALUATION_TRIGGERS: List[str] = ["만족", "그렇다"]


#4C0101
#910304
#AD0001
#CB1F1A
#F55142


# =========================
# 색상 팔레트 및 구성 설정
# =========================
# 메인 색상 팔레트 (11단계, 0%~100%, 밝은 색부터 진한 색 순)
PRIMARY_PALETTE = [ 
	"#343E4F",  # 0% 
	"#4D596F",  # 10% - 쿨그레이
	"#8694B1",  # 20%
	"#A7B3CB",  # 30%
	"#D2D9FE",  # 40%
	"#9EB0FF",  # 50%
	"#6C87FE",  # 60%
	"#5574FC",  # 70%
	"#324AFB",  # 80%
	"#1728C4",  # 90%
	"#17008C",  # 100% - 가장 진한 파랑

]

# 대비 색상 (레드 계열, 11단계, 0%~100%, 밝은 레드부터 진한 레드 순)
# #EF4444를 80% 색으로 하는 팔레트
CONTRAST_PALETTE = [
	"#CEF8E0",  # 0% - 가장 밝은 색
	"#ADF4CE",  # 10%
	"#89ECBC",  # 20%
	"#67DEA8",  # 30%
	"#49CC93",  # 40%  
	"#2FB880",  # 50%  --여기서부터 텍스트 컬러 white
	"#15A46E",  # 60%
	"#00915F",  # 70%
	"#007A4D",  # 80%
	"#005737",  # 90%
	"#003822",  # 100% - 가장 진한 색
]

# 색상 구성 설정
COLOR_CONFIG = {
    "heatmap": {
        "total_colors": 11,  # 히트맵은 11개 색상 모두 사용
        "start_index": 0,
        "end_index": 10
    },
    "pick_1_color": {
        "total_colors": 1,
        "indices": [8]  
    },
    "pick_2_colors": {
        "total_colors": 2,
        "indices": [10, 7]	
    },
    "pick_3_colors": {
        "total_colors": 3,
        "indices": [10, 8, 5] 
    },
    "pick_4_colors": {
        "total_colors": 4,
        "indices": [10, 8, 7, 5]  
    },
    "pick_5_colors": {
        "total_colors": 5,
        "indices": [10, 9, 8, 7, 5] 
    },
    "pick_6_colors": {
        "total_colors": 6,
        "indices": [10, 9, 8, 7, 6, 5] 
    },
    "pick_7_colors": {
        "total_colors": 7,
        "indices": [10, 9, 8, 7, 6, 5, 4]  
    },
    "pick_8_colors": {
        "total_colors": 7,
        "indices": [10, 9, 8, 7, 6, 5, 4, 3]  
    },
    "pick_9_colors": {
        "total_colors": 7,
        "indices": [10, 9, 8, 7, 6, 5, 4, 3, 2]  
    },
    "pick_10_colors": {
        "total_colors": 7,
        "indices": [10, 9, 8, 7, 6, 5, 4, 3, 2, 1]  
    },
    "pick_11_colors": {
        "total_colors": 7,
        "indices": [10, 9, 8, 7, 6, 5, 4, 3, 2, 1, 0]  
    }
}

# =========================
# 히트맵 색상 변환 설정
# =========================
# 색상 변환을 위한 수학적 파라미터들
HEATMAP_GAMMA = 1.0  # 감마 보정 (1.0 = 선형, >1.0 = 어두운 부분 강조)
HEATMAP_ALPHA = 0.7  # 끝단 강조 강도 (0<alpha<1: 저/고값 대비 강화)
HEATMAP_MIDRANGE_GAIN = 1.40  # 중간 구간 대비 증폭 (20~60% 구간 차이 확대)

# =========================
# 그레이스케일 적용 임계값
# =========================
# 전체 응답 수 대비 몇 % 미만일 때 그레이스케일로 표시할지 설정
# 통계적 유의성을 위해 최소 5건은 확보되어야 함
GRAYSCALE_THRESHOLD_PERCENT = 0.5  # 0.5% 미만이면 그레이스케일 적용
GRAYSCALE_MIN_COUNT = 5  # 최소 5건은 확보되어야 함

# 그레이스케일 히트맵용 색상 (11단계, 0%~100%, 밝은 회색부터 진한 회색 순)
# n이 부족한 행이나 기타 열에 사용
GRAYSCALE_PALETTE = [
	"#E0DEDE",  # 0% - 가장 밝은 회색
	"#CFCCCC",  # 10%
	"#BDBBBB",  # 20%
	"#ADAAAA",  # 30%
	"#999696",  # 40%
	"#827E7E",  # 50%. --여기서부터 텍스트 컬러 white
	"#706D6D",  # 60%
	"#635E5E",  # 70%
	"#524E4E",  # 80%
	"#403939",  # 90%
	"#161414",  # 100% - 가장 진한 회색
]

# =========================
# 교차분석 설정
# =========================
# 교차분석 최대 차원 (2차원, 3차원 등)
CROSS_ANALYSIS_MAX_DIMENSIONS = 2  # 2차원과 3차원 교차분석 수행

# 교차분석 차이 임계값 (전체 대비 차이 %p)
CROSS_ANALYSIS_DIFFERENCE_THRESHOLD = 10.0  # 0.001%p 이상 차이날 때만 엣지케이스로 분류

# 평가형 교차분석 차이 임계값 (전체 평균 점수 대비 차이 %)
EVALUATION_CROSS_ANALYSIS_DIFFERENCE_THRESHOLD = 5.0  # 5% 이상 차이날 때만 엣지케이스로 분류

# 교차분석 최소 응답 수 (신뢰성 확보)
CROSS_ANALYSIS_MIN_RESPONSES = 20  # 최소 20건 이상 응답이 있을 때만 분석

# 엣지케이스 표에서 각 셀당 최대 표시 개수
CROSS_ANALYSIS_MAX_CASES_PER_CELL = 3  # 각 셀당 최대 3개 엣지케이스 표시


# =========================
# 주관식 분석 표시 설정
# =========================
# '기타' 카테고리로 묶을 임계값 (건수 또는 비율 중 하나라도 해당되면 '기타'로 분류)
SUBJECTIVE_OTHER_THRESHOLD = 0  # 20건 이하인 카테고리를 '기타'로 묶음
SUBJECTIVE_OTHER_PERCENT_THRESHOLD = 0.0  # 1% 이하인 카테고리를 '기타'로 묶음

# 응답 내용 길이 기준 (이 길이 미만이면 분석에서 제외)
MIN_RESPONSE_LENGTH = 5  # 5글자 미만인 응답은 분석에서 제외

# 키워드 표시 개수 제한
SUBJECTIVE_KEYWORDS_LIMIT = 5  # 일반 카테고리에서 표시할 키워드 개수
SUBJECTIVE_KEYWORDS_LIMIT_OTHER = 10  # '기타' 카테고리에서 표시할 키워드 개수


# # =========================
# # 환경설정 (레이아웃/버킷)
# # - 각 행(row)에 표시할 세그 그래프를 지정합니다.
# # - buckets: 가로폭 비율 계산에 사용 (해당 세그의 버킷 수를 의미)
# # - 1행~7행 기본값 제공. 필요 시 수정/추가하세요.
# # - title은 UI 노출용, seg은 데이터 키 (아래 SEG_DEFS 참고 키 사용)
# # =========================
# LAYOUT_CONFIG: List[List[Dict[str, object]]] = [
# 	# 1행: 성별(2) | 계좌고객(2)
# 	[
# 		{"title": "① 성별", "seg": "gndr_seg", "buckets": 2},
# 		{"title": "② 계좌고객 여부", "seg": "account_seg", "buckets": 2},
# 	],
# 	# 2행: 연령대(7) 단독
# 	[
# 		{"title": "③ 연령대", "seg": "age_seg", "buckets": 7},
# 	],
# 	# 3행: 가입경과일(5) | VASP 연결(2)
# 	[
# 		{"title": "④ 가입경과일", "seg": "rgst_gap", "buckets": 5},
# 		{"title": "⑤ VASP 연결 여부", "seg": "vasp", "buckets": 2},
# 	],
# 	# 4행: 수신상품 가입(4) | 대출상품 가입(4)
# 	[
# 		{"title": "⑥ 수신상품 가입", "seg": "dp_seg", "buckets": 4},
# 		{"title": "⑦ 대출상품 가입", "seg": "loan_seg", "buckets": 5},
# 	],
# 	# 5행: 카드상품 가입(4) | 서비스 이용(3)
# 	[
# 		{"title": "⑧ 카드상품 가입", "seg": "card_seg", "buckets": 4},
# 		{"title": "⑨ 서비스 이용", "seg": "suv_seg", "buckets": 3},
# 	],
# ]


# =========================
# 주관식 분석 제외 규칙 설정
# =========================
# 주관식 요약에서 제외할 카테고리 목록 (기타로 분류됨)
SUBJECTIVE_EXCLUDE_CATEGORIES = {
    "긍정반응", "서비스만족", "감사"
}

# 주관식 키워드 추출에서 제외할 키워드 목록 (의미 없는 일반적 표현들)
SUBJECTIVE_EXCLUDE_KEYWORDS = {
    "무응답", "만족", "좋아요", "응답", "설문", "케이뱅크", "해주세요", 
    "않아요", "합니다", "있으면", "좋겠어요", "감사합니다", "매우만족합니다", 
    "Best", "은행", "없음", "안돼나요", "더", "매우만족"
}