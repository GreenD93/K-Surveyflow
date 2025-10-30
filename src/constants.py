import os
from typing import Dict, List

# =========================
# langchain constants
OPENAI_KEY = ""
#os.getenv("OPENAI_API_KEY")

USE_ASYNC_CLASSIFY = True  # 카테고리 분류 비동기 사용 여부
USE_ASYNC_ENRICH = True  # 감성/키워드 비동기 사용 여부
ASYNC_CONCURRENCY = 50  # 동시 실행 개수
# =========================

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
    "ranking_heatmap": "순위형 히트맵",                                 # 순위형 히트맵
    "subjective_summary": "주관식 요약",                                # 키워드 분석 및 요약
}

# 문항 타입별 컴포넌트 구성 설정
QUESTION_TYPE_COMPONENTS: Dict[str, List[str]] = {
    "objective": ["general_stats", "general_heatmap_with_cross_analysis"],           # 객관식: 일반형 응답통계 + 일반형 히트맵+교차분석
    "evaluation": ["general_stats", "evaluation_heatmap_with_cross_analysis"],       # 평가형: 일반형 응답통계 + 평가형 히트맵+교차분석
    "card": ["general_stats", "general_heatmap_with_cross_analysis"],                # 카드형: 일반형 응답통계 + 일반형 히트맵+교차분석
    "binary": ["general_stats", "general_heatmap_with_cross_analysis"],              # 이분형: 일반형 응답통계 + 일반형 히트맵+교차분석
    "content": ["general_stats", "general_heatmap_with_cross_analysis"],             # 콘텐츠형: 일반형 응답통계 + 일반형 히트맵+교차분석
    "list": ["general_stats", "general_heatmap_with_cross_analysis"],                # 목록형: 일반형 응답통계 + 일반형 히트맵+교차분석
    "ranking": ["ranking_stats", "ranking_heatmap"],               # 순위형: 순위형 응답통계 + 순위형 히트맵
    "subjective": ["subjective_summary"],                        # 주관식: 주관식 요약
}

# =========================
# 평가형 히트맵 분석 설정
# =========================
# 평가형 문항의 표준 라벨 순서 (매우 만족 → 매우 불만족)
EVAL_LABELS = ["매우 만족해요", "만족해요", "보통이에요", "불만족해요", "매우 불만족해요"]

# 평가형 히트맵으로 분류할 문항을 판단하는 키워드
EVALUATION_TRIGGERS: List[str] = ["만족", "그렇다"]


# 빨간색 팔레트 (11단계, 밝은 빨강부터 진한 빨강 순)
CONTRAST_PALETTE = [
	"#FEF2F2",  # 0% - 가장 밝은 빨강 (엣지케이스 기본 색상)
	"#FEE2E2",  # 10%
	"#FECACA",  # 20%
	"#FCA5A5",  # 30%
	"#F87171",  # 40%
	"#F55142",  # 50%
	"#F55142",  # 60% - 기존 가장 밝은 빨강
	"#CB1F1A",  # 70% - 기존 75%
	"#AD0001",  # 80% - 기존 50%
	"#910304",  # 90% - 기존 25%
	"#4C0101",  # 100% - 기존 가장 진한 빨강
]


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

