import csv
import sys
import os
import re
import math
from collections import Counter, defaultdict, OrderedDict
from datetime import datetime
from typing import Dict, List, Tuple, Optional
from itertools import combinations

# =========================
# 파일 경로 설정
# =========================
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")  # 데이터 파일이 저장된 디렉토리
CSV_FILE_NAME = "20250916_sample_data.csv"  # 기본 CSV 파일명
DEFAULT_CSV_PATH = os.path.join(DATA_DIR, CSV_FILE_NAME)  # 기본 CSV 파일 전체 경로

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

# =========================
# 유틸리티 함수들
# =========================
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
def is_evaluation_pattern(labels: List[str]) -> bool:
	"""
	라벨 리스트가 평가형 패턴인지 판단합니다.
	
	평가형 패턴:
	1. 만족도 패턴: 매우 만족 / 만족 / 보통 / 불만족 / 매우 불만족
	2. 동의도 패턴: 매우 그렇다 / 그렇다 / 보통이다 / 그렇지 않다 / 매우 그렇지 않다
	
	조건:
	- 5개 라벨 중 3개 이상이 평가형 키워드를 포함
	- "매우", "보통" 키워드가 포함된 라벨이 있어야 함
	"""
	if not labels or len(labels) < 3:
		return False
	
	# 평가형 키워드들
	eval_keywords = ["만족", "그렇다", "불만족", "그렇지 않다"]
	
	# 각 라벨에서 평가형 키워드 포함 여부 확인
	eval_count = 0
	has_very = False
	has_normal = False
	
	for label in labels:
		label_lower = label.lower()
		
		# 평가형 키워드 포함 여부
		if any(keyword in label for keyword in eval_keywords):
			eval_count += 1
		
		# "매우" 키워드 확인
		if "매우" in label:
			has_very = True
		
		# "보통" 키워드 확인
		if "보통" in label:
			has_normal = True
	
	# 평가형 패턴 판단 조건
	# 1. 전체 라벨의 60% 이상이 평가형 키워드 포함
	# 2. "매우"와 "보통" 키워드가 모두 포함
	return (eval_count >= len(labels) * 0.6) and has_very and has_normal

def _calculate_percentage(count: int, total: int) -> float:
	"""카운트와 총합으로부터 퍼센트를 계산합니다."""
	return round(100.0 * count / (total or 1), 1)

def _compute_overall_rank_from_rows_data(rows_data: List[Dict[str, object]], order: List[str]) -> List[str]:
	"""rows_data의 첫 행(전체)을 기준으로 보기별 퍼센트 순위(내림차순)를 계산합니다."""
	if not rows_data or not order:
		return []
	first = rows_data[0]
	cnts = first.get('cnts') or {}
	total = int(first.get('total') or 0) or 1
	try:
		pct_map: Dict[str, float] = {lb: (int(cnts.get(lb, 0)) * 100.0 / total) for lb in order}  # type: ignore
	except Exception:
		pct_map = {lb: 0.0 for lb in order}
	return sorted(order, key=lambda lb: (-pct_map.get(lb, 0.0), order.index(lb)))

def _calculate_top_satisfaction(cnts: Dict[str, int], order: List[str]) -> Tuple[float, str, List[str]]:
	"""상위 만족도 비율과 표시 텍스트, 포함된 라벨들을 계산합니다."""
	if not order or not cnts:
		return 0.0, "Top1+2", []
	
	total = sum(cnts.values())
	if total == 0:
		return 0.0, "Top1+2", []
	
	# 보기 개수에 따른 TopN 계산: top(rounddown(n/2))
	n_options = len(order)
	top_count = max(2, n_options // 2)  # 최소 2개, rounddown(n/2)
	
	# 상위 선택 (오른쪽부터, 점수가 높은 쪽부터)
	top_labels = order[-top_count:]  # 오른쪽부터 top_count 개수만큼
	top_text = f"Top{top_count}"
	
	# 상위 만족도 비율 계산
	top_count = sum(cnts.get(label, 0) for label in top_labels)
	top_pct = (top_count / total) * 100.0
	
	return round(top_pct, 1), top_text, top_labels

def _calculate_average_score(cnts: Dict[str, int], order: List[str] = None) -> float:
	"""만족도 카운트에서 평균점수를 계산합니다."""
	if not cnts:
		return 0.0
	
	total_score = 0
	total_count = 0
	
	# 평가형 문항의 경우 (숫자 답변)
	if order and all(label.isdigit() for label in order):
		# 숫자 답변을 그대로 점수로 사용
		for label, count in cnts.items():
			if label.isdigit():
				score = float(label)
				total_score += score * count
				total_count += count
	else:
		# 객관식 중 평가형으로 간주되는 경우
		# 히트맵 라벨 뒤의 숫자를 기준으로 점수 매핑 (왼쪽부터 1점, 오른쪽일수록 높은 점수)
		if order:
			score_mapping = {}
			for i, label in enumerate(order):
				score_mapping[label] = i + 1  # 왼쪽부터 1점, 오른쪽일수록 높은 점수 (1,2,3,4,5)
		else:
			# 기본 5점 척도 매핑
			score_mapping = {
				"매우 불만족해요": 1.0,
				"불만족해요": 2.0,
				"보통이에요": 3.0,
				"만족해요": 4.0,
				"매우 만족해요": 5.0,
			}
		
		for label, count in cnts.items():
			if label in score_mapping:
				total_score += score_mapping[label] * count
				total_count += count
	
	return total_score / total_count if total_count > 0 else 0.0

def _display_label(label: str, order: List[str] = None) -> str:
	"""표시용 라벨 정규화 및 점수 표시"""
	# order가 있는 경우 "n. 범례텍스트" 형태로 표시 (평가형과 일반형 모두 동일)
	if order and label in order:
		idx = order.index(label)
		number = idx + 1  # 1부터 시작하는 번호
		return f"{number}. {label}"
	
	return label

def _get_segment_combinations(segments: List[str], max_dimensions: int) -> List[Tuple[str, ...]]:
	"""세그먼트 조합을 생성합니다 (2차원부터 max_dimensions까지)"""
	combinations_list = []
	for r in range(2, min(max_dimensions + 1, len(segments) + 1)):
		combinations_list.extend(combinations(segments, r))
	return combinations_list

def _calculate_cross_analysis_difference(overall_pct: float, segment_pct: float) -> float:
	"""전체 대비 세그먼트 차이를 계산합니다."""
	return abs(segment_pct - overall_pct)

def _analyze_evaluation_cross_segments(question_rows: List[Dict[str, str]], question_title: str) -> List[Dict]:
	"""평가형 문항의 교차분석 - 전체 평균 점수 기준으로 세그먼트 조합별 평균 점수 비교"""
	edge_cases = []
	
	# 만족도 라벨을 점수로 변환 (텍스트 라벨과 숫자 응답 모두 처리)
	label_to_score = {
		"매우 만족해요": 5, "만족해요": 4, "보통이에요": 3, "불만족해요": 2, "매우 불만족해요": 1
	}
	
	# 전체 평균 점수 계산
	total_score = 0
	total_count = 0
	for row in question_rows:
		response = (row.get("lkng_cntnt") or row.get("answ_cntnt") or "").strip()
		# 텍스트 라벨인 경우
		if response in label_to_score:
			total_score += label_to_score[response]
			total_count += 1
		# 숫자 응답인 경우 (1-7 스케일)
		elif response.isdigit():
			score = int(response)
			if 1 <= score <= 7:  # 1-7 스케일
				total_score += score
				total_count += 1
	overall_avg_score = total_score / total_count if total_count > 0 else 0
	
	# 세그먼트 컬럼들 찾기 (메타데이터 컬럼 제외)
	excluded_columns = [
		"answ_id", "qsit_id", "qsit_type_ds_cd", "lkng_cntnt", "answ_cntnt", "text_yn", 
		"llm_level1", "llm_level2", "sentiment", "keywords", "surv_date", "lkng_sqn", "qsit_sqn", 
		"answ_sqn", "reg_dt", "upd_dt", "reg_user", "upd_user"
	]
	segment_columns = [col for col in question_rows[0].keys() 
					  if col not in excluded_columns and col.endswith("_seg")]
	
	# 2차원과 3차원 조합 생성
	from itertools import combinations
	for dim in range(2, min(CROSS_ANALYSIS_MAX_DIMENSIONS + 1, len(segment_columns) + 1)):
		for seg_combo in combinations(segment_columns, dim):
			# 세그먼트 조합별로 그룹화
			seg_groups = {}
			for row in question_rows:
				seg_values = tuple((row.get(col) or "").strip() for col in seg_combo)
				if all(seg_values):  # 모든 세그먼트 값이 있는 경우만
					if seg_values not in seg_groups:
						seg_groups[seg_values] = []
					seg_groups[seg_values].append(row)
			
			# 각 세그먼트 조합별로 평균 점수 계산
			for seg_values, group_rows in seg_groups.items():
				if len(group_rows) < CROSS_ANALYSIS_MIN_RESPONSES:
					continue
				
				# 해당 조합에서의 평균 점수 계산
				combo_score = 0
				combo_count = 0
				for row in group_rows:
					response = (row.get("lkng_cntnt") or row.get("answ_cntnt") or "").strip()
					# 텍스트 라벨인 경우
					if response in label_to_score:
						combo_score += label_to_score[response]
						combo_count += 1
					# 숫자 응답인 경우 (1-7 스케일)
					elif response.isdigit():
						score = int(response)
						if 1 <= score <= 7:  # 1-7 스케일
							combo_score += score
							combo_count += 1
				
				if combo_count == 0:
					continue
					
				combo_avg_score = combo_score / combo_count
				
				# 평균 점수 대비 편차 계산 (%)
				if overall_avg_score > 0:
					difference = ((combo_avg_score - overall_avg_score) / overall_avg_score) * 100
				else:
					difference = 0
				
				# 임계값 이상 차이날 때만 엣지케이스로 분류
				if abs(difference) >= EVALUATION_CROSS_ANALYSIS_DIFFERENCE_THRESHOLD:
					edge_case = {
						"question_title": question_title,
						"label": "전체 평균",  # 만족도는 전체 평균 기준
						"overall_pct": overall_avg_score,
						"combo_pct": combo_avg_score,
						"difference": difference,
						"segment_combination": dict(zip(seg_combo, seg_values)),
						"label_count": combo_count,
						"response_count": len(group_rows)
					}
					edge_cases.append(edge_case)
	
	return edge_cases
def _analyze_cross_segments(question_rows: List[Dict[str, str]], question_title: str, 
                           question_type: str, label: str) -> List[Dict]:
	"""교차분석을 수행하여 엣지케이스를 찾습니다."""
	if question_type == "subjective":
		return []  # 주관식은 제외
	
	# 사용 가능한 세그먼트 목록
	available_segments = [
		"gndr_seg", "account_seg", "age_seg", "rgst_gap", "vasp",
		"dp_seg", "loan_seg", "card_seg", "suv_seg"
	]
	
	# 실제 데이터에 존재하는 세그먼트만 필터링 (최적화)
	existing_segments = []
	seg_values_cache = {}  # 세그먼트 값들을 캐시
	seg_value_counts = {}  # 세그먼트 값별 빈도 캐시 (성능 최적화)
	
	# 한 번의 순회로 모든 세그먼트 값과 빈도를 수집 (성능 최적화)
	for row in question_rows:
		for seg in available_segments:
			val = (row.get(seg) or "").strip()
			if val and val not in ["", "0", "-", "N/A", "NA", "null", "NULL", "미응답", "무응답"]:
				# '기타' 버킷 제외
				if clean_axis_label(val) == '기타':
					continue
				if seg not in seg_values_cache:
					seg_values_cache[seg] = set()
					seg_value_counts[seg] = {}
				seg_values_cache[seg].add(val)
				seg_value_counts[seg][val] = seg_value_counts[seg].get(val, 0) + 1
	
	# 2개 이상의 값이 있는 세그먼트만 선택
	for seg in available_segments:
		if seg in seg_values_cache and len(seg_values_cache[seg]) > 1:
			existing_segments.append(seg)
	
	if len(existing_segments) < 2:
		return []
	
	# 전체 응답에서 해당 라벨의 비율 계산 (최적화)
	total_responses = len(question_rows)
	
	# 성능 최적화: 라벨 매칭을 위한 키 사전 계산
	label_key = "lkng_cntnt" if any((row.get("lkng_cntnt") or "").strip() for row in question_rows) else "answ_cntnt"
	label_responses = sum(1 for row in question_rows if (row.get(label_key) or "").strip() == label)
	overall_pct = _calculate_percentage(label_responses, total_responses)
	
	# 평가형 타입인 경우 평균 점수 계산
	if question_type == "evaluation":
		# 평가형 라벨을 점수로 변환
		label_to_score = {
			"매우 만족해요": 5, "만족해요": 4, "보통이에요": 3, "불만족해요": 2, "매우 불만족해요": 1
		}
		# 전체 평균 점수 계산 (성능 최적화: label_key 사용)
		total_score = 0
		total_count = 0
		response_scores = {}  # 응답별 점수 캐시
		for row in question_rows:
			response = (row.get(label_key) or "").strip()
			if response in label_to_score:
				score = label_to_score[response]
				total_score += score
				total_count += 1
				response_scores[response] = score  # 캐시에 저장
		overall_avg_score = total_score / total_count if total_count > 0 else 0
	
	# 라벨 매칭을 위한 사전 계산은 위에서 이미 완료됨
	
	# 전체 비율이 너무 낮거나 높으면 교차분석 의미 없음
	if overall_pct < 5.0 or overall_pct > 95.0:
		return []
	edge_cases = []
	
	# 세그먼트 조합별로 교차분석 수행
	max_dims = CROSS_ANALYSIS_MAX_DIMENSIONS
	segment_combinations = _get_segment_combinations(existing_segments, max_dims)
	
	# 조합 수 제한 제거 - 모든 의미 있는 조합을 분석
	
	# 통계 변수 초기화
	total_segment_combinations = len(segment_combinations)
	total_value_combinations = 0
	analyzed_combinations = 0
	
	for seg_combo in segment_combinations:
		# 각 조합에 대해 교차분석 수행 (캐시된 값 사용)
		seg_values_map = {seg: seg_values_cache[seg] for seg in seg_combo}
		
		# 각 세그먼트의 값이 너무 많으면 제한 (더 엄격하게)
		total_combinations = 1
		for seg in seg_combo:
			total_combinations *= len(seg_values_map[seg])
		total_value_combinations += total_combinations
		
		# 값 조합 수 제한도 제거 - 모든 조합을 분석
		
		# 각 세그먼트 값 조합에 대해 분석
		for seg_values in _generate_segment_value_combinations(seg_values_map):
			analyzed_combinations += 1
			
			# 성능 최적화: 빈도 기반 조기 필터링
			# 조합의 각 세그먼트 값이 너무 적은 빈도를 가지면 스킵
			min_frequency = float('inf')
			for seg, value in seg_values.items():
				frequency = seg_value_counts.get(seg, {}).get(value, 0)
				min_frequency = min(min_frequency, frequency)
			
			# 최소 빈도가 임계값보다 낮으면 스킵 (성능 최적화)
			if min_frequency < CROSS_ANALYSIS_MIN_RESPONSES:
				continue
			
			# 해당 조합에 해당하는 응답들 필터링 (최적화)
			filtered_rows = [row for row in question_rows 
							if all((row.get(seg) or "").strip() == value for seg, value in seg_values.items())]
			
			# 최소 응답 수 확인
			if len(filtered_rows) < CROSS_ANALYSIS_MIN_RESPONSES:
				continue
			
			# 평가형 타입인 경우 평균 점수 대비 편차 계산
			if question_type == "evaluation":
				# 해당 조합에서의 평균 점수 계산
				combo_score = 0
				combo_count = 0
				for row in filtered_rows:
					response = (row.get(label_key) or "").strip()
					if response in label_to_score:
						combo_score += label_to_score[response]
						combo_count += 1
				combo_avg_score = combo_score / combo_count if combo_count > 0 else 0
				
				# 평균 점수 대비 편차 계산 (%)
				if overall_avg_score > 0:
					difference = ((combo_avg_score - overall_avg_score) / overall_avg_score) * 100
				else:
					difference = 0
				
				# 임계값 이상 차이날 때만 엣지케이스로 분류
				if abs(difference) >= EVALUATION_CROSS_ANALYSIS_DIFFERENCE_THRESHOLD:
					edge_case = {
						"question_title": question_title,
						"label": label,
						"overall_pct": overall_avg_score,
						"combo_pct": combo_avg_score,
						"difference": difference,
						"segment_combination": seg_values,
						"label_count": combo_count,
						"response_count": len(filtered_rows)
					}
					edge_cases.append(edge_case)
			else:
				# 일반 교차분석 (기존 로직)
				# 해당 조합에서의 라벨 비율 계산 (최적화)
				combo_label_responses = sum(1 for row in filtered_rows if (row.get(label_key) or "").strip() == label)
				combo_pct = _calculate_percentage(combo_label_responses, len(filtered_rows))
				
				# 0% 응답은 제외 (의미 있는 엣지케이스가 아님)
				if combo_pct == 0:
					continue
				
				# 차이 계산
				difference = _calculate_cross_analysis_difference(overall_pct, combo_pct)
				
				# 임계값 이상 차이날 때만 엣지케이스로 분류
				if difference >= CROSS_ANALYSIS_DIFFERENCE_THRESHOLD:
					edge_case = {
						"question_title": question_title,
						"label": label,
						"overall_pct": overall_pct,
						"combo_pct": combo_pct,
						"difference": difference,
						"segment_combination": seg_values,
						"response_count": len(filtered_rows),
						"label_count": combo_label_responses
					}
					edge_cases.append(edge_case)
	
	# 교차분석 진행률 표시 (문항별로 표시하지 않음)
	# 문자와 응답별로 한 번씩만 점 표시
	print(".", end="", flush=True)
	
	# 차이 크기 순으로 정렬하고 반환
	edge_cases.sort(key=lambda x: x["difference"], reverse=True)
	return edge_cases

def _generate_segment_value_combinations(seg_values_map: Dict[str, set]) -> List[Dict[str, str]]:
	"""세그먼트 값들의 모든 조합을 생성합니다. (성능 최적화)"""
	if not seg_values_map:
		return []
	
	segments = list(seg_values_map.keys())
	values_lists = [sorted(list(seg_values_map[seg])) for seg in segments]  # 정렬로 일관성 확보
	
	# 성능 최적화: 조합 수 사전 계산
	total_combinations = 1
	for values in values_lists:
		total_combinations *= len(values)
	
	# 조합이 너무 많으면 제한 (메모리 보호)
	if total_combinations > 10000:
		# 상위 빈도 값들만 사용하여 조합 수 제한
		limited_values_lists = []
		for values in values_lists:
			if len(values) > 5:  # 5개 이상이면 상위 5개만 사용
				limited_values_lists.append(values[:5])
			else:
				limited_values_lists.append(values)
		values_lists = limited_values_lists
	
	combinations_list = []
	
	def generate_combinations(current_combo: Dict[str, str], seg_index: int):
		if seg_index == len(segments):
			combinations_list.append(current_combo.copy())
			return
		
		current_seg = segments[seg_index]
		for value in values_lists[seg_index]:
			current_combo[current_seg] = value
			generate_combinations(current_combo, seg_index + 1)
	
	generate_combinations({}, 0)
	return combinations_list

def _extract_comments_for_segment_combination(question_rows: List[Dict[str, str]], segment_combination: Dict[str, str], target_label: str = None, all_data: List[Dict[str, str]] = None, allowed_sentiments: List[str] = None) -> str:
	"""특정 세그먼트 조합에서 특정 답변을 선택한 고객들의 answ_id를 찾아서 모든 문항의 LLM 분석 결과를 추출합니다."""
	# all_data에서 해당 조합에 해당하는 응답들 필터링 (전체 데이터에서 직접 필터링)
	if all_data:
		filtered_rows = [row for row in all_data 
						if all((row.get(seg) or "").strip() == value for seg, value in segment_combination.items())]
	else:
		# all_data가 없으면 question_rows에서 필터링
		filtered_rows = [row for row in question_rows 
						if all((row.get(seg) or "").strip() == value for seg, value in segment_combination.items())]
	
	if not filtered_rows:
		return ""
	
	# 특정 답변을 선택한 응답자들의 answ_id 수집
	target_answ_ids = set()
	if target_label:
		# answ_id별로 그룹화하여 중복 제거
		answ_id_to_rows = {}
		for row in filtered_rows:
			answ_id = (row.get("answ_id") or "").strip()
			if answ_id:
				if answ_id not in answ_id_to_rows:
					answ_id_to_rows[answ_id] = []
				answ_id_to_rows[answ_id].append(row)
		
		# 각 answ_id에 대해 target_label과 일치하는 행이 있는지 확인
		for answ_id, rows in answ_id_to_rows.items():
			for row in rows:
				label_content = (row.get("lkng_cntnt") or "").strip()
				answer_content = (row.get("answ_cntnt") or "").strip()
				
				if label_content == target_label or answer_content == target_label:
					target_answ_ids.add(answ_id)
					break  # 해당 answ_id에 대해 일치하는 행을 찾았으면 다음 answ_id로
		
	else:
		# target_label이 없으면 모든 응답자의 answ_id 수집
		for row in filtered_rows:
			answ_id = (row.get("answ_id") or "").strip()
			if answ_id:
				target_answ_ids.add(answ_id)
	
	if not target_answ_ids or not all_data:
		return ""
	
	# 해당 answ_id들의 모든 문항에서 LLM 분석 결과 수집
	analysis_data = []
	for row in all_data:
		answ_id = (row.get("answ_id") or "").strip()
		if answ_id in target_answ_ids:
			qtype_code = (row.get("qsit_type_ds_cd") or "").strip()
			text_yn = (row.get("text_yn") or "").strip()
			
			# 응답 내용 길이 체크 (최소 길이 미만이면 제외)
			answ_cntnt = (row.get("answ_cntnt") or "").strip()
			if len(answ_cntnt) < MIN_RESPONSE_LENGTH:
				continue
			
			# 기타의견 (text_yn=1인 경우)
			if qtype_code == "10" and text_yn in ("1", "Y", "y"):
				llm_level1 = (row.get("llm_level1") or "").strip()
				# 카테고리 앞의 "NN. " 형태 숫자 제거
				import re
				llm_level1 = re.sub(r'^\d+\.\s*', '', llm_level1)
				# "기타 피드백"을 "기타"로 통합
				if llm_level1 == '기타 피드백':
					llm_level1 = '기타'
				sentiment = (row.get("sentiment") or "").strip()
				keywords = (row.get("keywords") or "").strip()
				
				if llm_level1 and keywords:
					analysis_data.append({
						"category": llm_level1,
						"sentiment": sentiment,
						"keywords": keywords
					})
			
			# 주관식 응답
			elif qtype_code == "20":
				llm_level1 = (row.get("llm_level1") or "").strip()
				# 카테고리 앞의 "NN. " 형태 숫자 제거
				import re
				llm_level1 = re.sub(r'^\d+\.\s*', '', llm_level1)
				# "기타 피드백"을 "기타"로 통합
				if llm_level1 == '기타 피드백':
					llm_level1 = '기타'
				sentiment = (row.get("sentiment") or "").strip()
				keywords = (row.get("keywords") or "").strip()
				
				if llm_level1 and keywords:
					analysis_data.append({
						"category": llm_level1,
						"sentiment": sentiment,
						"keywords": keywords
					})
	
	if not analysis_data:
		return ""
	
	# 카테고리별로 그룹화하여 빈도 계산 (제외 카테고리 필터링)
	from collections import Counter
	
	# sentiment 필터링 적용
	filtered_analysis_data = analysis_data
	if allowed_sentiments:
		# 감정 매핑 (새로운 sentiment 분류 반영)
		sentiment_map = {
			"긍정": "긍정",
			"부정": "부정", 
			"제안": "제안",
			"문의": "문의",
			"무응답": "무응답",
			"positive": "긍정",
			"negative": "부정",
			"suggestion": "제안",
			"inquiry": "문의",
			"no_response": "무응답"
		}
		filtered_analysis_data = [data for data in analysis_data 
								if sentiment_map.get(data.get("sentiment", ""), "무응답") in allowed_sentiments]
	
	categories = [data["category"] for data in filtered_analysis_data if data["category"] and data["category"] not in SUBJECTIVE_EXCLUDE_CATEGORIES]
	top_categories = Counter(categories).most_common(3)
	
	# 결과 포맷팅: [감정] llm_category(n) : keywords(n), keywords(n), keywords(n)... 형태
	result_parts = []
	
	for category, count in top_categories:
		# 해당 카테고리의 키워드들과 감정 수집
		category_keywords = []
		category_sentiments = []
		for data in filtered_analysis_data:
			if data["category"] == category:
				if data.get("keywords"):
					keywords_list = [kw.strip() for kw in data["keywords"].split(",") if kw.strip()]
					category_keywords.extend(keywords_list)
				if data.get("sentiment"):
					category_sentiments.append(data["sentiment"])
		
		# 키워드 빈도 계산 (제외 키워드 필터링)
		filtered_keywords = [kw for kw in category_keywords if kw not in SUBJECTIVE_EXCLUDE_KEYWORDS]
		keyword_counts = Counter(filtered_keywords)
		top_keywords_for_category = keyword_counts.most_common(3)
		
		# 감정 빈도 계산 (가장 많은 감정 선택)
		sentiment_counts = Counter(category_sentiments)
		top_sentiment = sentiment_counts.most_common(1)[0][0] if sentiment_counts else "중립"
		
		# 감정을 한글로 변환 (새로운 sentiment 분류 반영)
		sentiment_map = {
			"긍정": "긍정",
			"부정": "부정", 
			"제안": "제안",
			"문의": "문의",
			"무응답": "무응답",
			"positive": "긍정",
			"negative": "부정",
			"suggestion": "제안",
			"inquiry": "문의",
			"no_response": "무응답"
		}
		sentiment_display = sentiment_map.get(top_sentiment, "무응답")
		
		if top_keywords_for_category:
			keyword_text = ", ".join([f"{kw} ({count})" for kw, count in top_keywords_for_category])
			result_parts.append(f"[{sentiment_display}] {html_escape(category)} ({count}) : {html_escape(keyword_text)}")
		else:
			result_parts.append(f"[{sentiment_display}] {html_escape(category)} ({count})")
	
	return "<br>".join(result_parts)
def _analyze_segment_responses_in_other_questions(all_data: List[Dict[str, str]], segment_combination: Dict[str, str], current_question_id: str) -> str:
	"""특정 세그먼트 조합의 고객들이 다른 문항에서 응답한 내용을 분석합니다."""
	# 해당 세그먼트 조합에 해당하는 모든 응답 필터링
	segment_responses = [row for row in all_data 
						if all((row.get(seg) or "").strip() == value for seg, value in segment_combination.items())]
	
	if not segment_responses:
		return ""
	
	
	
	# 현재 문항이 아닌 다른 문항들의 응답 수집
	other_question_responses = {}
	
	for row in segment_responses:
		question_id = (row.get("qsit_id") or "").strip()
		qtype_code = (row.get("qsit_type_ds_cd") or "").strip()
		text_yn = (row.get("text_yn") or "").strip()
		
		# 디버깅: 현재 문항 ID와 다른 문항들 확인
		if question_id != current_question_id:
			if question_id not in other_question_responses:
				other_question_responses[question_id] = []
		
		# 응답 내용 길이 체크 (최소 길이 미만이면 제외)
		answ_cntnt = (row.get("answ_cntnt") or "").strip()
		if len(answ_cntnt) < MIN_RESPONSE_LENGTH:
			continue
		
		# 객관식 응답 (기타의견의 llm 분석 결과만)
		if qtype_code == "10":
				# 기타의견 (text_yn=1인 경우)
				if text_yn in ("1", "Y", "y"):
					llm_level1 = (row.get("llm_level1") or "").strip()
					# 카테고리 앞의 "NN. " 형태 숫자 제거
					import re
					llm_level1 = re.sub(r'^\d+\.\s*', '', llm_level1)
					# "기타 피드백"을 "기타"로 통합
					if llm_level1 == '기타 피드백':
						llm_level1 = '기타'
					sentiment = (row.get("sentiment") or "").strip()
					keywords = (row.get("keywords") or "").strip()
					
					if llm_level1 or sentiment or keywords:
						analysis_text = f"카테고리:{llm_level1}|감정:{sentiment}|키워드:{keywords}"
						other_question_responses[question_id].append(analysis_text)
		
		# 주관식 응답 (llm 분석 결과만)
		elif qtype_code == "20":
			llm_level1 = (row.get("llm_level1") or "").strip()
			# 카테고리 앞의 "NN. " 형태 숫자 제거
			import re
			llm_level1 = re.sub(r'^\d+\.\s*', '', llm_level1)
			# "기타 피드백"을 "기타"로 통합
			if llm_level1 == '기타 피드백':
				llm_level1 = '기타'
			sentiment = (row.get("sentiment") or "").strip()
			keywords = (row.get("keywords") or "").strip()
			
			if llm_level1 or sentiment or keywords:
				analysis_text = f"카테고리:{llm_level1}|감정:{sentiment}|키워드:{keywords}"
				other_question_responses[question_id].append(analysis_text)
	
	if not other_question_responses:
		return ""
	
	# 모든 문항의 llm 분석 결과를 통합
	all_categories = []
	all_sentiments = []
	all_keywords = []
	
	for question_id, responses in other_question_responses.items():
		for response in responses:
			# "카테고리:xxx|감정:yyy|키워드:zzz" 형태 파싱
			parts = response.split("|")
			for part in parts:
				if part.startswith("카테고리:"):
					category = part.replace("카테고리:", "").strip()
					if category:
						all_categories.append(category)
				elif part.startswith("감정:"):
					sentiment = part.replace("감정:", "").strip()
					if sentiment:
						all_sentiments.append(sentiment)
				elif part.startswith("키워드:"):
					keywords = part.replace("키워드:", "").strip()
					if keywords:
						# 키워드가 쉼표로 구분되어 있다면 분리
						keywords_list = [kw.strip() for kw in keywords.split(",") if kw.strip()]
						all_keywords.extend(keywords_list)
	
	# 빈도 계산 (제외 카테고리와 키워드 필터링)
	from collections import Counter
	filtered_categories = [cat for cat in all_categories if cat not in SUBJECTIVE_EXCLUDE_CATEGORIES]
	filtered_keywords = [kw for kw in all_keywords if kw not in SUBJECTIVE_EXCLUDE_KEYWORDS]
	top_categories = Counter(filtered_categories).most_common(2)
	top_sentiments = Counter(all_sentiments).most_common(2)
	top_keywords = Counter(filtered_keywords).most_common(3)
	
	# 결과 포맷팅
	result_parts = []
	
	if top_categories:
		category_text = ", ".join([f"{cat} ({count})" for cat, count in top_categories])
		result_parts.append(f"<strong>카테고리:</strong> {html_escape(category_text)}")
	
	if top_sentiments:
		sentiment_text = ", ".join([f"{sent} ({count})" for sent, count in top_sentiments])
		result_parts.append(f"<strong>감정:</strong> {html_escape(sentiment_text)}")
	
	if top_keywords:
		keyword_text = ", ".join([f"{kw} ({count})" for kw, count in top_keywords])
		result_parts.append(f"<strong>키워드:</strong> {html_escape(keyword_text)}")
	
	return "<br>".join(result_parts)

def _build_evaluation_edge_cases_section(edge_cases: List[Dict], all_labels: List[str] = None, question_rows: List[Dict[str, str]] = None, all_data: List[Dict[str, str]] = None, current_question_id: str = None) -> str:
	"""평가형 문항별 엣지케이스 섹션을 HTML로 생성합니다."""
	if not edge_cases:
		# 교차분석 결과가 없을 때 메시지 표시
		return (
			'<div style="margin:12px 0;padding:12px;border:1px solid #E5E7EB;border-radius:6px;background:#F9FAFB;">'
			+ '<div style="font-weight:700;font-size:14px;color:#111827;margin-bottom:8px;">🔍 교차분석</div>'
			+ '<div style="color:#6B7280;font-size:12px;">🔍 평균 대비 편차가 큰 Seg.가 없습니다</div>'
			+ '</div>'
		)
	
	# 엣지케이스를 상위/하위로 분류
	above_cases = []
	below_cases = []
	
	for case in edge_cases:
		if case["difference"] > 0:
			above_cases.append(case)
		else:
			below_cases.append(case)
	
	# 상위/하위 엣지케이스 정렬
	above_cases.sort(key=lambda x: x["difference"], reverse=True)
	below_cases.sort(key=lambda x: x["difference"])
	
	# 최대 개수 제한
	above_cases = above_cases[:CROSS_ANALYSIS_MAX_CASES_PER_CELL]
	below_cases = below_cases[:CROSS_ANALYSIS_MAX_CASES_PER_CELL]
	
	# 전체 평균 점수 계산 (제목에 표시용)
	total_score = 0
	total_count = 0
	label_to_score = {
		"매우 만족해요": 5, "만족해요": 4, "보통이에요": 3, "불만족해요": 2, "매우 불만족해요": 1
	}
	for row in question_rows:
		response = (row.get("lkng_cntnt") or row.get("answ_cntnt") or "").strip()
		# 텍스트 라벨인 경우
		if response in label_to_score:
			total_score += label_to_score[response]
			total_count += 1
		# 숫자 응답인 경우 (1-7 스케일)
		elif response.isdigit():
			score = int(response)
			if 1 <= score <= 7:  # 1-7 스케일
				total_score += score
				total_count += 1
	overall_avg_score = total_score / total_count if total_count > 0 else 0
	
	html = f"""
	<div style="margin-top:16px;padding:16px;background:#E5E7EB;border-radius:6px;border:1px solid #E2E8F0;">
		<h4 style="margin:0 0 8px 0;color:#1E293B;font-size:13px;font-weight:700;">🔍 전체 평균({overall_avg_score:.1f}점) 대비 편차가 큰 응답의 Seg. 교차 분석</h4>
		<p style="margin:0 0 12px 0;color:#64748B;font-size:12px;line-height:1.4;">
			전체 평균 점수 대비 <strong>{EVALUATION_CROSS_ANALYSIS_DIFFERENCE_THRESHOLD}%</strong> 이상 차이가 나는 Seg.조합과 해당 응답자들의 주관식 답변 키워드 교차 분석
		</p>
		<table style="width:100%;border-collapse:collapse;background:#FFFFFF;border-radius:4px;overflow:hidden;box-shadow:0 1px 2px rgba(0,0,0,0.05);border:1px solid #CBD5E1;">
			<thead>
				<tr style="background:#374151;">
					<th style="padding:8px;text-align:center;font-size:12px;font-weight:600;color:#FFFFFF;border:1px solid #CBD5E1;width:1fr;">평균 상회 ({EVALUATION_CROSS_ANALYSIS_DIFFERENCE_THRESHOLD}% 이상 높음)</th>
					<th style="padding:8px;text-align:center;font-size:12px;font-weight:600;color:#FFFFFF;border:1px solid #CBD5E1;width:1fr;">평균 하회 ({EVALUATION_CROSS_ANALYSIS_DIFFERENCE_THRESHOLD}% 이상 낮음)</th>
				</tr>
			</thead>
			<tbody>
	"""
	
	# 상위 엣지케이스 HTML 생성
	cases_html = []
	for case in above_cases:
		seg_combo_parts = []
		for seg, value in case["segment_combination"].items():
			display_value = get_segment_display_value(seg, value)
			seg_combo_parts.append(display_value)
		seg_combo_clean = " & ".join(seg_combo_parts)
		# 한 줄로 표시
		seg_combo_formatted = seg_combo_clean
		
		# LLM 분석 결과 추출 (전체 평균 기준이므로 label은 None으로 전달, 평균 상회는 긍정+중립만)
		segment_keywords = _extract_comments_for_segment_combination(question_rows, case["segment_combination"], None, all_data, ["긍정", "중립"])
		keywords_display = ""
		if segment_keywords:
			keywords_display = f"<div style='margin-top:4px;margin-left:8px;margin-right:4px;padding:4px;border:1px solid #E2E8F0;border-radius:6px;font-size:11px;color:#374151;line-height:1.3;'>{segment_keywords}</div>"
		
		cases_html.append(f"""
			<div style="margin-bottom:8px;">
				<div style="color:#1F2937;font-size:12px;line-height:1.2;margin-bottom:2px;font-weight:600;">• {seg_combo_formatted} : <span style="font-weight:600;color:#DC2626;">+{case["difference"]:.1f}% ({case["combo_pct"]:.1f}점, {case["response_count"]}건)</span></div>
				{keywords_display}
			</div>
		""")
	
	above_cell = "".join(cases_html) if cases_html else '<div style="text-align:center;color:#9CA3AF;font-size:12px;">-</div>'
	
	# 하위 엣지케이스 HTML 생성
	cases_html = []
	for case in below_cases:
		seg_combo_parts = []
		for seg, value in case["segment_combination"].items():
			display_value = get_segment_display_value(seg, value)
			seg_combo_parts.append(display_value)
		seg_combo_clean = " & ".join(seg_combo_parts)
		# 한 줄로 표시
		seg_combo_formatted = seg_combo_clean
		
		# LLM 분석 결과 추출 (전체 평균 기준이므로 label은 None으로 전달, 평균 하회는 부정+중립만)
		segment_keywords = _extract_comments_for_segment_combination(question_rows, case["segment_combination"], None, all_data, ["부정", "중립"])
		keywords_display = ""
		if segment_keywords:
			keywords_display = f"<div style='margin-top:4px;margin-left:8px;margin-right:4px;padding:4px;border:1px solid #E2E8F0;border-radius:6px;font-size:11px;color:#374151;line-height:1.3;'>{segment_keywords}</div>"
		
		cases_html.append(f"""
			<div style="margin-bottom:8px;">
				<div style="color:#1F2937;font-size:12px;line-height:1.2;margin-bottom:2px;font-weight:600;">• {seg_combo_formatted} : <span style="font-weight:600;color:#1D4ED8;">-{abs(case["difference"]):.1f}% ({case["combo_pct"]:.1f}점, {case["response_count"]}건)</span></div>
				{keywords_display}
			</div>
		""")
	
	below_cell = "".join(cases_html) if cases_html else '<div style="text-align:center;color:#9CA3AF;font-size:12px;">-</div>'
	
	# 단일 행으로 표시 (구분 열 제거, 두 컬럼 균등 분할)
	html += f"""
		<tr>
			<td style="padding:8px;border:1px solid #CBD5E1;vertical-align:top;font-size:12px;width:50%;">{above_cell}</td>
			<td style="padding:8px;border:1px solid #CBD5E1;vertical-align:top;font-size:12px;width:50%;">{below_cell}</td>
		</tr>
	"""
	
	html += """
			</tbody>
		</table>
	</div>
	"""
	
	return html
def _build_question_edge_cases_section(edge_cases: List[Dict], all_labels: List[str] = None, question_rows: List[Dict[str, str]] = None, all_data: List[Dict[str, str]] = None, current_question_id: str = None) -> str:
	"""문항별 엣지케이스 섹션을 새로운 방식으로 HTML로 생성합니다."""
	if not edge_cases:
		return ""
	
	# 세그먼트 한글명 매핑
	seg_korean_names = {
		"gndr_seg": "성별",
		"account_seg": "계좌고객",
		"age_seg": "연령대",
		"rgst_gap": "가입경과일",
		"vasp": "VASP 연결",
		"dp_seg": "수신상품 가입",
		"loan_seg": "대출상품 가입",
		"card_seg": "카드상품 가입",
		"suv_seg": "서비스 이용"
	}
	
	# 엣지케이스를 답변별로 그룹화하고 차이값 내림차순으로 정렬
	label_groups = {}
	for case in edge_cases:
		label = case["label"]
		if label not in label_groups:
			label_groups[label] = {"above": [], "below": []}
		
		# 평균보다 높은지 낮은지 구분
		if case["combo_pct"] > case["overall_pct"]:
			label_groups[label]["above"].append(case)
		else:
			label_groups[label]["below"].append(case)
	
	# 각 그룹을 차이값 내림차순으로 정렬하고 최대 개수만 유지
	for label in label_groups:
		label_groups[label]["above"].sort(key=lambda x: x["difference"], reverse=True)
		label_groups[label]["below"].sort(key=lambda x: x["difference"], reverse=True)
		label_groups[label]["above"] = label_groups[label]["above"][:CROSS_ANALYSIS_MAX_CASES_PER_CELL]
		label_groups[label]["below"] = label_groups[label]["below"][:CROSS_ANALYSIS_MAX_CASES_PER_CELL]
	
	# 모든 답변 라벨 수집 (엣지케이스가 없는 답변도 포함)
	if all_labels is None:
		all_labels = set()
		for case in edge_cases:
			all_labels.add(case["label"])
		all_labels = list(all_labels)
	
	# 전체 응답에서 각 라벨의 비율 계산
	label_overall_pcts = {}
	for label in all_labels:
		# 해당 라벨의 전체 비율 찾기
		for case in edge_cases:
			if case["label"] == label:
				label_overall_pcts[label] = case["overall_pct"]
				break
	
	# 답변별로 정렬 (전체 비율 높은 순)
	sorted_labels = sorted(all_labels, key=lambda x: label_overall_pcts.get(x, 0), reverse=True)
	
	html = f"""
	<div style="margin-top:16px;padding:16px;background:#E5E7EB;border-radius:6px;border:1px solid #E2E8F0;">
		<h4 style="margin:0 0 8px 0;color:#1E293B;font-size:13px;font-weight:700;">🔍 평균 대비 편차가 큰 답변의 교차 분석</h4>
		<p style="margin:0 0 12px 0;color:#64748B;font-size:12px;line-height:1.4;">
			전체 응답 대비 <strong>{CROSS_ANALYSIS_DIFFERENCE_THRESHOLD}%p</strong> 이상 차이가 나는 Seg.조합과 해당 응답자들의 주관식 답변 키워드 교차 분석
		</p>
		<table style="width:100%;border-collapse:collapse;background:#FFFFFF;border-radius:4px;overflow:hidden;box-shadow:0 1px 2px rgba(0,0,0,0.05);border:1px solid #CBD5E1;table-layout:fixed;">
			<thead>
				<tr style="background:#374151;">
					<th style="padding:8px;text-align:center;font-size:12px;font-weight:600;color:#FFFFFF;border:1px solid #CBD5E1;width:120px;">구분</th>
					<th style="padding:8px;text-align:center;font-size:12px;font-weight:600;color:#FFFFFF;border:1px solid #CBD5E1;width:calc((100% - 120px) / 2);">평균 상회 ({CROSS_ANALYSIS_DIFFERENCE_THRESHOLD}%p 이상 높음)</th>
					<th style="padding:8px;text-align:center;font-size:12px;font-weight:600;color:#FFFFFF;border:1px solid #CBD5E1;width:calc((100% - 120px) / 2);">평균 하회 ({CROSS_ANALYSIS_DIFFERENCE_THRESHOLD}%p 이상 낮음)</th>
				</tr>
			</thead>
			<tbody>
	"""
	# 답변별로 행 생성 (엣지케이스가 있는 답변만)
	for label in sorted_labels:
		overall_pct = label_overall_pcts.get(label, 0)
		above_cases = label_groups.get(label, {}).get("above", [])
		below_cases = label_groups.get(label, {}).get("below", [])
		
		# 엣지케이스가 없는 답변은 행을 생성하지 않음
		if not above_cases and not below_cases:
			continue
		
		# 해당 라벨의 모든 엣지케이스에서 의견 수집
		all_comments = []
		for case in above_cases + below_cases:
			comments = _extract_comments_for_segment_combination(question_rows, case["segment_combination"], label, all_data)
			if comments:
				all_comments.append(comments)
		
		# 의견들을 구분자로 연결
		comments_display = "<br><br>".join(all_comments[:2]) if all_comments else "-"
		
		html += f"""
				<tr>
					<td style="padding:8px;text-align:center;font-size:12px;font-weight:600;color:#475569;border:1px solid #CBD5E1;vertical-align:top;background:#F8FAFC;">
						{html_escape(label)}<br><span style="font-size:12px;color:#64748B;">(전체 {overall_pct:.1f}%)</span>
					</td>
		"""
		
		# 평균 상회 셀
		if above_cases:
			cases_html = []
			for case in above_cases:
				seg_combo_parts = []
				for seg, value in case["segment_combination"].items():
					display_value = get_segment_display_value(seg, value)
					seg_combo_parts.append(display_value)
				seg_combo_clean = " & ".join(seg_combo_parts)
				# 한 줄로 표시
				seg_combo_formatted = seg_combo_clean
				
				# 해당 세그먼트의 주관식/기타의견 키워드 추출 (현재 문항, 평균 상회는 긍정+중립만)
				segment_keywords = _extract_comments_for_segment_combination(question_rows, case["segment_combination"], label, all_data, ["긍정", "중립"])
				keywords_display = ""
				if segment_keywords:
					keywords_display = f"<div style='margin-top:4px;margin-left:8px;margin-right:4px;padding:4px;border:1px solid #E2E8F0;border-radius:6px;font-size:11px;color:#374151;line-height:1.3;'>{segment_keywords}</div>"
				
				cases_html.append(f"""
					<div style="margin-bottom:8px;">
						<div style="color:#1F2937;font-size:12px;line-height:1.2;margin-bottom:2px;font-weight:600;">• {seg_combo_formatted} : <span style="font-weight:600;color:#DC2626;">+{case["difference"]:.1f}%p ({case["combo_pct"]:.1f}%, {case["label_count"]}건/{case["response_count"]}건)</span></div>
						{keywords_display}
					</div>
				""")
			
			html += f"""
                <td style="padding:8px;font-size:12px;color:#1E293B;border:1px solid #CBD5E1;vertical-align:top;">
                    {''.join(cases_html)}
                </td>
			"""
		else:
			html += """
                    <td style="padding:8px;text-align:center;font-size:12px;color:#94A3B8;border:1px solid #CBD5E1;vertical-align:top;">
                        -
                    </td>
			"""
		
		# 평균 하회 셀 (긍정키워드 박스 색상 사용)
		if below_cases:
			cases_html = []
			for case in below_cases:
				seg_combo_parts = []
				for seg, value in case["segment_combination"].items():
					display_value = get_segment_display_value(seg, value)
					seg_combo_parts.append(display_value)
				seg_combo_clean = " & ".join(seg_combo_parts)
				# 한 줄로 표시
				seg_combo_formatted = seg_combo_clean
				
				# 해당 세그먼트의 주관식/기타의견 키워드 추출 (현재 문항, 평균 하회는 부정+중립만)
				segment_keywords = _extract_comments_for_segment_combination(question_rows, case["segment_combination"], label, all_data, ["부정", "중립"])
				keywords_display = ""
				if segment_keywords:
					keywords_display = f"<div style='margin-top:4px;margin-left:8px;margin-right:4px;padding:4px;border:1px solid #E2E8F0;border-radius:6px;font-size:11px;color:#374151;line-height:1.3;'>{segment_keywords}</div>"
				
				cases_html.append(f"""
					<div style="margin-bottom:8px;">
						<div style="color:#1F2937;font-size:12px;line-height:1.2;margin-bottom:2px;font-weight:600;">• {seg_combo_formatted} : <span style="font-weight:600;color:#1D4ED8;">-{case["difference"]:.1f}%p ({case["combo_pct"]:.1f}%, {case["label_count"]}건/{case["response_count"]}건)</span></div>
						{keywords_display}
					</div>
				""")
			
			html += f"""
                <td style="padding:8px;font-size:12px;color:#1E293B;border:1px solid #CBD5E1;vertical-align:top;">
                    {''.join(cases_html)}
                </td>
			"""
		else:
			html += """
                    <td style="padding:8px;text-align:center;font-size:12px;color:#94A3B8;border:1px solid #CBD5E1;vertical-align:top;">
                        -
                    </td>
			"""
		
		html += """
				</tr>
		"""
	
	html += """
			</tbody>
		</table>
	</div>
	"""
	
	return html

def _build_edge_cases_section(all_edge_cases: List[Dict]) -> str:
	"""엣지케이스 섹션을 HTML로 생성합니다."""
	if not all_edge_cases:
		return ""
	
	# 세그먼트 한글명 매핑
	seg_korean_names = {
		"gndr_seg": "성별",
		"account_seg": "계좌고객",
		"age_seg": "연령대",
		"rgst_gap": "가입경과일",
		"vasp": "VASP 연결",
		"dp_seg": "수신상품 가입",
		"loan_seg": "대출상품 가입",
		"card_seg": "카드상품 가입",
		"suv_seg": "서비스 이용"
	}
	
	html = f"""
	<div style="margin-top:32px;padding:24px;background:#F9FAFB;border-radius:8px;border:1px solid #E5E7EB;">
		<h3 style="margin:0 0 16px 0;color:#111827;font-size:18px;font-weight:700;">🔍 교차분석 엣지케이스</h3>
		<p style="margin:0 0 20px 0;color:#6B7280;font-size:14px;line-height:1.5;">
			전체 응답 대비 <strong>{CROSS_ANALYSIS_DIFFERENCE_THRESHOLD}%</strong> 이상 차이가 나는 세그먼트 조합을 분석했습니다.
			(최소 {CROSS_ANALYSIS_MIN_RESPONSES}건 이상 응답, 최대 {CROSS_ANALYSIS_MAX_DIMENSIONS}차원 교차분석)
		</p>
		<table style="width:100%;border-collapse:collapse;background:#FFFFFF;border-radius:6px;overflow:hidden;box-shadow:0 1px 3px rgba(0,0,0,0.1);">
			<thead>
				<tr style="background:#F3F4F6;">
					<th style="padding:12px;text-align:left;font-size:12px;font-weight:600;color:#374151;border-bottom:1px solid #E5E7EB;">문항</th>
					<th style="padding:12px;text-align:left;font-size:12px;font-weight:600;color:#374151;border-bottom:1px solid #E5E7EB;">답변</th>
					<th style="padding:12px;text-align:center;font-size:12px;font-weight:600;color:#374151;border-bottom:1px solid #E5E7EB;">전체</th>
					<th style="padding:12px;text-align:center;font-size:12px;font-weight:600;color:#374151;border-bottom:1px solid #E5E7EB;">세그조합</th>
					<th style="padding:12px;text-align:center;font-size:12px;font-weight:600;color:#374151;border-bottom:1px solid #E5E7EB;">차이</th>
					<th style="padding:12px;text-align:center;font-size:12px;font-weight:600;color:#374151;border-bottom:1px solid #E5E7EB;">응답수</th>
				</tr>
			</thead>
			<tbody>
	"""
	
	for i, case in enumerate(all_edge_cases):
		# 세그먼트 조합을 한글로 변환
		seg_combo_text = []
		for seg, value in case["segment_combination"].items():
			seg_name = seg_korean_names.get(seg, seg)
			seg_value = get_segment_display_value(seg, value)  # 세그먼트 값도 한글로 변환
			seg_combo_text.append(f"{seg_name}: {seg_value}")
		seg_combo_display = " | ".join(seg_combo_text)
		
		# 차이에 따른 색상 결정
		difference = case["difference"]
		if difference >= 30:
			diff_color = "#DC2626"  # 빨간색 (매우 큰 차이)
		elif difference >= 20:
			diff_color = "#EA580C"  # 주황색 (큰 차이)
		else:
			diff_color = "#D97706"  # 노란색 (보통 차이)
		
		# 배경색 (짝수/홀수 행)
		bg_color = "#FFFFFF" if i % 2 == 0 else "#F9FAFB"
		
		html += f"""
				<tr style="background:{bg_color};">
					<td style="padding:12px;font-size:12px;color:#111827;border-bottom:1px solid #F3F4F6;vertical-align:top;">
						{html_escape(case["question_title"][:30])}{"..." if len(case["question_title"]) > 30 else ""}
					</td>
					<td style="padding:12px;font-size:12px;color:#111827;border-bottom:1px solid #F3F4F6;vertical-align:top;">
						{html_escape(case["label"])}
					</td>
					<td style="padding:12px;font-size:12px;color:#6B7280;border-bottom:1px solid #F3F4F6;text-align:center;">
						{case["overall_pct"]:.1f}%
					</td>
					<td style="padding:12px;font-size:12px;color:#6B7280;border-bottom:1px solid #F3F4F6;text-align:center;">
						{case["combo_pct"]:.1f}%
					</td>
					<td style="padding:12px;font-size:12px;color:{diff_color};font-weight:600;border-bottom:1px solid #F3F4F6;text-align:center;">
						+{difference:.1f}%
					</td>
					<td style="padding:12px;font-size:12px;color:#6B7280;border-bottom:1px solid #F3F4F6;text-align:center;">
						{case["response_count"]}건
					</td>
				</tr>
				<tr style="background:{bg_color};">
					<td colspan="6" style="padding:8px 12px;font-size:11px;color:#9CA3AF;border-bottom:1px solid #F3F4F6;">
						세그먼트 조합: {html_escape(seg_combo_display)}
					</td>
				</tr>
		"""
	
	html += """
			</tbody>
		</table>
	</div>
	"""
	
	return html

def build_question_components(question_rows: List[Dict[str, str]], qtype: str, label_order: List[str], question_title: str, all_data: List[Dict[str, str]] = None, question_id: str = None) -> List[str]:
	"""
	문항 타입에 따라 설정된 컴포넌트들을 동적으로 생성합니다.
	
	Args:
		question_rows: 해당 문항의 응답 데이터
		qtype: 문항 타입 (objective, evaluation, subjective 등)
		label_order: 라벨 순서
		question_title: 문항 제목
		all_data: 전체 데이터 (교차분석용)
		question_id: 문항 ID
	
	Returns:
		생성된 컴포넌트 HTML 리스트
	"""
	components = []
	
	# 문항 타입에 따른 컴포넌트 구성 가져오기
	component_config = QUESTION_TYPE_COMPONENTS.get(qtype, ["general_stats"])
	
	# 각 컴포넌트 생성
	for component_type in component_config:
		if component_type == "general_stats":
			# 일반형 응답통계 컴포넌트
			stats_html = build_general_stats_component(question_rows, label_order, question_title)
			if stats_html:
				components.append(stats_html)
				
		elif component_type == "general_heatmap":
			# 일반형 히트맵 컴포넌트 (히트맵만)
			heatmap_html = build_general_heatmap_only(question_rows, label_order, question_title, all_data, question_id)
			if heatmap_html:
				components.append(heatmap_html)
				
		elif component_type == "general_heatmap_with_cross_analysis":
			# 일반형 히트맵 + 교차분석 컴포넌트
			heatmap_html = build_general_heatmap(question_rows, label_order, question_title, all_data, question_id)
			if heatmap_html:
				components.append(heatmap_html)
				
		elif component_type == "evaluation_heatmap":
			# 평가형 히트맵 컴포넌트 (히트맵만)
			eval_heatmap_html = build_evaluation_heatmap_only(question_rows, label_order, question_title, all_data, question_id)
			if eval_heatmap_html:
				components.append(eval_heatmap_html)
				
		elif component_type == "evaluation_heatmap_with_cross_analysis":
			# 평가형 히트맵 + 교차분석 컴포넌트
			eval_heatmap_html = build_objective_evaluation_heatmap(question_rows, label_order, question_title, all_data, question_id)
			if eval_heatmap_html:
				components.append(eval_heatmap_html)
				
		elif component_type == "ranking_stats":
			# 순위형 응답통계 컴포넌트
			ranking_stats_html = build_ranking_stats_component(question_rows, label_order, question_title)
			if ranking_stats_html:
				components.append(ranking_stats_html)
				
		elif component_type == "ranking_chart":
			# 순위형 차트 컴포넌트
			ranking_chart_html = build_ranking_chart_component(question_rows, label_order, question_title)
			if ranking_chart_html:
				components.append(ranking_chart_html)
				
		elif component_type == "subjective_summary":
			# 주관식 요약 컴포넌트
			subjective_html = build_subjective_summary_component(question_rows, question_title)
			if subjective_html:
				components.append(subjective_html)
				
	
	return components

def build_general_stats_component(question_rows: List[Dict[str, str]], label_order: List[str], question_title: str) -> str:
	"""일반형 응답통계 컴포넌트를 생성합니다."""
	if not question_rows:
		return ""
	
	# 문항 타입 확인
	qtype = get_question_type(question_rows)
	
	# 응답 통계 계산
	ordered_counts = {}
	
	if qtype == "subjective":
		# 주관식의 경우: 유효한 응답만 카운트
		valid_responses = 0
		for row in question_rows:
			# 주관식의 경우 answ_cntnt 필드 확인
			content = (row.get("answ_cntnt") or "").strip()
			if content and content not in {".", "0", "-", "N/A", "NA", "null", "NULL", "미응답", "무응답"}:
				valid_responses += 1
		
		if valid_responses > 0:
			ordered_counts["응답"] = valid_responses
	else:
		# 객관식 계열의 경우: label_order 기반으로 처리
		if label_order:
			for row in question_rows:
				label = (row.get("lkng_cntnt") or "").strip()
				if label in label_order:
					ordered_counts[label] = ordered_counts.get(label, 0) + 1
	
	if not ordered_counts:
		return ""
	
	# 평가형 문항의 경우 특별한 정렬 적용
	if qtype == "evaluation" or is_evaluation_pattern(list(ordered_counts.keys())):
		# 평가형 문항의 점수 매핑 (높은 점수부터)
		evaluation_scores = {
			"매우 만족해요": 5,
			"만족해요": 4,
			"보통이에요": 3,
			"불만족해요": 2,
			"매우 불만족해요": 1
		}
		
		# 막대그래프와 범례 모두 점수 기준 내림차순 정렬 (높은 점수부터)
		items = []
		for label in label_order:
			if label in ordered_counts:
				items.append((label, ordered_counts[label]))
		items.sort(key=lambda x: evaluation_scores.get(x[0], 0), reverse=True)
		
		# 범례: 막대그래프와 동일한 순서로 정렬
		legend_items = items.copy()
		
		# 막대그래프: 막대그래프와 동일한 순서로 정렬
		chart_items = items.copy()
		
		legend_html = build_legend_table_from_items_heatmap_evaluation_with_numbers(legend_items)
		chart_html = build_stacked_bar_html_ordered_height_heatmap(chart_items, 110)
	else:
		# 일반 문항의 경우: answ_cntnt 값의 오름차순으로 정렬
		items = []
		for label in label_order:
			if label in ordered_counts:
				items.append((label, ordered_counts[label]))
		
		# answ_cntnt 값의 오름차순으로 정렬 (숫자 우선, 그 다음 문자열)
		def sort_key_for_general(label):
			# 숫자인 경우 숫자로 변환
			try:
				return (0, float(label))
			except ValueError:
				return (1, label)
		
		items.sort(key=lambda x: sort_key_for_general(x[0]))
		
		legend_html = build_legend_table_from_items_heatmap_with_numbers(items)
		chart_html = build_stacked_bar_html_ordered_height_heatmap(items, 110)
	long_legend = False  # PRIMARY_PALETTE 사용 시 항상 가로 배치
	
	if not long_legend:
		# 기존: 좌(그래프 60%) - 우(범례 40%) 배치
		layout_html = (
			'<table role="presentation" cellpadding="0" cellspacing="0" border="0" '
			'style="width:100%;border-collapse:collapse;table-layout:fixed;margin-bottom:5px;">'
			+ '<tbody><tr>'
			+ f'<td style="padding:0 0 0 12px;vertical-align:top;width:60%;">{chart_html}</td>'
			+ '<td style="width:12px;line-height:0;font-size:0;">&nbsp;</td>'
			+ f'<td style="padding:0 12px 0 0;vertical-align:top;width:40%;">{legend_html}</td>'
			+ '</tr></tbody></table>'
		)
	else:
		# 세로 배치: 1행(그래프 100%), 2행(간격 8px), 3행(범례 100%)
		layout_html = (
			'<table role="presentation" cellpadding="0" cellspacing="0" border="0" '
			'style="width:100%;border-collapse:collapse;table-layout:fixed;margin-bottom:5px;">'
			+ '<tbody>'
			+ f'<tr><td style="padding:0 12px 0 12px;vertical-align:top;width:100%;">{chart_html}</td></tr>'
			+ '<tr><td style="height:8px;line-height:8px;font-size:0;">&nbsp;</td></tr>'
			+ f'<tr><td style="padding:0 12px 0 12px;vertical-align:top;width:100%;">{legend_html}</td></tr>'
			+ '</tbody></table>'
		)
	# 총 응답 수 계산
	total_responses = sum(ordered_counts.values()) if ordered_counts else 0
	total_responses_formatted = f"{total_responses:,}"
	
	# 기존과 동일한 스타일로 HTML 생성
	stats_html = (
		'<div style="margin:12px 0 12px 0;padding:12px;border:1px solid #E5E7EB;border-radius:6px;background:#F9FAFB;">'
		+ f'<div style="font-weight:700;font-size:14px;color:#111827;margin-bottom:8px;">응답통계 (n={total_responses_formatted})</div>'
		+ layout_html
		+ '</div>'
	)
	
	return stats_html

def build_ranking_stats_component(question_rows: List[Dict[str, str]], label_order: List[str], question_title: str) -> str:
	"""순위형 응답통계 컴포넌트를 생성합니다."""
	# 순위형 통계 로직 구현 (기존 순위형 로직 활용)
	return build_general_stats_component(question_rows, label_order, question_title)

def build_ranking_chart_component(question_rows: List[Dict[str, str]], label_order: List[str], question_title: str) -> str:
	"""순위형 차트 컴포넌트를 생성합니다."""
	# 기존 순위형 차트 로직 활용
	if not question_rows or not label_order:
		return ""
	
	# 간단한 순위 차트 HTML 생성
	chart_html = '<div style="margin:12px 0;padding:12px;border:1px solid #E5E7EB;border-radius:6px;background:#FFFFFF;">'
	chart_html += f'<h4 style="margin:0 0 12px 0;color:#1E293B;font-size:14px;font-weight:700;">📈 순위 차트</h4>'
	chart_html += '<div style="color:#6B7280;font-size:12px;">순위형 차트 구현 예정</div>'
	chart_html += '</div>'
	
	return chart_html

def build_subjective_summary_component(question_rows: List[Dict[str, str]], question_title: str) -> str:
	"""주관식 요약 컴포넌트를 생성합니다."""
	if not question_rows:
		return ""
	
	# 주관식 총 응답 수 계산
	total_subjective_responses = len(question_rows)
	total_subjective_responses_formatted = f"{total_subjective_responses:,}"
	
	# 기존과 동일한 스타일로 HTML 생성
	summary_html = (
		'<div style="margin:12px 0;padding:12px;border:1px solid #E5E7EB;border-radius:6px;background:#F9FAFB;">'
		+ f'<div style="font-weight:700;font-size:14px;color:#111827;margin-bottom:8px;">주관식 요약 (n={total_subjective_responses_formatted})</div>'
		+ build_subjective_section(question_rows)
		+ '</div>'
	)
	
	return summary_html
def build_general_heatmap_only(question_rows: List[Dict[str, str]], label_order: List[str], question_title: str = "객관식 문항", all_data: List[Dict[str, str]] = None, question_id: str = None) -> str:
	"""객관식(일반) 문항용 히트맵: 행=세그 버킷, 열=라벨.
	- 만족도 전용 요약/순만족도 없이, 퍼센트 셀만 표시
	- 스타일은 만족도 히트맵과 톤앤매너 일치
	- 교차분석 제외
	"""
	order = list(label_order)
	# 세그 정의: (표시명, 키)
	seg_defs: List[Tuple[str, str]] = [
		("성별", "gndr_seg"),
		("계좌고객", "account_seg"),
		("연령대", "age_seg"),
		("가입경과일", "rgst_gap"),
		("VASP 연결", "vasp"),
		("수신상품 가입", "dp_seg"),
		("대출상품 가입", "loan_seg"),
		("카드상품 가입", "card_seg"),
		("서비스 이용", "suv_seg"),
	]
	# 세그별 버킷 후보(존재하는 것만 사용). 일부는 정해진 순서를 제공
	preferred_orders: Dict[str, List[str]] = {
		"gndr_seg": ["01.남성", "02.여성"],
		"age_seg": ["01.10대","02.20대","03.30대","04.40대","05.50대","06.60대","07.기타"],
	}
	# 버킷 수집
	seg_bucket_rows: List[Tuple[str, List[Dict[str, str]]]] = []
	# 전체(집계) 먼저 한 줄 추가
	seg_bucket_rows.append(("전체", question_rows))
	for seg_title, seg_key in seg_defs:
		vals = set()
		for r in question_rows:
			v = (r.get(seg_key) or "").strip()
			if v:
				vals.add(v)
		# 선호 순서가 있으면 그 순서로, 아니면 문자열 정렬
		if seg_key in preferred_orders:
			ordered_vals = [v for v in preferred_orders[seg_key] if v in vals]
			# 누락분은 사전순으로 뒤에
			remain = sorted([v for v in vals if v not in set(ordered_vals)])
			ordered_vals += remain
		else:
			ordered_vals = sorted(vals)
		for raw_val in ordered_vals:
			# '기타' 버킷 제외
			if clean_axis_label(raw_val) == '기타':
				continue
			bucket_label = f"{seg_title} - {clean_axis_label(raw_val)}"
			rows_subset = [r for r in question_rows if (r.get(seg_key) or '').strip() == raw_val]
			if not rows_subset:
				continue
			seg_bucket_rows.append((bucket_label, rows_subset))

	# 스타일(기존 보고서 톤) - 모든 라인 제거, 헤더/본문 하단 보더 제거
	head_style = 'padding:6px 8px;color:#111827;font-size:12px;text-align:center;'
	# 만족도 라벨 헤더 전용 스타일(패딩 4px, 수직 중앙 정렬)
	label_head_style = 'padding:0 2px;color:#111827;font-size:12px;text-align:center;vertical-align:middle;overflow:hidden;'
	rowhead_style = 'padding:0 8px;color:#111827;font-size:12px;text-align:left;white-space:nowrap;height:20px;vertical-align:middle;'
	# 폰트 크기 12px을 강제(이메일 클라이언트 상속 방지). 숫자 중앙 정렬 및 고정 높이 20px
	cell_style_base = 'padding:0;text-align:center;white-space:nowrap;font-size:11px;line-height:1.2;height:20px;vertical-align:middle;'

	# 기타 항목이 있는지 확인
	has_other = any(lb == "기타" for lb in order)
	
	# 동적 폭 계산: 세그(110) + 값(120) + 스페이서(20) + 기타스페이서(20) + 기타(40) + 나머지항목들(균등분할)
	fixed_width = 110 + 120 + 20  # 세그 + 값 + 스페이서
	if has_other:
		fixed_width += 20 + 60  # 기타스페이서 + 기타 (60px로 변경)
		other_count = 1
		normal_count = len(order) - 1
	else:
		other_count = 0
		normal_count = len(order)
	
	# 모든 히트맵 열을 40px로 고정
	normal_width = 40
	
	# 헤더 구성: 세그먼트(세그/값) | (값-히트맵) 20px | 라벨들(1fr씩) | (히트맵-기타) 20px | 기타
	colgroup = (
		'<col style="width:100px;min-width:100px;max-width:100px;">'  # 세그명 (고정 100px)
		+ '<col style="width:110px;min-width:110px;max-width:110px;">'  # 값 (고정 110px)
		+ '<col style="width:20px;min-width:20px;max-width:20px;">'   # 값-히트맵 간격 (고정 20px)
		+ ''.join(['<col style="width:1fr;">' for _ in range(len(order) - (1 if has_other else 0))])  # 일반 히트맵 열들 (1fr씩 배분)
		+ ('<col style="width:20px;min-width:20px;max-width:20px;">' if has_other else '')  # 히트맵-기타 간격 (고정 20px, 기타가 있을 때만)
		+ ('<col style="width:60px;min-width:60px;max-width:60px;">' if has_other else '')  # 기타 (고정 60px, 기타가 있을 때만)
	)
	head_cells = [
		f'<th style="{head_style}">&nbsp;</th>',
		f'<th style="{head_style}">&nbsp;</th>'
	]
	# (값-히트맵) 갭 헤더(반응형)
	head_cells.append('<th style="padding:0;line-height:0;font-size:0;">&nbsp;</th>')
	# 일반 히트맵 열들 헤더
	for lb in order:
		if lb != "기타":  # 기타가 아닌 열들만
			head_cells.append(
				f'<th style="{label_head_style}"><div style="display:block;width:100%;height:100%;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;line-height:1.2;text-align:center;">{html_escape(_display_label(lb, order))}</div></th>'
			)
	# (히트맵-기타) 갭 헤더(반응형, 기타가 있을 때만)
	if has_other:
		head_cells.append('<th style="padding:0;line-height:0;font-size:0;">&nbsp;</th>')
	# 기타 헤더 (기타가 있을 때만)
	if has_other:
		head_cells.append(
			f'<th style="{label_head_style}"><div style="display:block;width:100%;height:100%;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;line-height:1.2;text-align:center;">{html_escape(_display_label("기타", order))}</div></th>'
		)
	head_html = '<thead><tr>' + ''.join(head_cells) + '</tr></thead>'

	# 바디 생성(두 단계: 데이터 준비 → rowspan 적용하여 렌더)
	rows_data: List[Dict[str, object]] = []
	for name, rows in seg_bucket_rows:
		cnts = {l: 0 for l in order}
		for r in rows:
			label = label_for_row(r, 'objective') or ''
			if label in cnts:
				cnts[label] += 1
		total = sum(cnts.values()) or 1
		# 세그/값 분리
		if ' - ' in name:
			seg_name, seg_value = name.split(' - ', 1)
		else:
			seg_name, seg_value = name, ''
		rows_data.append({
			'seg_name': seg_name,
			'seg_value': seg_value,
			'cnts': cnts,
			'total': total,
		})

	# 전체 행(첫 번째)의 보기별 퍼센트 순위 계산
	if rows_data:
		overall_cnts = rows_data[0]['cnts']  # type: ignore
		overall_total = int(rows_data[0]['total'])  # type: ignore
		overall_pct_map: Dict[str, float] = {lb: (overall_cnts[lb] * 100.0 / (overall_total or 1)) for lb in order}  # type: ignore
		overall_rank: List[str] = sorted(order, key=lambda lb: (-overall_pct_map.get(lb, 0.0), order.index(lb)))

	# 전체 응답 수 계산 (임계치 판단용) - 전체 행의 응답 수 사용
	total_responses = len(question_rows)
	threshold_count = max(int(total_responses * GRAYSCALE_THRESHOLD_PERCENT / 100.0), GRAYSCALE_MIN_COUNT)

	# 동적 색상 스케일링을 위한 최소/최대값 계산 (그레이스케일 대상 제외, 기타 열 제외)
	all_pcts: List[float] = []
	for rd in rows_data:
		cnts = rd['cnts']  # type: ignore
		total = int(rd['total'])
		# 그레이스케일 대상이 아닌 경우만 색상 스케일링에 포함
		if total >= threshold_count:
			# 히트맵 열들의 퍼센트 (기타 열 제외)
			for lb in order:
				if lb != "기타":  # 기타 열은 색상 스케일링에서 제외
					pct = _calculate_percentage(cnts[lb], total)
					all_pcts.append(pct)
	
	min_pct = min(all_pcts) if all_pcts else 0.0
	max_pct = max(all_pcts) if all_pcts else 100.0

	# 기타 열만의 동적 색상 스케일링을 위한 최소/최대값 계산
	other_pcts: List[float] = []
	for rd in rows_data:
		cnts = rd['cnts']  # type: ignore
		total = int(rd['total'])
		if "기타" in cnts:
			pct = _calculate_percentage(cnts["기타"], total)
			other_pcts.append(pct)
	
	min_other_pct = min(other_pcts) if other_pcts else 0.0
	max_other_pct = max(other_pcts) if other_pcts else 100.0

	# 전체 행(첫 번째)의 보기별 퍼센트 순위 계산 (엣지케이스 비교용)
	overall_rank: List[str] = _compute_overall_rank_from_rows_data(rows_data, order)

	# 전체 행(첫 번째)의 보기별 퍼센트 순위 계산 (엣지케이스 비교용)
	overall_rank: List[str] = _compute_overall_rank_from_rows_data(rows_data, order)

	# 전체 행(첫 번째)의 보기별 퍼센트 순위 계산 (엣지케이스 비교용)
	overall_rank: List[str] = _compute_overall_rank_from_rows_data(rows_data, order)

	# 전체 행(첫 번째)의 보기별 퍼센트 순위 계산 (교차분석 엣지케이스 비교용)
	overall_rank: List[str] = _compute_overall_rank_from_rows_data(rows_data, order)

	# 전체 행(첫 번째)의 보기별 퍼센트 순위 계산 (엣지케이스 비교용)
	overall_rank: List[str] = []
	if rows_data:
		overall_cnts = rows_data[0]['cnts']  # type: ignore
		overall_total = int(rows_data[0]['total'])  # type: ignore
		overall_pct_map = {lb: (overall_cnts[lb] * 100.0 / (overall_total or 1)) for lb in order}  # type: ignore
		overall_rank = sorted(order, key=lambda lb: (-overall_pct_map.get(lb, 0.0), order.index(lb)))

	# 전체 행(첫 번째)의 보기별 퍼센트 순위 계산 (엣지케이스 비교용)
	overall_rank: List[str] = []
	if rows_data:
		overall_cnts = rows_data[0]['cnts']  # type: ignore
		overall_total = int(rows_data[0]['total'])  # type: ignore
		overall_pct_map = {lb: (overall_cnts[lb] * 100.0 / (overall_total or 1)) for lb in order}  # type: ignore
		overall_rank = sorted(order, key=lambda lb: (-overall_pct_map.get(lb, 0.0), order.index(lb)))

	# 전체 행(첫 번째)의 보기별 퍼센트 순위 계산 (엣지케이스 비교용)
	overall_rank: List[str] = _compute_overall_rank_from_rows_data(rows_data, order)

	# 세그별 첫번째 인덱스와 rowspan 계산
	first_index: Dict[str, int] = {}
	rowspan_count: Dict[str, int] = {}
	for idx, rd in enumerate(rows_data):
		seg = str(rd['seg_name'])
		if seg not in first_index:
			first_index[seg] = idx
		rowspan_count[seg] = rowspan_count.get(seg, 0) + 1

	# 값 셀 막대 스케일 기준(최대 n)
	max_total = max((int(rd['total']) for rd in rows_data), default=1) or 1

	# 전체 행 기준 보기별 퍼센트 순위(내림차순) 계산
	overall_rank: List[str] = _compute_overall_rank_from_rows_data(rows_data, order)

	body_rows: List[str] = []
	for idx, rd in enumerate(rows_data):
		seg_name = str(rd['seg_name'])
		seg_value = str(rd['seg_value'])
		cnts = rd['cnts']  # type: ignore
		total = int(rd['total'])
		# 세그 그룹 시작 시(첫 그룹 제외) 세그/값 영역에 하나의 연속 라인을 별도 행으로 추가해 끊김 방지
		cells: List[str] = []
		is_edgecase = False
		is_group_start = (idx == first_index.get(seg_name))
		if is_group_start and idx != 0:
			# 전체 폭으로 1px 가로줄을 그려 세그/값/히트맵을 관통
			# 위/아래 간격을 4px씩 확보
			colspan = 3 + (len(order) - (1 if has_other else 0)) + (1 if has_other else 0) + (1 if has_other else 0)  # 세그+값+간격 + 일반히트맵열 + 히트맵-기타간격 + 기타열
			body_rows.append('<tr><td colspan="' + str(colspan) + '" style="padding:4px 0;height:0;line-height:0;"><div style="height:1px;background:repeating-linear-gradient(to right, #E5E7EB 0 2px, transparent 2px 4px);"></div></td></tr>')
		if is_group_start:
			cells.append(f'<td rowspan="{rowspan_count.get(seg_name,1)}" style="{rowhead_style}">{html_escape(seg_name)}</td>')
		# 이 행의 보기별 퍼센트 순위 계산 (엣지케이스 판단용)
		seg_pct_map: Dict[str, float] = {lb: (cnts[lb] * 100.0 / (total or 1)) for lb in order}
		seg_rank: List[str] = sorted(order, key=lambda lb: (-seg_pct_map.get(lb, 0.0), order.index(lb)))
		# 전체 순위가 비어있으면 즉시 계산하여 안전하게 사용
		if not overall_rank and rows_data:
			overall_cnts = rows_data[0]['cnts']  # type: ignore
			overall_total = int(rows_data[0]['total'])  # type: ignore
			overall_pct_map = {lb: (overall_cnts[lb] * 100.0 / (overall_total or 1)) for lb in order}  # type: ignore
			overall_rank = sorted(order, key=lambda lb: (-overall_pct_map.get(lb, 0.0), order.index(lb)))
		is_edgecase = (seg_value != '' and bool(orank) and seg_rank != orank)

		# 이 행의 보기별 퍼센트 순위 계산 (엣지케이스 판단용)
		seg_pct_map: Dict[str, float] = {lb: (cnts[lb] * 100.0 / (total or 1)) for lb in order}
		seg_rank: List[str] = sorted(order, key=lambda lb: (-seg_pct_map.get(lb, 0.0), order.index(lb)))
		orank: List[str] = _compute_overall_rank_from_rows_data(rows_data, order)
		is_edgecase = (seg_value != '' and bool(orank) and seg_rank != orank)

		# 이 행의 보기별 퍼센트 순위 계산 (엣지케이스 판단용)
		seg_pct_map: Dict[str, float] = {lb: (cnts[lb] * 100.0 / (total or 1)) for lb in order}
		seg_rank: List[str] = sorted(order, key=lambda lb: (-seg_pct_map.get(lb, 0.0), order.index(lb)))
		orank: List[str] = _compute_overall_rank_from_rows_data(rows_data, order)
		is_edgecase = (seg_value != '' and bool(orank) and seg_rank != orank)

		# 값 열: 100% 폭 테이블 + 좌측 bar TD(비율, 텍스트 포함) + 우측 여백 TD(잔여)
		bar_w = int(round((total / (max_total or 1)) * 100))
		bar_w_css = max(1, bar_w)  # 폭 0%에서도 텍스트가 보이도록 최소 1px 확보
		# 값셀 좌우 여백 제거(패딩 0)
		value_td_style = 'padding:0;color:#111827;font-size:12px;text-align:left;white-space:nowrap;height:20px;position:relative;overflow:hidden;vertical-align:middle;'
		# 값 열: 100% 폭 테이블 + 좌측 bar TD(비율, 텍스트 포함) + 우측 여백 TD(잔여)
		bar_html = (
			'<table role="presentation" cellpadding="0" cellspacing="0" border="0" style="border-collapse:collapse;width:100%;height:20px;table-layout:fixed;">'
			'<tr>'
			f'<td width="{bar_w_css}%" style="height:20px;line-height:20px;vertical-align:middle;'
			+ ("background-color:#FECACA;" if is_edgecase else "background-color:#D1D5DB;")
			+ 'padding:0;color:#111827;font-size:11px;white-space:nowrap;overflow:visible;">'
			+ f'<span style="margin-left:4px;{("box-shadow: inset 0 0 0 2px #EF4444;" if is_edgecase else "")}">{html_escape(seg_value)}'
			+ f'<span style="color:#6B7280;margin-left:6px;">(n={total:,})</span></span>'
			+ '</td>'
			f'<td width="{100 - bar_w_css}%" style="height:20px;line-height:20px;vertical-align:middle;padding:0;margin:0;"></td>'
			+ '</tr></table>'
		)
		text_html = ''
		if seg_value:
			cells.append(f'<td style="{value_td_style}">{bar_html}{text_html}</td>')
		else:
			# 전체 행도 동일한 방식으로 표시
			bar_html = (
				'<table role="presentation" cellpadding="0" cellspacing="0" border="0" style="border-collapse:collapse;width:100%;height:20px;table-layout:fixed;">'
				'<tr>'
				f'<td width="{bar_w_css}%" style="height:20px;line-height:20px;vertical-align:middle;background-color:#D1D5DB;padding:0;color:#111827;font-size:11px;white-space:nowrap;overflow:visible;">'
				+ '<span style="margin-left:4px;">전체'
				+ f'<span style="color:#6B7280;margin-left:6px;">(n={total:,})</span></span>'
				+ '</td>'
				f'<td width="{100 - bar_w_css}%" style="height:20px;line-height:20px;vertical-align:middle;padding:0;margin:0;"></td>'
				+ '</tr></table>'
			)
			cells.append(
				f'<td style="{value_td_style}">{bar_html}</td>'
			)
		# 값-히트맵 사이 스페이서(반응형) - 세그 단위로 행 병합
		if is_group_start:
			cells.append(f'<td rowspan="{rowspan_count.get(seg_name,1)}" style="line-height:0;font-size:0;{("box-shadow: inset 0 0 0 2px #EF4444;" if is_edgecase else "")}">\n\t<div style="padding:0 4px;">\n\t\t<div style="height:16px;background:transparent;"></div>\n\t</div>\n</td>')
		# 퍼센트 셀들 - n이 임계치 미만이면 그레이스케일 적용, 기타 열은 항상 그레이스케일
		use_grayscale = total < threshold_count
		# 일반 히트맵 열들
		for lb in order:
			if lb != "기타":  # 기타가 아닌 열들만
				pct = round(100.0 * cnts[lb] / (total or 1), 1)
				if use_grayscale:
					bg = _shade_for_grayscale_dynamic(pct, min_pct, max_pct)
				else:
					bg = _shade_for_pct_dynamic(pct, min_pct, max_pct)
				fg = _auto_text_color(bg)
				cells.append(
					f'<td style="{cell_style_base}width:60px;padding:0;background:{bg};background-color:{bg};background-image:none;color:{fg};{("box-shadow: inset 0 0 0 2px #EF4444;" if is_edgecase else "")}">{pct:.1f}%</td>'
				)
		# (히트맵-기타) 갭 셀(반응형, 기타가 있을 때만) - 세그 단위로 행 병합
		if has_other:
			if is_group_start:
				cells.append(f'<td rowspan="{rowspan_count.get(seg_name,1)}" style="line-height:0;font-size:0;{("box-shadow: inset 0 0 0 2px #EF4444;" if is_edgecase else "")}">\n\t<div style="padding:0 4px;">\n\t\t<div style="height:16px;background:transparent;"></div>\n\t</div>\n</td>')
		# 기타 열 (기타가 있을 때만) - 단일 색상 (0%~30% 단계)
		if has_other:
			pct = round(100.0 * cnts["기타"] / (total or 1), 1)
			bg = _shade_for_other_column(pct)
			fg = _auto_text_color(bg)
			cells.append(
				f'<td style="{cell_style_base}width:60px;min-width:60px;max-width:60px;padding:0;background:{bg};background-color:{bg};background-image:none;color:{fg};border-radius:12px;overflow:hidden;">{pct:.1f}%</td>'
			)
		# 엣지케이스 행: 모든 데이터 셀에 빨간 테두리 적용(세그명 셀 제외)
		# 엣지케이스 테두리 주입 제거
		# 엣지케이스 행: 모든 데이터 셀에 빨간 테두리 적용(세그명 셀 제외)
		# 엣지케이스 테두리 주입 제거
		# 엣지케이스 행: 모든 데이터 셀에 빨간 테두리 적용(세그명 셀 제외)
		# 엣지케이스 테두리 주입 제거
		# 엣지케이스 행: 모든 데이터 셀에 빨간 테두리 적용(세그명 셀 제외)
		# 엣지케이스 테두리 주입 제거
		# 엣지케이스 행: 모든 데이터 셀에 빨간 테두리 적용(세그명 셀 제외)
		# 엣지케이스 테두리 주입 제거
		# 엣지케이스 행: 모든 데이터 셀에 빨간 테두리 적용(세그명 셀 제외)
		# 엣지케이스 테두리 주입 제거
		# 엣지케이스 행: 모든 데이터 셀에 빨간 테두리 적용(세그명 셀 제외)
		# 엣지케이스 테두리 주입 제거
		# 엣지케이스 행: 모든 데이터 셀에 빨간 테두리 적용(세그명 셀 제외)
		if is_edgecase and cells:
			border_tb = 'border:2px solid #EF4444;'
			left_data_idx = 1 if is_group_start else 0
			for j in range(len(cells)):
				if j < left_data_idx:
					continue
				if 'style="' in cells[j]:
					extra = border_tb
					if j == left_data_idx:
						extra += 'border-left:2px solid #EF4444;'
					if j == len(cells) - 1:
						extra += 'border-right:2px solid #EF4444;'
					cells[j] = cells[j].replace('style="', f'style="{extra}')
		body_rows.append('<tr>' + ''.join(cells) + '</tr>')
	table = (
		'<table role="presentation" cellpadding="0" cellspacing="0" border="0" '
		'style="width:100%;table-layout:fixed;border-collapse:collapse;padding-left:4px;padding-right:8px;">'
		+ f'<colgroup>{colgroup}</colgroup>'
		+ head_html + '<tbody>' + ''.join(body_rows) + '</tbody>' + '</table>'
	)
	# 제목 (아래 간격 0)
	heading = '<div style="font-weight:700;font-size:14px;color:#111827;margin-bottom:0;">Seg.별 히트맵</div>'
	
	# 기타 응답 요약 추가
	other_summary = build_other_responses_summary(question_rows)
	
	return '<div style="margin:12px 0;padding:12px;border:1px solid #E5E7EB;border-radius:6px;background:#FFFFFF;">' + heading + table + (other_summary if other_summary else '') + '</div>'
def build_evaluation_heatmap_only(question_rows: List[Dict[str, str]], label_order: List[str], question_title: str = "평가형 문항", all_data: List[Dict[str, str]] = None, question_id: str = None) -> str:
	"""모든 세그먼트를 포함하는 평가형 히트맵(행=세그 버킷, 열=평가 라벨+순만족도).
	기존 보고서 스타일(테이블+인라인 CSS)과 색상램프(_shade_for_pct)를 사용한다.
	교차분석 제외
	"""
	# 실제 데이터에서 라벨 추출 (label_order 우선, 없으면 데이터에서 추출)
	if label_order:
		order = [lb for lb in label_order]
	else:
		# 데이터에서 실제 답변 라벨 추출
		labels = set()
		for r in question_rows:
			content = (r.get('lkng_cntnt') or r.get('answ_cntnt') or '').strip()
			if content:
				labels.add(content)
		# 만족도 순서로 정렬 (응답통계와 일치: 높은 점수부터)
		# 긍정적 -> 부정적 순서로 정렬
		satisfaction_order = ["매우 만족해요", "만족해요", "보통이에요", "불만족해요", "매우 불만족해요"]
		order = []
		# 만족도 순서에 있는 것들 먼저 추가
		for label in satisfaction_order:
			if label in labels:
				order.append(label)
		# 나머지는 알파벳 순으로 추가
		remaining = sorted([l for l in labels if l not in order])
		order.extend(remaining)
	# 세그 정의: (표시명, 키)
	seg_defs: List[Tuple[str, str]] = [
		("성별", "gndr_seg"),
		("계좌고객", "account_seg"),
		("연령대", "age_seg"),
		("가입경과일", "rgst_gap"),
		("VASP 연결", "vasp"),
		("수신상품 가입", "dp_seg"),
		("대출상품 가입", "loan_seg"),
		("카드상품 가입", "card_seg"),
		("서비스 이용", "suv_seg"),
	]
	# 세그별 버킷 후보(존재하는 것만 사용). 일부는 정해진 순서를 제공
	preferred_orders: Dict[str, List[str]] = {
		"gndr_seg": ["01.남성", "02.여성"],
		"age_seg": ["01.10대","02.20대","03.30대","04.40대","05.50대","06.60대","07.기타"],
	}
	# 버킷 수집
	seg_bucket_rows: List[Tuple[str, List[Dict[str, str]]]] = []
	# 전체(집계) 먼저 한 줄 추가
	seg_bucket_rows.append(("전체", question_rows))
	for seg_title, seg_key in seg_defs:
		vals = set()
		for r in question_rows:
			v = (r.get(seg_key) or "").strip()
			if v:
				vals.add(v)
		# 선호 순서가 있으면 그 순서로, 아니면 문자열 정렬
		if seg_key in preferred_orders:
			ordered_vals = [v for v in preferred_orders[seg_key] if v in vals]
			# 누락분은 사전순으로 뒤에
			remain = sorted([v for v in vals if v not in set(ordered_vals)])
			ordered_vals += remain
		else:
			ordered_vals = sorted(vals)
		for raw_val in ordered_vals:
			# '기타' 버킷 제외
			if clean_axis_label(raw_val) == '기타':
				continue
			bucket_label = f"{seg_title} - {clean_axis_label(raw_val)}"
			rows_subset = [r for r in question_rows if (r.get(seg_key) or '').strip() == raw_val]
			if not rows_subset:
				continue
			seg_bucket_rows.append((bucket_label, rows_subset))

	# 요약 카드 데이터(전체 기준)
	def _counts(rows: List[Dict[str, str]]) -> Dict[str, int]:
		c = {l: 0 for l in order}
		for r in rows:
			content = (r.get('lkng_cntnt') or r.get('answ_cntnt') or '').strip()
			# 숫자 답변을 텍스트로 변환 (평가형 문항용)
			if content.isdigit():
				score = int(content)
				if score >= 7:
					content = "매우 만족해요"
				elif score >= 6:
					content = "만족해요"
				elif score >= 4:
					content = "보통이에요"
				elif score >= 3:
					content = "불만족해요"
				else:
					content = "매우 불만족해요"
			if content in c:
				c[content] += 1
		return c
	def _pos_rate(rows: List[Dict[str, str]]) -> float:
		c = _counts(rows)
		t = sum(c.values()) or 1
		# 긍정적 응답 비율 계산 (첫 번째와 두 번째 라벨)
		if len(order) >= 2:
			return (c[order[0]] + c[order[1]]) * 100.0 / t
		elif len(order) >= 1:
			return c[order[0]] * 100.0 / t
		else:
			return 0.0
	overall_pos = _pos_rate(question_rows)
	# 세그 버킷 중 전체 제외하고 최고/최저 탐색
	pairs = [(name, _pos_rate(rows)) for (name, rows) in seg_bucket_rows if name != '전체']
	best = max(pairs, key=lambda x: x[1]) if pairs else ("-", overall_pos)
	worst = min(pairs, key=lambda x: x[1]) if pairs else ("-", overall_pos)
	gap = max(0.0, round(best[1] - worst[1], 1))
	
	# 스타일(기존 보고서 톤) - 모든 라인 제거, 헤더/본문 하단 보더 제거
	head_style = 'padding:6px 8px;color:#111827;font-size:12px;text-align:center;'
	# 만족도 라벨 헤더 전용 스타일(패딩 4px, 수직 중앙 정렬)
	label_head_style = 'padding:0 2px;color:#111827;font-size:12px;text-align:center;vertical-align:middle;overflow:hidden;'
	rowhead_style = 'padding:0 8px;color:#111827;font-size:12px;text-align:left;white-space:nowrap;height:20px;vertical-align:middle;'
	# 폰트 크기 12px을 강제(이메일 클라이언트 상속 방지). 숫자 중앙 정렬 및 고정 높이 20px
	cell_style_base = 'padding:0;text-align:center;white-space:nowrap;font-size:11px;line-height:1.2;height:20px;vertical-align:middle;'

	# 헤더 구성: 세그먼트(세그/값) | (값-히트맵) 20px | 5라벨(1fr씩) | (히트맵-지표) 20px | 순만족도
	colgroup = (
		'<col style="width:100px;min-width:100px;max-width:100px;">'  # 세그명 (고정 100px)
		'<col style="width:110px;min-width:110px;max-width:110px;">'  # 값 (고정 110px)
		+ '<col style="width:20px;min-width:20px;max-width:20px;">'   # 값-히트맵 간격 (고정 20px)
		+ ''.join(['<col style="width:1fr;">' for _ in range(len(order))])  # 히트맵 열들 (1fr씩 배분)
		+ '<col style="width:20px;min-width:20px;max-width:20px;">'  # 히트맵-지표 간격 (고정 20px)
		+ '<col style="width:60px;min-width:60px;max-width:60px;">'  # 순만족도 (고정 80px)
		+ '<col style="width:60px;min-width:60px;max-width:60px;">'  # 평균점수 (고정 80px)
	)
	head_cells = [
		f'<th style="{head_style}">&nbsp;</th>',
		f'<th style="{head_style}">&nbsp;</th>'
	]
	# (값-히트맵) 갭 헤더(반응형)
	head_cells.append('<th style="padding:0;line-height:0;font-size:0;">&nbsp;</th>')
	for lb in order:
		# 라벨 줄바꿈 허용을 위해 래퍼 div 사용(폭 기준으로 개행), 어미 제거
		head_cells.append(
			f'<th style="{label_head_style}"><div style="display:block;width:100%;height:100%;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;line-height:1.2;text-align:center;">{html_escape(_display_label(lb, order))}</div></th>'
		)
	# (히트맵-지표) 갭 헤더(반응형)
	head_cells.append('<th style="padding:0;line-height:0;font-size:0;">&nbsp;</th>')
	# 순만족도 헤더 텍스트 계산 (실제 데이터로 계산)
	_, top_text, top_labels = _calculate_top_satisfaction({l: 1 for l in order}, order)
	head_cells.append(f'<th style="{head_style}padding:0;"><div style="display:block;width:100%;height:100%;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;line-height:1.2;text-align:center;">{top_text}</div></th>')
	head_cells.append(f'<th style="{head_style}padding:0;"><div style="display:block;width:100%;height:100%;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;line-height:1.2;text-align:center;">평균점수</div></th>')
	head_html = '<thead><tr>' + ''.join(head_cells) + '</tr></thead>'

	# 바디 생성(두 단계: 데이터 준비 → rowspan 적용하여 렌더)
	rows_data: List[Dict[str, object]] = []
	for name, rows in seg_bucket_rows:
		cnts = {l: 0 for l in order}
		for r in rows:
			content = (r.get('lkng_cntnt') or r.get('answ_cntnt') or '').strip()
			if content in cnts:
				cnts[content] += 1
		total = sum(cnts.values()) or 1
		# 세그/값 분리
		if ' - ' in name:
			seg_name, seg_value = name.split(' - ', 1)
		else:
			seg_name, seg_value = name, ''
		rows_data.append({
			'seg_name': seg_name,
			'seg_value': seg_value,
			'cnts': cnts,
			'total': total,
		})

	# 전체 행(첫 번째)의 보기별 퍼센트 순위 계산 (엣지케이스 비교용)
	overall_rank: List[str] = []
	if rows_data:
		overall_cnts = rows_data[0]['cnts']  # type: ignore
		overall_total = int(rows_data[0]['total'])  # type: ignore
		overall_pct_map: Dict[str, float] = {lb: ((overall_cnts[lb] * 100.0) / (overall_total or 1)) for lb in order}  # type: ignore
		overall_rank = sorted(order, key=lambda lb: (-overall_pct_map.get(lb, 0.0), order.index(lb)))
	
	# 전체 응답 수 계산 (임계치 판단용) - 전체 행의 응답 수 사용
	total_responses = len(question_rows)
	threshold_count = max(int(total_responses * GRAYSCALE_THRESHOLD_PERCENT / 100.0), GRAYSCALE_MIN_COUNT)
	
	# 전체 평균점수 계산 (모든 행의 데이터를 합쳐서)
	all_cnts = {l: 0 for l in order}
	for d in rows_data:
		for label, count in d['cnts'].items():
			all_cnts[label] += count
	overall_avg_score = _calculate_average_score(all_cnts, order)
	
	# 모든 세그먼트의 평균점수를 먼저 계산 (반올림 없이)
	segment_avg_scores = []
	for d in rows_data:
		avg_score = _calculate_average_score(d['cnts'], order)
		segment_avg_scores.append(avg_score)

	# 동적 색상 스케일링을 위한 최소/최대값 계산 (그레이스케일 대상 제외, 순만족도 열 제외)
	heatmap_pcts: List[float] = []
	sun_pcts: List[float] = []
	avg_scores: List[float] = []
	for rd in rows_data:
		cnts = rd['cnts']  # type: ignore
		total = int(rd['total'])
		# 그레이스케일 대상이 아닌 경우만 색상 스케일링에 포함
		if total >= threshold_count:
			# 히트맵 5개 열의 퍼센트 (순만족도 열 제외)
			for lb in order:
				pct = _calculate_percentage(cnts[lb], total)
				heatmap_pcts.append(pct)
			# 순만족도는 별도 수집 (히트맵 색상 스케일링에서 제외)
			sun_pct, _, _ = _calculate_top_satisfaction(cnts, order)
			sun_pcts.append(sun_pct)
			# 평균점수 수집 (색상 스케일링용)
			avg_score = _calculate_average_score(cnts, order)
			avg_scores.append(avg_score)
	
	min_heatmap_pct = min(heatmap_pcts) if heatmap_pcts else 0.0
	max_heatmap_pct = max(heatmap_pcts) if heatmap_pcts else 100.0
	min_sun_pct = min(sun_pcts) if sun_pcts else 0.0
	max_sun_pct = max(sun_pcts) if sun_pcts else 100.0
	min_avg_score = min(avg_scores) if avg_scores else 1.0
	max_avg_score = max(avg_scores) if avg_scores else 5.0

	# 전체 행(첫 번째)의 보기별 퍼센트 순위 계산 (엣지케이스 비교용)
	overall_rank: List[str] = []
	if rows_data:
		overall_cnts = rows_data[0]['cnts']  # type: ignore
		overall_total = int(rows_data[0]['total'])  # type: ignore
		overall_pct_map: Dict[str, float] = {lb: ((overall_cnts[lb] * 100.0) / (overall_total or 1)) for lb in order}  # type: ignore
		overall_rank = sorted(order, key=lambda lb: (-overall_pct_map.get(lb, 0.0), order.index(lb)))

	# 세그별 첫번째 인덱스와 rowspan 계산
	first_index: Dict[str, int] = {}
	rowspan_count: Dict[str, int] = {}
	for idx, rd in enumerate(rows_data):
		seg = str(rd['seg_name'])
		if seg not in first_index:
			first_index[seg] = idx
		rowspan_count[seg] = rowspan_count.get(seg, 0) + 1

	# 값 셀 막대 스케일 기준(최대 n)
	max_total = max((int(rd['total']) for rd in rows_data), default=1) or 1
	
	body_rows: List[str] = []
	for idx, rd in enumerate(rows_data):
		seg_name = str(rd['seg_name'])
		seg_value = str(rd['seg_value'])
		cnts = rd['cnts']  # type: ignore
		total = int(rd['total'])
		# 미리 계산된 평균점수 사용
		avg_score = segment_avg_scores[idx]
		# 세그 그룹 시작 시(첫 그룹 제외) 세그/값 영역에 하나의 연속 라인을 별도 행으로 추가해 끊김 방지
		cells: List[str] = []
		is_group_start = (idx == first_index.get(seg_name))
		if is_group_start and idx != 0:
			# 전체 폭으로 1px 가로줄을 그려 세그/값/히트맵/지표를 관통
			# 위/아래 간격을 4px씩 확보
			# 평가형 히트맵 열 구조: 세그명(1) + 값(1) + 간격(1) + 히트맵열들(len(order)) + 간격(1) + 순만족도(1) + 평균점수(1) = 6 + len(order)
			total_cols = 6 + len(order)
			body_rows.append(f'<tr><td colspan="{total_cols}" style="padding:4px 0;height:0;line-height:0;"><div style="height:1px;background:repeating-linear-gradient(to right, #E5E7EB 0 2px, transparent 2px 4px);"></div></td></tr>')
		if is_group_start:
			cells.append(f'<td rowspan="{rowspan_count.get(seg_name,1)}" style="{rowhead_style}">{html_escape(seg_name)}</td>')
		# 이 행의 보기별 퍼센트 순위 계산 (엣지케이스 판단용)
		seg_pct_map: Dict[str, float] = {lb: (cnts[lb] * 100.0 / (total or 1)) for lb in order}
		seg_rank: List[str] = sorted(order, key=lambda lb: (-seg_pct_map.get(lb, 0.0), order.index(lb)))
		orank: List[str] = _compute_overall_rank_from_rows_data(rows_data, order)
		is_edgecase = (seg_value != '' and bool(orank) and seg_rank != orank)

		# 이 행의 보기별 퍼센트 순위 계산 (엣지케이스 판단용)
		seg_pct_map: Dict[str, float] = {lb: ((cnts[lb] * 100.0) / (total or 1)) for lb in order}
		seg_rank: List[str] = sorted(order, key=lambda lb: (-seg_pct_map.get(lb, 0.0), order.index(lb)))
		orank: List[str] = _compute_overall_rank_from_rows_data(rows_data, order)
		is_edgecase = (seg_value != '' and bool(orank) and seg_rank != orank)

		# 값 열: 100% 폭 테이블 + 좌측 bar TD(비율, 텍스트 포함) + 우측 여백 TD(잔여)
		bar_w = int(round((total / (max_total or 1)) * 100))
		bar_w_css = max(1, bar_w)  # 폭 0%에서도 텍스트가 보이도록 최소 1px 확보
		# 값셀 좌우 여백 제거(패딩 0)
		value_td_style = 'padding:0;color:#111827;font-size:12px;text-align:left;white-space:nowrap;height:20px;position:relative;overflow:hidden;vertical-align:middle;'
		# 값 열: 100% 폭 테이블 + 좌측 bar TD(비율, 텍스트 포함) + 우측 여백 TD(잔여)
		bar_html = (
			'<table role="presentation" cellpadding="0" cellspacing="0" border="0" style="border-collapse:collapse;width:100%;height:20px;table-layout:fixed;">'
			'<tr>'
			f'<td width="{bar_w_css}%" style="height:20px;line-height:20px;vertical-align:middle;'
			+ ("background-color:#FECACA;" if is_edgecase else "background-color:#D1D5DB;")
			+ 'padding:0;color:#111827;font-size:11px;white-space:nowrap;overflow:visible;">'
			+ f'<span style="margin-left:4px;">{html_escape(seg_value)}'
			+ f'<span style="color:#6B7280;margin-left:6px;">(n={total:,})</span></span>'
			+ '</td>'
			f'<td width="{100 - bar_w_css}%" style="height:20px;line-height:20px;vertical-align:middle;padding:0;margin:0;"></td>'
			+ '</tr></table>'
		)
		text_html = ''
		if seg_value:
			cells.append(f'<td style="{value_td_style}">{bar_html}{text_html}</td>')
		else:
			# 전체 행도 동일한 방식으로 표시
			bar_html = (
				'<table role="presentation" cellpadding="0" cellspacing="0" border="0" style="border-collapse:collapse;width:100%;height:20px;table-layout:fixed;">'
				'<tr>'
				f'<td width="{bar_w_css}%" style="height:20px;line-height:20px;vertical-align:middle;background-color:#D1D5DB;padding:0;color:#111827;font-size:11px;white-space:nowrap;overflow:visible;">'
				+ '<span style="margin-left:4px;">전체'
				+ f'<span style="color:#6B7280;margin-left:6px;">(n={total:,})</span></span>'
				+ '</td>'
				f'<td width="{100 - bar_w_css}%" style="height:20px;line-height:20px;vertical-align:middle;padding:0;margin:0;"></td>'
				+ '</tr></table>'
			)
			cells.append(
				f'<td style="{value_td_style}">{bar_html}</td>'
			)
		# (값-히트맵) 갭 헤더(반응형) - 세그 단위로 행 병합
		if is_group_start:
			cells.append(f'<td rowspan="{rowspan_count.get(seg_name,1)}" style="line-height:0;font-size:0;{("box-shadow: inset 0 0 0 2px #EF4444;" if is_edgecase else "")}">\n\t<div style="padding:0 4px;">\n\t\t<div style="height:16px;background:transparent;"></div>\n\t</div>\n</td>')
		# 퍼센트 셀들(표시값 기준으로 순만족도 계산 일치화) - n이 임계치 미만이면 그레이스케일 적용
		pct_map: Dict[str, float] = {}
		use_grayscale = total < threshold_count
		for lb in order:
			pct = round(100.0 * cnts[lb] / (total or 1), 1)
			pct_map[lb] = pct
			if use_grayscale:
				bg = _shade_for_grayscale_dynamic(pct, min_heatmap_pct, max_heatmap_pct)
			else:
				bg = _shade_for_pct_dynamic(pct, min_heatmap_pct, max_heatmap_pct)
			fg = _auto_text_color(bg)
			cells.append(
				f'<td style="{cell_style_base}width:60px;padding:0;background:{bg};background-color:{bg};background-image:none;color:{fg};">{pct:.1f}%</td>'
			)
		# (히트맵-지표) 갭 헤더(반응형) - 세그 단위로 행 병합
		if is_group_start:
			cells.append(f'<td rowspan="{rowspan_count.get(seg_name,1)}" style="line-height:0;font-size:0;">\n\t<div style="padding:0 4px;">\n\t\t<div style="height:16px;background:transparent;"></div>\n\t</div>\n</td>')
		# 순만족도 계산 - 상위 절반 기준
		sun, _, _ = _calculate_top_satisfaction(cnts, order)
		# 순만족도: n이 임계치 미만이면 그레이스케일, 아니면 CONTRAST_PALETTE 팔레트
		if use_grayscale:
			bg_sun = _shade_for_grayscale_dynamic(sun, min_sun_pct, max_sun_pct)
		else:
			bg_sun = _shade_for_pct_dynamic(sun, min_sun_pct, max_sun_pct)
		fg_sun = _auto_text_color(bg_sun)
		cells.append(
			f'<td style="{cell_style_base}width:60px;min-width:60px;max-width:60px;padding:0;background:{bg_sun};background-color:{bg_sun};background-image:none;color:{fg_sun};border-radius:12px;overflow:hidden;{("box-shadow: inset 0 0 0 2px #EF4444;" if is_edgecase else "")}">{sun:.1f}%</td>'
		)
		# 평균점수(평균대비) - 5점 척도로 계산, 전체 평균과의 차이를 퍼센트로 표시
		# avg_score는 이미 위에서 미리 계산됨
		
		# 평균점수를 동적 범위로 변환 (실제 데이터 범위 사용)
		avg_pct = ((avg_score - min_avg_score) / (max_avg_score - min_avg_score)) * 100.0 if max_avg_score > min_avg_score else 50.0
		# 평균점수는 동적 범위로 색상 스케일링
		if use_grayscale:
			bg_avg = _shade_for_grayscale_dynamic(avg_pct, 0.0, 100.0)
		else:
			bg_avg = _shade_for_pct_dynamic(avg_pct, 0.0, 100.0)
		fg_avg = _auto_text_color(bg_avg)
		
		# 모든 행에서 평균점수만 소수점 3자리까지 표시 (괄호 부분 제거)
		avg_display = f"{avg_score:.3f}"
		cells.append(
			f'<td style="{cell_style_base}width:60px;min-width:60px;max-width:60px;padding:0;background:{bg_avg};background-color:{bg_avg};background-image:none;color:{fg_avg};border-radius:12px;overflow:hidden;{("box-shadow: inset 0 0 0 2px #EF4444;" if is_edgecase else "")}">{avg_display}</td>'
		)
		# 엣지케이스 행: 모든 데이터 셀에 빨간 테두리 적용(세그명 셀 제외)
		if is_edgecase and cells:
			border_tb = 'border:2px solid #EF4444;'
			left_data_idx = 1 if is_group_start else 0
			for j in range(len(cells)):
				if j < left_data_idx:
					continue
				if 'style="' in cells[j]:
					extra = border_tb
					if j == left_data_idx:
						extra += 'border-left:2px solid #EF4444;'
					if j == len(cells) - 1:
						extra += 'border-right:2px solid #EF4444;'
					cells[j] = cells[j].replace('style="', f'style="{extra}')
		row_attr = '' if is_edgecase else ''
		body_rows.append('<tr' + row_attr + '>' + ''.join(cells) + '</tr>')

	# 상단 카드(요약)
	card = (
		'<table role="presentation" cellpadding="0" cellspacing="0" border="0" style="width:100%;table-layout:separate;border-collapse:separate;border-spacing:12px 0;margin:8px 0 12px 0;">'
		'<tr>'
		f'<td style="padding:12px;border:1px solid #E5E7EB;border-radius:8px;background:#FFFFFF;text-align:center;"><div style="color:#0F172A;font-size:18px;font-weight:800;">{overall_pos:.1f}%</div><div style="color:#6B7280;font-size:12px;margin-top:4px;">전체 만족도</div></td>'
		f'<td style="padding:12px;border:1px solid #E5E7EB;border-radius:8px;background:#FFFFFF;text-align:center;"><div style="color:#0F172A;font-size:18px;font-weight:800;">{best[1]:.1f}%</div><div style="color:#6B7280;font-size:12px;margin-top:4px;">최고 ({html_escape(str(best[0]))})</div></td>'
		f'<td style="padding:12px;border:1px solid #E5E7EB;border-radius:8px;background:#FFFFFF;text-align:center;"><div style="color:#0F172A;font-size:18px;font-weight:800;">{worst[1]:.1f}%</div><div style="color:#6B7280;font-size:12px;margin-top:4px;">최저 ({html_escape(str(worst[0]))})</div></td>'
		f'<td style="padding:12px;border:1px solid #E5E7EB;border-radius:8px;background:#FFFFFF;text-align:center;"><div style="color:#0F172A;font-size:18px;font-weight:800;">{gap:.1f}p</div><div style="color:#6B7280;font-size:12px;margin-top:4px;">최대 격차</div></td>'
		'</tr>'
		'</table>'
	)

	# 테이블 본문(셀 간격 1px) - 반응형 레이아웃
	table = (
		'<table role="presentation" cellpadding="0" cellspacing="0" border="0" '
		'style="width:100%;table-layout:fixed;border-collapse:collapse;padding-left:4px;padding-right:8px;">'
		+ f'<colgroup>{colgroup}</colgroup>'
		+ head_html + '<tbody>' + ''.join(body_rows) + '</tbody>' + '</table>'
	)

	# 범례 제거됨

	# 제목 (아래 간격 0)
	heading = '<div style="font-weight:700;font-size:14px;color:#111827;margin-bottom:0;">Seg.별 히트맵</div>'

	# 요약(카드/랭크) 제거하고 제목 바로 아래 히트맵 표시
	return '<div style="margin:12px 0;padding:12px;border:1px solid #E5E7EB;border-radius:6px;background:#FFFFFF;">' + heading + table + '</div>'

def _hex_to_rgb(h: str) -> Tuple[int, int, int]:
	h = h.lstrip('#')
	return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def _norm_label_kor(s: str) -> str:
	v = (s or '').strip().replace('  ', ' ')
	aliases = {
		"매우만족": "매우 만족해요",
		"매우 만족": "매우 만족해요",
		"아주 만족": "매우 만족해요",
		"만족": "만족해요",
		"보통": "보통이에요",
		"중립": "보통이에요",
		"불만족": "불만족해요",
		"매우 불만족": "매우 불만족해요",
		"아주 불만족": "매우 불만족해요",
	}
	return aliases.get(v, v)


def _bucket_from_text(s: str) -> Optional[str]:
	"""문구에서 만족도 버킷을 추출(부분 일치 포함)."""
	t = (s or '').strip()
	if not t:
		return None
	u = _norm_label_kor(t)
	# 완전 매칭 우선
	if u in EVAL_LABELS:
		return u
	ls = u
	
	# 숫자 답변을 텍스트로 변환 (평가형 문항용)
	if ls.isdigit():
		score = int(ls)
		if score >= 7:
			return "매우 만족해요"
		elif score >= 6:
			return "만족해요"
		elif score >= 4:
			return "보통이에요"
		elif score >= 3:
			return "불만족해요"
		else:
			return "매우 불만족해요"
	
	# 실제 데이터의 다양한 라벨 매칭
	# 긍정적 응답
	if any(word in ls for word in ['맞아요', '최고예요', '좋아요', '만족해요', '매우 만족해요']):
		if '매우' in ls or '최고' in ls:
			return "매우 만족해요"
		else:
			return "만족해요"
	
	# 부정적 응답
	if any(word in ls for word in ['아니예요', '별로예요', '불만족해요', '매우 불만족해요']):
		if '매우' in ls or '별로' in ls:
			return "매우 불만족해요"
		else:
			return "불만족해요"
	
	# 중립적 응답
	if any(word in ls for word in ['보통이에요', '보통']):
		return "보통이에요"
	
	# 기존 부분 키워드 매칭 (하위 호환성)
	if ('매우' in ls and '불만족' in ls) or ('최악' in ls):
		return "매우 불만족해요"
	if '불만족' in ls or '아쉬' in ls or '불편' in ls:
		return "불만족해요"
	if '보통' in ls or '중립' in ls:
		return "보통이에요"
	if ('매우' in ls and '만족' in ls) or ('아주' in ls and '만족' in ls):
		return "매우 만족해요"
	if '만족' in ls or '좋' in ls:
		return "만족해요"
	
	# 추가 매칭: "매우 만족", "만족", "보통", "불만족", "매우 불만족" 형태
	if ls == "매우 만족":
		return "매우 만족해요"
	if ls == "만족":
		return "만족해요"
	if ls == "보통":
		return "보통이에요"
	if ls == "불만족":
		return "불만족해요"
	if ls == "매우 불만족":
		return "매우 불만족해요"
	return None
def build_objective_evaluation_heatmap(question_rows: List[Dict[str, str]], label_order: List[str], question_title: str = "평가형 문항", all_data: List[Dict[str, str]] = None, question_id: str = None) -> str:
	"""모든 세그먼트를 포함하는 평가형 히트맵(행=세그 버킷, 열=평가형 라벨+순만족도).
	기존 보고서 스타일(테이블+인라인 CSS)과 색상램프(_shade_for_pct)를 사용한다.
	"""
	# 실제 데이터에서 라벨 추출 (만족도 패턴은 항상 재정렬)
	if label_order and not is_evaluation_pattern(label_order):
		order = [lb for lb in label_order]
	else:
		# 데이터에서 실제 답변 라벨 추출
		labels = set()
		for r in question_rows:
			content = (r.get('lkng_cntnt') or r.get('answ_cntnt') or '').strip()
			if content:
				labels.add(content)
		# 만족도 순서로 정렬 (응답통계와 일치: 높은 점수부터)
		# 긍정적 -> 부정적 순서로 정렬
		satisfaction_order = ["매우 만족해요", "만족해요", "보통이에요", "불만족해요", "매우 불만족해요"]
		order = []
		# 만족도 순서에 있는 것들 먼저 추가
		for label in satisfaction_order:
			if label in labels:
				order.append(label)
		# 나머지는 알파벳 순으로 추가
		remaining = sorted([l for l in labels if l not in order])
		order.extend(remaining)
	# 세그 정의: (표시명, 키)
	seg_defs: List[Tuple[str, str]] = [
		("성별", "gndr_seg"),
		("계좌고객", "account_seg"),
		("연령대", "age_seg"),
		("가입경과일", "rgst_gap"),
		("VASP 연결", "vasp"),
		("수신상품 가입", "dp_seg"),
		("대출상품 가입", "loan_seg"),
		("카드상품 가입", "card_seg"),
		("서비스 이용", "suv_seg"),
	]
	# 세그별 버킷 후보(존재하는 것만 사용). 일부는 정해진 순서를 제공
	preferred_orders: Dict[str, List[str]] = {
		"gndr_seg": ["01.남성", "02.여성"],
		"age_seg": ["01.10대","02.20대","03.30대","04.40대","05.50대","06.60대","07.기타"],
	}
	# 버킷 수집
	seg_bucket_rows: List[Tuple[str, List[Dict[str, str]]]] = []
	# 전체(집계) 먼저 한 줄 추가
	seg_bucket_rows.append(("전체", question_rows))
	for seg_title, seg_key in seg_defs:
		vals = set()
		for r in question_rows:
			v = (r.get(seg_key) or "").strip()
			if v:
				vals.add(v)
		# 선호 순서가 있으면 그 순서로, 아니면 문자열 정렬
		if seg_key in preferred_orders:
			ordered_vals = [v for v in preferred_orders[seg_key] if v in vals]
			# 누락분은 사전순으로 뒤에
			remain = sorted([v for v in vals if v not in set(ordered_vals)])
			ordered_vals += remain
		else:
			ordered_vals = sorted(vals)
		for raw_val in ordered_vals:
			# '기타' 버킷 제외
			if clean_axis_label(raw_val) == '기타':
				continue
			bucket_label = f"{seg_title} - {clean_axis_label(raw_val)}"
			rows_subset = [r for r in question_rows if (r.get(seg_key) or '').strip() == raw_val]
			if not rows_subset:
				continue
			seg_bucket_rows.append((bucket_label, rows_subset))

	# 요약 카드 데이터(전체 기준)
	def _counts(rows: List[Dict[str, str]]) -> Dict[str, int]:
		c = {l: 0 for l in order}
		for r in rows:
			content = (r.get('lkng_cntnt') or r.get('answ_cntnt') or '').strip()
			# 숫자 답변을 텍스트로 변환 (평가형 문항용)
			if content.isdigit():
				score = int(content)
				if score >= 7:
					content = "매우 만족해요"
				elif score >= 6:
					content = "만족해요"
				elif score >= 4:
					content = "보통이에요"
				elif score >= 3:
					content = "불만족해요"
				else:
					content = "매우 불만족해요"
			if content in c:
				c[content] += 1
		return c
	def _pos_rate(rows: List[Dict[str, str]]) -> float:
		c = _counts(rows)
		t = sum(c.values()) or 1
		# 긍정적 응답 비율 계산 (첫 번째와 두 번째 라벨)
		if len(order) >= 2:
			return (c[order[0]] + c[order[1]]) * 100.0 / t
		elif len(order) >= 1:
			return c[order[0]] * 100.0 / t
		else:
			return 0.0
	overall_pos = _pos_rate(question_rows)
	# 세그 버킷 중 전체 제외하고 최고/최저 탐색
	pairs = [(name, _pos_rate(rows)) for (name, rows) in seg_bucket_rows if name != '전체']
	best = max(pairs, key=lambda x: x[1]) if pairs else ("-", overall_pos)
	worst = min(pairs, key=lambda x: x[1]) if pairs else ("-", overall_pos)
	gap = max(0.0, round(best[1] - worst[1], 1))

	# 스타일(기존 보고서 톤) - 모든 라인 제거, 헤더/본문 하단 보더 제거
	head_style = 'padding:6px 8px;color:#111827;font-size:12px;text-align:center;'
	# 만족도 라벨 헤더 전용 스타일(패딩 4px, 수직 중앙 정렬)
	label_head_style = 'padding:0 2px;color:#111827;font-size:12px;text-align:center;vertical-align:middle;overflow:hidden;'
	rowhead_style = 'padding:0 8px;color:#111827;font-size:12px;text-align:left;white-space:nowrap;height:20px;vertical-align:middle;'
	# 폰트 크기 12px을 강제(이메일 클라이언트 상속 방지). 숫자 중앙 정렬 및 고정 높이 20px
	cell_style_base = 'padding:0;text-align:center;white-space:nowrap;font-size:11px;line-height:1.2;height:20px;vertical-align:middle;'

	# 헤더 구성: 세그먼트(세그/값) | (값-히트맵) 20px | 5라벨(1fr씩) | (히트맵-지표) 20px | 순만족도
	colgroup = (
		'<col style="width:100px;min-width:100px;max-width:100px;">'  # 세그명 (고정 100px)
		'<col style="width:110px;min-width:110px;max-width:110px;">'  # 값 (고정 110px)
		+ '<col style="width:20px;min-width:20px;max-width:20px;">'   # 값-히트맵 간격 (고정 20px)
		+ ''.join(['<col style="width:1fr;">' for _ in range(len(order))])  # 히트맵 열들 (1fr씩 배분)
		+ '<col style="width:20px;min-width:20px;max-width:20px;">'  # 히트맵-지표 간격 (고정 20px)
		+ '<col style="width:60px;min-width:60px;max-width:60px;">'  # 순만족도 (고정 80px)
		+ '<col style="width:60px;min-width:60px;max-width:60px;">'  # 평균점수 (고정 80px)
	)
	head_cells = [
		f'<th style="{head_style}">&nbsp;</th>',
		f'<th style="{head_style}">&nbsp;</th>'
	]
	# (값-히트맵) 갭 헤더(반응형)
	head_cells.append('<th style="padding:0;line-height:0;font-size:0;">&nbsp;</th>')
	for lb in order:
		# 라벨 줄바꿈 허용을 위해 래퍼 div 사용(폭 기준으로 개행), 어미 제거
		head_cells.append(
			f'<th style="{label_head_style}"><div style="display:block;width:100%;height:100%;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;line-height:1.2;text-align:center;">{html_escape(_display_label(lb, order))}</div></th>'
		)
	# (히트맵-지표) 갭 헤더(반응형)
	head_cells.append('<th style="padding:0;line-height:0;font-size:0;">&nbsp;</th>')
	# 순만족도 헤더 텍스트 계산 (실제 데이터로 계산)
	_, top_text, top_labels = _calculate_top_satisfaction({l: 1 for l in order}, order)
	head_cells.append(f'<th style="{head_style}padding:0;"><div style="display:block;width:100%;height:100%;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;line-height:1.2;text-align:center;">{top_text}</div></th>')
	head_cells.append(f'<th style="{head_style}padding:0;"><div style="display:block;width:100%;height:100%;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;line-height:1.2;text-align:center;">평균점수</div></th>')
	head_html = '<thead><tr>' + ''.join(head_cells) + '</tr></thead>'

	# 전체 평균 대비 엣지케이스 판단을 위한 전체 순위 계산
	overall_rank: List[str] = []
	if seg_bucket_rows:
		# 전체(첫 번째 원소)의 분포를 기준으로 전체 순위 산출
		overall_cnts_eval: Dict[str, int] = {l: 0 for l in order}
		for r in seg_bucket_rows[0][1]:
			content = (r.get('lkng_cntnt') or r.get('answ_cntnt') or '').strip()
			if content in overall_cnts_eval:
				overall_cnts_eval[content] += 1
		overall_total_eval = sum(overall_cnts_eval.values()) or 1
		overall_pct_map_eval: Dict[str, float] = {lb: (overall_cnts_eval[lb] * 100.0 / overall_total_eval) for lb in order}
		overall_rank = sorted(order, key=lambda lb: (-overall_pct_map_eval.get(lb, 0.0), order.index(lb)))
	# 바디 생성(두 단계: 데이터 준비 → rowspan 적용하여 렌더)
	rows_data: List[Dict[str, object]] = []
	for name, rows in seg_bucket_rows:
		cnts = {l: 0 for l in order}
		for r in rows:
			content = (r.get('lkng_cntnt') or r.get('answ_cntnt') or '').strip()
			if content in cnts:
				cnts[content] += 1
		total = sum(cnts.values()) or 1
		# 세그/값 분리
		if ' - ' in name:
			seg_name, seg_value = name.split(' - ', 1)
		else:
			seg_name, seg_value = name, ''
		rows_data.append({
			'seg_name': seg_name,
			'seg_value': seg_value,
			'cnts': cnts,
			'total': total,
		})

	# 전체 응답 수 계산 (임계치 판단용) - 전체 행의 응답 수 사용
	total_responses = len(question_rows)
	threshold_count = max(int(total_responses * GRAYSCALE_THRESHOLD_PERCENT / 100.0), GRAYSCALE_MIN_COUNT)
	
	# 전체 평균점수 계산 (모든 행의 데이터를 합쳐서)
	all_cnts = {l: 0 for l in order}
	for d in rows_data:
		for label, count in d['cnts'].items():
			all_cnts[label] += count
	overall_avg_score = _calculate_average_score(all_cnts, order)
	
	# 모든 세그먼트의 평균점수를 먼저 계산 (반올림 없이)
	segment_avg_scores = []
	for d in rows_data:
		avg_score = _calculate_average_score(d['cnts'], order)
		segment_avg_scores.append(avg_score)

	# 동적 색상 스케일링을 위한 최소/최대값 계산 (그레이스케일 대상 제외, 순만족도 열 제외)
	heatmap_pcts: List[float] = []
	sun_pcts: List[float] = []
	avg_scores: List[float] = []
	for rd in rows_data:
		cnts = rd['cnts']  # type: ignore
		total = int(rd['total'])
		# 그레이스케일 대상이 아닌 경우만 색상 스케일링에 포함
		if total >= threshold_count:
			# 히트맵 5개 열의 퍼센트 (순만족도 열 제외)
			for lb in order:
				pct = _calculate_percentage(cnts[lb], total)
				heatmap_pcts.append(pct)
			# 순만족도는 별도 수집 (히트맵 색상 스케일링에서 제외)
			sun_pct, _, _ = _calculate_top_satisfaction(cnts, order)
			sun_pcts.append(sun_pct)
			# 평균점수 수집 (색상 스케일링용)
			avg_score = _calculate_average_score(cnts, order)
			avg_scores.append(avg_score)
	
	min_heatmap_pct = min(heatmap_pcts) if heatmap_pcts else 0.0
	max_heatmap_pct = max(heatmap_pcts) if heatmap_pcts else 100.0
	min_sun_pct = min(sun_pcts) if sun_pcts else 0.0
	max_sun_pct = max(sun_pcts) if sun_pcts else 100.0
	min_avg_score = min(avg_scores) if avg_scores else 1.0
	max_avg_score = max(avg_scores) if avg_scores else 5.0

	# 세그별 첫번째 인덱스와 rowspan 계산
	first_index: Dict[str, int] = {}
	rowspan_count: Dict[str, int] = {}
	for idx, rd in enumerate(rows_data):
		seg = str(rd['seg_name'])
		if seg not in first_index:
			first_index[seg] = idx
		rowspan_count[seg] = rowspan_count.get(seg, 0) + 1

	# 값 셀 막대 스케일 기준(최대 n)
	max_total = max((int(rd['total']) for rd in rows_data), default=1) or 1

	body_rows: List[str] = []
	for idx, rd in enumerate(rows_data):
		seg_name = str(rd['seg_name'])
		seg_value = str(rd['seg_value'])
		cnts = rd['cnts']  # type: ignore
		total = int(rd['total'])
		# 미리 계산된 평균점수 사용
		avg_score = segment_avg_scores[idx]
		# 세그 그룹 시작 시(첫 그룹 제외) 세그/값 영역에 하나의 연속 라인을 별도 행으로 추가해 끊김 방지
		cells: List[str] = []
		is_group_start = (idx == first_index.get(seg_name))
		if is_group_start and idx != 0:
			# 전체 폭으로 1px 가로줄을 그려 세그/값/히트맵/지표를 관통
			# 위/아래 간격을 4px씩 확보
			# 평가형 히트맵 열 구조: 세그명(1) + 값(1) + 간격(1) + 히트맵열들(len(order)) + 간격(1) + 순만족도(1) + 평균점수(1) = 6 + len(order)
			total_cols = 6 + len(order)
			body_rows.append(f'<tr><td colspan="{total_cols}" style="padding:4px 0;height:0;line-height:0;"><div style="height:1px;background:repeating-linear-gradient(to right, #E5E7EB 0 2px, transparent 2px 4px);"></div></td></tr>')
		if is_group_start:
			cells.append(f'<td rowspan="{rowspan_count.get(seg_name,1)}" style="{rowhead_style}">{html_escape(seg_name)}</td>')
		# 이 행의 보기별 퍼센트 순위 계산 (엣지케이스 판단용)
		seg_pct_map: Dict[str, float] = {lb: (cnts[lb] * 100.0 / (total or 1)) for lb in order}
		seg_rank: List[str] = sorted(order, key=lambda lb: (-seg_pct_map.get(lb, 0.0), order.index(lb)))
		orank: List[str] = _compute_overall_rank_from_rows_data(rows_data, order)
		is_edgecase = (seg_value != '' and bool(orank) and seg_rank != orank)
		# 값 열: 100% 폭 테이블 + 좌측 bar TD(비율, 텍스트 포함) + 우측 여백 TD(잔여)
		bar_w = int(round((total / (max_total or 1)) * 100))
		bar_w_css = max(1, bar_w)  # 폭 0%에서도 텍스트가 보이도록 최소 1px 확보
		# 값셀 좌우 여백 제거(패딩 0)
		value_td_style = 'padding:0;color:#111827;font-size:12px;text-align:left;white-space:nowrap;height:20px;position:relative;overflow:hidden;vertical-align:middle;'
		# 값 열: 100% 폭 테이블 + 좌측 bar TD(비율, 텍스트 포함) + 우측 여백 TD(잔여)
		bar_html = (
			'<table role="presentation" cellpadding="0" cellspacing="0" border="0" style="border-collapse:collapse;width:100%;height:20px;table-layout:fixed;">'
			'<tr>'
			f'<td width="{bar_w_css}%" style="height:20px;line-height:20px;vertical-align:middle;'
			+ ("background-color:#FECACA;" if is_edgecase else "background-color:#D1D5DB;")
			+ 'padding:0;color:#111827;font-size:11px;white-space:nowrap;overflow:visible;">'
			+ f'<span style="margin-left:4px;">{html_escape(seg_value)}'
			+ f'<span style="color:#6B7280;margin-left:6px;">(n={total:,})</span></span>'
			+ '</td>'
			f'<td width="{100 - bar_w_css}%" style="height:20px;line-height:20px;vertical-align:middle;padding:0;margin:0;"></td>'
			+ '</tr></table>'
		)
		text_html = ''
		if seg_value:
			cells.append(f'<td style="{value_td_style}">{bar_html}{text_html}</td>')
		else:
			# 전체 행도 동일한 방식으로 표시
			bar_html = (
				'<table role="presentation" cellpadding="0" cellspacing="0" border="0" style="border-collapse:collapse;width:100%;height:20px;table-layout:fixed;">'
				'<tr>'
				f'<td width="{bar_w_css}%" style="height:20px;line-height:20px;vertical-align:middle;background-color:#D1D5DB;padding:0;color:#111827;font-size:11px;white-space:nowrap;overflow:visible;">'
				+ '<span style="margin-left:4px;">전체'
				+ f'<span style="color:#6B7280;margin-left:6px;">(n={total:,})</span></span>'
				+ '</td>'
				f'<td width="{100 - bar_w_css}%" style="height:20px;line-height:20px;vertical-align:middle;padding:0;margin:0;"></td>'
				+ '</tr></table>'
			)
			cells.append(
				f'<td style="{value_td_style}">{bar_html}</td>'
			)
		# (값-히트맵) 갭 헤더(반응형) - 세그의 첫 번째 행에서만 그라데이션 표시
		if is_group_start:
			cells.append(f'<td rowspan="{rowspan_count.get(seg_name,1)}" style="line-height:0;font-size:0;">\n\t<div style="padding:0 4px;">\n\t\t<div style="height:16px;background:transparent;"></div>\n\t</div>\n</td>')
		# 퍼센트 셀들(표시값 기준으로 순만족도 계산 일치화) - n이 임계치 미만이면 그레이스케일 적용
		pct_map: Dict[str, float] = {}
		use_grayscale = total < threshold_count
		for lb in order:
			pct = round(100.0 * cnts[lb] / (total or 1), 1)
			pct_map[lb] = pct
			if use_grayscale:
				bg = _shade_for_grayscale_dynamic(pct, min_heatmap_pct, max_heatmap_pct)
			else:
				bg = _shade_for_pct_dynamic(pct, min_heatmap_pct, max_heatmap_pct)
			fg = _auto_text_color(bg)
			cells.append(
				f'<td style="{cell_style_base}width:60px;padding:0;background:{bg};background-color:{bg};background-image:none;color:{fg};">{pct:.1f}%</td>'
			)
		# (히트맵-지표) 갭 헤더(반응형) - 세그 단위로 행 병합
		if is_group_start:
			cells.append(f'<td rowspan="{rowspan_count.get(seg_name,1)}" style="line-height:0;font-size:0;">\n\t<div style="padding:0 4px;">\n\t\t<div style="height:16px;background:transparent;"></div>\n\t</div>\n</td>')
		# 순만족도 계산 - 상위 절반 기준
		sun, _, _ = _calculate_top_satisfaction(cnts, order)
		# 순만족도: n이 임계치 미만이면 그레이스케일, 아니면 CONTRAST_PALETTE 팔레트
		if use_grayscale:
			bg_sun = _shade_for_grayscale_dynamic(sun, min_sun_pct, max_sun_pct)
		else:
			bg_sun = _shade_for_pct_dynamic(sun, min_sun_pct, max_sun_pct)
		fg_sun = _auto_text_color(bg_sun)
		cells.append(
			f'<td style="{cell_style_base}width:60px;min-width:60px;max-width:60px;padding:0;background:{bg_sun};background-color:{bg_sun};background-image:none;color:{fg_sun};border-radius:12px;overflow:hidden;">{sun:.1f}%</td>'
		)
		# 평균점수(평균대비) - 5점 척도로 계산, 전체 평균과의 차이를 퍼센트로 표시
		# avg_score는 이미 위에서 미리 계산됨
		
		# 평균점수를 동적 범위로 변환 (실제 데이터 범위 사용)
		avg_pct = ((avg_score - min_avg_score) / (max_avg_score - min_avg_score)) * 100.0 if max_avg_score > min_avg_score else 50.0
		# 평균점수는 동적 범위로 색상 스케일링
		if use_grayscale:
			bg_avg = _shade_for_grayscale_dynamic(avg_pct, 0.0, 100.0)
		else:
			bg_avg = _shade_for_pct_dynamic(avg_pct, 0.0, 100.0)
		fg_avg = _auto_text_color(bg_avg)
		
		# 모든 행에서 평균점수만 소수점 3자리까지 표시 (괄호 부분 제거)
		avg_display = f"{avg_score:.3f}"
		cells.append(
			f'<td style="{cell_style_base}width:60px;min-width:60px;max-width:60px;padding:0;background:{bg_avg};background-color:{bg_avg};background-image:none;color:{fg_avg};border-radius:12px;overflow:hidden;">{avg_display}</td>'
		)
		row_attr = '' if is_edgecase else ''
		body_rows.append('<tr' + row_attr + '>' + ''.join(cells) + '</tr>')

	# 상단 카드(요약)
	card = (
		'<table role="presentation" cellpadding="0" cellspacing="0" border="0" style="width:100%;table-layout:separate;border-collapse:separate;border-spacing:12px 0;margin:8px 0 12px 0;">'
		'<tr>'
		f'<td style="padding:12px;border:1px solid #E5E7EB;border-radius:8px;background:#FFFFFF;text-align:center;"><div style="color:#0F172A;font-size:18px;font-weight:800;">{overall_pos:.1f}%</div><div style="color:#6B7280;font-size:12px;margin-top:4px;">전체 만족도</div></td>'
		f'<td style="padding:12px;border:1px solid #E5E7EB;border-radius:8px;background:#FFFFFF;text-align:center;"><div style="color:#0F172A;font-size:18px;font-weight:800;">{best[1]:.1f}%</div><div style="color:#6B7280;font-size:12px;margin-top:4px;">최고 ({html_escape(str(best[0]))})</div></td>'
		f'<td style="padding:12px;border:1px solid #E5E7EB;border-radius:8px;background:#FFFFFF;text-align:center;"><div style="color:#0F172A;font-size:18px;font-weight:800;">{worst[1]:.1f}%</div><div style="color:#6B7280;font-size:12px;margin-top:4px;">최저 ({html_escape(str(worst[0]))})</div></td>'
		f'<td style="padding:12px;border:1px solid #E5E7EB;border-radius:8px;background:#FFFFFF;text-align:center;"><div style="color:#0F172A;font-size:18px;font-weight:800;">{gap:.1f}p</div><div style="color:#6B7280;font-size:12px;margin-top:4px;">최대 격차</div></td>'
		'</tr>'
		'</table>'
	)

	# 테이블 본문(셀 간격 1px) - 반응형 레이아웃
	table = (
		'<table role="presentation" cellpadding="0" cellspacing="0" border="0" '
		'style="width:100%;table-layout:fixed;border-collapse:collapse;padding-left:4px;padding-right:8px;">'
		+ f'<colgroup>{colgroup}</colgroup>'
		+ head_html + '<tbody>' + ''.join(body_rows) + '</tbody>' + '</table>'
	)

	# 범례 제거됨

	# 제목 (아래 간격 0)
	heading = '<div style="font-weight:700;font-size:14px;color:#111827;margin-bottom:0;">Seg.별 히트맵</div>'

	# 세그별 순만족도(Top2) 랭킹 요약(부등호 체인)
	def _build_seg_rank_summary() -> str:
		cells_html: List[str] = []
		for seg_title, seg_key in seg_defs:
			# seg 값별 rows 수집
			val_to_rows: Dict[str, List[Dict[str, str]]] = {}
			for r in question_rows:
				val_raw = (r.get(seg_key) or '').strip()
				if not val_raw or '기타' in val_raw:
					continue
				val_to_rows.setdefault(val_raw, []).append(r)
			if not val_to_rows:
				continue
			# 각 값의 Top2 비율 계산
			pairs: List[Tuple[str, float]] = []
			for v, rs in val_to_rows.items():
				c = _counts(rs)
				tt = sum(c.values()) or 1
				pos_rate = (c[order[0]] + c[order[1]]) * 100.0 / tt
				pairs.append((v, pos_rate))
			# 내림차순 정렬
			pairs.sort(key=lambda x: x[1], reverse=True)
			# 표시용 체인 구성: 라벨만(세그명/퍼센트 제외)
			labels_only: List[str] = []
			for v, _pr in pairs:
				label_disp = clean_axis_label(v) if 'clean_axis_label' in globals() else v
				labels_only.append(html_escape(label_disp))
			chain_html = ' <span style="color:#9CA3AF;padding:0 6px;">&gt;</span> '.join(labels_only)
			# 박스 스타일로 감싸기(한 줄에 이어 붙이기)
			cells_html.append(
				'<td style="padding:0 8px 8px 0;vertical-align:top;">'
				+ '<div style="padding:6px 8px;border:1px solid #E5E7EB;border-radius:6px;background:#F9FAFB;color:#374151;font-size:12px;">'
				+ chain_html
				+ '</div>'
				+ '</td>'
			)
		if not cells_html:
			return ''
		# 버킷 갯수 기반으로 2줄로 분할: 상단 절반, 하단 절반
		n = len(cells_html)
		top = (n + 1) // 2
		row1 = ''.join(cells_html[:top])
		row2 = ''.join(cells_html[top:])
		return (
			'<table role="presentation" cellpadding="0" cellspacing="0" border="0" '
			'style="width:100%;border-collapse:collapse;margin:0 0 6px 0;">'
			+ '<tr>' + row1 + '</tr>'
			+ ('<tr>' + row2 + '</tr>' if row2 else '')
			+ '</table>'
		)

	# 교차분석 엣지케이스 수집 (평가형은 전체 평균 점수 기준)
	edge_cases = _analyze_evaluation_cross_segments(question_rows, question_title)
	
	# 엣지케이스 섹션 생성 (평가형용)
	edge_cases_section = _build_evaluation_edge_cases_section(edge_cases, order, question_rows, all_data, question_id)
	
	# 요약(카드/랭크) 제거하고 제목 바로 아래 히트맵 표시
	return '<div style="margin:12px 0;padding:12px;border:1px solid #E5E7EB;border-radius:6px;background:#FFFFFF;">' + heading + table + edge_cases_section + '</div>'


def detect_encoding(file_path: str) -> str:
	"""Return a best-effort encoding for Korean CSV files."""
	for enc in ("utf-8-sig", "cp949", "euc-kr", "utf-8"):
		try:
			with open(file_path, "r", encoding=enc) as f:
				f.readline()
			return enc
		except Exception:
			continue
	# Fallback
	return "utf-8"


def read_rows(file_path: str) -> List[Dict[str, str]]:
	enc = detect_encoding(file_path)
	with open(file_path, "r", encoding=enc, newline="") as f:
		reader = csv.DictReader(f)
		rows: List[Dict[str, str]] = []
		for row in reader:
			# Normalize keys (strip whitespace)
			normalized = { (k.strip() if isinstance(k, str) else k): (v.strip() if isinstance(v, str) else v) for k, v in row.items() }
			rows.append(normalized)
	return rows


def get_first_nonempty(rows: List[Dict[str, str]], key: str) -> Optional[str]:
	for r in rows:
		val = r.get(key)
		if val:
			return val
	return None


def get_report_title(rows: List[Dict[str, str]]) -> str:
	# Use main_ttl text as requested; fallback to surv_id
	title = get_first_nonempty(rows, "main_ttl")
	if title:
		return title
	return f"Survey Report ({get_first_nonempty(rows, 'surv_id') or 'N/A'})"


def group_by_question(rows: List[Dict[str, str]]) -> Dict[str, Dict[str, object]]:
	"""
	Return mapping: question_key -> { 'title': str, 'rows': list[dict] }
	Prefer grouping key by qsit_sqn if available; include qsit_ttl for display.
	"""
	grouped: Dict[str, Dict[str, object]] = {}
	for r in rows:
		qid = r.get("qsit_sqn") or r.get("qsit_ttl") or "unknown"
		title = r.get("qsit_ttl") or f"문항 {qid}"
		if qid not in grouped:
			grouped[qid] = {"title": title, "rows": []}
		grouped[qid]["rows"].append(r)
	return grouped
def pick_label_for_row(r: Dict[str, str]) -> Optional[str]:
	"""Pick the most informative label among answ_cntnt > lkng_cntnt > answ_sqn.
	Exclude blanks and dots.
	"""
	for key in ("answ_cntnt", "lkng_cntnt", "answ_sqn"):
		v = r.get(key)
		if v is None:
			continue
		v = v.strip()
		if not v or v == "." or v == "0":
			continue
		return v
	return None


def compute_distribution(question_rows: List[Dict[str, str]]) -> Counter:
	ctr: Counter = Counter()
	for r in question_rows:
		label = pick_label_for_row(r)
		if label is None:
			continue
		ctr[label] += 1
	return ctr


def get_question_type(question_rows: List[Dict[str, str]]) -> str:
	"""
	문항 타입 매핑:
	- 10: objective(객관식)
	- 20: subjective(주관식)
	- 30: evaluation(평가형)
	- 40: content(콘텐츠형)
	- 50: list(목록형)
	- 60: card(카드형)
	- 70: binary(이분형)
	- 80: ranking(순위형)
	기본값은 objective
	
	단, 객관식(10)이지만 평가형 패턴인 경우 평가형으로 처리
	"""
	mapping = {
		"10": "objective",
		"20": "subjective",
		"30": "evaluation",
		"40": "content",
		"50": "list",
		"60": "card",
		"70": "binary",
		"80": "ranking",
	}
	
	# 먼저 기본 타입 결정
	base_type = "objective"
	for r in question_rows:
		val = (r.get("qsit_type_ds_cd") or "").strip()
		if val in mapping:
			base_type = mapping[val]
			break
	
	# 객관식이지만 평가형 패턴인 경우 평가형으로 처리
	if base_type == "objective":
		# 라벨 추출하여 평가형 패턴 확인
		labels = set()
		for r in question_rows:
			lb = label_for_row(r, "objective")
			if lb:
				labels.add(lb)
		
		if labels and is_evaluation_pattern(list(labels)):
			return "evaluation"
	
	return base_type


def question_type_label(qtype: str) -> str:
	"""한국어 문항 타입 라벨 반환."""
	ko = {
		"objective": "객관식",
		"subjective": "주관식",
		"evaluation": "평가형",
		"content": "콘텐츠형",
		"list": "목록형",
		"card": "카드형",
		"binary": "이분형",
		"ranking": "순위형",
	}
	return ko.get(qtype, "객관식")


def label_for_row(r: Dict[str, str], qtype: str) -> Optional[str]:
	"""
	라벨 선택 규칙:
	- 객관식 계열(objective/evaluation/content/list/card/binary/ranking):
	  기본은 lkng_cntnt. 단, code=10(객관식)이고 text_yn=1이면 '기타'로 분류.
	  (lkng_cntnt가 없으면 answ_cntnt 보조 사용)
	- 주관식(subjective): answ_cntnt 사용.
	- 공통: 공백/무효 토큰 제외.
	"""
	objective_like = {"objective", "evaluation", "content", "list", "card", "binary", "ranking"}
	if qtype in objective_like:
		qtype_code = (r.get("qsit_type_ds_cd") or "").strip()
		text_yn = (r.get("text_yn") or "").strip()
		if qtype_code == "10" and text_yn in ("1", "Y", "y"):
			raw = "기타"
		else:
			raw = (r.get("lkng_cntnt") or r.get("answ_cntnt"))
	else:
		raw = r.get("answ_cntnt")
	if raw is None:
		return None
	v = str(raw).strip()
	INVALID = {".", "0", "-", "N/A", "NA", "null", "NULL", "미응답", "무응답"}
	if not v or v in INVALID:
		return None
	return v


def sortkey_for_row(r: Dict[str, str]):
	"""answ_cntnt 기준 오름차순 정렬(숫자 우선 파싱)."""
	s = (r.get("answ_cntnt") or "").strip()
	if s == "":
		return "~"
	try:
		return float(s)
	except Exception:
		return s
def compute_overall_distribution(question_rows: List[Dict[str, str]]):
	"""(OrderedDict[label->count], label_order, qtype)를 반환.
	- 원천 데이터에서 중복 제거를 수행하므로 추가 dedup을 하지 않습니다.
	"""
	qtype = get_question_type(question_rows)
	counts: Dict[str, int] = defaultdict(int)
	sortmap: Dict[str, object] = {}
	for r in question_rows:
		lb = label_for_row(r, qtype)
		if lb is None:
			continue
		counts[lb] += 1
		if lb not in sortmap:
			sortmap[lb] = sortkey_for_row(r)

	def _mixed_sort_key(v: object):
		if isinstance(v, (int, float)):
			return (0, float(v))
		# try numeric parse from string
		s = str(v)
		try:
			return (0, float(s))
		except Exception:
			return (1, s)

	# 평가형 문항의 경우 특별한 정렬 순서 적용
	if qtype == "evaluation" or is_evaluation_pattern(list(counts.keys())):
		# 평가형 순서: 점수가 낮은 것(매우 불만족)에서 높은 것(매우 만족)으로
		satisfaction_order = ["매우 불만족해요", "불만족해요", "보통이에요", "만족해요", "매우 만족해요"]
		label_order = []
		# 만족도 순서에 있는 것들 먼저 추가
		for label in satisfaction_order:
			if label in counts:
				label_order.append(label)
		# 나머지는 기존 정렬 방식으로 추가
		remaining = [k for k in counts.keys() if k not in label_order]
		remaining_sorted = sorted(remaining, key=lambda k: _mixed_sort_key(sortmap.get(k, k)))
		label_order.extend(remaining_sorted)
	else:
		# 일반 문항의 경우 기존 정렬 방식 사용
		label_order = sorted(counts.keys(), key=lambda k: _mixed_sort_key(sortmap.get(k, k)))
	
	ordered = OrderedDict((lb, counts[lb]) for lb in label_order)
	return ordered, label_order, qtype


def build_stacked_bar_html_ordered(items: List[Tuple[str, int]]) -> str:
	"""정렬된 (label,count) 목록을 받아 100% 누적막대 HTML을 반환."""
	total = sum(c for _, c in items) or 1
	segments_html: List[str] = []
	for idx, (label, count) in enumerate(items):
		pct = round(count * 100.0 / total, 2)
		width = max(1.0, pct)
		color = color_for_index(idx)
		segments_html.append(
			f'<td style="padding:0;height:50px;background:{color};width:{width}%;text-align:center;">'
			f'<div style="color:#FFFFFF;font-size:11px;line-height:50px;white-space:nowrap;">{pct:.1f}%</div>'
			'</td>'
		)
	return (
		'<table role="presentation" cellpadding="0" cellspacing="0" border="0" style="width:100%;margin-top:6px;">'
		+ "<tr>" + "".join(segments_html) + "</tr></table>"
	)


def build_stacked_bar_html_ordered_height(items: List[Tuple[str, int]], height_px: int) -> str:
	"""100% 누적막대, 높이를 지정 가능."""
	total = sum(c for _, c in items) or 1
	segments_html: List[str] = []
	for idx, (label, count) in enumerate(items):
		pct = round(count * 100.0 / total, 2)
		width = max(1.0, pct)
		color = color_for_index(idx)
		text_color = _auto_text_color(color)
		segments_html.append(
			f'<td style="padding:0;height:{height_px}px;background:{color};width:{width}%;text-align:center;">'
			f'<div style="color:{text_color};font-size:11px;line-height:{height_px}px;white-space:nowrap;">{pct:.1f}%</div>'
			'</td>'
		)
	return (
		'<table role="presentation" cellpadding="0" cellspacing="0" border="0" style="width:100%;margin-top:6px;">'
		+ "<tr>" + "".join(segments_html) + "</tr></table>"
	)

def build_stacked_bar_html_ordered_height_evaluation(items: List[Tuple[str, int]], height_px: int) -> str:
	"""평가형 문항 전용 100% 누적막대: 높은 점수에 진한 색 적용"""
	total = sum(c for _, c in items) or 1
	segments_html: List[str] = []
	for idx, (label, count) in enumerate(items):
		pct = round(count * 100.0 / total, 2)
		width = max(1.0, pct)
		color = color_for_evaluation_index(idx, len(items))
		text_color = _auto_text_color(color)
		segments_html.append(
			f'<td style="padding:0;height:{height_px}px;background:{color};width:{width}%;text-align:center;">'
			f'<div style="color:{text_color};font-size:11px;line-height:{height_px}px;white-space:nowrap;">{pct:.1f}%</div>'
			'</td>'
		)
	return (
		'<table role="presentation" cellpadding="0" cellspacing="0" border="0" style="width:100%;margin-top:6px;">'
		+ "<tr>" + "".join(segments_html) + "</tr></table>"
	)

def build_stacked_bar_html_ordered_height_heatmap(items: List[Tuple[str, int]], height_px: int) -> str:
	"""PRIMARY_PALETTE 기반 100% 누적막대: 중간값(60%)을 기준으로 확장된 색상 적용"""
	total = sum(c for _, c in items) or 1
	segments_html: List[str] = []
	for idx, (label, count) in enumerate(items):
		pct = round(count * 100.0 / total, 2)
		width = max(1.0, pct)
		color = color_for_stats_with_heatmap_shades(idx, len(items))
		text_color = _auto_text_color(color)
		segments_html.append(
			f'<td style="padding:0;height:{height_px}px;background:{color};width:{width}%;text-align:center;">'
			f'<div style="color:{text_color};font-size:11px;line-height:{height_px}px;white-space:nowrap;">{pct:.1f}%</div>'
			'</td>'
		)
	return (
		'<table role="presentation" cellpadding="0" cellspacing="0" border="0" style="width:100%;margin-top:6px;">'
		+ "<tr>" + "".join(segments_html) + "</tr></table>"
	)


def build_stacked_bar_with_labels(items: List[Tuple[str, int]]) -> str:
	"""세그 상세용: 각 구간 내부에 "count (pct%)" 라벨을 중앙 정렬로 표기."""
	total = sum(c for _, c in items) or 1
	cells: List[str] = []
	for idx, (label, count) in enumerate(items):
		pct = round(count * 100.0 / total, 1)
		width = round(max(1.0, count * 100.0 / total), 2)
		color = color_for_index(idx)
		text = f"{count} ({pct}%)"
		label_html = text if width >= 12 else ""
		cells.append(
			(
				'<td style="padding:0;height:12px;vertical-align:middle;text-align:center;'
				f'background:{color};width:{width}%;color:#FFFFFF;font-size:11px;line-height:12px;">'
				+ label_html + "</td>"
			)
		)
	return (
		'<table role="presentation" cellpadding="0" cellspacing="0" border="0" style="width:100%;border-collapse:collapse;margin-top:6px;">'
		+ "<tr>" + "".join(cells) + "</tr></table>"
	)


def build_legend_table_from_items(items: List[Tuple[str, int]]) -> str:
	total = sum(c for _, c in items) or 1
	rows_html: List[str] = []
	for idx, (label, count) in enumerate(items):
		pct = round(count * 100.0 / total, 1)
		color = color_for_index(idx)
		rows_html.append(
			"""
			<tr>
				<td style=\"padding:2px 6px;white-space:nowrap;vertical-align:top;line-height:1.1;\">\n\t\t\t\t\t<span style=\"display:inline-block;width:10px;height:10px;background:{color};border-radius:2px;margin-right:6px;\"></span>\n\t\t\t\t\t<span style=\"font-size:12px;color:#111827;\">{label}</span>\n\t\t\t\t</td>\n\t\t\t\t<td style=\"padding:2px 0 2px 6px;text-align:right;white-space:nowrap;color:#374151;font-size:12px;line-height:1.1;\">{count} ({pct}%)</td>\n\t\t\t</tr>
			""".replace("{color}", color)
			.replace("{label}", html_escape(str(label)))
			.replace("{count}", str(count))
			.replace("{pct}", f"{pct}")
		)
	return (
		'<table role="presentation" cellpadding="0" cellspacing="0" border="0" style="width:100%;border-collapse:collapse;margin-top:6px;">'
		+ "".join(rows_html) + "</table>"
	)

def build_legend_table_from_items_evaluation(items: List[Tuple[str, int]]) -> str:
	"""평가형 문항 전용 범례: 높은 점수에 진한 색 적용"""
	total = sum(c for _, c in items) or 1
	rows_html: List[str] = []
	for idx, (label, count) in enumerate(items):
		pct = round(count * 100.0 / total, 1)
		color = color_for_evaluation_index(idx, len(items))
		rows_html.append(
			"""
			<tr>
				<td style=\"padding:2px 6px;white-space:nowrap;vertical-align:top;line-height:1.1;\">\n\t\t\t\t\t<span style=\"display:inline-block;width:10px;height:10px;background:{color};border-radius:2px;margin-right:6px;\"></span>\n\t\t\t\t\t<span style=\"font-size:12px;color:#111827;\">{label}</span>\n\t\t\t\t</td>\n\t\t\t\t<td style=\"padding:2px 0 2px 6px;text-align:right;white-space:nowrap;color:#374151;font-size:12px;line-height:1.1;\">{count} ({pct}%)</td>\n\t\t\t</tr>
			""".replace("{color}", color)
			.replace("{label}", html_escape(str(label)))
			.replace("{count}", str(count))
			.replace("{pct}", f"{pct}")
		)
	return (
		'<table role="presentation" cellpadding="0" cellspacing="0" border="0" style="width:100%;border-collapse:collapse;margin-top:6px;">'
		+ "".join(rows_html) + "</table>"
	)

def build_legend_table_from_items_heatmap(items: List[Tuple[str, int]]) -> str:
	"""PRIMARY_PALETTE 기반 범례: 중간값(60%)을 기준으로 확장된 색상 적용"""
	total = sum(c for _, c in items) or 1
	rows_html: List[str] = []
	for idx, (label, count) in enumerate(items):
		pct = round(count * 100.0 / total, 1)
		color = color_for_stats_with_heatmap_shades(idx, len(items))
		rows_html.append(
			"""
			<tr>
				<td style=\"padding:2px 6px;white-space:nowrap;vertical-align:top;line-height:1.1;\">\n\t\t\t\t\t<span style=\"display:inline-block;width:10px;height:10px;background:{color};border-radius:2px;margin-right:6px;\"></span>\n\t\t\t\t\t<span style=\"font-size:12px;color:#111827;\">{label}</span>\n\t\t\t\t</td>\n\t\t\t\t<td style=\"padding:2px 0 2px 6px;text-align:right;white-space:nowrap;color:#374151;font-size:12px;line-height:1.1;\">{count} ({pct}%)</td>\n\t\t\t</tr>
			""".replace("{color}", color)
			.replace("{label}", html_escape(str(label)))
			.replace("{count}", str(count))
			.replace("{pct}", f"{pct}")
		)
	return (
		'<table role="presentation" cellpadding="0" cellspacing="0" border="0" style="width:100%;border-collapse:collapse;margin-top:6px;">'
		+ "".join(rows_html) + "</table>"
	)

def build_legend_table_from_items_heatmap_with_numbers(items: List[Tuple[str, int]]) -> str:
	"""PRIMARY_PALETTE 기반 범례: 번호가 포함된 범례 (N+1. 범례내용 형태)"""
	total = sum(c for _, c in items) or 1
	rows_html: List[str] = []
	for idx, (label, count) in enumerate(items):
		pct = round(count * 100.0 / total, 1)
		color = color_for_stats_with_heatmap_shades(idx, len(items))
		numbered_label = f"{idx + 1}. {label}"
		rows_html.append(
			"""
			<tr>
				<td style=\"padding:2px 6px;white-space:nowrap;vertical-align:top;line-height:1.1;\">\n\t\t\t\t\t<span style=\"display:inline-block;width:10px;height:10px;background:{color};border-radius:2px;margin-right:6px;\"></span>\n\t\t\t\t\t<span style=\"font-size:12px;color:#111827;\">{numbered_label}</span>\n\t\t\t\t</td>\n\t\t\t\t<td style=\"padding:2px 0 2px 6px;text-align:right;white-space:nowrap;color:#374151;font-size:12px;line-height:1.1;\">{count} ({pct}%)</td>\n\t\t\t</tr>
			""".replace("{color}", color)
			.replace("{numbered_label}", html_escape(str(numbered_label)))
			.replace("{count}", str(count))
			.replace("{pct}", f"{pct}")
		)
	return (
		'<table role="presentation" cellpadding="0" cellspacing="0" border="0" style="width:100%;border-collapse:collapse;margin-top:6px;">'
		+ "".join(rows_html) + "</table>"
	)

def build_legend_table_from_items_heatmap_evaluation_with_numbers(items: List[Tuple[str, int]]) -> str:
	"""평가형 문항용 PRIMARY_PALETTE 기반 범례: 번호가 포함된 범례 (N+1. 범례내용 형태)"""
	total = sum(c for _, c in items) or 1
	rows_html: List[str] = []
	for idx, (label, count) in enumerate(items):
		pct = round(count * 100.0 / total, 1)
		color = color_for_stats_with_heatmap_shades(idx, len(items))
		numbered_label = f"{idx + 1}. {label}"
		rows_html.append(
			"""
			<tr>
				<td style=\"padding:2px 6px;white-space:nowrap;vertical-align:top;line-height:1.1;\">\n\t\t\t\t\t<span style=\"display:inline-block;width:10px;height:10px;background:{color};border-radius:2px;margin-right:6px;\"></span>\n\t\t\t\t\t<span style=\"font-size:12px;color:#111827;\">{numbered_label}</span>\n\t\t\t\t</td>\n\t\t\t\t<td style=\"padding:2px 0 2px 6px;text-align:right;white-space:nowrap;color:#374151;font-size:12px;line-height:1.1;\">{count} ({pct}%)</td>\n\t\t\t</tr>
			""".replace("{color}", color)
			.replace("{numbered_label}", html_escape(str(numbered_label)))
			.replace("{count}", str(count))
			.replace("{pct}", f"{pct}")
		)
	return (
		'<table role="presentation" cellpadding="0" cellspacing="0" border="0" style="width:100%;border-collapse:collapse;margin-top:6px;">'
		+ "".join(rows_html) + "</table>"
	)

SEG_DEFS: List[Tuple[str, str]] = [
	("성별", "gndr_seg"),
	("계좌고객", "account_seg"),
	("연령대", "age_seg"),
	("가입경과일", "rgst_gap"),
	("VASP 연결", "vasp"),
	("수신상품 가입", "dp_seg"),
	("대출상품 가입", "loan_seg"),
	("카드상품 가입", "card_seg"),
	("서비스 이용", "suv_seg"),
]
def compute_seg_distributions(
	question_rows: List[Dict[str, str]],
	seg_key: str,
	label_order: List[str],
) -> List[Tuple[str, List[Tuple[str, int]]]]:
	"""세그 값별 (label,count) 목록을 반환. 세그값과 항목은 오름차순.
	- 원천 데이터에서 중복 제거를 수행하므로 추가 dedup을 하지 않습니다.
	"""
	rows = question_rows
	by_seg: Dict[str, List[Dict[str, str]]] = defaultdict(list)
	for r in rows:
		seg_val = (r.get(seg_key) or "").strip()
		# '기타' 버킷 제외
		if clean_axis_label(seg_val) == '기타':
			continue
		if seg_val == "":
			seg_val = "(미표기)"
		by_seg[seg_val].append(r)

	ordered_seg_vals = sorted(by_seg.keys())
	results: List[Tuple[str, List[Tuple[str, int]]]] = []
	qtype = get_question_type(rows)
	for seg_val in ordered_seg_vals:
		rows_seg = by_seg[seg_val]
		local_counts: Dict[str, int] = defaultdict(int)
		for r in rows_seg:
			lb = label_for_row(r, qtype)
			if lb is None:
				continue
			local_counts[lb] += 1
		items = [(lb, local_counts.get(lb, 0)) for lb in label_order]
		results.append((seg_val, items))
	return results


def build_seg_panel_html(seg_title: str, seg_key: str, question_rows: List[Dict[str, str]], label_order: List[str]) -> str:
	pairs = compute_seg_distributions(question_rows, seg_key, label_order)
	if not pairs:
		return (
			f'<div style="margin:10px 0;padding:12px;border:1px solid #E5E7EB;border-radius:6px;"><div style="font-weight:700;font-size:13px;color:#111827;">{html_escape(seg_title)}</div><div style="color:#6B7280;font-size:12px;margin-top:4px;">데이터 없음</div></div>'
		)

	# 기존 상세 세로 스택 막대(이메일 호환형) 유지용 보조 함수
	def build_stacked_vertical_chart(
		pairs_local: List[Tuple[str, List[Tuple[str, int]]]],
		order: List[str],
	) -> str:
		max_h = 140
		n = len(pairs_local) or 1
		col_w_pct = round(100.0 / n, 4)
		label_to_index = {lb: i for i, lb in enumerate(order)}
		cols: List[str] = []
		label_cells: List[str] = []
		# compute maximum total for scaling auxiliary bar
		max_total = 1
		for _seg_val, _items in pairs_local:
			_total = sum(c for _, c in _items)
			if _total > max_total:
				max_total = _total
		for seg_val, items in pairs_local:
			total = sum(c for _, c in items) or 1
			seg_rows: List[str] = []
			used = 0
			# right column rows aligned to each segment height; always present to keep spacing consistent
			right_rows: List[str] = []
			for lb in order:
				count = 0
				for name, c in items:
					if name == lb:
						count = c
						break
				h = int(round(max_h * (count / total)))
				used += h
				color = color_for_index(label_to_index[lb])
				pct = count * 100.0 / total
				if h >= 14:
					label_html = (f'<div style="height:{h}px;line-height:{h}px;color:#FFFFFF;font-size:9px;white-space:nowrap;text-align:center;">{pct:.1f}%</div>')
					seg_rows.append(f'<tr><td style="height:{h}px;background:{color};">{label_html}</td></tr>')
					# right col keeps empty space with same height
					right_rows.append(f'<tr><td style="height:{h}px;background:transparent;"></td></tr>')
				else:
					# short segment: no inner label, draw label on right column at matching height
					seg_rows.append(f'<tr><td style="height:{h}px;background:{color};"></td></tr>')
					right_label = (f'<div style="height:{h}px;line-height:{h}px;color:#111827;font-size:9px;white-space:nowrap;text-align:left;">{pct:.1f}%</div>')
					right_rows.append(f'<tr><td style="height:{h}px;padding:0;">{right_label}</td></tr>')
			rest = max_h - used
			if rest > 0:
				seg_rows.append(f'<tr><td style="height:{rest}px;background:transparent;"></td></tr>')
				right_rows.append(f'<tr><td style="height:{rest}px;background:transparent;"></td></tr>')
			col_label = clean_axis_label(seg_val)
			# main stacked bar (32px) with mean label above, and auxiliary bar (8px)
			main_bar_core = (
				f'<table role="presentation" cellpadding="0" cellspacing="0" border="0" style="height:{max_h}px;border-collapse:collapse;width:32px;">'
				+ ''.join(seg_rows)
				+ '</table>'
			)
			main_bar = (
				f'<table role="presentation" cellpadding="0" cellspacing="0" border="0" style="border-collapse:collapse;width:32px;">'
				f'<tr><td style="height:12px;text-align:center;color:#111827;font-size:9px;line-height:12px;white-space:nowrap;"></td></tr>'
				f'<tr><td style="padding:0;line-height:0;">{main_bar_core}</td></tr>'
				f'</table>'
			)
			# 작은 라벨 전용 우측 컬럼
			right_col_w = 24
			small_label_col = (
				f'<table role="presentation" cellpadding="0" cellspacing="0" border="0" style="height:{max_h}px;border-collapse:collapse;width:{right_col_w}px;">'
				+ ''.join(right_rows)
				+ '</table>'
			)
			# 보조 막대(간격 유지용)
			aux_bar = (
				f'<table role="presentation" cellpadding="0" cellspacing="0" border="0" width="8" style="height:{max_h}px;border-collapse:collapse;width:8px;table-layout:fixed;">'
				f'<tr><td style="height:{max_h}px;background:transparent;line-height:0;font-size:0;"></td></tr>'
				+ '</table>'
			)
			inner = (
				'<table role="presentation" cellpadding="0" cellspacing="0" border="0" style="border-collapse:collapse;margin:0 auto;">'
				'<tr style="line-height:0;font-size:0;vertical-align:bottom;">'
				f'<td style="vertical-align:bottom;padding:0;line-height:0;">{aux_bar}</td>'
				f'<td style="vertical-align:bottom;padding:0;line-height:0;">{main_bar}</td>'
				f'<td style="vertical-align:bottom;padding:0 0 0 4px;line-height:0;">{small_label_col}</td>'
				'</tr>'
				'</table>'
			)
			col = f'<td style="padding:0 3px;width:{col_w_pct}%;vertical-align:bottom;text-align:center;">{inner}</td>'
			cols.append(col)
			label_cells.append(
				f'<td style="padding-top:4px;color:#374151;font-size:9px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;text-align:center;">{html_escape(col_label)}</td>'
			)
		bars_html = (
			'<table role="presentation" cellpadding="0" cellspacing="0" border="0" style="width:100%;border-collapse:collapse;">'
			+ '<tr style="line-height:0;font-size:0;vertical-align:bottom;">' + ''.join(cols) + '</tr>'
			+ f'<tr><td colspan="{len(cols)}" style="padding:0;height:0;border-bottom:1px solid #E5E7EB;"></td></tr>'
			+ '<tr>' + ''.join(label_cells) + '</tr>'
			+ '</table>'
		)
		return (
			'<div style="width:100%;">' + bars_html + '</div>'
		)

	chart = build_stacked_vertical_chart(pairs, label_order)
	return (
		f'<div style="margin:0;padding:12px;border:1px solid #E5E7EB;border-radius:6px;background:#F9FAFB;">'
		f'<div style="font-weight:700;font-size:13px;color:#111827;margin-bottom:8px;">{html_escape(seg_title)}</div>'
		f'{chart}'
		'</div>'
	)


def build_vertical_bars_with_labels(items: List[Tuple[str, int]]) -> str:
	"""세그 상세용 세로 막대 그래프. 각 항목을 세로 바(최대 120px)로, 내부에 count (pct%) 표기."""
	max_h = 120
	total = sum(c for _, c in items) or 1
	n = len(items) or 1
	col_width_pct = round(100.0 / n, 4)
	cols: List[str] = []
	for idx, (label, count) in enumerate(items):
		pct = round(count * 100.0 / total, 1)
		height = int(round(max_h * (count / total)))
		spacer = max_h - height
		color = color_for_index(idx)
		text = f"{count} ({pct}%)"
		# 항상 표기하되, 절대위치로 배치해 막대 높이에 영향이 없도록 처리
		if height >= 16:
			inside = f'<div style="position:absolute;left:0;right:0;top:50%;transform:translateY(-50%);color:#FFFFFF;font-size:11px;white-space:nowrap;text-align:center;z-index:1;pointer-events:none;">{text}</div>'
		else:
			inside = f'<div style="position:absolute;left:0;right:0;bottom:0;transform:none;color:#FFFFFF;font-size:11px;white-space:nowrap;text-align:center;z-index:1;pointer-events:none;">{text}</div>'
		cols.append(
			(
				f'<td style="padding:0 2px;width:{col_width_pct}%;vertical-align:bottom;text-align:center;">'
				f'<table role="presentation" cellpadding="0" cellspacing="0" border="0" style="width:100%;height:{max_h}px;border-collapse:collapse;">'
				f'<tr><td style="height:{spacer}px;padding:0;"></td></tr>'
				f'<tr><td style="height:{height}px;background:{color};position:relative;overflow:visible;">{inside}</td></tr>'
				f'</table>'
				f'<div style="margin-top:4px;color:#374151;font-size:11px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">{html_escape(str(label))}</div>'
				f'</td>'
			)
		)

	return (
		'<table role="presentation" cellpadding="0" cellspacing="0" border="0" style="width:100%;border-collapse:collapse;">'
		+ '<tr>' + ''.join(cols) + '</tr>'
		+ '</table>'
	)


def unique_count(rows: List[Dict[str, str]], key: str) -> int:
	seen = set()
	for r in rows:
		v = r.get(key)
		if v:
			seen.add(v)
	return len(seen)


def color_for_index(i: int) -> str:
	"""기본 색상 인덱스 함수: PRIMARY_PALETTE에서 순환하여 색상 반환"""
	return PRIMARY_PALETTE[i % len(PRIMARY_PALETTE)]

def color_for_evaluation_index(i: int, total_items: int) -> str:
	"""평가형 문항 전용 색상: 높은 점수(오른쪽)에 진한 색을 적용"""
	# 오른쪽일수록 진한 색 (역순 인덱스 사용)
	reverse_idx = total_items - 1 - i
	return PRIMARY_PALETTE[reverse_idx % len(PRIMARY_PALETTE)]

def color_for_stats_with_heatmap_shades(i: int, total_items: int) -> str:
	"""응답통계 전용 색상: PRIMARY_PALETTE를 사용하여 COLOR_CONFIG에 따라 색상 선택"""
	# COLOR_CONFIG에서 해당 항목 수에 맞는 설정 가져오기
	if total_items == 1:
		config = COLOR_CONFIG["pick_1_color"]
	elif total_items == 2:
		config = COLOR_CONFIG["pick_2_colors"]
	elif total_items == 3:
		config = COLOR_CONFIG["pick_3_colors"]
	elif total_items == 4:
		config = COLOR_CONFIG["pick_4_colors"]
	elif total_items == 5:
		config = COLOR_CONFIG["pick_5_colors"]
	elif total_items == 6:
		config = COLOR_CONFIG["pick_6_colors"]
	elif total_items == 7:
		config = COLOR_CONFIG["pick_7_colors"]
	elif total_items == 8:
		config = COLOR_CONFIG["pick_8_colors"]
	elif total_items == 9:
		config = COLOR_CONFIG["pick_9_colors"]
	elif total_items == 10:
		config = COLOR_CONFIG["pick_10_colors"]
	elif total_items == 11:
		config = COLOR_CONFIG["pick_11_colors"]
	else:
		# 12개 이상: 전체 PRIMARY_PALETTE 범위를 균등 분할
		step = (len(PRIMARY_PALETTE) - 1) / (total_items - 1)
		idx = int(round(i * step))
		idx = max(0, min(len(PRIMARY_PALETTE) - 1, idx))
		return PRIMARY_PALETTE[idx]
	
	# 설정된 인덱스에서 색상 가져오기
	idx = config["indices"][i]
	return PRIMARY_PALETTE[idx]


def html_escape(s: str) -> str:
	return (
		s.replace("&", "&amp;")
		.replace("<", "&lt;")
		.replace(">", "&gt;")
		.replace('"', "&quot;")
		.replace("'", "&#39;")
		.replace("\n", "<br>")
	)


def clean_axis_label(label: str) -> str:
	"""Remove leading numeric prefixes like '01.' from axis labels."""
	if not label:
		return label
	return re.sub(r"^\s*\d+\.?\s*", "", str(label))



def _split_keywords(s: Optional[str]) -> List[str]:
	if not s:
		return []
	parts = [p.strip() for p in str(s).split(',')]
	return [p for p in parts if p]


def aggregate_subjective_by_category(question_rows: List[Dict[str, str]]):
	"""카테고리별로 긍정/부정/제안/문의/무응답 수치와 키워드 빈도를 집계한다.
	반환: [ { 'category': str, 'pos': int, 'neg': int, 'sug': int, 'inq': int, 'no_resp': int, 'pos_kw': Counter, 'neg_kw': Counter, 'sug_kw': Counter, 'inq_kw': Counter } ]
	내림차순(총합) 정렬.
	"""
	from collections import Counter as _Counter
	by_cat: Dict[str, Dict[str, object]] = {}
	for r in question_rows:
		# 응답 내용 길이 체크 (최소 길이 미만이면 제외)
		answ_cntnt = (r.get('answ_cntnt') or '').strip()
		if len(answ_cntnt) < MIN_RESPONSE_LENGTH:
			continue
		
		cat = (r.get('llm_level1') or '(미분류)').strip() or '(미분류)'
		# 카테고리 앞의 "NN. " 형태 숫자 제거
		import re
		cat = re.sub(r'^\d+\.\s*', '', cat)
		sent = (r.get('sentiment') or '').strip()
		
		# 무응답 처리: 카테고리가 무응답이거나 sentiment가 무응답이면 무응답으로 분류
		if cat == '무응답' or sent == '무응답':
			cat = '무응답'
			sent = '무응답'
		# "기타 피드백"을 "기타"로 통합
		elif cat == '기타 피드백':
			cat = '기타'
		# 제외 카테고리는 "기타"로 묶기 (단순응답 제거)
		elif cat in SUBJECTIVE_EXCLUDE_CATEGORIES:
			cat = '기타'
		
		keywords = [kw for kw in _split_keywords(r.get('keywords')) if kw not in SUBJECTIVE_EXCLUDE_KEYWORDS]
		entry = by_cat.get(cat)
		if entry is None:
			entry = by_cat[cat] = { 
				'category': cat, 
				'pos': 0, 'neg': 0, 'sug': 0, 'inq': 0, 'no_resp': 0, 
				'pos_kw': _Counter(), 'neg_kw': _Counter(), 'sug_kw': _Counter(), 'inq_kw': _Counter(), 'no_resp_kw': _Counter() 
			}
		
		# 새로운 sentiment 분류 적용
		if sent == '긍정':
			entry['pos'] = int(entry['pos']) + 1  # type: ignore
			entry['pos_kw'].update(keywords)  # type: ignore
		elif sent == '부정':
			entry['neg'] = int(entry['neg']) + 1  # type: ignore
			entry['neg_kw'].update(keywords)  # type: ignore
		elif sent == '제안':
			entry['sug'] = int(entry['sug']) + 1  # type: ignore
			entry['sug_kw'].update(keywords)  # type: ignore
		elif sent == '문의':
			entry['inq'] = int(entry['inq']) + 1  # type: ignore
			entry['inq_kw'].update(keywords)  # type: ignore
		elif sent == '무응답':
			entry['no_resp'] = int(entry['no_resp']) + 1  # type: ignore
			entry['no_resp_kw'].update(keywords)  # type: ignore
		else:
			# 분류되지 않는 케이스는 기타로 처리
			if cat != '기타':
				# 기타 카테고리로 이동
				others_entry = by_cat.get('기타')
				if others_entry is None:
					others_entry = by_cat['기타'] = { 
						'category': '기타', 
						'pos': 0, 'neg': 0, 'sug': 0, 'inq': 0, 'no_resp': 0, 
						'pos_kw': _Counter(), 'neg_kw': _Counter(), 'sug_kw': _Counter(), 'inq_kw': _Counter(), 'no_resp_kw': _Counter() 
					}
				others_entry['pos'] = int(others_entry['pos']) + 1  # type: ignore
				others_entry['pos_kw'].update(keywords)  # type: ignore
			else:
				entry['pos'] = int(entry['pos']) + 1  # type: ignore
				entry['pos_kw'].update(keywords)  # type: ignore
	# 정렬 및 0건 카테고리 제거 + 기타 묶기
	items = list(by_cat.values())
	# 합계 계산 헬퍼 (새로운 sentiment 분류 반영)
	def _tot(d):
		return int(d['pos']) + int(d['neg']) + int(d['sug']) + int(d['inq']) + int(d['no_resp'])  # type: ignore
	# 0건 제거
	items = [d for d in items if _tot(d) > 0]
	from collections import Counter as __Counter
	
	# 총 응답 수 계산 (비율 계산용)
	total_responses = sum(_tot(d) for d in items)
	
	others = { 
		'category': '기타', 
		'pos': 0, 'neg': 0, 'sug': 0, 'inq': 0, 'no_resp': 0, 
		'pos_kw': __Counter(), 'neg_kw': __Counter(), 'sug_kw': __Counter(), 'inq_kw': __Counter(), 'no_resp_kw': __Counter() 
	}
	kept = []
	for d in items:
		# 절대값 조건 OR 비율 조건 (둘 중 하나라도 만족하면 기타로 분류)
		count = _tot(d)
		percent = (count / total_responses * 100) if total_responses > 0 else 0
		if count <= SUBJECTIVE_OTHER_THRESHOLD or percent <= SUBJECTIVE_OTHER_PERCENT_THRESHOLD:
			others['pos'] += int(d['pos'])  # type: ignore
			others['neg'] += int(d['neg'])  # type: ignore
			others['sug'] += int(d['sug'])  # type: ignore
			others['inq'] += int(d['inq'])  # type: ignore
			others['no_resp'] += int(d['no_resp'])  # type: ignore
			others['pos_kw'].update(d['pos_kw'])  # type: ignore
			others['neg_kw'].update(d['neg_kw'])  # type: ignore
			others['sug_kw'].update(d['sug_kw'])  # type: ignore
			others['inq_kw'].update(d['inq_kw'])  # type: ignore
			others['no_resp_kw'].update(d['no_resp_kw'])  # type: ignore
		else:
			kept.append(d)
	# 기타가 0이 아니면 추가
	if _tot(others) > 0:
		others_entry = others
	else:
		others_entry = None
	# 기타와 무응답을 정렬에서 제외하고 별도로 관리
	no_response_entry = None
	others_entry_final = None
	
	# 기타와 무응답을 제거
	filtered_kept = []
	for d in kept:
		cat = str(d['category'])  # type: ignore
		if cat == '무응답':
			no_response_entry = d
		elif cat == '기타':
			others_entry_final = d
		else:
			filtered_kept.append(d)
	
	# 나머지 카테고리들을 건수 기준으로 정렬
	filtered_kept.sort(key=lambda d: int(d['pos']) + int(d['neg']) + int(d['sug']) + int(d['inq']) + int(d['no_resp']), reverse=True)  # type: ignore
	
	# 최종 순서: 정렬된 카테고리들 → 기타 → 무응답
	kept = filtered_kept
	if others_entry_final is not None:
		kept.append(others_entry_final)
	elif others_entry is not None:
		kept.append(others_entry)
	
	if no_response_entry is not None:
		kept.append(no_response_entry)
	
	return kept
def build_subjective_section(question_rows: List[Dict[str, str]]) -> str:
	rows = aggregate_subjective_by_category(question_rows)
	if not rows:
		return '<div style="margin:8px 0;color:#6B7280;font-size:12px;">주관식 응답이 없습니다.</div>'
	# 막대 너비 스케일링을 위한 최대값 (새로운 sentiment 분류 포함) - 무응답과 기타는 별도 스케일링
	excluded_categories = {'무응답', '기타'}
	normal_rows = [r for r in rows if str(r.get('category', '')) not in excluded_categories]
	special_rows = [r for r in rows if str(r.get('category', '')) in excluded_categories]
	
	# 일반 카테고리들의 최대값 (새로운 sentiment 분류 반영)
	max_bar_normal = max(max(int(r['pos']), int(r['neg']), int(r['sug']), int(r['inq']), int(r['no_resp'])) for r in normal_rows) if normal_rows else 1
	# 무응답과 기타의 최대값
	max_bar_special = max(max(int(r['pos']), int(r['neg']), int(r['sug']), int(r['inq']), int(r['no_resp'])) for r in special_rows) if special_rows else 1
	# 색상 - 5개 sentiment에 대한 색상 설정
	config = COLOR_CONFIG["pick_1_color"]
	pos_color = PRIMARY_PALETTE[config["indices"][0]]  # 긍정: PRIMARY_PALETTE에서 80% 색상
	neg_color = CONTRAST_PALETTE[config["indices"][0]]  # 부정: CONTRAST_PALETTE에서 80% 색상
	sug_color = "#10B981"  # 제안: 초록색
	inq_color = "#3B82F6"  # 문의: 파란색
	no_resp_color = GRAYSCALE_PALETTE[config["indices"][0]]  # 무응답: 회색
	# 헤더 - 열 너비: 순번(40px) + 카테고리(130px) + 응답수(220px) + 키워드5개(나머지 균등분할)
	keyword_col_width = "calc((100% - 390px) / 4)"  # 390px = 40+130+220
	head = (
		'<table role="presentation" cellpadding="0" cellspacing="0" border="0" style="width:100%;table-layout:fixed;border-collapse:collapse;">'
		f'<colgroup><col style="width:40px;"><col style="width:130px;"><col style="width:220px;"><col style="width:{keyword_col_width};"><col style="width:{keyword_col_width};"><col style="width:{keyword_col_width};"><col style="width:{keyword_col_width};"></colgroup>'
		'<thead><tr>'
		'<th style="text-align:left;padding:6px 8px;color:#374151;font-size:12px;border-bottom:1px solid #E5E7EB;">순번</th>'
		'<th style="text-align:left;padding:6px 8px;color:#374151;font-size:12px;border-bottom:1px solid #E5E7EB;">카테고리</th>'
		'<th style="text-align:left;padding:6px 8px;color:#374151;font-size:12px;border-bottom:1px solid #E5E7EB;">긍정/부정/제안/문의 수</th>'
		'<th style="text-align:left;padding:6px 8px;color:#374151;font-size:12px;border-bottom:1px solid #E5E7EB;">긍정 키워드</th>'
		'<th style="text-align:left;padding:6px 8px;color:#374151;font-size:12px;border-bottom:1px solid #E5E7EB;">부정 키워드</th>'
		'<th style="text-align:left;padding:6px 8px;color:#374151;font-size:12px;border-bottom:1px solid #E5E7EB;">제안 키워드</th>'
		'<th style="text-align:left;padding:6px 8px;color:#374151;font-size:12px;border-bottom:1px solid #E5E7EB;">문의 키워드</th>'
		'</tr></thead><tbody>'
	)
	row_html: List[str] = []
	for idx, d in enumerate(rows, start=1):
		pos = int(d['pos'])  # type: ignore
		neg = int(d['neg'])  # type: ignore
		sug = int(d['sug'])  # type: ignore
		inq = int(d['inq'])  # type: ignore
		no_resp = int(d['no_resp'])  # type: ignore
		cat = str(d['category'])  # type: ignore
		cat_total = pos + neg + sug + inq + no_resp
		pos_kw: Counter = d['pos_kw']  # type: ignore
		neg_kw: Counter = d['neg_kw']  # type: ignore
		sug_kw: Counter = d['sug_kw']  # type: ignore
		inq_kw: Counter = d['inq_kw']  # type: ignore
		no_resp_kw: Counter = d['no_resp_kw']  # type: ignore
		
		# 기타 위쪽에 대시 스타일의 가로줄 추가
		if cat == '기타':
			row_html.append('<tr><td colspan="7" style="padding:8px 0 4px 0;height:0;line-height:0;"><div style="height:2px;background:transparent;"></div></td></tr>')
		
		# 바 너비(%): 최소 가시성 3% - 카테고리에 따라 적절한 max_bar 사용
		current_max_bar = max_bar_special if cat in excluded_categories else max_bar_normal
		pos_w = max(3.0, round(100.0 * pos / current_max_bar, 2))
		neg_w = max(3.0, round(100.0 * neg / current_max_bar, 2))
		sug_w = max(3.0, round(100.0 * sug / current_max_bar, 2))
		inq_w = max(3.0, round(100.0 * inq / current_max_bar, 2))
		bars = (
			'<table role="presentation" cellpadding="0" cellspacing="0" border="0" style="width:100%;table-layout:fixed;border-collapse:collapse;">'
			'<tbody>'
			'<tr>'
			'<td style="width:44px;padding:0 6px 0 0;color:#111827;font-size:12px;white-space:nowrap;">긍정</td>'
			f'<td style="padding:0;vertical-align:middle;overflow:hidden;">'
			f'<div style="height:12px;background:#E5E7EB;overflow:hidden;width:100%;"><div style="height:12px;background:{pos_color};width:{pos_w}%;"></div></div>'
			'</td>'
			f'<td style="width:30px;padding-left:6px;color:#111827;font-size:12px;white-space:nowrap;">{pos}</td>'
			'</tr>'
			'<tr>'
			'<td style="width:44px;padding:4px 6px 0 0;color:#111827;font-size:12px;white-space:nowrap;">부정</td>'
			f'<td style="padding:4px 0 0 0;vertical-align:middle;overflow:hidden;">'
			f'<div style="height:12px;background:#E5E7EB;overflow:hidden;width:100%;"><div style="height:12px;background:{neg_color};width:{neg_w}%;"></div></div>'
			'</td>'
			f'<td style="width:40px;padding:4px 0 0 6px;color:#111827;font-size:12px;white-space:nowrap;">{neg}</td>'
			'</tr>'
			'<tr>'
			'<td style="width:44px;padding:4px 6px 0 0;color:#111827;font-size:12px;white-space:nowrap;">제안</td>'
			f'<td style="padding:4px 0 0 0;vertical-align:middle;overflow:hidden;">'
			f'<div style="height:12px;background:#E5E7EB;overflow:hidden;width:100%;"><div style="height:12px;background:{sug_color};width:{sug_w}%;"></div></div>'
			'</td>'
			f'<td style="width:40px;padding:4px 0 0 6px;color:#111827;font-size:12px;white-space:nowrap;">{sug}</td>'
			'</tr>'
			'<tr>'
			'<td style="width:44px;padding:4px 6px 0 0;color:#111827;font-size:12px;white-space:nowrap;">문의</td>'
			f'<td style="padding:4px 0 0 0;vertical-align:middle;overflow:hidden;">'
			f'<div style="height:12px;background:#E5E7EB;overflow:hidden;width:100%;"><div style="height:12px;background:{inq_color};width:{inq_w}%;"></div></div>'
			'</td>'
			f'<td style="width:40px;padding:4px 0 0 6px;color:#111827;font-size:12px;white-space:nowrap;">{inq}</td>'
			'</tr>'
			'</tbody></table>'
		)
		# 키워드: 기본 최대 SUBJECTIVE_KEYWORDS_LIMIT, 기타는 SUBJECTIVE_KEYWORDS_LIMIT_OTHER
		limit_kw = SUBJECTIVE_KEYWORDS_LIMIT_OTHER if cat == '기타' else SUBJECTIVE_KEYWORDS_LIMIT
		pos_list = [f"{html_escape(k)} ({c})" for k, c in pos_kw.most_common(limit_kw)]
		neg_list = [f"{html_escape(k)} ({c})" for k, c in neg_kw.most_common(limit_kw)]
		sug_list = [f"{html_escape(k)} ({c})" for k, c in sug_kw.most_common(limit_kw)]
		inq_list = [f"{html_escape(k)} ({c})" for k, c in inq_kw.most_common(limit_kw)]
		no_resp_list = [f"{html_escape(k)} ({c})" for k, c in no_resp_kw.most_common(limit_kw)]
		# 키워드 셀(폭 고정, 높이 통일) - 새로운 sentiment 분류 반영
		pos_kw_cell = (
			'<div style="padding:6px;border:1px solid #B9C5FE;background:#E8EDFF;border-radius:6px;min-height:60px;">'
			'<div style="color:#2539E9;font-size:12px;font-weight:700;margin-bottom:4px;">긍정</div>'
			f'<div style="color:#2539E9;font-size:12px;word-break:break-word;">{", ".join(pos_list) if pos_list else "-"}</div>'
			'</div>'
		)
		neg_kw_cell = (
			'<div style="padding:6px;border:1px solid #FEE2E2;background:#FEF2F2;border-radius:6px;min-height:60px;">'
			'<div style="color:#991B1B;font-size:12px;font-weight:700;margin-bottom:4px;">부정</div>'
			f'<div style="color:#991B1B;font-size:12px;word-break:break-word;">{", ".join(neg_list) if neg_list else "-"}</div>'
			'</div>'
		)
		sug_kw_cell = (
			'<div style="padding:6px;border:1px solid #D1FAE5;background:#ECFDF5;border-radius:6px;min-height:60px;">'
			'<div style="color:#065F46;font-size:12px;font-weight:700;margin-bottom:4px;">제안</div>'
			f'<div style="color:#065F46;font-size:12px;word-break:break-word;">{", ".join(sug_list) if sug_list else "-"}</div>'
			'</div>'
		)
		inq_kw_cell = (
			'<div style="padding:6px;border:1px solid #DBEAFE;background:#EFF6FF;border-radius:6px;min-height:60px;">'
			'<div style="color:#1E40AF;font-size:12px;font-weight:700;margin-bottom:4px;">문의</div>'
			f'<div style="color:#1E40AF;font-size:12px;word-break:break-word;">{", ".join(inq_list) if inq_list else "-"}</div>'
			'</div>'
		)
		# 무응답과 기타는 순번셀과 카테고리 셀 병합
		if cat in excluded_categories:
			row_html.append(
				'<tr>'
				f'<td colspan="2" style="padding:8px;color:#111827;font-size:12px;">{html_escape(cat)} ({cat_total})</td>'
				f'<td style="padding:8px;overflow:hidden;">{bars}</td>'
				f'<td style="padding:4px;width:100px;vertical-align:top;">{pos_kw_cell}</td>'
				f'<td style="padding:4px;width:100px;vertical-align:top;">{neg_kw_cell}</td>'
				f'<td style="padding:4px;width:100px;vertical-align:top;">{sug_kw_cell}</td>'
				f'<td style="padding:4px;width:100px;vertical-align:top;">{inq_kw_cell}</td>'
				'</tr>'
			)
		else:
			row_html.append(
				'<tr>'
				f'<td style="padding:8px;color:#374151;font-size:12px;">{idx}</td>'
				f'<td style="padding:8px;color:#111827;font-size:12px;">{html_escape(cat)} ({cat_total})</td>'
				f'<td style="padding:8px;overflow:hidden;">{bars}</td>'
				f'<td style="padding:4px;width:100px;vertical-align:top;">{pos_kw_cell}</td>'
				f'<td style="padding:4px;width:100px;vertical-align:top;">{neg_kw_cell}</td>'
				f'<td style="padding:4px;width:100px;vertical-align:top;">{sug_kw_cell}</td>'
				f'<td style="padding:4px;width:100px;vertical-align:top;">{inq_kw_cell}</td>'
				'</tr>'
			)
	return head + ''.join(row_html) + '</tbody></table>'


def generate_html(rows: List[Dict[str, str]]) -> str:
	report_title = html_escape(get_report_title(rows))
	grouped = group_by_question(rows)
	
	# 교차분석 시작 메시지
	print("🔍 교차분석중", end="", flush=True)
	# Sort by numeric qsit_sqn when possible
	def sort_key(item: Tuple[str, Dict[str, object]]):
		qid, data = item
		try:
			return int(qid)
		except Exception:
			return 10**9
	ordered = sorted(grouped.items(), key=sort_key)

	# Summary / Header stats (원천 데이터 기준 사용)
	all_rows = rows
	total_respondents = unique_count(all_rows, "cust_id")
	total_questions = len(grouped)
	# question type counts
	qtype_counts = {"objective": 0, "subjective": 0, "evaluation": 0, "content": 0, "list": 0, "card": 0, "binary": 0, "ranking": 0}
	for qid, data in ordered:
		qt = get_question_type(data["rows"])  # type: ignore
		if qt == "objective":
			# 객관식이지만 평가형 패턴인지 확인
			label_order = [label_for_row(row, qt) for row in data["rows"]]
			label_order = [lb for lb in label_order if lb]  # None 제거
			if is_evaluation_pattern(label_order):
				qtype_counts["evaluation"] += 1
			else:
				qtype_counts["objective"] += 1
		else:
			qtype_counts[qt] += 1
	# date range from surv_date
	from datetime import datetime as _dt
	def _to_date(v: str):
		v = (v or "").strip()
		for fmt in ("%Y-%m-%d", "%Y.%m.%d", "%Y%m%d"):
			try:
				return _dt.strptime(v, fmt)
			except Exception:
				continue
		return None
	dates = [d for d in [_to_date(r.get("surv_date") or "") for r in all_rows] if d]
	period_text = ""
	if dates:
		start = min(dates).strftime("%Y.%m.%d")
		end = max(dates).strftime("%Y.%m.%d")
		period_text = f"수집 기간: {start} ~ {end}"

	sections: List[str] = []
	for q_index, (qid, data) in enumerate(ordered, start=1):
		raw_title = str(data.get("title", f"문항 {qid}"))
		q_rows: List[Dict[str, str]] = data["rows"]  # type: ignore
		
		# 1. qsit_type_ds_cd 값에 따라 기본 문항 타입 결정
		base_qtype = get_question_type(q_rows)
		
		# 2. 응답 분포 계산
		ordered_counts, label_order, _ = compute_overall_distribution(q_rows)
		
		# 3. 객관식이지만 평가형 패턴인 경우 qtype을 evaluation으로 변경
		effective_qtype = base_qtype
		if base_qtype == "objective" and is_evaluation_pattern(label_order):
			effective_qtype = "evaluation"
		keywords_ctr = extract_keywords(q_rows)

		section_parts: List[str] = []
		# Header layout - effective_qtype에 따라 문항 타입 표시
		display_type = question_type_label(effective_qtype)
		
		section_parts.append(
			f'<div style="margin:18px 0 4px 0;font-weight:700;color:#111827;font-size:16px;">{q_index}번 문항 <span style="font-weight:400;color:#374151;">| {display_type}</span></div>'
		)
		section_parts.append(
			f'<div style="margin:0 0 12px 0;color:#111827;font-size:16px;font-weight:700;">{html_escape(raw_title)}</div>'
		)

		# 동적 컴포넌트 시스템: effective_qtype에 따라 설정된 컴포넌트들을 생성
		dynamic_components = build_question_components(q_rows, effective_qtype, label_order, raw_title, rows, qid)
		section_parts.extend(dynamic_components)

		sections.append("".join(section_parts))


	html = f"""
	<!DOCTYPE html>
	<html>
	<head>
		<meta charset="UTF-8" />
		<meta name="viewport" content="width=device-width, initial-scale=1.0" />
		<title>{report_title}</title>

	</head>
	<body style="margin:0;padding:0;background:#F3F4F6;font-family:'맑은 고딕','Malgun Gothic','Apple SD Gothic Neo','Noto Sans CJK KR',-apple-system,BlinkMacSystemFont,sans-serif;">
		<!--[if mso]>
		<table role="presentation" align="center" cellpadding="0" cellspacing="0" border="0" width="{REPORT_MIN_WIDTH}"><tr><td>
		<![endif]-->
		<style>
			/* 이메일 호환성을 위한 기본 스타일 */
			/* 공통 테이블 스타일 */
			table {{
				border-collapse: collapse;
			}}
			/* 공통 텍스트 정렬 */
			.text-center {{
				text-align: center;
			}}
			.text-right {{
				text-align: right;
			}}
			/* 공통 수직 정렬 */
			.vertical-bottom {{
				vertical-align: bottom;
			}}
			.vertical-top {{
				vertical-align: top;
			}}
			/* 공통 텍스트 처리 */
			.white-space-nowrap {{
				white-space: nowrap;
			}}
			.overflow-hidden {{
				overflow: hidden;
			}}
			.overflow-visible {{
				overflow: visible;
			}}
			.text-overflow-ellipsis {{
				text-overflow: ellipsis;
			}}
		</style>
		<table role="presentation" cellpadding="0" cellspacing="0" border="0" style="width:100%;max-width:{REPORT_MAX_WIDTH}px;min-width:{REPORT_MIN_WIDTH}px;margin:0 auto;table-layout:fixed;background:#FFFFFF;border-radius:8px;">
			<tr>
				<td style="padding:0;">
								<tr>
									<td style="padding:20px 12px 8px 12px;">
										<div style="font-size:20px;font-weight:800;color:#111827;">{report_title} AI 보고서</div>
										<div style="margin-top:4px;color:#6B7280;font-size:14px;">{period_text}</div>
										<div style="margin-top:2px;color:#6B7280;font-size:14px;">응답 건 수: {total_respondents:,}건</div>
										<div style="margin-top:2px;color:#6B7280;font-size:14px;">문항 수: 총 {total_questions}건 ({', '.join([f'{question_type_label(k)} {v}건' for k, v in qtype_counts.items() if v > 0])})</div>
									</td>
								</tr>
								<tr>
									<td style="padding:8px 12px 20px 12px;">{''.join(sections)}</td>
								</tr>
		</table>
		<!--[if mso]>
		</td></tr></table>
		<![endif]-->
	</body>
	</html>
	"""
	
	# 교차분석 완료 메시지
	print(" 완료")
	
	return html


def save_report(html: str, report_num: int = 1, total_reports: int = 1, out_dir: str = os.path.join(os.path.dirname(__file__), "reports")) -> str:
	os.makedirs(out_dir, exist_ok=True)
	date_str = datetime.now().strftime("%Y%m%d")
	
	# 새로운 파일명 형식: survey_report_(N)of(M)_(YYYYMMDD).html
	filename = f"survey_report_{report_num}of{total_reports}_{date_str}.html"
	
	path = os.path.join(out_dir, filename)
	with open(path, "w", encoding="utf-8") as f:
		f.write(html)
	return path
def main(argv: List[str]) -> int:
	# CLI usage: python csv_report_generator3.py --csv data/20250902_sample_data.csv
	csv_path: Optional[str] = None
	i = 0
	while i < len(argv):
		if argv[i] == "--csv" and i + 1 < len(argv):
			csv_path = argv[i + 1]
			i += 2
			continue
		i += 1

	if not csv_path:
		# 환경설정 기본 경로 우선 사용
		if os.path.exists(DEFAULT_CSV_PATH):
			csv_path = DEFAULT_CSV_PATH
		else:
			# Fallback: data/ 폴더의 최신 CSV
			cand_dir = DATA_DIR
			if os.path.isdir(cand_dir):
				cands = [os.path.join(cand_dir, f) for f in os.listdir(cand_dir) if f.lower().endswith(".csv")]
				csv_path = max(cands, key=os.path.getmtime) if cands else None

	if not csv_path or not os.path.exists(csv_path):
		print("[ERROR] CSV 파일을 찾을 수 없습니다. --csv 경로를 지정하세요.")
		return 1

	rows = read_rows(csv_path)
	if not rows:
		print("[ERROR] CSV에 데이터가 없습니다.")
		return 1

	# main_ttl별로 데이터 분리
	main_ttl_groups = defaultdict(list)
	for row in rows:
		main_ttl = row.get('main_ttl', '').strip()
		if main_ttl:
			main_ttl_groups[main_ttl].append(row)
		else:
			# main_ttl이 없는 경우 기본 그룹으로 처리
			main_ttl_groups['기본'].append(row)

	if not main_ttl_groups:
		print("[ERROR] main_ttl 데이터가 없습니다.")
		return 1

	# 각 main_ttl별로 별도 보고서 생성
	generated_reports = []
	total_reports = len(main_ttl_groups)
	
	for idx, (main_ttl, group_rows) in enumerate(main_ttl_groups.items(), 1):
		print(f"[INFO] '{main_ttl}' 보고서 생성 중... (데이터 {len(group_rows)}건)")
		
		html = generate_html(group_rows)
		out_path = save_report(html, idx, total_reports)
		generated_reports.append(out_path)
		print(f"[OK] '{main_ttl}' 보고서 생성 완료: {out_path}")

	print(f"[COMPLETE] 총 {len(generated_reports)}개 보고서 생성 완료")
	for report_path in generated_reports:
		print(f"  - {report_path}")
	
	return 0


def build_keywords_html(keywords_ctr: Counter) -> str:
	"""키워드 Counter를 HTML로 변환"""
	if not keywords_ctr:
		return '<div style="color:#6B7280;font-size:12px;">키워드가 없습니다.</div>'
	
	# 상위 10개 키워드 선택
	top_keywords = keywords_ctr.most_common(10)
	
	# HTML 생성
	html_parts = []
	html_parts.append('<div style="margin:8px 0;">')
	
	keyword_items = []
	for keyword, count in top_keywords:
		keyword_items.append(f'<span style="display:inline-block;background:#F3F4F6;color:#374151;padding:2px 6px;margin:1px;border-radius:4px;font-size:11px;">{html_escape(keyword)} ({count})</span>')
	
	html_parts.append(''.join(keyword_items))
	html_parts.append('</div>')
	
	return ''.join(html_parts)


def extract_keywords(question_rows: List[Dict[str, str]]) -> Counter:
	ctr: Counter = Counter()
	for r in question_rows:
		kw = r.get("keywords")
		if not kw:
			continue
		# Split by comma
		parts = [p.strip() for p in kw.split(",") if p and p.strip()]
		for p in parts:
			ctr[p] += 1
	return ctr


def _shade_for_pct(p: float) -> str:
	# 0~100 → 감마 맵핑 후 0..steps-1로 양자화 (히트맵용 CONTRAST_PALETTE 사용)
	steps = len(CONTRAST_PALETTE)
	if steps <= 1:
		return CONTRAST_PALETTE[0] if CONTRAST_PALETTE else "#E5E7EB"
	t = max(0.0, min(1.0, p / 100.0))
	# 감마 적용(값이 낮을수록 밝은 영역, 높을수록 진한 영역 강조)
	t_gamma = pow(t, HEATMAP_GAMMA)
	# 끝단 강조 S-curve: 가운데는 약간 압축하고 저/고값 구간 변화를 더 키움
	u = 2.0 * t_gamma - 1.0
	s = (abs(u) ** HEATMAP_ALPHA)
	if u < 0:
		s = -s
	t_emph = (s + 1.0) / 2.0
	# 중간 구간(20~60%) 대비 증폭: 구간 내 상대값을 중심(0.5) 기준으로 확대/축소
	if 0.2 <= t_emph <= 0.6:
		m = (t_emph - 0.2) / 0.4  # 0..1
		m = 0.5 + (m - 0.5) * HEATMAP_MIDRANGE_GAIN
		# 다시 0.2..0.6 범위로 복귀
		t_emph = 0.2 + max(0.0, min(1.0, m)) * 0.4
	# 저/고 구간(≤30%, ≥80%)에서 추가 강조: 구간 내부를 지수(0.7)로 확장
	if t_emph >= 0.8:
		seg = (t_emph - 0.8) / 0.2
		seg = max(0.0, min(1.0, seg))
		boost = 0.8 + (seg ** 0.7) * 0.2
		t_emph = boost
	elif t_emph <= 0.3:
		seg = (t_emph / 0.3)
		seg = max(0.0, min(1.0, seg))
		boost = (seg ** 0.7) * 0.3
		t_emph = boost
	idx = int(round(t_emph * (steps - 1)))
	idx = max(0, min(steps - 1, idx))
	return CONTRAST_PALETTE[idx]

def _shade_for_pct_dynamic(p: float, min_pct: float, max_pct: float) -> str:
	"""동적 범위에 따른 색상 변환. min_pct~max_pct를 CONTRAST_PALETTE 팔레트에 매핑 (히트맵용)."""
	steps = len(CONTRAST_PALETTE)
	if steps <= 1:
		return CONTRAST_PALETTE[0] if CONTRAST_PALETTE else "#E5E7EB"
	if max_pct <= min_pct:
		return CONTRAST_PALETTE[steps // 2]  # 중간 색상 반환
	
	# min_pct~max_pct를 0~1로 정규화 (단순 선형 변환)
	t = max(0.0, min(1.0, (p - min_pct) / (max_pct - min_pct)))
	
	# 연속적인 색상 보간
	return _interpolate_color(t, CONTRAST_PALETTE)

def _shade_for_stats_dynamic(p: float, min_pct: float, max_pct: float) -> str:
	"""응답통계용 동적 범위에 따른 색상 변환. min_pct~max_pct를 PRIMARY_PALETTE 팔레트에 매핑."""
	steps = len(PRIMARY_PALETTE)
	if steps <= 1:
		return PRIMARY_PALETTE[0] if PRIMARY_PALETTE else "#E5E7EB"
	if max_pct <= min_pct:
		return PRIMARY_PALETTE[steps // 2]  # 중간 색상 반환
	
	# min_pct~max_pct를 0~1로 정규화 (단순 선형 변환)
	t = max(0.0, min(1.0, (p - min_pct) / (max_pct - min_pct)))
	
	# 연속적인 색상 보간
	return _interpolate_color(t, PRIMARY_PALETTE)

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

def _shade_for_sun_evaluation_dynamic(p: float, min_pct: float, max_pct: float) -> str:
	"""순만족도 전용 동적 색상 변환. min_pct~max_pct를 SUN_EVALUATION_SHADES 팔레트에 매핑."""
	steps = len(SUN_EVALUATION_SHADES)
	if steps <= 1:
		return SUN_EVALUATION_SHADES[0] if SUN_EVALUATION_SHADES else "#FFF7ED"
	if max_pct <= min_pct:
		return SUN_EVALUATION_SHADES[steps // 2]  # 중간 색상 반환
	# min_pct~max_pct를 0~1로 정규화 (보정 없이 순수하게)
	t = max(0.0, min(1.0, (p - min_pct) / (max_pct - min_pct)))
	# 연속적인 색상 보간
	return _interpolate_color(t, SUN_EVALUATION_SHADES)

def _shade_for_grayscale_dynamic(p: float, min_pct: float, max_pct: float) -> str:
	"""그레이스케일 동적 색상 변환. min_pct~max_pct를 GRAYSCALE_PALETTE 팔레트에 매핑."""
	steps = len(GRAYSCALE_PALETTE)
	if steps <= 1:
		return GRAYSCALE_PALETTE[0] if GRAYSCALE_PALETTE else "#F9FAFB"
	if max_pct <= min_pct:
		return GRAYSCALE_PALETTE[steps // 2]  # 중간 색상 반환
	# min_pct~max_pct를 0~1로 정규화 (보정 없이 순수하게)
	t = max(0.0, min(1.0, (p - min_pct) / (max_pct - min_pct)))
	# 연속적인 색상 보간
	return _interpolate_color(t, GRAYSCALE_PALETTE)


def _auto_text_color(bg_hex: str) -> str:
	"""배경색 대비에 따라 글자색 자동 선택(화이트/다크). YIQ 기준."""
	r, g, b = _hex_to_rgb(bg_hex)
	yiq = (r * 299 + g * 587 + b * 114) / 1000
	return "#FFFFFF" if yiq < 140 else "#0B1F4D"

def _shade_for_other_column(pct: float) -> str:
	"""기타열용 고정 색상"""
	# 기타열은 항상 #D1D5DB 색상으로 고정
	return "#D1D5DB"


def _interpolate_color(t: float, color_palette: List[str]) -> str:
	"""0~1 사이의 값 t에 대해 색상 팔레트에서 보간된 색상을 반환."""
	if not color_palette:
		return "#E5E7EB"
	if len(color_palette) == 1:
		return color_palette[0]
	
	# t를 팔레트 인덱스 범위로 변환
	steps = len(color_palette)
	idx = t * (steps - 1)
	
	# 정수 부분과 소수 부분 분리
	idx_floor = int(idx)
	idx_ceil = min(idx_floor + 1, steps - 1)
	fraction = idx - idx_floor
	
	# 경계 처리
	if idx_floor >= steps - 1:
		return color_palette[-1]
	if idx_floor < 0:
		return color_palette[0]
	
	# 두 색상 사이 보간
	color1 = color_palette[idx_floor]
	color2 = color_palette[idx_ceil]
	
	return _blend_colors(color1, color2, fraction)


def _blend_colors(color1: str, color2: str, ratio: float) -> str:
	"""두 색상을 주어진 비율로 혼합하여 새로운 색상을 반환."""
	# HEX 색상을 RGB로 변환
	r1, g1, b1 = int(color1[1:3], 16), int(color1[3:5], 16), int(color1[5:7], 16)
	r2, g2, b2 = int(color2[1:3], 16), int(color2[3:5], 16), int(color2[5:7], 16)
	
	# 보간 계산
	r = int(r1 + (r2 - r1) * ratio)
	g = int(g1 + (g2 - g1) * ratio)
	b = int(b1 + (b2 - b1) * ratio)
	
	# RGB를 HEX로 변환
	return f"#{r:02x}{g:02x}{b:02x}"


def build_ranking_chart(question_rows: List[Dict[str, str]], ordered_counts: "OrderedDict[str, int]") -> str:
	"""순위형 전용 간단 랭킹 차트(이메일 호환 테이블 기반).
	- 막대: 비율에 비례한 회색 배경 + 기본 팔레트 전경
	- 정렬: 상위→하위
	- 레이아웃: 항목명(좌) | 막대+퍼센트(우)
	"""
	items = list(ordered_counts.items())
	if not items:
		return '<div style="color:#6B7280;font-size:12px;">유효한 응답이 없습니다.</div>'
	# 총합
	total = sum(v for _, v in items) or 1
	# 행 빌드
	rows_html: List[str] = []
	for label, cnt in items:
		pct = round(100.0 * cnt / total, 1)
		bar_w = int(round(pct))
		rows_html.append(
			'<tr>'
			f'<td style="padding:4px 8px;color:#374151;font-size:12px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">{html_escape(label)}</td>'
			'<td style="padding:4px 8px;">'
			f'<div style="position:relative;height:16px;background:#E5E7EB;border-radius:8px;overflow:hidden;">'
			f'<div style="position:absolute;left:0;top:0;bottom:0;width:{bar_w}%;background:{PRIMARY_PALETTE[1]};"></div>'
			f'<div style="position:relative;z-index:1;text-align:right;color:#111827;font-size:12px;line-height:16px;padding:0 6px;">{pct:.1f}%</div>'
			'</div>'
			'</td>'
			'</tr>'
		)
	return (
		'<table role="presentation" cellpadding="0" cellspacing="0" border="0" '
		'style="width:100%;border-collapse:separate;table-layout:fixed;">'
		'<colgroup><col style="width:40%;"><col style="width:60%;"></colgroup>'
		'<tbody>' + ''.join(rows_html) + '</tbody></table>'
	)
def build_other_responses_summary(question_rows: List[Dict[str, str]]) -> str:
	"""기타 응답들을 수집하여 주관식 요약과 같은 형태로 표시"""
	# 기타 응답 수집 (text_yn=1이고 lkng_cntnt가 있는 경우)
	other_responses = []
	for r in question_rows:
		qtype_code = (r.get("qsit_type_ds_cd") or "").strip()
		text_yn = (r.get("text_yn") or "").strip()
		if qtype_code == "10" and text_yn in ("1", "Y", "y"):
			other_text = (r.get("answ_cntnt") or "").strip()
			# 응답 내용 길이 체크 (최소 길이 미만이면 제외)
			if len(other_text) < MIN_RESPONSE_LENGTH:
				continue
			if other_text and other_text not in {".", "0", "-", "N/A", "NA", "null", "NULL", "미응답", "무응답"}:
				other_responses.append(r)  # 전체 행을 저장
	
	if not other_responses:
		return ""
	
	# 주관식 요약과 동일한 로직으로 카테고리별 분류
	rows = aggregate_subjective_by_category(other_responses)
	if not rows:
		return ""
	
	# 주관식 요약과 동일한 HTML 생성
	html_parts = []
	# 총 응답 수 계산
	total_other_responses = len(other_responses)
	total_other_responses_formatted = f"{total_other_responses:,}"
	html_parts.append(f'<div style="margin-top:24px;font-weight:700;font-size:14px;color:#111827;margin-bottom:8px;">기타 응답 요약 (n={total_other_responses_formatted})</div>')
	
	# 막대 너비 스케일링을 위한 최대값 (새로운 sentiment 분류 포함) - 무응답과 기타는 별도 스케일링
	excluded_categories = {'무응답', '기타'}
	normal_rows = [r for r in rows if str(r.get('category', '')) not in excluded_categories]
	special_rows = [r for r in rows if str(r.get('category', '')) in excluded_categories]
	
	# 일반 카테고리들의 최대값 (새로운 sentiment 분류 반영)
	max_bar_normal = max(max(int(r['pos']), int(r['neg']), int(r['sug']), int(r['inq']), int(r['no_resp'])) for r in normal_rows) if normal_rows else 1
	# 무응답과 기타의 최대값
	max_bar_special = max(max(int(r['pos']), int(r['neg']), int(r['sug']), int(r['inq']), int(r['no_resp'])) for r in special_rows) if special_rows else 1
	# 색상 - 5개 sentiment에 대한 색상 설정
	config = COLOR_CONFIG["pick_1_color"]
	pos_color = PRIMARY_PALETTE[config["indices"][0]]  # 긍정: PRIMARY_PALETTE에서 80% 색상
	neg_color = CONTRAST_PALETTE[config["indices"][0]]  # 부정: CONTRAST_PALETTE에서 80% 색상
	sug_color = "#10B981"  # 제안: 초록색
	inq_color = "#3B82F6"  # 문의: 파란색
	no_resp_color = GRAYSCALE_PALETTE[config["indices"][0]]  # 무응답: 회색
	# 헤더 - 열 너비: 순번(40px) + 카테고리(130px) + 응답수(220px) + 키워드5개(나머지 균등분할)
	keyword_col_width = "calc((100% - 390px) / 4)"  # 390px = 40+130+220
	head = (
		'<table role="presentation" cellpadding="0" cellspacing="0" border="0" style="width:100%;table-layout:fixed;border-collapse:collapse;">'
		f'<colgroup><col style="width:40px;"><col style="width:130px;"><col style="width:220px;"><col style="width:{keyword_col_width};"><col style="width:{keyword_col_width};"><col style="width:{keyword_col_width};"><col style="width:{keyword_col_width};"></colgroup>'
		'<thead><tr>'
		'<th style="text-align:left;padding:6px 8px;color:#374151;font-size:12px;border-bottom:1px solid #E5E7EB;">순번</th>'
		'<th style="text-align:left;padding:6px 8px;color:#374151;font-size:12px;border-bottom:1px solid #E5E7EB;">카테고리</th>'
		'<th style="text-align:left;padding:6px 8px;color:#374151;font-size:12px;border-bottom:1px solid #E5E7EB;">긍정/부정/제안/문의 수</th>'
		'<th style="text-align:left;padding:6px 8px;color:#374151;font-size:12px;border-bottom:1px solid #E5E7EB;">긍정 키워드</th>'
		'<th style="text-align:left;padding:6px 8px;color:#374151;font-size:12px;border-bottom:1px solid #E5E7EB;">부정 키워드</th>'
		'<th style="text-align:left;padding:6px 8px;color:#374151;font-size:12px;border-bottom:1px solid #E5E7EB;">제안 키워드</th>'
		'<th style="text-align:left;padding:6px 8px;color:#374151;font-size:12px;border-bottom:1px solid #E5E7EB;">문의 키워드</th>'
		'</tr></thead><tbody>'
	)
	row_html: List[str] = []
	for idx, d in enumerate(rows, start=1):
		pos = int(d['pos'])  # type: ignore
		neg = int(d['neg'])  # type: ignore
		sug = int(d['sug'])  # type: ignore
		inq = int(d['inq'])  # type: ignore
		no_resp = int(d['no_resp'])  # type: ignore
		cat = str(d['category'])  # type: ignore
		cat_total = pos + neg + sug + inq + no_resp
		pos_kw: Counter = d['pos_kw']  # type: ignore
		neg_kw: Counter = d['neg_kw']  # type: ignore
		sug_kw: Counter = d['sug_kw']  # type: ignore
		inq_kw: Counter = d['inq_kw']  # type: ignore
		no_resp_kw: Counter = d['no_resp_kw']  # type: ignore
		
		# 기타 위쪽에 대시 스타일의 가로줄 추가
		if cat == '기타':
			row_html.append('<tr><td colspan="7" style="padding:8px 0 4px 0;height:0;line-height:0;"><div style="height:2px;background:transparent;"></div></td></tr>')
		
		# 바 너비(%): 최소 가시성 3% - 카테고리에 따라 적절한 max_bar 사용
		current_max_bar = max_bar_special if cat in excluded_categories else max_bar_normal
		pos_w = max(3.0, round(100.0 * pos / current_max_bar, 2))
		neg_w = max(3.0, round(100.0 * neg / current_max_bar, 2))
		sug_w = max(3.0, round(100.0 * sug / current_max_bar, 2))
		inq_w = max(3.0, round(100.0 * inq / current_max_bar, 2))
		bars = (
			'<table role="presentation" cellpadding="0" cellspacing="0" border="0" style="width:100%;table-layout:fixed;border-collapse:collapse;">'
			'<tbody>'
			'<tr>'
			'<td style="width:44px;padding:0 6px 0 0;color:#111827;font-size:12px;white-space:nowrap;">긍정</td>'
			f'<td style="padding:0;vertical-align:middle;overflow:hidden;">'
			f'<div style="height:12px;background:#E5E7EB;overflow:hidden;width:100%;"><div style="height:12px;background:{pos_color};width:{pos_w}%;"></div></div>'
			'</td>'
			f'<td style="width:30px;padding-left:6px;color:#111827;font-size:12px;white-space:nowrap;">{pos}</td>'
			'</tr>'
			'<tr>'
			'<td style="width:44px;padding:4px 6px 0 0;color:#111827;font-size:12px;white-space:nowrap;">부정</td>'
			f'<td style="padding:4px 0 0 0;vertical-align:middle;overflow:hidden;">'
			f'<div style="height:12px;background:#E5E7EB;overflow:hidden;width:100%;"><div style="height:12px;background:{neg_color};width:{neg_w}%;"></div></div>'
			'</td>'
			f'<td style="width:40px;padding:4px 0 0 6px;color:#111827;font-size:12px;white-space:nowrap;">{neg}</td>'
			'</tr>'
			'<tr>'
			'<td style="width:44px;padding:4px 6px 0 0;color:#111827;font-size:12px;white-space:nowrap;">제안</td>'
			f'<td style="padding:4px 0 0 0;vertical-align:middle;overflow:hidden;">'
			f'<div style="height:12px;background:#E5E7EB;overflow:hidden;width:100%;"><div style="height:12px;background:{sug_color};width:{sug_w}%;"></div></div>'
			'</td>'
			f'<td style="width:40px;padding:4px 0 0 6px;color:#111827;font-size:12px;white-space:nowrap;">{sug}</td>'
			'</tr>'
			'<tr>'
			'<td style="width:44px;padding:4px 6px 0 0;color:#111827;font-size:12px;white-space:nowrap;">문의</td>'
			f'<td style="padding:4px 0 0 0;vertical-align:middle;overflow:hidden;">'
			f'<div style="height:12px;background:#E5E7EB;overflow:hidden;width:100%;"><div style="height:12px;background:{inq_color};width:{inq_w}%;"></div></div>'
			'</td>'
			f'<td style="width:40px;padding:4px 0 0 6px;color:#111827;font-size:12px;white-space:nowrap;">{inq}</td>'
			'</tr>'
			'</tbody></table>'
		)
		# 키워드: 기본 최대 SUBJECTIVE_KEYWORDS_LIMIT, 기타는 SUBJECTIVE_KEYWORDS_LIMIT_OTHER
		limit_kw = SUBJECTIVE_KEYWORDS_LIMIT_OTHER if cat == '기타' else SUBJECTIVE_KEYWORDS_LIMIT
		pos_list = [f"{html_escape(k)} ({c})" for k, c in pos_kw.most_common(limit_kw)]
		neg_list = [f"{html_escape(k)} ({c})" for k, c in neg_kw.most_common(limit_kw)]
		sug_list = [f"{html_escape(k)} ({c})" for k, c in sug_kw.most_common(limit_kw)]
		inq_list = [f"{html_escape(k)} ({c})" for k, c in inq_kw.most_common(limit_kw)]
		no_resp_list = [f"{html_escape(k)} ({c})" for k, c in no_resp_kw.most_common(limit_kw)]
		# 키워드 셀(폭 고정, 높이 통일) - 새로운 sentiment 분류 반영
		pos_kw_cell = (
			'<div style="padding:6px;border:1px solid #B9C5FE;background:#E8EDFF;border-radius:6px;min-height:60px;">'
			'<div style="color:#2539E9;font-size:12px;font-weight:700;margin-bottom:4px;">긍정</div>'
			f'<div style="color:#2539E9;font-size:11px;word-break:break-word;">{", ".join(pos_list) if pos_list else "-"}</div>'
			'</div>'
		)
		neg_kw_cell = (
			'<div style="padding:6px;border:1px solid #FEE2E2;background:#FEF2F2;border-radius:6px;min-height:60px;">'
			'<div style="color:#991B1B;font-size:12px;font-weight:700;margin-bottom:4px;">부정</div>'
			f'<div style="color:#991B1B;font-size:11px;word-break:break-word;">{", ".join(neg_list) if neg_list else "-"}</div>'
			'</div>'
		)
		sug_kw_cell = (
			'<div style="padding:6px;border:1px solid #D1FAE5;background:#ECFDF5;border-radius:6px;min-height:60px;">'
			'<div style="color:#065F46;font-size:12px;font-weight:700;margin-bottom:4px;">제안</div>'
			f'<div style="color:#065F46;font-size:11px;word-break:break-word;">{", ".join(sug_list) if sug_list else "-"}</div>'
			'</div>'
		)
		inq_kw_cell = (
			'<div style="padding:6px;border:1px solid #DBEAFE;background:#EFF6FF;border-radius:6px;min-height:60px;">'
			'<div style="color:#1E40AF;font-size:12px;font-weight:700;margin-bottom:4px;">문의</div>'
			f'<div style="color:#1E40AF;font-size:11px;word-break:break-word;">{", ".join(inq_list) if inq_list else "-"}</div>'
			'</div>'
		)
		# 무응답과 기타는 순번셀과 카테고리 셀 병합
		if cat in excluded_categories:
			row_html.append(
				'<tr>'
				f'<td colspan="2" style="padding:8px;color:#111827;font-size:12px;">{html_escape(cat)} ({cat_total})</td>'
				f'<td style="padding:8px;">{bars}</td>'
				f'<td style="padding:4px;vertical-align:top;">{pos_kw_cell}</td>'
				f'<td style="padding:4px;vertical-align:top;">{neg_kw_cell}</td>'
				f'<td style="padding:4px;vertical-align:top;">{sug_kw_cell}</td>'
				f'<td style="padding:4px;vertical-align:top;">{inq_kw_cell}</td>'
				'</tr>'
			)
		else:
			row_html.append(
				'<tr>'
				f'<td style="padding:8px;color:#111827;font-size:12px;text-align:center;">{idx}</td>'
				f'<td style="padding:8px;color:#111827;font-size:12px;">{html_escape(cat)} ({cat_total})</td>'
				f'<td style="padding:8px;">{bars}</td>'
				f'<td style="padding:4px;vertical-align:top;">{pos_kw_cell}</td>'
				f'<td style="padding:4px;vertical-align:top;">{neg_kw_cell}</td>'
				f'<td style="padding:4px;vertical-align:top;">{sug_kw_cell}</td>'
				f'<td style="padding:4px;vertical-align:top;">{inq_kw_cell}</td>'
				'</tr>'
			)
	html_parts.append(head + ''.join(row_html) + '</tbody></table>')
	
	return ''.join(html_parts)


def build_general_heatmap(question_rows: List[Dict[str, str]], label_order: List[str], question_title: str = "객관식 문항", all_data: List[Dict[str, str]] = None, question_id: str = None) -> str:
	"""객관식(일반) 문항용 히트맵: 행=세그 버킷, 열=라벨.
	- 만족도 전용 요약/순만족도 없이, 퍼센트 셀만 표시
	- 스타일은 만족도 히트맵과 톤앤매너 일치
	"""
	# 만족도 패턴인 경우 라벨 재정렬
	if is_evaluation_pattern(label_order):
		# 만족도 순서로 정렬 (왼쪽일수록 점수 낮음, 오른쪽일수록 점수 높음)
		satisfaction_order = ["매우 불만족해요", "불만족해요", "보통이에요", "만족해요", "매우 만족해요"]
		order = []
		# 만족도 순서에 있는 것들 먼저 추가
		for label in satisfaction_order:
			if label in label_order:
				order.append(label)
		# 나머지는 알파벳 순으로 추가
		remaining = sorted([l for l in label_order if l not in order])
		order.extend(remaining)
	else:
		order = list(label_order)
	# 세그 정의: (표시명, 키)
	seg_defs: List[Tuple[str, str]] = [
		("성별", "gndr_seg"),
		("계좌고객", "account_seg"),
		("연령대", "age_seg"),
		("가입경과일", "rgst_gap"),
		("VASP 연결", "vasp"),
		("수신상품 가입", "dp_seg"),
		("대출상품 가입", "loan_seg"),
		("카드상품 가입", "card_seg"),
		("서비스 이용", "suv_seg"),
	]
	# 세그별 버킷 후보(존재하는 것만 사용). 일부는 정해진 순서를 제공
	preferred_orders: Dict[str, List[str]] = {
		"gndr_seg": ["01.남성", "02.여성"],
		"age_seg": ["01.10대","02.20대","03.30대","04.40대","05.50대","06.60대","07.기타"],
	}
	# 버킷 수집
	seg_bucket_rows: List[Tuple[str, List[Dict[str, str]]]] = []
	# 전체(집계) 먼저 한 줄 추가
	seg_bucket_rows.append(("전체", question_rows))
	for seg_title, seg_key in seg_defs:
		vals = set()
		for r in question_rows:
			v = (r.get(seg_key) or "").strip()
			if v:
				vals.add(v)
		# 선호 순서가 있으면 그 순서로, 아니면 문자열 정렬
		if seg_key in preferred_orders:
			ordered_vals = [v for v in preferred_orders[seg_key] if v in vals]
			# 누락분은 사전순으로 뒤에
			remain = sorted([v for v in vals if v not in set(ordered_vals)])
			ordered_vals += remain
		else:
			ordered_vals = sorted(vals)
		for raw_val in ordered_vals:
			# '기타' 버킷 제외
			if clean_axis_label(raw_val) == '기타':
				continue
			bucket_label = f"{seg_title} - {clean_axis_label(raw_val)}"
			rows_subset = [r for r in question_rows if (r.get(seg_key) or '').strip() == raw_val]
			if not rows_subset:
				continue
			seg_bucket_rows.append((bucket_label, rows_subset))

	# 스타일(기존 보고서 톤) - 모든 라인 제거, 헤더/본문 하단 보더 제거
	head_style = 'padding:6px 8px;color:#111827;font-size:12px;text-align:center;'
	# 만족도 라벨 헤더 전용 스타일(패딩 4px, 수직 중앙 정렬)
	label_head_style = 'padding:0 2px;color:#111827;font-size:12px;text-align:center;vertical-align:middle;overflow:hidden;'
	rowhead_style = 'padding:0 8px;color:#111827;font-size:12px;text-align:left;white-space:nowrap;height:20px;vertical-align:middle;'
	# 폰트 크기 12px을 강제(이메일 클라이언트 상속 방지). 숫자 중앙 정렬 및 고정 높이 20px
	cell_style_base = 'padding:0;text-align:center;white-space:nowrap;font-size:11px;line-height:1.2;height:20px;vertical-align:middle;'

	# 기타 항목이 있는지 확인
	has_other = any(lb == "기타" for lb in order)
	
	# 동적 폭 계산: 세그(110) + 값(120) + 스페이서(20) + 기타스페이서(20) + 기타(40) + 나머지항목들(균등분할)
	fixed_width = 110 + 120 + 20  # 세그 + 값 + 스페이서
	if has_other:
		fixed_width += 20 + 60  # 기타 스페이서 + 기타 (60px로 변경)
		other_count = 1
		normal_count = len(order) - 1
	else:
		other_count = 0
		normal_count = len(order)
	
	# 모든 히트맵 열을 40px로 고정
	normal_width = 40
	
	# 헤더 구성: 세그먼트(세그/값) | (값-히트맵) 20px | 라벨들(1fr씩) | (히트맵-기타) 20px | 기타
	colgroup = (
		'<col style="width:100px;min-width:100px;max-width:100px;">'  # 세그명 (고정 100px)
		+ '<col style="width:110px;min-width:110px;max-width:110px;">'  # 값 (고정 110px)
		+ '<col style="width:20px;min-width:20px;max-width:20px;">'   # 값-히트맵 간격 (고정 20px)
		+ ''.join(['<col style="width:1fr;">' for _ in range(len(order) - (1 if has_other else 0))])  # 일반 히트맵 열들 (1fr씩 배분)
		+ ('<col style="width:20px;min-width:20px;max-width:20px;">' if has_other else '')  # 히트맵-기타 간격 (고정 20px, 기타가 있을 때만)
		+ ('<col style="width:60px;min-width:60px;max-width:60px;">' if has_other else '')  # 기타 (고정 60px, 기타가 있을 때만)
	)
	head_cells = [
		f'<th style="{head_style}">&nbsp;</th>',
		f'<th style="{head_style}">&nbsp;</th>'
	]
	# (값-히트맵) 갭 헤더(반응형)
	head_cells.append('<th style="padding:0;line-height:0;font-size:0;">&nbsp;</th>')
	# 일반 히트맵 열들 헤더
	for lb in order:
		if lb != "기타":  # 기타가 아닌 열들만
			head_cells.append(
				f'<th style="{label_head_style}"><div style="display:block;width:100%;height:100%;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;line-height:1.2;text-align:center;">{html_escape(_display_label(lb, order))}</div></th>'
			)
	# (히트맵-기타) 갭 헤더(반응형, 기타가 있을 때만)
	if has_other:
		head_cells.append('<th style="padding:0;line-height:0;font-size:0;">&nbsp;</th>')
	# 기타 헤더 (기타가 있을 때만)
	if has_other:
		head_cells.append(
			f'<th style="{label_head_style}"><div style="display:block;width:100%;height:100%;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;line-height:1.2;text-align:center;">{html_escape(_display_label("기타", order))}</div></th>'
		)
	head_html = '<thead><tr>' + ''.join(head_cells) + '</tr></thead>'

	# 바디 생성(두 단계: 데이터 준비 → rowspan 적용하여 렌더)
	rows_data: List[Dict[str, object]] = []
	for name, rows in seg_bucket_rows:
		cnts = {l: 0 for l in order}
		for r in rows:
			label = label_for_row(r, 'objective') or ''
			if label in cnts:
				cnts[label] += 1
		total = sum(cnts.values()) or 1
		# 세그/값 분리
		if ' - ' in name:
			seg_name, seg_value = name.split(' - ', 1)
		else:
			seg_name, seg_value = name, ''
		rows_data.append({
			'seg_name': seg_name,
			'seg_value': seg_value,
			'cnts': cnts,
			'total': total,
		})

	# 전체 응답 수 계산 (임계치 판단용) - 전체 행의 응답 수 사용
	total_responses = len(question_rows)
	threshold_count = max(int(total_responses * GRAYSCALE_THRESHOLD_PERCENT / 100.0), GRAYSCALE_MIN_COUNT)

	# 동적 색상 스케일링을 위한 최소/최대값 계산 (그레이스케일 대상 제외, 기타 열 제외)
	all_pcts: List[float] = []
	for rd in rows_data:
		cnts = rd['cnts']  # type: ignore
		total = int(rd['total'])
		# 그레이스케일 대상이 아닌 경우만 색상 스케일링에 포함
		if total >= threshold_count:
			# 히트맵 열들의 퍼센트 (기타 열 제외)
			for lb in order:
				if lb != "기타":  # 기타 열은 색상 스케일링에서 제외
					pct = _calculate_percentage(cnts[lb], total)
					all_pcts.append(pct)
	
	min_pct = min(all_pcts) if all_pcts else 0.0
	max_pct = max(all_pcts) if all_pcts else 100.0

	# 기타 열만의 동적 색상 스케일링을 위한 최소/최대값 계산
	other_pcts: List[float] = []
	for rd in rows_data:
		cnts = rd['cnts']  # type: ignore
		total = int(rd['total'])
		if "기타" in cnts:
			pct = _calculate_percentage(cnts["기타"], total)
			other_pcts.append(pct)
	
	min_other_pct = min(other_pcts) if other_pcts else 0.0
	max_other_pct = max(other_pcts) if other_pcts else 100.0

	# 세그별 첫번째 인덱스와 rowspan 계산
	first_index: Dict[str, int] = {}
	rowspan_count: Dict[str, int] = {}
	for idx, rd in enumerate(rows_data):
		seg = str(rd['seg_name'])
		if seg not in first_index:
			first_index[seg] = idx
		rowspan_count[seg] = rowspan_count.get(seg, 0) + 1

	# 값 셀 막대 스케일 기준(최대 n)
	max_total = max((int(rd['total']) for rd in rows_data), default=1) or 1

	body_rows: List[str] = []
	for idx, rd in enumerate(rows_data):
		seg_name = str(rd['seg_name'])
		seg_value = str(rd['seg_value'])
		cnts = rd['cnts']  # type: ignore
		total = int(rd['total'])
		# 세그 그룹 시작 시(첫 그룹 제외) 세그/값 영역에 하나의 연속 라인을 별도 행으로 추가해 끊김 방지
		cells: List[str] = []
		is_group_start = (idx == first_index.get(seg_name))
		if is_group_start and idx != 0:
			# 전체 폭으로 1px 가로줄을 그려 세그/값/히트맵을 관통
			# 위/아래 간격을 4px씩 확보
			colspan = 3 + (len(order) - (1 if has_other else 0)) + (1 if has_other else 0) + (1 if has_other else 0)  # 세그+값+간격 + 일반히트맵열 + 히트맵-기타간격 + 기타열
			body_rows.append('<tr><td colspan="' + str(colspan) + '" style="padding:4px 0;height:0;line-height:0;"><div style="height:1px;background:repeating-linear-gradient(to right, #E5E7EB 0 2px, transparent 2px 4px);"></div></td></tr>')
		if is_group_start:
			cells.append(f'<td rowspan="{rowspan_count.get(seg_name,1)}" style="{rowhead_style}">{html_escape(seg_name)}</td>')
		# 이 행의 보기별 퍼센트 순위 계산 (엣지케이스 판단용)
		seg_pct_map: Dict[str, float] = {lb: (cnts[lb] * 100.0 / (total or 1)) for lb in order}
		seg_rank: List[str] = sorted(order, key=lambda lb: (-seg_pct_map.get(lb, 0.0), order.index(lb)))
		orank: List[str] = _compute_overall_rank_from_rows_data(rows_data, order)
		is_edgecase = (seg_value != '' and bool(orank) and seg_rank != orank)

		# 값 열: 100% 폭 테이블 + 좌측 bar TD(비율, 텍스트 포함) + 우측 여백 TD(잔여)
		bar_w = int(round((total / (max_total or 1)) * 100))
		bar_w_css = max(1, bar_w)  # 폭 0%에서도 텍스트가 보이도록 최소 1px 확보
		# 값셀 좌우 여백 제거(패딩 0)
		value_td_style = 'padding:0;color:#111827;font-size:12px;text-align:left;white-space:nowrap;height:20px;position:relative;overflow:hidden;vertical-align:middle;'
		# 값 열: 100% 폭 테이블 + 좌측 bar TD(비율, 텍스트 포함) + 우측 여백 TD(잔여)
		bar_html = (
			'<table role="presentation" cellpadding="0" cellspacing="0" border="0" style="border-collapse:collapse;width:100%;height:20px;table-layout:fixed;">'
			'<tr>'
			f'<td width="{bar_w_css}%" style="height:20px;line-height:20px;vertical-align:middle;'
			+ ("background-color:#FECACA;" if is_edgecase else "background-color:#D1D5DB;")
			+ 'padding:0;color:#111827;font-size:11px;white-space:nowrap;overflow:visible;">'
			+ f'<span style="margin-left:4px;">{html_escape(seg_value)}'
			+ f'<span style="color:#6B7280;margin-left:6px;">(n={total:,})</span></span>'
			+ '</td>'
			f'<td width="{100 - bar_w_css}%" style="height:20px;line-height:20px;vertical-align:middle;padding:0;margin:0;"></td>'
			+ '</tr></table>'
		)
		text_html = ''
		if seg_value:
			cells.append(f'<td style="{value_td_style}">{bar_html}{text_html}</td>')
		else:
			# 전체 행도 동일한 방식으로 표시
			bar_html = (
				'<table role="presentation" cellpadding="0" cellspacing="0" border="0" style="border-collapse:collapse;width:100%;height:20px;table-layout:fixed;">'
				'<tr>'
				f'<td width="{bar_w_css}%" style="height:20px;line-height:20px;vertical-align:middle;background-color:#D1D5DB;padding:0;color:#111827;font-size:11px;white-space:nowrap;overflow:visible;">'
				+ '<span style="margin-left:4px;">전체'
				+ f'<span style="color:#6B7280;margin-left:6px;">(n={total:,})</span></span>'
				+ '</td>'
				f'<td width="{100 - bar_w_css}%" style="height:20px;line-height:20px;vertical-align:middle;padding:0;margin:0;"></td>'
				+ '</tr></table>'
			)
			cells.append(
				f'<td style="{value_td_style}">{bar_html}</td>'
			)
		# 값-히트맵 사이 스페이서(32px) - 세그 단위로 행 병합
		if is_group_start:
			cells.append(f'<td rowspan="{rowspan_count.get(seg_name,1)}" style="line-height:0;font-size:0;">\n\t<div style="padding:0 4px;">\n\t\t<div style="height:16px;background:transparent;"></div>\n\t</div>\n</td>')
		# 퍼센트 셀들 - n이 임계치 미만이면 그레이스케일 적용, 기타 열은 항상 그레이스케일
		use_grayscale = total < threshold_count
		for lb in order:
			# 기타 항목 앞에 대시 스페이서 추가
			if lb == "기타" and has_other:
				if is_group_start:
					cells.append(f'<td rowspan="{rowspan_count.get(seg_name,1)}" style="width:20px;min-width:20px;max-width:20px;line-height:0;font-size:0;">\n\t<div style="padding:0 4px;">\n\t\t<div style="height:16px;background:transparent;"></div>\n\t</div>\n</td>')
			pct = round(100.0 * cnts[lb] / (total or 1), 1)
			if use_grayscale or lb == "기타":
				if lb == "기타":
					bg = _shade_for_other_column(pct)  # 기타열은 단일 색상 (0%~30% 단계)
				else:
					bg = _shade_for_grayscale_dynamic(pct, min_pct, max_pct)
			else:
				bg = _shade_for_pct_dynamic(pct, min_pct, max_pct)
			fg = _auto_text_color(bg)
			if lb == "기타":
				cells.append(
					f'<td style="{cell_style_base}width:60px;min-width:60px;max-width:60px;padding:0;background:{bg};background-color:{bg};background-image:none;color:{fg};border-radius:12px;overflow:hidden;">{pct:.1f}%</td>'
				)
			else:
				cells.append(
					f'<td style="{cell_style_base}width:60px;padding:0;background:{bg};background-color:{bg};background-image:none;color:{fg};">{pct:.1f}%</td>'
				)
		row_attr = '' if is_edgecase else ''
		body_rows.append('<tr' + row_attr + '>' + ''.join(cells) + '</tr>')
	table = (
		'<table role="presentation" cellpadding="0" cellspacing="0" border="0" '
		'style="width:100%;table-layout:fixed;border-collapse:collapse;padding-left:4px;padding-right:8px;">'
		+ f'<colgroup>{colgroup}</colgroup>'
		+ head_html + '<tbody>' + ''.join(body_rows) + '</tbody>' + '</table>'
	)
	# 제목 (아래 간격 0)
	heading = '<div style="font-weight:700;font-size:14px;color:#111827;margin-bottom:0;">Seg.별 히트맵</div>'
	
	# 교차분석 엣지케이스 수집
	edge_cases = []
	for label in order:
		edge_cases.extend(_analyze_cross_segments(question_rows, question_title, "objective", label))
	
	# 엣지케이스 섹션 생성
	edge_cases_section = _build_question_edge_cases_section(edge_cases, order, question_rows, all_data, question_id)
	
	# 기타 응답 요약 추가
	other_summary = build_other_responses_summary(question_rows)
	
	return '<div style="margin:12px 0;padding:12px;border:1px solid #E5E7EB;border-radius:6px;background:#FFFFFF;">' + heading + table + edge_cases_section + (other_summary if other_summary else '') + '</div>'


if __name__ == "__main__":
	sys.exit(main(sys.argv[1:]))