# 히트맵 색상 (11단계, 0%~100%, 밝은 색부터 진한 색 순)
# #EF4444를 80% 색으로 하는 팔레트
HEATMAP_PALETTE = [
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

# 순위형 가중치 환경변수
RANKING_WEIGHTS_ENABLED = True
RANKING_WEIGHTS = {
	"heatmap": {
		1:  [1],
		2:  [2, 1],
		3:  [3, 2, 1],
		4:  [4, 3, 2, 1],
		5:  [5, 4, 3, 2, 1],
		6:  [6, 5, 4, 3, 2, 1],
		7:  [7, 6, 5, 4, 3, 2, 1],
		8:  [8, 7, 6, 5, 4, 3, 2, 1],
		9:  [9, 8, 7, 6, 5, 4, 3, 2, 1],
		10: [10, 9, 8, 7, 6, 5, 4, 3, 2, 1],
	},
	# stats 가중치 세분화: 1~10개 선택 케이스 모두 정의
	# 1+2순위: 선택 개수에 따라 [2], [2,1], 이후는 항상 [2,1]
	"stats_1or2": {
		1:  [2],
		2:  [2, 1],
		3:  [2, 1],
		4:  [2, 1],
		5:  [2, 1],
		6:  [2, 1],
		7:  [2, 1],
		8:  [2, 1],
		9:  [2, 1],
		10: [2, 1],
	},
	# 1+2+3순위: 선택 개수에 따라 [3], [3,2], [3,2,1], 이후는 항상 [3,2,1]
	"stats_1or2or3": {
		1:  [3],
		2:  [3, 2],
		3:  [3, 2, 1],
		4:  [3, 2, 1],
		5:  [3, 2, 1],
		6:  [3, 2, 1],
		7:  [3, 2, 1],
		8:  [3, 2, 1],
		9:  [3, 2, 1],
		10: [3, 2, 1],
	},
}

# 응답자 단위 정규화 옵션 (on/off)
# True: 한 응답자의 (1+2) 혹은 (1+2+3) 가중치 합이 항상 1이 되도록 정규화
# False: 고정 가중치(2,1 / 3,2,1)를 그대로 사용
RANKING_NORMALIZE_PER_RESPONDENT = True

# =========================
# 히트맵 색상 변환 설정
# =========================
# 색상 변환을 위한 수학적 파라미터들
HEATMAP_GAMMA = 1.0  # 감마 보정 (1.0 = 선형, >1.0 = 어두운 부분 강조)
HEATMAP_ALPHA = 0.7  # 끝단 강조 강도 (0<alpha<1: 저/고값 대비 강화)
HEATMAP_MIDRANGE_GAIN = 1.40  # 중간 구간 대비 증폭 (20~60% 구간 차이 확대)

# 그래프 내부 텍스트 최소 폭 임계값(px)
GRAPH_INTERNAL_TEXT_MIN_PX = 24  # px

# 응답통계 차트 레이아웃 추정치 (막대 px 계산용)
GENERAL_STATS_CHART_LEFT_COL_PCT = 0.60  # 좌측 차트 영역 가로 비율 (layout_html 기준 60%)
GENERAL_STATS_CHART_LEFT_PADDING_PX = 8  # 좌측 차트 셀 내부 left padding (layout_html)

# 아래 스택 라벨(외부 라벨) 렌더링 규격
GRAPH_EXTERNAL_LABEL_ROW_HEIGHT_PX = 8
GRAPH_EXTERNAL_LABEL_ROW_GAP_PX = 4
GRAPH_GUIDELINE_COLOR = "#9CA3AF"
GRAPH_GUIDELINE_STYLE = "0.5px dashed"

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
# 교차분석 최대 차원 (예: 2 → 2차원 조합까지)
# 현재 설정값 2: 2차원 교차만 수행 (3차원은 수행하지 않음)
CROSS_ANALYSIS_MAX_DIMENSIONS = 2

# 교차분석 차이 임계값 (전체 대비 차이 %p)
CROSS_ANALYSIS_DIFFERENCE_THRESHOLD = 10.0  # 10%p 이상 차이날 때만 엣지케이스로 분류

# 평가형 교차분석 차이 임계값 (전체 평균 점수 대비 차이 %)
# 주석 보정: 실제 값은 10.0%p 이며, 10%p 이상 차이 시 엣지케이스로 분류
EVALUATION_CROSS_ANALYSIS_DIFFERENCE_THRESHOLD = 10.0

# 교차분석 최소 응답 수 (신뢰성 확보)
CROSS_ANALYSIS_MIN_RESPONSES = 20  # 최소 20건 이상 응답이 있을 때만 분석

# 엣지케이스 표에서 각 셀당 최대 표시 개수
CROSS_ANALYSIS_MAX_CASES_PER_CELL = 3  # 각 셀당 최대 3개 엣지케이스 표시

# 평균대비 gap 상위 노출 개수 (교차분석 표 전체 상위 N개)
CROSS_ANALYSIS_TOP_K = 5


# =========================
# 주관식 분석 표시 설정
# =========================
# 응답 내용 길이 기준 (이 길이 미만이면 분석에서 제외)
MIN_RESPONSE_LENGTH = 5  # 5글자 미만인 응답은 분석에서 제외
# 노출 카테고리 최대 개수 설정
SUBJECTIVE_MAX_CATEGORIES = 10  # 주관식 요약 상위 카테고리 개수
OBJECTIVE_OTHER_MAX_CATEGORIES = 5  # 객관식 기타 응답 요약 상위 카테고리 개수
# 주관식 막대 색상/스타일 (PoC 전용)
SUBJECTIVE_POS_BAR_COLOR = "#4262FF"
SUBJECTIVE_NEG_BAR_COLOR = "#F55142"
SUBJECTIVE_NEU_BAR_COLOR = "#8694B1"
SUBJECTIVE_BAR_BG_COLOR = "#E0E6F1"
SUBJECTIVE_BAR_HEIGHT_PX = 16


# 주관식/기타 응답 기타 묶기 임계치 및 키워드 노출 개수 (사용처 존재)
SUBJECTIVE_OTHER_THRESHOLD = 0
SUBJECTIVE_OTHER_PERCENT_THRESHOLD = 0.0
SUBJECTIVE_KEYWORDS_LIMIT = 5
SUBJECTIVE_KEYWORDS_LIMIT_OTHER = 10


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

# 순만족도 전용 색상 팔레트 (주황색 계열)
SUN_EVALUATION_SHADES = [
	"#FFF7ED",  # 0% - 매우 밝은 주황
	"#FFEDD5",  # 10%
	"#FED7AA",  # 20%
	"#FDBA74",  # 30%
	"#FB923C",  # 40%
	"#F97316",  # 50%
	"#EA580C",  # 60%
	"#DC2626",  # 70%
	"#B91C1C",  # 80%
	"#991B1B",  # 90%
	"#7F1D1D",  # 100% - 매우 진한 빨강
]

# 원숫자(동그라미 숫자) 매핑: 1~10
CIRCLED_NUMS = ['①','②','③','④','⑤','⑥','⑦','⑧','⑨','⑩']

def get_segment_display_value(seg: str, value: str) -> str:
	"""
	세그먼트와 값을 받아서 사용자 친화적인 표시값을 반환합니다.
	원본 값으로 먼저 매핑을 시도하고, 실패하면 원본 값을 그대로 반환합니다.
	"""
	# 세그먼트별 매핑 딕셔너리
	mapping = {
		"gndr_seg": {
			"01.남성": "남성", 
			"02.여성": "여성"
		},
		"account_seg": {
			"01.계좌": "계좌고객", 
			"02.비계좌": "비계좌고객"
		},
		"age_seg": {
			"01.10대": "10대", 
			"02.20대": "20대", 
			"03.30대": "30대", 
			"04.40대": "40대", 
			"05.50대": "50대", 
			"06.60대": "60대"
		},
		"rgst_gap": {
			"01.3개월미만": "가입 3개월미만 경과", 
			"02.6개월미만": "가입 6개월미만 경과", 
			"03.1년미만": "가입 1년미만 경과", 
			"04.2년미만": "가입 2년미만 경과", 
			"05.2년 이상": "가입 2년이상 경과"
		},
		"vasp": {
			"미연결": "VASP 미연결", 
			"연결": "VASP 연결"
		},
		"dp_seg": {
			"02.1~3개": "수신상품 1~3개 가입", 
			"03.4~5개": "수신상품 4~5개 가입", 
			"04.6개 이상": "수신상품 6개 이상 가입",
			"05.미보유": "수신상품 미보유"
		},
		"loan_seg": {
			"01.사장님담보": "사장님담보대출 가입", 
			"02.사장님": "사장님대출 가입", 
			"03.담보전세": "담보·전세대출 가입", 
			"04.신용": "신용대출 가입", 
			"05.미보유": "대출 미보유"
		},
		"card_seg": {
			"02.체크": "체크카드 가입", 
			"03.신용": "신용카드 가입",
			"04.체크신용": "체크&신용카드 가입", 
			"05.미보유": "카드 미보유"
		},
		"suv_seg": {
			"01.미이용": "서비스 미이용", 
			"02.1~3개": "서비스 1~3개 이용", 
			"02.4개 이상": "서비스 4개 이상 이용"
		}
	}
	
	# 해당 세그먼트의 매핑이 있으면 사용, 없으면 원본 값 반환
	if seg in mapping:
		return mapping[seg].get(value, value)
	else:
		return value