import csv
import sys
import os
import re
import json
from collections import Counter, defaultdict, OrderedDict
from typing import Dict, List, Tuple, Optional, Set
from itertools import combinations

from src.constants import *
from src.utils import *

# =========================
# 파일 경로 설정
# =========================
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")  # 데이터 파일이 저장된 디렉토리
CSV_FILE_NAME = "20251023_sample_data.csv"  # 기본 CSV 파일명
DEFAULT_CSV_PATH = os.path.join(DATA_DIR, CSV_FILE_NAME)  # 기본 CSV 파일 전체 경로

# 환경변수로 가중치/정규화 설정을 동적으로 오버라이드
def _parse_bool_env(name: str, default: bool) -> bool:
    """환경변수의 참/거짓 문자열을 bool로 파싱.
    허용 값: 1, true, yes, y, on (대소문자 무관). 미설정 시 default 반환
    """
    val = os.getenv(name)
    if val is None:
        return default
    v = val.strip().lower()
    return v in ("1", "true", "yes", "y", "on")

def _load_env_ranking_weights() -> None:
    """순위형 가중치 구성을 환경변수에서 읽어 동적으로 오버라이드.
    - RANKING_WEIGHTS_JSON: 전체 맵 일괄 오버라이드(권장)
    - RANKING_WEIGHTS_STATS_1OR2 / _1OR2OR3: 부분 맵만 덮어쓰기
    - RANKING_NORMALIZE_PER_RESPONDENT: 응답자 단위 정규화 여부
    실패해도 조용히 무시하여 기본값 유지
    """
    global RANKING_WEIGHTS, RANKING_NORMALIZE_PER_RESPONDENT
    # 전체 JSON으로 오버라이드 (권장)
    raw = os.getenv("RANKING_WEIGHTS_JSON")
    if raw:
        try:
            data = json.loads(raw)
            if isinstance(data, dict):
                RANKING_WEIGHTS = data  # type: ignore
        except Exception:
            pass
    else:
        # 개별 맵만 JSON 문자열로 오버라이드 허용
        s12 = os.getenv("RANKING_WEIGHTS_STATS_1OR2")
        if s12:
            try:
                data12 = json.loads(s12)
                if isinstance(data12, dict):
                    RANKING_WEIGHTS.setdefault("stats_1or2", {})
                    for k, v in data12.items():
                        try:
                            key = int(k)
                        except Exception:
                            continue
                        if isinstance(v, list):
                            RANKING_WEIGHTS["stats_1or2"][key] = v  # type: ignore
            except Exception:
                pass
        s123 = os.getenv("RANKING_WEIGHTS_STATS_1OR2OR3")
        if s123:
            try:
                data123 = json.loads(s123)
                if isinstance(data123, dict):
                    RANKING_WEIGHTS.setdefault("stats_1or2or3", {})
                    for k, v in data123.items():
                        try:
                            key = int(k)
                        except Exception:
                            continue
                        if isinstance(v, list):
                            RANKING_WEIGHTS["stats_1or2or3"][key] = v  # type: ignore
            except Exception:
                pass
    # 정규화 여부 env 적용
    RANKING_NORMALIZE_PER_RESPONDENT = _parse_bool_env("RANKING_NORMALIZE_PER_RESPONDENT", RANKING_NORMALIZE_PER_RESPONDENT)

_load_env_ranking_weights()

# 공통 Remark 텍스트
def build_remark_block(items: List[str]) -> str:
	"""Remark 항목 목록을 받아 HTML 블록을 생성. 항목이 없으면 빈 문자열 반환."""
	if not items:
		return ""
	return (
		f'<div style="margin:6px 0 0 0;font-size:11px;line-height:1.6;color:{GRAYSCALE_PALETTE[5]};">'
		+ '<div style="font-weight:700;color:#67748E;margin-bottom:2px;">※ Remark</div>'
		+ ''.join(f'<div>{itm}</div>' for itm in items)
		+ '</div>'
	)


def build_heatmap_remark(base_items: Optional[List[str]] = None, include_edgecase_marker: bool = False) -> str:
	items: List[str] = []
	if base_items:
		items.extend(base_items)
	if include_edgecase_marker:
		edge_item = (
			'· '
			+ f'<span style="color:{CONTRAST_PALETTE[3]};">■</span>'
			+ f'<span style="color:{GRAYSCALE_PALETTE[5]};"> : 전체 평균대비 응답순서가 다른 Seg.</span>'
		)
		if edge_item not in items:
			items.append(edge_item)
	return build_remark_block(items)


def has_heatmap_edgecase_marker(html: str) -> bool:
	marker1 = f"box-shadow: inset 0 0 0 2px {CONTRAST_PALETTE[3]}"
	marker2 = f"background-color:{CONTRAST_PALETTE[3]}"
	return (marker1 in html) or (marker2 in html)

# =========================
# 유틸리티 함수들
# =========================

def is_evaluation_pattern(labels: List[str]) -> bool:
    """Deprecated: 항상 False 반환(호환성을 위해 남겨둠)."""
    return False

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
	# 숫자 접두 제거: 항상 원본 라벨만 반환
	return label

# 원숫자(동그라미 숫자) 매핑: 1~10
CIRCLED_NUMS = ['①','②','③','④','⑤','⑥','⑦','⑧','⑨','⑩']

def _circled_num(n: int) -> str:
	"""1~10은 원숫자 기호로, 그 외는 숫자 그대로 반환."""
	try:
		if 1 <= int(n) <= 10:
			return CIRCLED_NUMS[int(n) - 1]
	except Exception:
		pass
	return str(n)

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
	"""일반형 교차분석: 특정 라벨의 전체 대비 세그 조합 편차(%) 탐지.

	처리 개요:
	- 세그 후보 중 실제 데이터가 2개 이상 버킷을 가진 세그만 사용
	- 2차원까지 조합(CROSS_ANALYSIS_MAX_DIMENSIONS 적용)
	- 각 조합에 대해 (해당 라벨 비율 - 전체 라벨 비율)의 차이가
	  `CROSS_ANALYSIS_DIFFERENCE_THRESHOLD`(퍼센트 포인트) 이상이면 엣지케이스로 수집
	- 최소 응답 수(`CROSS_ANALYSIS_MIN_RESPONSES`) 미만인 조합은 신뢰성 문제로 제외
	"""
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
	"""평가형 교차분석 표를 '기타 응답 요약' 스타일로 생성한다.
	- 제목: Seg.간 교차분석
	- 열: 보기문항 | 2가지 이상 특성이 결합된 고객 | 평균점수 | 응답수
	- 각 행은 (라벨, 세그 조합) 단위로 구성
	"""
	if not edge_cases:
		return ""

	# 표시용 인덱스 (평가형은 전체 평균 기준이므로 라벨 고정)
	if all_labels is None:
		all_labels = ["전체 평균"]
	label_pos = {lb: (idx + 1) for idx, lb in enumerate(all_labels)}

	parts: List[str] = []
	parts.append('<div style="margin-top:16px;">')
	parts.append('<div style="font-weight:700;font-size:14px;color:#111827;margin-bottom:8px;">Seg.간 교차분석</div>')
	parts.append('<table style="width:100%;border-collapse:collapse;border:1px solid #E5E7EB;">')
	parts.append('<thead><tr>'
				 '<th style="background:#4D596F;color:#FFFFFF;font-size:12px;padding:8px;border:1px solid #E5E7EB;width:280px;">평가문항</th>'
				 '<th style="background:#4D596F;color:#FFFFFF;font-size:12px;padding:8px;border:1px solid #E5E7EB;">2가지 특성이 결합된 고객</th>'
				 '<th style="background:#4D596F;color:#FFFFFF;font-size:12px;padding:8px;border:1px solid #E5E7EB;width:180px;">평균점수</th>'
				 '<th style="background:#4D596F;color:#FFFFFF;font-size:12px;padding:8px;border:1px solid #E5E7EB;width:60px;">응답수</th>'
				 '</tr></thead><tbody>')

	# 케이스를 차이 큰 순으로 제한 (전역 TOP K)
	cases = sorted(edge_cases, key=lambda x: abs(float(x.get("difference", 0.0))), reverse=True)[:CROSS_ANALYSIS_TOP_K]
	# 같은 보기문항끼리 묶어서 첫 번째 셀 병합(rowspan)
	grouped_cases: Dict[str, List[Dict]] = {}
	for case in cases:
		lb = str(case.get("label", "전체 평균"))
		grouped_cases.setdefault(lb, []).append(case)
	for lb, lb_cases in grouped_cases.items():
		rowspan = len(lb_cases)
		overall = float(lb_cases[0].get("overall_pct", 0.0))
		qtitle = str(lb_cases[0].get("question_title", ""))
		if not qtitle and question_rows:
			try:
				qtitle = (question_rows[0].get("qsit_ttl") or "").strip()
			except Exception:
				qtitle = ""
		question_cell_text = html_escape(qtitle) if qtitle else html_escape(lb)
		avg_text = f" ({overall:.2f}점)" if overall else ""
		question_cell_html = f"<strong>{question_cell_text}</strong>{avg_text}"
		for idx, case in enumerate(lb_cases):
			combo = float(case.get("combo_pct", 0.0))
			diff_pct = float(case.get("difference", 0.0))
			pill_parts: List[str] = []
			for seg, value in case.get("segment_combination", {}).items():
				display_value = get_segment_display_value(seg, value)
				pill_parts.append(f'<span style="display:inline-block;background:#EDF1F7;padding:6px 8px;margin:2px 0;white-space:nowrap;">{html_escape(display_value)}</span>')
			seg_html = ('<span style="margin:0 6px;color:#6B7280;"> + </span>').join(pill_parts) if pill_parts else '-'
			is_pos = (diff_pct >= 0)
			bg = 'rgba(66,98,255,0.08)' if is_pos else 'rgba(226,58,50,0.08)'
			fg = SUBJECTIVE_POS_BAR_COLOR if is_pos else SUBJECTIVE_NEG_BAR_COLOR
			parts.append('<tr>')
			if idx == 0:
				parts.append(
					f'<td rowspan="{rowspan}" style="border:1px solid #E5E7EB;padding:8px;vertical-align:middle;font-size:12px;line-height:1.4;">{question_cell_html}</td>'
				)
			parts.append(
				f'<td style="border:1px solid #E5E7EB;padding:8px;vertical-align:middle;font-size:12px;text-align:center;">{seg_html}</td>'
			)
			parts.append(
				f'<td style="border:1px solid #E5E7EB;padding:8px;vertical-align:middle;font-size:12px;white-space:nowrap;background:{bg};color:{fg};text-align:center;">{combo:.3f} (평균 대비 {diff_pct:+.1f}%)</td>'
			)
			parts.append(
				f'<td style="border:1px solid #E5E7EB;padding:8px;vertical-align:middle;font-size:12px;text-align:center;">{int(case.get("response_count", 0)):,}건</td>'
			)
			parts.append('</tr>')

	parts.append('</tbody></table>')
	parts.append('</div>')
	return ''.join(parts)

def _build_question_edge_cases_section(edge_cases: List[Dict], all_labels: List[str] = None, question_rows: List[Dict[str, str]] = None, all_data: List[Dict[str, str]] = None, current_question_id: str = None) -> str:
	"""일반형(객관식) 교차분석 표를 '기타 응답 요약' 스타일로 생성한다.
	- 제목: Seg.간 교차분석
	- 열: 보기문항 | 2가지 이상 특성이 결합된 고객 | 응답율 | 응답수
	- 각 행은 (라벨, 세그 조합) 단위로 구성
	"""
	if not edge_cases:
		return ""
	
	# 라벨 순서 및 표시용 인덱스
	if all_labels is None:
		all_labels = list({case["label"] for case in edge_cases})
	label_pos = {lb: (idx + 1) for idx, lb in enumerate(all_labels)}

	# 라벨별 전체 비율
	label_overall_pcts: Dict[str, float] = {}
	for case in edge_cases:
		if case["label"] not in label_overall_pcts:
			label_overall_pcts[case["label"]] = float(case.get("overall_pct", 0.0))

	# 라벨별로 케이스 그룹화 및 정렬 (전역 Top-K 선정을 위해 자르지 않음)
	grouped: Dict[str, List[Dict]] = {}
	for c in edge_cases:
		grouped.setdefault(c["label"], []).append(c)
	for lb in grouped:
		grouped[lb].sort(key=lambda x: abs(float(x.get("combo_pct", 0.0)) - float(x.get("overall_pct", 0.0))), reverse=True)

	# 전역 Top-K 케이스 선별 (gap 내림차순)
	all_cases_ranked: List[Tuple[str, Dict]] = []  # (label, case)
	for lb, cases in grouped.items():
		for cs in cases:
			all_cases_ranked.append((lb, cs))
	all_cases_ranked.sort(key=lambda t: abs(float(t[1].get("combo_pct", 0.0)) - float(t[1].get("overall_pct", 0.0))), reverse=True)
	selected = all_cases_ranked[:CROSS_ANALYSIS_TOP_K]

	# 렌더링 준비
	parts: List[str] = []
	parts.append('<div style="margin-top:16px;">')
	parts.append('<div style="font-weight:700;font-size:14px;color:#111827;margin-bottom:8px;">Seg.간 교차분석</div>')
	parts.append('<table style="width:100%;border-collapse:collapse;border:1px solid #E5E7EB;">')
	parts.append('<thead><tr>'
				 '<th style="background:#4D596F;color:#FFFFFF;font-size:12px;padding:8px;border:1px solid #E5E7EB;width:280px;">보기문항</th>'
				 '<th style="background:#4D596F;color:#FFFFFF;font-size:12px;padding:8px;border:1px solid #E5E7EB;">2가지 특성이 결합된 고객</th>'
				 '<th style="background:#4D596F;color:#FFFFFF;font-size:12px;padding:8px;border:1px solid #E5E7EB;width:180px;">응답율</th>'
				 '<th style="background:#4D596F;color:#FFFFFF;font-size:12px;padding:8px;border:1px solid #E5E7EB;width:60px;">응답수</th>'
				 '</tr></thead><tbody>')

	# 같은 보기문항끼리 묶기 및 첫 번째 셀 병합(rowspan)
	grouped_selected: Dict[str, List[Dict]] = {}
	for lb, case in selected:
		grouped_selected.setdefault(lb, []).append(case)
	# 보기문항 정렬: n번보기(=label_pos) 오름차순
	ordered_labels = sorted(grouped_selected.keys(), key=lambda k: label_pos.get(k, 0))
	for lb in ordered_labels:
		lb_cases = grouped_selected.get(lb, [])
		# 같은 보기문항 내 정렬: 평균대비 gap 내림차순
		lb_cases_sorted = sorted(
			lb_cases,
			key=lambda c: abs(float(c.get('combo_pct', 0.0)) - float(label_overall_pcts.get(lb, 0.0))),
			reverse=True
		)
		overall_pct = float(label_overall_pcts.get(lb, 0.0))
		pos = label_pos.get(lb, 0)
		rowspan = len(lb_cases_sorted)
		for idx, case in enumerate(lb_cases_sorted):
			combo_pct = float(case.get('combo_pct', 0.0))
			# 평균 대비 (부호 포함, %p)
			signed_diff = combo_pct - overall_pct
			# 응답율 색상 (긍정/부정)
			is_pos = (signed_diff >= 0)
			bg = 'rgba(66,98,255,0.08)' if is_pos else 'rgba(226,58,50,0.08)'
			fg = SUBJECTIVE_POS_BAR_COLOR if is_pos else SUBJECTIVE_NEG_BAR_COLOR
			# 세গ 조합 pill (센터 정렬, 배경 #EDF1F7, 무테, 모서리 없음)
			pill_parts: List[str] = []
			for seg, value in case.get('segment_combination', {}).items():
				display_value = get_segment_display_value(seg, value)
				pill_parts.append(f'<span style="display:inline-block;background:#EDF1F7;padding:6px 8px;margin:2px 0;white-space:nowrap;">{html_escape(display_value)}</span>')
			seg_html = ('<span style="margin:0 6px;color:#6B7280;"> + </span>').join(pill_parts) if pill_parts else '-'
			parts.append('<tr>')
			if idx == 0:
				parts.append(
					f'<td rowspan="{rowspan}" style="border:1px solid #E5E7EB;padding:8px;vertical-align:middle;font-size:12px;line-height:1.4;"><strong>{_circled_num(pos)} {html_escape(lb)}</strong> ({overall_pct:.1f}%)</td>'
				)
			parts.append(
				f'<td style="border:1px solid #E5E7EB;padding:8px;vertical-align:middle;font-size:12px;text-align:center;">{seg_html}</td>'
			)
			parts.append(
				f'<td style="border:1px solid #E5E7EB;padding:8px;vertical-align:middle;font-size:12px;white-space:nowrap;background:{bg};color:{fg};text-align:center;">{combo_pct:.1f}% (평균 대비 {signed_diff:+.1f}%p)</td>'
			)
			parts.append(
				f'<td style="border:1px solid #E5E7EB;padding:8px;vertical-align:middle;font-size:12px;text-align:center;">{int(case.get("response_count", 0)):,}건</td>'
			)
			parts.append('</tr>')

	parts.append('</tbody></table>')
	parts.append('</div>')
	return ''.join(parts)

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
				
		elif component_type == "ranking_heatmap":
			# 순위형 히트맵 컴포넌트
			ranking_heatmap_html = build_ranking_heatmap_component(question_rows, label_order, question_title)
			if ranking_heatmap_html:
				components.append(ranking_heatmap_html)
				
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
				if label:
					if label in label_order:
						ordered_counts[label] = ordered_counts.get(label, 0) + 1
				else:
					# 빈 라벨은 '기타'로 집계
					ordered_counts["기타"] = ordered_counts.get("기타", 0) + 1

	if qtype == "evaluation" and label_order:
		for label in label_order:
			ordered_counts.setdefault(label, 0)
	
	if not ordered_counts:
		return ""
	
	# 모든 문항 유형: answ_cntnt 값의 오름차순으로 정렬 (숫자 우선, 그 다음 문자열)
	# 라벨별 정렬키를 answ_cntnt에서 직접 도출
	from collections import defaultdict as _dd
	label_sort_key: Dict[str, Tuple[int, object]] = {}
	for r in question_rows:
		label = (r.get("lkng_cntnt") or "").strip()
		if label not in ordered_counts:
			continue
		answ_val = (r.get("answ_cntnt") or "").strip()
		key: Tuple[int, object]
		try:
			key = (0, float(answ_val))
		except Exception:
			key = (1, answ_val)
		# 라벨에 대한 최초/가장 작은 키 유지
		if (label not in label_sort_key) or (key < label_sort_key[label]):
			label_sort_key[label] = key
	# 폴백: 정렬키 없는 라벨은 라벨 문자열 기반으로 숫자 파싱 시도 → 문자열
	def _fallback_key(label: str) -> Tuple[int, object]:
		try:
			return (0, float(label))
		except Exception:
			return (1, label)
	items = [(label, ordered_counts.get(label, 0)) for label in label_order]
	# label_order에 없더라도 '기타'가 있으면 맨 끝에 추가
	if "기타" in ordered_counts and all(lbl != "기타" for (lbl, _cnt) in items):
		items.append(("기타", ordered_counts["기타"]))
	items.sort(key=lambda x: label_sort_key.get(x[0], _fallback_key(x[0])))
	
	# 평가형은 qsit_type_ds_cd==30인 경우에만 평가형 포맷 적용
	# - 범례: 숫자 라벨에 원숫자 프리픽스(①~) + "점" 접미사 적용
	# - 그래프: 100% 누적 막대 높이 110px, 색상은 heatmap 확장 팔레트
	if qtype == "evaluation":
		legend_html = build_legend_table_from_items_heatmap_evaluation_with_numbers(items, question_rows)
		chart_html = build_stacked_bar_html_ordered_height_heatmap(items, 110)
		# 평가형 전용: 그래프 하단 좌/우 라벨(minm_lbl_txt, max_lbl_txt)
		#   - 좌측(최소치)은 빨강, 우측(최대치)은 파랑으로 시각적 구분
		try:
			min_label = ((question_rows[0].get("minm_lbl_txt") or "").strip()) if question_rows else ""
		except Exception:
			min_label = ""
		try:
			max_label = ((question_rows[0].get("max_lbl_txt") or "").strip()) if question_rows else ""
		except Exception:
			max_label = ""
		if min_label or max_label:
			chart_html = (
				chart_html
				+ '<div style="margin-top:8px;display:flex;justify-content:space-between;align-items:center;">'
				+ f'<span style="color:#E23A32;font-size:12px;line-height:1;text-align:center;">{html_escape(min_label)}</span>'
				+ f'<span style="color:#4262FF;font-size:12px;line-height:1;text-align:center;">{html_escape(max_label)}</span>'
				+ '</div>'
			)
	else:
		# 일반형은 원숫자 프리픽스만 적용(점 접미사 없음), 기타는 마지막에 별도 열로 표시
		legend_html = build_legend_table_from_items_heatmap_with_numbers(items)
		chart_html = build_stacked_bar_html_ordered_height_heatmap(items, 110)
	# Base/Total 계산: Base=고유 cust_id 수(응답자수), Total=총 응답 행 수(답변수)
	unique_cust_ids = set()
	for row in question_rows:
		cust_id = (row.get("cust_id") or "").strip()
		if cust_id:
			unique_cust_ids.add(cust_id)
	base_n = len(unique_cust_ids)
	total_n = len(question_rows)
	base_formatted = f"{base_n:,}"
	total_formatted = f"{total_n:,}"

	# 상단 헤더: 좌측 응답 통계 제목, 우측 LEGEND 제목을 같은 행에 배치
	# - 응답자수와 답변수가 같으면 답변수 생략
	base_total_text = (
		f"(응답자수={base_formatted} / 답변수={total_formatted})" if total_n != base_n
		else f"(응답자수={base_formatted})"
	)
	left_title_html = f'<div style="font-weight:700;font-size:14px;color:#111827;margin:0 0 8px 0;">응답 통계 <span style="font-weight:400;">{base_total_text}</span></div>'
	right_title_html = '<div style="font-weight:700;font-size:12px;color:#67748E;padding:2px 0 0 0;">LEGEND</div>'

	long_legend = False  # PRIMARY_PALETTE 사용 시 항상 가로 배치
	
	if not long_legend:
		# 레전드 라벨의 최장 길이에 따라 fr 비율 결정
		max_legend_len = 0
		for _label, _cnt in items:
			try:
				_l = len(str(_label))
			except Exception:
				_l = 0
			if _l > max_legend_len:
				max_legend_len = _l
		if max_legend_len < 10:
			left_fr, right_fr = 7, 3
		elif max_legend_len <= 20:
			left_fr, right_fr = 6, 4
		else:
			left_fr, right_fr = 5, 5
		# CSS Grid로 제목 행과 콘텐츠 행을 같은 비율의 2열 그리드에 배치
		layout_html = (
			f'<div style="display:grid;grid-template-columns:{left_fr}fr {right_fr}fr;column-gap:12px;align-items:start;margin-bottom:5px;">'
			+ f'<div style="padding:0 0 0 8px;align-self:end;">{left_title_html}</div>'
			+ f'<div style="padding:0 12px 0 0;align-self:end;">{right_title_html}</div>'
			+ f'<div style="padding:0 0 0 8px;">{chart_html}</div>'
			+ f'<div style="padding:0 12px 0 0;">{legend_html}</div>'
			+ '</div>'
		)
	else:
		# 세로 배치: 1행(헤더 100%), 2행(그래프 100%), 3행(간격 8px), 4행(LEGEND 제목), 5행(범례 100%)
		layout_html = (
			'<table role="presentation" cellpadding="0" cellspacing="0" border="0" '
			'style="width:100%;border-collapse:collapse;table-layout:fixed;margin-bottom:5px;">'
			+ '<tbody>'
			+ f'<tr><td style="padding:0 12px 0 12px;vertical-align:bottom;width:100%;">{left_title_html}</td></tr>'
			+ f'<tr><td style="padding:0 12px 0 8px;vertical-align:top;width:100%;">{chart_html}</td></tr>'
			+ '<tr><td style="height:8px;line-height:8px;font-size:0;">&nbsp;</td></tr>'
			+ f'<tr><td style="padding:0 12px 0 12px;vertical-align:bottom;width:100%;">{right_title_html}</td></tr>'
			+ f'<tr><td style="padding:0 12px 0 12px;vertical-align:top;width:100%;">{legend_html}</td></tr>'
			+ '</tbody></table>'
		)

	# 최종 컨테이너 출력
	stats_html = (
		'<div style="margin:12px 0 12px 0;padding:12px;border:1px solid #E5E7EB;border-radius:6px;background:#F9FAFB;">'
		+ layout_html
		+ '</div>'
	)
	
	return stats_html

def build_ranking_stats_component(question_rows: List[Dict[str, str]], label_order: List[str], question_title: str) -> str:
	"""순위형 응답통계 컴포넌트를 생성합니다."""
	if not question_rows or not label_order:
		return ""
	
	# 순위형 데이터 분석
	ranking_data = analyze_ranking_data(question_rows, label_order)
	if not ranking_data:
		return ""
	
	# 3개의 누적 통계 컴포넌트 생성
	stats_html = ""
	# Base(응답자 수)
	base_n = len({(r.get('cust_id') or '').strip() for r in question_rows if (r.get('cust_id') or '').strip()})
	
	# 1순위 응답통계
	stats_html += build_ranking_cumulative_stats(ranking_data['1순위']['counts'], "1순위", question_title, ranking_data['1순위']['n'], ranking_data['1순위'].get('parts'), base_n)
	
	# 1+2순위 응답통계
	stats_html += build_ranking_cumulative_stats(ranking_data['1+2순위']['counts'], "1+2순위", question_title, ranking_data['1+2순위']['n'], ranking_data['1+2순위'].get('parts'), base_n)
	
	# 1+2+3순위 응답통계
	stats_html += build_ranking_cumulative_stats(ranking_data['1+2+3순위']['counts'], "1+2+3순위", question_title, ranking_data['1+2+3순위']['n'], ranking_data['1+2+3순위'].get('parts'), base_n)
	
	return stats_html

def build_ranking_cumulative_stats(ranking_data: Dict[str, int], rank_type: str, question_title: str, n_answ_ids: int, parts: Dict[str, Dict[str, int]] = None, base_n: int = 0) -> str:
	"""순위형 누적 통계 컴포넌트를 생성합니다."""
	if not ranking_data:
		return ""
	
	# 총 응답 수 계산 (그래프 비율 산출용) - 가중치 합을 분모로 사용
	total_responses = sum(ranking_data.values())
	if total_responses == 0:
		return ""
	
	# 선택지별 퍼센트 계산 (가중치 적용 가능)
	stats_data = []
	for choice, count in ranking_data.items():
		# 0건 항목은 표시/범례에서 제외 (필터링된 모수만 노출)
		if count <= 0:
			continue
		percentage = round(100.0 * float(count) / float(total_responses), 1)
		stats_data.append({
			'choice': choice,
			'count': count,
			'percentage': percentage
		})
	
	# 라벨(선택지) 값의 오름차순으로 정렬 (숫자 우선, 그 다음 문자열)
	def _sort_key_for_label(v: object):
		try:
			return (0, float(str(v)))
		except Exception:
			return (1, str(v))
	stats_data.sort(key=lambda x: _sort_key_for_label(x['choice']))
	
	# 히트맵 색상 계산
	max_percentage = max([item['percentage'] for item in stats_data]) if stats_data else 0
	# 팔레트: 5색 고정 (요청사항) - COLOR_CONFIG['pick_5_colors'] 사용
	palette5 = [color_for_fixed_5_by_index(i) for i in range(5)]
	
	# 히트맵 HTML 생성
	heatmap_html = '<table role="presentation" cellpadding="0" cellspacing="0" border="0" style="width:100%;margin-top:6px;">'
	heatmap_html += '<tr>'
	
	for idx, item in enumerate(stats_data):
		width = float(item['percentage'])
		color = palette5[idx % len(palette5)]
		text_color = '#FFFFFF' if width > 15 else '#0B1F4D'
		
		heatmap_html += f'<td style="padding:0;height:110px;background:{color};width:{width}%;text-align:center;">'
		heatmap_html += f'<div style="color:{text_color};font-size:11px;line-height:110px;white-space:nowrap;">{width:.1f}%</div>'
		heatmap_html += '</td>'
	
	heatmap_html += '</tr></table>'
	
	# 범례 HTML 생성
	def _strip_rank_prefix(label: str) -> str:
		# 'x순위' 접두 제거 후 나머지 텍스트 반환
		if not label:
			return label
		pos = label.find('순위')
		if pos != -1:
			return label[pos+2:].strip()
		return label

	legend_html = '<table role="presentation" cellpadding="0" cellspacing="0" border="0" style="width:100%;border-collapse:collapse;margin-top:6px;">'
	for idx, item in enumerate(stats_data, start=1):
		color = palette5[(idx-1) % len(palette5)]
		choice_raw = item['choice']
		choice = _strip_rank_prefix(choice_raw)
		choice_display = f"{_circled_num(idx)} {choice}"
		count = float(item['count'])
		pct = float(item['percentage'])
		# 범례: 라벨 접미사 제거, 괄호에는 %만 표시, 소숫점 1자리 고정
		label_suffix = ''
		value_suffix = f' ({pct:.1f}%)'
		legend_html += '<tr>'
		legend_html += f'<td style="padding:2px 6px;white-space:nowrap;vertical-align:top;line-height:1.1;">'
		legend_html += f'<span style="display:inline-block;width:10px;height:10px;background:{color};border-radius:2px;margin-right:6px;"></span>'
		legend_html += f'<span style="font-size:12px;color:#111827;">{_circled_num(idx)} {choice}{label_suffix}</span>'
		legend_html += '</td>'
		legend_html += f'<td style="padding:2px 0 2px 6px;text-align:right;white-space:nowrap;color:#374151;font-size:12px;line-height:1.1;">{int(count):,} {value_suffix}</td>'
		legend_html += '</tr>'
	
	legend_html += '</table>'
	# 가중치 안내 문구 생성: 정규화(True)인 경우에만 당구장 표기, False면 안내 자체 생략
	weights_note_html = ''
	if RANKING_NORMALIZE_PER_RESPONDENT:
		if rank_type == '1+2순위':
			weights_note_html = (
				f'<div style="margin-top:6px;color:#6B7280;font-size:11px;">'
				f'&nbsp;&nbsp;&nbsp;&nbsp;※ 응답자 단위로 응답 합이 1이 되도록 정규화'
				f'</div>'
			)
		elif rank_type == '1+2+3순위':
			weights_note_html = (
				f'<div style="margin-top:6px;color:#6B7280;font-size:11px;">'
				f'&nbsp;&nbsp;&nbsp;&nbsp;※ 응답자 단위로 응답 합이 1이 되도록 정규화'
				f'</div>'
			)
	
	# 제목용 가중치 표기 구성 (형식: n순위=x / m순위=y ...)
	# rank_type별 현재 환경 가중치에서 제목용 텍스트를 동적 구성
	def _weights_title_for(sel_cnt: int, ranks: List[int]) -> str:
		arr_map = 'stats_1or2' if len(ranks) == 2 else 'stats_1or2or3'
		arr = RANKING_WEIGHTS.get(arr_map, {}).get(sel_cnt)
		if not isinstance(arr, list) or not arr:
			# 기본값으로 ranks 길이에 맞는 디폴트
			arr = [2, 1] if len(ranks) == 2 else [3, 2, 1]
		pairs = []
		for i, r in enumerate(ranks):
			w = arr[i] if i < len(arr) else 0
			pairs.append(f"{r}순위={w}")
		return " / ".join(pairs)

	if rank_type == '1순위':
		weights_text = ''  # 1순위는 가중치 표기 생략
	elif rank_type == '1+2순위':
		weights_text = _weights_title_for(2, [1, 2])
	elif rank_type == '1+2+3순위':
		weights_text = _weights_title_for(3, [1, 2, 3])
	else:
		weights_text = ''
	# 레전드 최장 라벨 길이에 따른 fr 비율 계산
	max_legend_len = 0
	for _item in stats_data:
		try:
			_lbl = _strip_rank_prefix(_item.get('choice'))
			_l = len(str(_lbl))
		except Exception:
			_l = 0
		if _l > max_legend_len:
			max_legend_len = _l
	if max_legend_len < 10:
		left_fr, right_fr = 7, 3
	elif max_legend_len <= 20:
		left_fr, right_fr = 6, 4
	else:
		left_fr, right_fr = 5, 5
	# 제목(좌) / LEGEND(우) 타이틀
	weights_text_fragment = (f', 가중치 : {weights_text}') if weights_text else ''
	base_total_text = f"(응답자수={base_n:,})"
	left_title_html = f'<div style="font-weight:700;font-size:14px;color:#111827;margin:0 0 8px 0;">{rank_type} 응답통계 <span style="font-weight:400;">{base_total_text}{weights_text_fragment}</span></div>'
	right_title_html = '<div style="font-weight:700;font-size:12px;color:#67748E;padding:2px 0 0 0;">LEGEND</div>'
	# 레전드 최장 라벨 길이에 따른 fr 비율 계산 (일반형과 동일 기준: <10 → 7:3, ≤20 → 6:4, 그 외 5:5)
	max_legend_len = 0
	for _item in stats_data:
		try:
			_lbl = _strip_rank_prefix(_item.get('choice'))
			_l = len(str(_lbl))
		except Exception:
			_l = 0
		if _l > max_legend_len:
			max_legend_len = _l
	if max_legend_len < 10:
		left_fr, right_fr = 7, 3
	elif max_legend_len <= 20:
		left_fr, right_fr = 6, 4
	else:
		left_fr, right_fr = 5, 5
	# 일반형과 동일한 2행 Grid 레이아웃 (제목행 + 콘텐츠행)
	layout_html = (
		f'<div style="display:grid;grid-template-columns:{left_fr}fr {right_fr}fr;column-gap:12px;align-items:start;margin-bottom:5px;">'
		+ f'<div style="padding:0 0 0 8px;align-self:end;">{left_title_html}</div>'
		+ f'<div style="padding:0 12px 0 0;align-self:end;">{right_title_html}</div>'
		+ f'<div style="padding:0 0 0 8px;">{heatmap_html}</div>'
		+ f'<div style="padding:0 12px 0 0;">{legend_html}</div>'
		+ '</div>'
	)
	# 전체 컨테이너 (일반형과 동일 스타일)
	stats_html = (
		'<div style="margin:12px 0;padding:12px;border:1px solid #E5E7EB;border-radius:6px;background:#F9FAFB;">'
		+ layout_html
		+ f'{weights_note_html}'
		+ '</div>'
	)
	
	return stats_html


def build_ranking_heatmap_component(question_rows: List[Dict[str, str]], label_order: List[str], question_title: str) -> str:
	"""순위형 히트맵 컴포넌트: 일반형과 동일한 컨테이너/제목/범례 + 정규화 안내"""
	if not question_rows or not label_order:
		return ""
	order = list(label_order)
	# 순위형 전용 히트맵 테이블 생성(가중치/정규화 적용)
	table = _render_ranking_heatmap_table(question_rows, order)
	if not table:
		return ""
	# 엣지케이스 범례 노출 여부 감지
	def _has_edgecase_marker(html: str) -> bool:
		marker1 = f"box-shadow: inset 0 0 0 2px {CONTRAST_PALETTE[3]}"
		marker2 = f"background-color:{CONTRAST_PALETTE[3]}"
		return (marker1 in html) or (marker2 in html)
	has_edgecase = _has_edgecase_marker(table)

	# 가중치/정규화 안내 (heatmap 가중치 기준) → Remark 항목으로 이동
	def _compute_heatmap_weights_text(rows: List[Dict[str, str]], header_order: List[str]) -> str:
		max_rank_found = 1
		for r in rows:
			text = (r.get('answ_cntnt') or '').strip() or (r.get('lkng_cntnt') or '').strip()
			if '순위' in text:
				parts = text.split('순위')
				try:
					rank_num = int(parts[0]) if parts and parts[0].isdigit() else 0
					if 1 <= rank_num <= 10:
						max_rank_found = max(max_rank_found, rank_num)
				except Exception:
					pass
		max_rank_found = max(1, min(10, max_rank_found))
		weights = RANKING_WEIGHTS.get('heatmap', {}).get(max_rank_found, list(range(max_rank_found, 0, -1)))
		pairs = []
		for i, w in enumerate(weights, start=1):
			pairs.append(f"{i}순위={w}")
		return ' / '.join(pairs)
	weights_text_core = _compute_heatmap_weights_text(question_rows, order)
	weights_bullet = (
		f'· 가중치 : {weights_text_core} (응답자 단위로 응답 합이 1이 되도록 정규화)'
		if RANKING_NORMALIZE_PER_RESPONDENT
		else f'· 가중치 : {weights_text_core}'
	)
	# Remark 블록 구성
	remark_items: List[str] = []
	remark_items.append(weights_bullet)
	remark_items.append('· 분석 시점에 탈회고객이 포함된 경우, 해당 고객은 Seg.분석에서 제외되어 Seg.별 응답자수 합이 전체 응답자 수와 다를 수 있음')
	if has_edgecase:
		remark_items.append('· ' + f'<span style="color:{CONTRAST_PALETTE[3]};">■</span>' + f'<span style="color:{GRAYSCALE_PALETTE[5]};"> : 전체 평균대비 응답순서가 다른 Seg.</span>')
	legend_note_html = (
		f'<div style="margin:6px 0 0 0;font-size:11px;line-height:1.6;color:{GRAYSCALE_PALETTE[5]};">'
		+ '<div style="font-weight:700;color:#67748E;margin-bottom:2px;">※ Remark</div>'
		+ ''.join([f'<div>{itm}</div>' for itm in remark_items])
		+ '</div>'
	)
	# 기존 normalize_note_html는 Remark로 이동했으므로 비움
	normalize_note_html = ''
	# 제목 및 컨테이너(일반형과 동일)
	heading = '<div style="font-weight:700;font-size:14px;color:#111827;margin-bottom:0;">Seg.별 히트맵</div>'
	return (
		'<div style="margin:12px 0;padding:12px;border:1px solid #E5E7EB;border-radius:6px;background:#FFFFFF;">'
		+ heading + table + legend_note_html +'</div>'
	)


def _render_ranking_heatmap_table(question_rows: List[Dict[str, str]], order: List[str]) -> str:
	"""순위형 히트맵 테이블: RANKING_WEIGHTS['heatmap'] 가중치 기반 비율 계산 적용"""
	# 세그 정의 및 버킷 수집 (일반형과 동일)
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
	preferred_orders: Dict[str, List[str]] = {
		"gndr_seg": ["01.남성", "02.여성"],
		"age_seg": ["01.10대","02.20대","03.30대","04.40대","05.50대","06.60대","07.기타"],
	}
	seg_bucket_rows: List[Tuple[str, List[Dict[str, str]]]] = []
	seg_bucket_rows.append(("전체", question_rows))
	for seg_title, seg_key in seg_defs:
		vals = set()
		for r in question_rows:
			v = (r.get(seg_key) or "").strip()
			if v:
				vals.add(v)
		if seg_key in preferred_orders:
			ordered_vals = [v for v in preferred_orders[seg_key] if v in vals]
			remain = sorted([v for v in vals if v not in set(ordered_vals)])
			ordered_vals += remain
		else:
			ordered_vals = sorted(vals)
		for raw_val in ordered_vals:
			if clean_axis_label(raw_val) == '기타':
				continue
			bucket_label = f"{seg_title} - {clean_axis_label(raw_val)}"
			rows_subset = [r for r in question_rows if (r.get(seg_key) or '').strip() == raw_val]
			if not rows_subset:
				continue
			seg_bucket_rows.append((bucket_label, rows_subset))

	# 스타일 (일반형과 동일)
	head_style = 'padding:6px 8px;color:#111827;font-size:12px;text-align:center;'
	label_head_style = 'padding:0 2px;color:#111827;font-size:12px;text-align:center;vertical-align:middle;overflow:hidden;'
	rowhead_style = 'padding:0 8px;color:#111827;font-size:12px;text-align:left;white-space:nowrap;height:20px;vertical-align:middle;'
	cell_style_base = 'padding:0;text-align:center;white-space:nowrap;font-size:11px;line-height:1.2;height:20px;vertical-align:middle;'

	# 헤더 (일반형과 동일) + 순위 접두 제거 유틸
	def _strip_rank_prefix_display(s: str) -> str:
		try:
			return re.sub(r'^\s*\d+\s*순위\s*', '', s).strip()
		except Exception:
			return s

	def _extract_respondent_ranks(rows: List[Dict[str, str]]) -> Dict[str, Dict[int, str]]:
		invalids = {'.', '0', '-', 'N/A', 'NA', 'null', 'NULL', '미응답', '무응답'}
		res: Dict[str, Dict[int, str]] = {}
		for r in rows:
			cust_id = (r.get('cust_id') or '').strip()
			if not cust_id or cust_id in invalids:
				continue
			text = (r.get('answ_cntnt') or '').strip() or (r.get('lkng_cntnt') or '').strip()
			if not text or text in invalids:
				continue
			if '순위' in text:
				left, right = text.split('순위', 1)
				try:
					rank = int(left) if left.isdigit() else 1
					idx_raw = int(right) if right.isdigit() else -1
					label_val: Optional[str] = None
					# 0-based 우선, 실패 시 1-based 보정
					if 0 <= idx_raw < len(order):
						label_val = order[idx_raw]
					elif 1 <= idx_raw <= len(order):
						label_val = order[idx_raw - 1]
					if label_val is not None:
						# 순위 접두 제거하여 canonical choice 라벨로 저장
						res.setdefault(cust_id, {})[rank] = _strip_rank_prefix_display(label_val)
				except Exception:
					continue
		return res

	global_map = _extract_respondent_ranks(question_rows)
	used_label_seq: List[str] = []
	for ranks in global_map.values():
		for choice in ranks.values():
			if choice not in used_label_seq:
				used_label_seq.append(choice)
	# 응답에서 사용된 canonical choice 라벨들의 순서 (중복 제거) - x 값 오름차순 정렬
	def _extract_choice_index(label: str) -> int:
		# 라벨이 "n순위x" 또는 접두 제거된 문자열일 수 있음. 숫자만 추출하여 정렬 키로 사용
		try:
			m = re.search(r'(\d+)$', label)
			return int(m.group(1)) if m else 10**9
		except Exception:
			return 10**9
	used_order: List[str] = sorted([lb for lb in used_label_seq], key=_extract_choice_index)
	# 순위형은 '기타' 열 없음. 필요시 전체 라벨(기타 제외) 대비 fallback (x 오름차순)
	order_no_other: List[str] = sorted([ _strip_rank_prefix_display(lb) for lb in order if lb != "기타" ], key=_extract_choice_index)
	# 헤더 라벨(정적): used_order가 있으면 그것을, 없으면 order_no_other 사용
	header_labels_static: List[str] = used_order if used_order else order_no_other

	def _strip_rank_prefix_display(s: str) -> str:
		try:
			return re.sub(r'^\s*\d+\s*순위\s*', '', s).strip()
		except Exception:
			return s

	colgroup = (
		'<col style="width:100px;min-width:100px;max-width:100px;">'
		+ '<col style="width:110px;min-width:110px;max-width:110px;">'
		+ '<col style="width:20px;min-width:20px;max-width:20px;">'
		+ ''.join(['<col style="width:1fr;">' for _ in range(len(used_order) if used_order else len(order_no_other))])
	)
	head_cells = [
		f'<th style="{head_style}">&nbsp;</th>',
		f'<th style="{head_style}">&nbsp;</th>'
	]
	head_cells.append('<th style="padding:0;line-height:0;font-size:0;">&nbsp;</th>')
	for i, lb in enumerate(used_order if used_order else order_no_other, start=1):
		prefix = _circled_num(i)
		head_cells.append(
			f'<th style="{label_head_style}"><div style="display:block;width:100%;height:100%;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;line-height:1.2;text-align:center;">{prefix} {html_escape(lb)}</div></th>'
		)
	head_html = '<thead><tr>' + ''.join(head_cells) + '</tr></thead>'

	# 질문 전체에서 사용할 heatmap 가중치 배열 선택 (최대 순위 개수 기준)
	# (중복 정의 제거: 위에서 정의한 _extract_respondent_ranks 사용)

	global_map = _extract_respondent_ranks(question_rows)
	max_ranks = max((len(v) for v in global_map.values()), default=1)
	max_ranks = max(1, min(10, max_ranks))
	weights_for_question = RANKING_WEIGHTS.get('heatmap', {}).get(max_ranks, list(range(max_ranks, 0, -1)))

	def _norm_map(present: List[int]) -> Dict[int, float]:
		pairs: Dict[int, float] = {}
		for i, r in enumerate(sorted(present)):
			pairs[r] = float(weights_for_question[i]) if i < len(weights_for_question) else 0.0
		if RANKING_NORMALIZE_PER_RESPONDENT:
			t = sum(pairs.values()) or 1.0
			for k in list(pairs.keys()):
				pairs[k] /= t
		return pairs

	# 데이터 준비 (각 버킷에서 가중치 기반 비율 계산)
	rows_data: List[Dict[str, object]] = []
	for name, rows in seg_bucket_rows:
		# 해당 버킷 내 응답자별 랭크 맵 만들기
		local_map = _extract_respondent_ranks(rows)
		# 카운트 맵을 canonical 헤더 라벨 기준으로 준비
		header_labels: List[str] = used_order if used_order else order_no_other
		cnts_float: Dict[str, float] = {l: 0.0 for l in header_labels}
		for cust_id, ranks in local_map.items():
			present = [r for r in ranks.keys() if 1 <= r <= 10]
			wmap = _norm_map(present)
			for r, choice in ranks.items():
				w = float(wmap.get(r, 0.0))
				if choice in cnts_float:
					cnts_float[choice] += w
		# 비율 계산용 총합
		total_float = sum(cnts_float.values()) or 1.0
		if ' - ' in name:
			seg_name, seg_value = name.split(' - ', 1)
		else:
			seg_name, seg_value = name, ''
		rows_data.append({'seg_name': seg_name,'seg_value': seg_value,'cnts_float': cnts_float,'total_float': total_float, 'resp_count': len(local_map)})

	# 히트맵 색상 스케일 및 임계치 계산(일반형과 동일 정책)
	# - 임계치: 전체 응답 대비 GRAYSCALE_THRESHOLD_PERCENT% 또는 GRAYSCALE_MIN_COUNT
	# - 색상 스케일: 표시 대상 퍼센트들의 min/max를 사용
	# 전체 응답 수(행 기준)
	total_responses = len(question_rows)
	threshold_count = max(int(total_responses * GRAYSCALE_THRESHOLD_PERCENT / 100.0), GRAYSCALE_MIN_COUNT)
	all_pcts: List[float] = []
	for rd in rows_data:
		cnts_float_map: Dict[str, float] = rd['cnts_float']  # type: ignore
		total_float_val: float = float(rd['total_float'])  # type: ignore
		resp_count = int(rd.get('resp_count', 0))
		if resp_count >= threshold_count:
			for lb in (used_order if used_order else order_no_other):
				pct = (100.0 * float(cnts_float_map.get(lb, 0.0)) / (total_float_val or 1.0))
				all_pcts.append(round(pct, 1))
	min_pct = min(all_pcts) if all_pcts else 0.0
	max_pct = max(all_pcts) if all_pcts else 100.0

	# 헤더/바디 렌더링 (일반형 구조 복제)
	body_rows: List[str] = []
	# 전체 순위(엣지케이스 비교용): 전체 행의 비율 기반 순위
	overall_rank: List[str] = []
	if rows_data:
		overall = rows_data[0]
		overall_map: Dict[str, float] = overall['cnts_float']  # type: ignore
		overall_rank = sorted(header_labels_static, key=lambda lb: (-(overall_map.get(lb, 0.0)), header_labels_static.index(lb)))
	first_index: Dict[str, int] = {}
	rowspan_count: Dict[str, int] = {}
	for idx, rd in enumerate(rows_data):
		seg = str(rd['seg_name'])
		if seg not in first_index:
			first_index[seg] = idx
		rowspan_count[seg] = rowspan_count.get(seg, 0) + 1
	max_total = max((int(rd.get('resp_count', 0)) for rd in rows_data), default=1) or 1
	for idx, rd in enumerate(rows_data):
		seg_name = str(rd['seg_name'])
		seg_value = str(rd['seg_value'])
		cnts_float: Dict[str, float] = rd['cnts_float']  # type: ignore
		total_float: float = float(rd['total_float'])  # type: ignore
		resp_count = int(rd.get('resp_count', 0))
		cells: List[str] = []
		is_group_start = (idx == first_index.get(seg_name))
		if is_group_start and idx != 0:
			colspan = 3 + len(used_order if used_order else order_no_other)
			body_rows.append('<tr><td colspan="' + str(colspan) + '" style="padding:4px 0;height:0;line-height:0;"><div style="height:1px;background:repeating-linear-gradient(to right, #E5E7EB 0 2px, transparent 2px 4px);"></div></td></tr>')
		if is_group_start:
			cells.append(f'<td rowspan="{rowspan_count.get(seg_name,1)}" style="{rowhead_style}">{html_escape(seg_name)}</td>')
		# 엣지케이스 판단 (값 바 강조 전용)
		seg_pct_map: Dict[str, float] = {lb: (float(cnts_float.get(lb, 0.0)) * 100.0 / (total_float or 1.0)) for lb in header_labels_static}
		seg_rank: List[str] = sorted(header_labels_static, key=lambda lb: (-seg_pct_map.get(lb, 0.0), header_labels_static.index(lb)))
		is_edgecase = (seg_value != '' and bool(overall_rank) and seg_rank != overall_rank)
		# 값 열 (총합 바: 응답자 수 기반 막대)
		bar_w = int(round((resp_count / (max_total or 1)) * 100))
		bar_w_css = max(1, bar_w)
		value_td_style = 'padding:0;color:#111827;font-size:12px;text-align:left;white-space:nowrap;height:20px;position:relative;overflow:hidden;vertical-align:middle;'
		bar_html = (
			'<table role="presentation" cellpadding="0" cellspacing="0" border="0" style="border-collapse:collapse;width:100%;height:20px;table-layout:fixed;">'
			'<tr>'
			f'<td width="{bar_w_css}%" style="height:20px;line-height:20px;vertical-align:middle;'
			+ (f"background-color:{CONTRAST_PALETTE[3]};box-shadow: inset 0 0 0 2px {CONTRAST_PALETTE[3]};" if is_edgecase else "background-color:#D1D5DB;")
			+ 'padding:0;color:#111827;font-size:11px;white-space:nowrap;overflow:visible;">'
			+ f'<span style="margin-left:4px;">{html_escape(seg_value)}'
			+ (f'<span style="color:#6B7280;margin-left:6px;">(답변수={resp_count:,})</span></span>' if not seg_value else f'<span style="color:#6B7280;margin-left:6px;">({resp_count:,})</span></span>')
			+ '</td>'
			f'<td width="{100 - bar_w_css}%" style="height:20px;line-height:20px;vertical-align:middle;padding:0;margin:0;"></td>'
			+ '</tr></table>'
		)
		if seg_value:
			cells.append(f'<td style="{value_td_style}">{bar_html}</td>')
		else:
			cells.append(f'<td style="{value_td_style}">{bar_html}</td>')
		# 값-히트맵 스페이서
		if is_group_start:
			cells.append('<td rowspan="' + str(rowspan_count.get(seg_name,1)) + '" style="line-height:0;font-size:0;">\n\t<div style=\"padding:0 4px;\">\n\t\t<div style=\"height:16px;background:transparent;\"></div>\n\t</div>\n</td>')
		# 퍼센트 셀들 (전체 라벨: '기타' 없음)
		for lb in (used_order if used_order else order_no_other):
			pct = round(100.0 * float(cnts_float.get(lb, 0.0)) / (total_float or 1.0), 1)
			use_grayscale = (resp_count < threshold_count)
			bg = _shade_for_grayscale_dynamic(pct, min_pct, max_pct) if use_grayscale else _shade_for_pct_dynamic(pct, min_pct, max_pct)
			fg = _auto_text_color(bg)
			cells.append(f'<td style="{cell_style_base}width:60px;padding:0;background:{bg};background-color:{bg};background-image:none;color:{fg};">{pct:.1f}%</td>')
		body_rows.append('<tr>' + ''.join(cells) + '</tr>')

	return (
		'<table role="presentation" cellpadding="0" cellspacing="0" border="0" '
		'style="width:100%;table-layout:fixed;border-collapse:collapse;padding-left:4px;padding-right:8px;">'
		+ f'<colgroup>{colgroup}</colgroup>'
		+ head_html + '<tbody>' + ''.join(body_rows) + '</tbody>' + '</table>'
	)


def analyze_ranking_data(question_rows: List[Dict[str, str]], label_order: List[str]) -> Dict[str, Dict[str, object]]:
	"""순위형 데이터를 분석하여 각 순위별 통계를 계산합니다.
	반환: { 구간: { 'counts': {choice: count}, 'n': 고유 answ_id 수, 'parts': { '1': {...}, '2': {...}, '3': {...} } } }
	"""
	# 각 순위별 통계 구조 초기화
	ranking_stats: Dict[str, Dict[str, object]] = {
		'1순위': {
			'counts': {choice: 0 for choice in label_order},
			'n': 0,
			'parts': {'1': {choice: 0 for choice in label_order}}
		},
		'1+2순위': {
			'counts': {choice: 0 for choice in label_order},
			'n': 0,
			'parts': {
				'1': {choice: 0 for choice in label_order},
				'2': {choice: 0 for choice in label_order}
			}
		},
		'1+2+3순위': {
			'counts': {choice: 0 for choice in label_order},
			'n': 0,
			'parts': {
				'1': {choice: 0 for choice in label_order},
				'2': {choice: 0 for choice in label_order},
				'3': {choice: 0 for choice in label_order}
			}
		},
	}
	# 응답자별 순위 데이터 수집
	respondent_rankings: Dict[str, Dict[int, str]] = {}
	respondent_answ_ids: Dict[str, set] = {'1순위': set(), '1+2순위': set(), '1+2+3순위': set()}
	for row in question_rows:
		cust_id = str(row.get('cust_id', ''))
		answ_id = str(row.get('answ_id', ''))
		answ_cntnt = str(row.get('answ_cntnt', ''))
		lkng_cntnt = str(row.get('lkng_cntnt', ''))
		invalids = ['.', '0', '-', 'N/A', 'NA', 'null', 'NULL', '미응답', '무응답']
		if not cust_id or cust_id in invalids:
			continue
		ranking_text = answ_cntnt if answ_cntnt not in invalids else lkng_cntnt
		if ranking_text and ranking_text not in invalids:
			try:
				if '순위' in ranking_text:
					parts = ranking_text.split('순위')
					if len(parts) == 2:
						rank = int(parts[0]) if parts[0].isdigit() else 1
						choice_index = int(parts[1]) if parts[1].isdigit() else 0
						if cust_id not in respondent_rankings:
							respondent_rankings[cust_id] = {}
						if 0 <= choice_index < len(label_order):
							respondent_rankings[cust_id][rank] = label_order[choice_index]
							if rank == 1:
								respondent_answ_ids['1순위'].add(answ_id)
								respondent_answ_ids['1+2순위'].add(answ_id)
								respondent_answ_ids['1+2+3순위'].add(answ_id)
							elif rank == 2:
								respondent_answ_ids['1+2순위'].add(answ_id)
								respondent_answ_ids['1+2+3순위'].add(answ_id)
							elif rank == 3:
								respondent_answ_ids['1+2+3순위'].add(answ_id)
			except:
				continue
	for cust_id, rankings in respondent_rankings.items():
		# 응답자가 실제로 선택한 순위 집합
		present_12 = [r for r in (1, 2) if r in rankings]
		present_123 = [r for r in (1, 2, 3) if r in rankings]
		# 선택한 순위 개수에 따른 가중치 배열 선택
		sel_cnt = len(rankings)
		arr_12 = RANKING_WEIGHTS.get('stats_1or2', {}).get(sel_cnt, [2, 1])
		arr_123 = RANKING_WEIGHTS.get('stats_1or2or3', {}).get(sel_cnt, [3, 2, 1])
		# 배열을 rank->weight 맵으로 변환
		base_weights_12 = {1: float(arr_12[0]) if len(arr_12) > 0 else 0.0, 2: float(arr_12[1]) if len(arr_12) > 1 else 0.0}
		base_weights_123 = {
			1: float(arr_123[0]) if len(arr_123) > 0 else 0.0,
			2: float(arr_123[1]) if len(arr_123) > 1 else 0.0,
			3: float(arr_123[2]) if len(arr_123) > 2 else 0.0,
		}
		# 응답자 단위 정규화
		def _normalized_weights(base_map: Dict[int, float], present: List[int]) -> Dict[int, float]:
			if not present:
				return {}
			if RANKING_NORMALIZE_PER_RESPONDENT:
				total = sum(base_map.get(r, 0.0) for r in present)
				if total <= 0:
					return {r: 0.0 for r in present}
				return {r: (base_map.get(r, 0.0) / total) for r in present}
			else:
				return {r: base_map.get(r, 0.0) for r in present}
		weights_12 = _normalized_weights(base_weights_12, present_12)
		weights_123 = _normalized_weights(base_weights_123, present_123)
		# 1순위: 가중치 제외(단순 1 카운트)
		if 1 in rankings:
			choice = rankings[1]
			if choice in ranking_stats['1순위']['counts']:
				ranking_stats['1순위']['counts'][choice] += 1.0
				ranking_stats['1순위']['parts']['1'][choice] += 1.0
		# 1+2순위: 고정 가중치(2,1) 사용, 옵션에 따라 응답자 단위 정규화
		if 1 in rankings:
			choice = rankings[1]
			w = float(weights_12.get(1, 0.0))
			if choice in ranking_stats['1+2순위']['counts'] and w > 0:
				ranking_stats['1+2순위']['counts'][choice] += w
				ranking_stats['1+2순위']['parts']['1'][choice] += w
		if 2 in rankings:
			choice = rankings[2]
			w = float(weights_12.get(2, 0.0))
			if choice in ranking_stats['1+2순위']['counts'] and w > 0:
				ranking_stats['1+2순위']['counts'][choice] += w
				ranking_stats['1+2순위']['parts']['2'][choice] += w
		# 1+2+3순위: 고정 가중치(3,2,1) 사용, 옵션에 따라 응답자 단위 정규화
		if 1 in rankings:
			choice = rankings[1]
			w = float(weights_123.get(1, 0.0))
			if choice in ranking_stats['1+2+3순위']['counts'] and w > 0:
				ranking_stats['1+2+3순위']['counts'][choice] += w
				ranking_stats['1+2+3순위']['parts']['1'][choice] += w
		if 2 in rankings:
			choice = rankings[2]
			w = float(weights_123.get(2, 0.0))
			if choice in ranking_stats['1+2+3순위']['counts'] and w > 0:
				ranking_stats['1+2+3순위']['counts'][choice] += w
				ranking_stats['1+2+3순위']['parts']['2'][choice] += w
		if 3 in rankings:
			choice = rankings[3]
			w = float(weights_123.get(3, 0.0))
			if choice in ranking_stats['1+2+3순위']['counts'] and w > 0:
				ranking_stats['1+2+3순위']['counts'][choice] += w
				ranking_stats['1+2+3순위']['parts']['3'][choice] += w
	ranking_stats['1순위']['n'] = len(respondent_answ_ids['1순위'])
	ranking_stats['1+2순위']['n'] = len(respondent_answ_ids['1+2순위'])
	ranking_stats['1+2+3순위']['n'] = len(respondent_answ_ids['1+2+3순위'])
	return ranking_stats


def build_cumulative_ranking_chart(ranking_data: Dict[str, Dict[str, object]], question_title: str) -> str:
	"""누적 순위형 막대그래프를 생성합니다.
	입력 ranking_data는 analyze_ranking_data의 반환 구조를 사용합니다.
	"""
	# 색상 팔레트 (5단계 파란색 그라데이션)
	colors = ['#b9c5fe', '#819afe', '#5574fc', '#2539e9', '#17008c']
	
	# counts 사전만 추출
	counts_by_rank: Dict[str, Dict[str, int]] = {
		'1순위': ranking_data.get('1순위', {}).get('counts', {}) if isinstance(ranking_data.get('1순위'), dict) else {},
		'1+2순위': ranking_data.get('1+2순위', {}).get('counts', {}) if isinstance(ranking_data.get('1+2순위'), dict) else {},
		'1+2+3순위': ranking_data.get('1+2+3순위', {}).get('counts', {}) if isinstance(ranking_data.get('1+2+3순위'), dict) else {},
	}
	
	# 각 순위별 최대값 계산
	max_values: Dict[str, int] = {}
	for rank_type, data in counts_by_rank.items():
		max_values[rank_type] = max(data.values()) if data else 0
	
	# 전체 최대값
	overall_max = max(max_values.values()) if max_values else 1
	if overall_max <= 0:
		overall_max = 1
	
	# 선택지 목록 (데이터에서 추출)
	choices = list(counts_by_rank['1순위'].keys()) if counts_by_rank['1순위'] else []
	
	chart_html = f'''
	<div style="margin:12px 0;padding:16px;border:1px solid #E5E7EB;border-radius:8px;background:#FFFFFF;">
		<h4 style="margin:0 0 16px 0;color:#1E293B;font-size:16px;font-weight:700;">📊 누적 순위 분석</h4>
		<div style="display:flex;gap:20px;align-items:flex-end;height:462px;border-bottom:2px solid #E5E7EB;padding-bottom:12px;">
	'''
	
	# 각 선택지별 막대그래프 생성
	for i, choice in enumerate(choices):
		color = colors[i % len(colors)]
		
		# 각 순위별 값
		rank1_value = ranking_data['1순위'].get(choice, 0)
		rank12_value = ranking_data['1+2순위'].get(choice, 0)
		rank123_value = ranking_data['1+2+3순위'].get(choice, 0)
		
		# 막대 높이 계산 (462px 기준)
		height1 = (rank1_value / overall_max) * 400 if overall_max > 0 else 0
		height12 = (rank12_value / overall_max) * 400 if overall_max > 0 else 0
		height123 = (rank123_value / overall_max) * 400 if overall_max > 0 else 0
		
		chart_html += f'''
			<div style="display:flex;flex-direction:column;align-items:center;flex:1;min-width:80px;">
				<!-- 1+2+3순위 막대 -->
				<div style="position:relative;width:24px;height:{height123}px;background:{color};border-radius:2px 2px 0 0;margin-bottom:2px;">
					<div style="position:absolute;top:-20px;left:50%;transform:translateX(-50%) rotate(270deg);color:#374151;font-size:11px;font-weight:600;white-space:nowrap;">
						{rank123_value}
					</div>
				</div>
				
				<!-- 1+2순위 막대 -->
				<div style="position:relative;width:24px;height:{height12}px;background:{color}CC;border-radius:2px 2px 0 0;margin-bottom:2px;">
					<div style="position:absolute;top:-20px;left:50%;transform:translateX(-50%) rotate(270deg);color:#374151;font-size:11px;font-weight:600;white-space:nowrap;">
						{rank12_value}
					</div>
				</div>
				
				<!-- 1순위 막대 -->
				<div style="position:relative;width:24px;height:{height1}px;background:{color}99;border-radius:2px 2px 0 0;margin-bottom:2px;">
					<div style="position:absolute;top:-20px;left:50%;transform:translateX(-50%) rotate(270deg);color:#374151;font-size:11px;font-weight:600;white-space:nowrap;">
						{rank1_value}
					</div>
				</div>
				
				<!-- 선택지 라벨 -->
				<div style="margin-top:8px;text-align:center;color:#374151;font-size:12px;font-weight:600;max-width:80px;word-break:break-word;">
					{choice}
				</div>
			</div>
		'''
	
	chart_html += '''
		</div>
		
		<!-- 범례 -->
		<div style="margin-top:16px;display:flex;justify-content:center;gap:24px;">
			<div style="display:flex;align-items:center;gap:6px;">
				<div style="width:10px;height:10px;background:#b9c5fe;border-radius:2px;"></div>
				<span style="color:#374151;font-size:12px;font-weight:500;">1순위</span>
			</div>
			<div style="display:flex;align-items:center;gap:6px;">
				<div style="width:10px;height:10px;background:#819afe;border-radius:2px;"></div>
				<span style="color:#374151;font-size:12px;font-weight:500;">1+2순위</span>
			</div>
			<div style="display:flex;align-items:center;gap:6px;">
				<div style="width:10px;height:10px;background:#5574fc;border-radius:2px;"></div>
				<span style="color:#374151;font-size:12px;font-weight:500;">1+2+3순위</span>
			</div>
		</div>
	</div>
	'''
	
	return chart_html

def build_subjective_summary_component(question_rows: List[Dict[str, str]], question_title: str) -> str:
	"""PoC 스타일(카테고리별 주요 키워드 리포트)로 주관식 컴포넌트를 생성한다."""
	if not question_rows:
		return ""
	
	# 입력 정리: PoC 기준 필터 (text_yn 허용, category_level2 제외)
	rows: List[Dict[str, str]] = []
	# PoC 제외 카테고리 (category_level2 기준)
	_excluded_l2 = {'단순 칭찬/불만', '욕설·무관한 피드백', '개선 의사 없음 (“없습니다”)'}
	def _is_text_allowed(row: Dict[str, str]) -> bool:
		val = row.get("text_yn")
		if val is None:
			return True
		val_s = str(val).strip()
		if val_s == "":
			return True
		return val_s in {"1", "Y", "y"}
	for r in question_rows:
		# text_yn이 명시된 경우 허용값만 통과
		if not _is_text_allowed(r):
			continue
		# category_level2 제외 규칙
		l2 = (r.get("category_level2") or "").strip()
		if l2 in _excluded_l2:
			continue
		# 유효응답 필터(무효값/최소길이) 제거: 원문 그대로 사용
		rows.append(r)
	if not rows:
		return '<div style="margin:8px 0;color:#6B7280;font-size:12px;">주관식 응답이 없습니다.</div>'

	from collections import defaultdict, Counter

	def _cat(row: Dict[str, str]) -> str:
		# PoC와 동일: category_level1 > category_level2만 사용 (정제/폴백 제거)
		c1 = (row.get("category_level1") or "").strip()
		c2 = (row.get("category_level2") or "").strip()
		if c1 or c2:
			sep = " > " if (c1 and c2) else ""
			return (c1 + sep + c2)
		return ""

	def _sent_raw(row: Dict[str, str]) -> str:
		# 감정 맵핑 제거: 원본 sentiment 그대로 사용
		s = (row.get("sentiment") or "").strip()
		return s

	def _split_kw(s: Optional[str]) -> List[str]:
		if not s:
			return []
		return [p.strip() for p in str(s).split(",") if p and p.strip()]

	# 카테고리별 감정 카운트
	cat_sent_counts: Dict[str, Counter] = defaultdict(lambda: Counter())
	cat_total: Counter = Counter()
	for r in rows:
		c = _cat(r)
		s = _sent_raw(r)
		cat_sent_counts[c][s] += 1
		cat_total[c] += 1

	# 상위 카테고리 선별 (환경 변수 사용)
	top10_cats: List[str] = [c for c, _ in cat_total.most_common(SUBJECTIVE_MAX_CATEGORIES)]

	# 키워드 집계: (cat,sent,kw) → cnt
	kw_counts: Counter = Counter()
	for r in rows:
		c = _cat(r)
		s = _sent_raw(r)
		for kw in _split_kw(r.get("keywords"))[:3]:
			if kw in SUBJECTIVE_EXCLUDE_KEYWORDS:
				continue
			kw_counts[(c, s, kw)] += 1

	# 감정별 상위 5개 키워드 문자열 생성
	keyword_anal_map: Dict[Tuple[str, str], str] = {}
	# 그룹핑을 위해 정렬 후 순회
	for (c, s, kw), cnt in sorted(kw_counts.items(), key=lambda x: (-x[1], x[0][2])):
		key = (c, s)
		if key not in keyword_anal_map:
			keyword_anal_map[key] = f"{kw}({cnt})"
		else:
			# 이미 5개면 스킵
			existing = keyword_anal_map[key]
			if existing.count("(") >= 5:
				continue
			keyword_anal_map[key] = existing + ", " + f"{kw}({cnt})"

	# 데이터2: 요약문 랭킹용 행 구성
	entries: List[Dict[str, object]] = []
	_seen: Set[Tuple[str, str, str, str]] = set()
	for r in rows:
		c = _cat(r)
		s = _sent_raw(r)
		if c not in top10_cats:
			continue
		kw_anal = keyword_anal_map.get((c, s), "")
		text = (r.get("answ_cntnt") or "").strip()
		summary = (r.get("summary") or "").strip() or text
		key = (c, s, summary, text)
		if key in _seen:
			continue
		_seen.add(key)
		# 키워드 히트 수 계산
		def _kw_hits(kw_anal_text: str, body: str) -> int:
			if not kw_anal_text or not body:
				return 0
			kws = [re.sub(r"\(.*\)", "", k).strip() for k in kw_anal_text.split(",")]
			return sum(1 for k in kws if k and k in body)
		hits = _kw_hits(kw_anal, text)
		entries.append({
			"cat": c,
			"sent": s,
			"summary": summary,
			"kw_anal": kw_anal,
			"hits": hits,
			"len": len(summary),
		})

	# 감정별 랭킹 및 개수 제한 적용 (선택 단계에서 중복 제거하며 limit 채움)
	def _normalize_summary_text(text: str) -> str:
		s = (text or "").strip()
		s = re.sub(r"\s+", " ", s)
		return s

	def _pick_summaries(cat: str, sent: str, limit: int) -> List[str]:
		cand = [e for e in entries if e["cat"] == cat and e["sent"] == sent]
		cand.sort(key=lambda e: (-int(e["hits"]), -int(e["len"])))
		seen_norm: Set[str] = set()
		result: List[str] = []
		for e in cand:
			s = str(e["summary"])
			sn = _normalize_summary_text(s)
			if sn in seen_norm:
				continue
			seen_norm.add(sn)
			result.append(s)
			if len(result) >= limit:
				break
		return result

	# HTML 생성 (PoC 테이블 스타일)
	def _pct(a: int, b: int) -> str:
		val = (a * 100.0) / (b or 1)
		return f"{val:.1f}%"

	# 헤딩 및 컨테이너 (Base/Total 병행 표기)
	base_n = len({(r.get('cust_id') or '').strip() for r in question_rows if (r.get('cust_id') or '').strip()})
	total_n = len(question_rows)
	base_total_text = (
		f"(응답자수={base_n:,} / 답변수={total_n:,})" if total_n != base_n
		else f"(응답자수={base_n:,})"
	)
	html_parts: List[str] = []
	# 컨테이너는 기존 카드 레이아웃 유지
	html_parts.append('<div style="margin:12px 0;padding:12px;border:1px solid #E5E7EB;border-radius:6px;background:#FFFFFF;">')
	html_parts.append(f'<div style="font-weight:700;font-size:14px;color:#111827;margin-bottom:8px;">카테고리별 주요 키워드 리포트 <span style="color:#6B7280;font-weight:400;font-size:12px;margin-left:6px;">{base_total_text}</span></div>')
	# 테이블 시작
	html_parts.append('<table style="width:100%;border-collapse:collapse;border:1px solid #E5E7EB;">')
	html_parts.append('<thead><tr>'
		"<th style=\"background:#4D596F;color:#FFFFFF;font-size:12px;padding:0px;border:1px solid #E5E7EB;width:30px;\">순번</th>"
		"<th style=\"background:#4D596F;color:#FFFFFF;font-size:12px;padding:8px;border:1px solid #E5E7EB;width:180px;\">카테고리</th>"
		"<th style=\"background:#4D596F;color:#FFFFFF;font-size:12px;padding:8px;border:1px solid #E5E7EB;width:175px;\">감정분석</th>"
		"<th style=\"background:#4D596F;color:#FFFFFF;font-size:12px;padding:8px;border:1px solid #E5E7EB;\">주요 키워드</th>"
		'</tr></thead><tbody>')

	for i, cat in enumerate(top10_cats, start=1):
		resp = int(cat_total[cat])
		pos_cnt = int(cat_sent_counts[cat]["긍정"])
		neg_cnt = int(cat_sent_counts[cat]["부정"])
		neu_cnt = int(cat_sent_counts[cat]["중립"])
		pos_pct = _pct(pos_cnt, resp)
		neg_pct = _pct(neg_cnt, resp)
		neu_pct = _pct(neu_cnt, resp)
		pos_summary_list = _pick_summaries(cat, "긍정", 3)
		neg_summary_list = _pick_summaries(cat, "부정", 3)
		neu_summary_list = _pick_summaries(cat, "중립", 2)
		# 요약 중복 제거(순서 보존)
		def _dedupe_preserve(items: List[str]) -> List[str]:
			seen: Set[str] = set()
			result: List[str] = []
			for s in items:
				ss = (s or "").strip()
				if ss and ss not in seen:
					seen.add(ss)
					result.append(ss)
			return result
		pos_summary_list = _dedupe_preserve(pos_summary_list)
		neg_summary_list = _dedupe_preserve(neg_summary_list)
		neu_summary_list = _dedupe_preserve(neu_summary_list)

		cell_idx = (
			f'<td style="border:1px solid #E5E7EB;padding:0px;color:#374151;font-size:12px;width:20px;text-align:center;">{i}</td>'
		)
		# 카테고리 표시: "부모 > 자식" → 줄바꿈 + "└ 자식 (n)"
		if " > " in cat:
			parent_cat, child_cat = cat.split(" > ", 1)
			cat_display_html = (
				f'{html_escape(parent_cat)}<br>'
				f'<span style="white-space:nowrap;">└ {html_escape(child_cat)} '
				f'<span style="color:#6B7280;font-size:11px;">({resp}건)</span></span>'
			)
		else:
			cat_display_html = f'{html_escape(cat)} <span style="color:#6B7280;font-size:11px;">({resp}건)</span>'
		cell_cat = (
			f'<td style="border:1px solid #E5E7EB;padding:8px;vertical-align:middle;font-size:12px;line-height:1.4;width:180px;">'
			f'{cat_display_html}'
			'</td>'
		)
		cell_sent = (
			'<td style="border:1px solid #E5E7EB;padding:8px;vertical-align:middle;width:175px;">'
			# 긍정
			f'<div style="display:flex;align-items:center;gap:6px;margin-bottom:4px;">'
			f'<div style="width:120px;height:{SUBJECTIVE_BAR_HEIGHT_PX}px;background:{SUBJECTIVE_BAR_BG_COLOR};overflow:hidden;position:relative;"><div style="position:absolute;left:0;top:0;bottom:0;width:{pos_pct};background:{SUBJECTIVE_POS_BAR_COLOR};"></div></div>'
			f'<div style="color:#111827;font-size:10px;white-space:nowrap;">긍정 {pos_pct}</div>'
			'</div>'
			# 부정
			f'<div style="display:flex;align-items:center;gap:6px;margin-bottom:4px;">'
			f'<div style="width:120px;height:{SUBJECTIVE_BAR_HEIGHT_PX}px;background:{SUBJECTIVE_BAR_BG_COLOR};overflow:hidden;position:relative;"><div style="position:absolute;left:0;top:0;bottom:0;width:{neg_pct};background:{SUBJECTIVE_NEG_BAR_COLOR};"></div></div>'
			f'<div style="color:#111827;font-size:10px;white-space:nowrap;">부정 {neg_pct}</div>'
			'</div>'
			# 중립
			f'<div style="display:flex;align-items:center;gap:6px;">'
			f'<div style="width:120px;height:{SUBJECTIVE_BAR_HEIGHT_PX}px;background:{SUBJECTIVE_BAR_BG_COLOR};overflow:hidden;position:relative;"><div style="position:absolute;left:0;top:0;bottom:0;width:{neu_pct};background:{SUBJECTIVE_NEU_BAR_COLOR};"></div></div>'
			f'<div style="color:#111827;font-size:10px;white-space:nowrap;">중립 {neu_pct}</div>'
			'</div>'
			'</td>'
		)
		# 주요 키워드: 2열 레이아웃(좌: 라벨+건수, 우: 문자열)
		pos_list_html = ("<ul style='margin:0;padding-left:16px;'>" + "".join(f"<li>{html_escape(x)}</li>" for x in pos_summary_list) + "</ul>") if pos_summary_list else "-"
		neg_list_html = ("<ul style='margin:0;padding-left:16px;'>" + "".join(f"<li>{html_escape(x)}</li>" for x in neg_summary_list) + "</ul>") if neg_summary_list else "-"
		neu_list_html = ("<ul style='margin:0;padding-left:16px;'>" + "".join(f"<li>{html_escape(x)}</li>" for x in neu_summary_list) + "</ul>") if neu_summary_list else "-"
		cell_kw = (
			'<td style="border:1px solid #E5E7EB;padding:0;vertical-align:top;font-size:11px;line-height:1.3;">'
			# 긍정 블록 (블록 간 마진 제거)
			f'<div style="margin:0;background:rgba(66,98,255,0.04);padding:6px;">'
			'<table role="presentation" cellpadding="0" cellspacing="0" border="0" style="width:100%;table-layout:fixed;">'
			'<colgroup><col style="width:60px;"><col></colgroup>'
			'<tr>'
			f'<td style="padding:0;color:{SUBJECTIVE_POS_BAR_COLOR};font-weight:400;font-size:12px;white-space:nowrap;vertical-align:middle;text-align:center;">긍정 ({pos_cnt})</td>'
			f'<td style="padding:0;color:#111827;font-size:12px;vertical-align:middle;">{pos_list_html}</td>'
			'</tr>'
			'</table>'
			'</div>'
			# 부정 블록 (블록 간 마진 제거)
			f'<div style="margin:0;background:rgba(226,58,50,0.04);padding:6px;">'
			'<table role="presentation" cellpadding="0" cellspacing="0" border="0" style="width:100%;table-layout:fixed;">'
			'<colgroup><col style="width:60px;"><col></colgroup>'
			'<tr>'
			f'<td style="padding:0;color:{SUBJECTIVE_NEG_BAR_COLOR};font-weight:400;font-size:12px;white-space:nowrap;vertical-align:middle;text-align:center;">부정 ({neg_cnt})</td>'
			f'<td style="padding:0;color:#111827;font-size:12px;vertical-align:middle;">{neg_list_html}</td>'
			'</tr>'
			'</table>'
			'</div>'
			# 중립 블록 (블록 간 마진 제거)
			f'<div style="margin:0;background:rgba(0,0,0,0.04);padding:6px;">'
			'<table role="presentation" cellpadding="0" cellspacing="0" border="0" style="width:100%;table-layout:fixed;">'
			'<colgroup><col style="width:60px;"><col></colgroup>'
			'<tr>'
			f'<td style="padding:0;color:{SUBJECTIVE_NEU_BAR_COLOR};font-weight:400;font-size:12px;white-space:nowrap;vertical-align:middle;text-align:center;">중립 ({neu_cnt})</td>'
			f'<td style="padding:0;color:#111827;font-size:12px;vertical-align:middle;">{neu_list_html}</td>'
			'</tr>'
			'</table>'
			'</div>'
			'</td>'
		)
		html_parts.append('<tr>' + cell_idx + cell_cat + cell_sent + cell_kw + '</tr>')

	html_parts.append('</tbody></table>')
	html_parts.append('</div>')

	return ''.join(html_parts)


def _render_general_heatmap_table(question_rows: List[Dict[str, str]], order: List[str]) -> str:
	"""일반형 히트맵 테이블을 생성한다. (with_cross_analysis 버전 렌더 기준)
	- 행: 세그 버킷(전체 + 각 세그 값)
	- 열: 라벨(기타 열은 오른쪽 고정)
	- 엣지케이스: 전체 대비 응답순서가 다른 세그 조합을 감지하여 값 바에만 강조색 적용
	- 색상 스케일: n(해당 행의 total)이 임계치 미만이면 그레이스케일, 아니면 동적 히트맵 스케일링
	"""
	# 세그 정의 및 버킷 수집
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
	preferred_orders: Dict[str, List[str]] = {
		"gndr_seg": ["01.남성", "02.여성"],
		"age_seg": ["01.10대","02.20대","03.30대","04.40대","05.50대","06.60대","07.기타"],
	}
	seg_bucket_rows: List[Tuple[str, List[Dict[str, str]]]] = []
	seg_bucket_rows.append(("전체", question_rows))
	for seg_title, seg_key in seg_defs:
		vals = set()
		for r in question_rows:
			v = (r.get(seg_key) or "").strip()
			if v:
				vals.add(v)
		if seg_key in preferred_orders:
			ordered_vals = [v for v in preferred_orders[seg_key] if v in vals]
			remain = sorted([v for v in vals if v not in set(ordered_vals)])
			ordered_vals += remain
		else:
			ordered_vals = sorted(vals)
		for raw_val in ordered_vals:
			if clean_axis_label(raw_val) == '기타':
				continue
			bucket_label = f"{seg_title} - {clean_axis_label(raw_val)}"
			rows_subset = [r for r in question_rows if (r.get(seg_key) or '').strip() == raw_val]
			if not rows_subset:
				continue
			seg_bucket_rows.append((bucket_label, rows_subset))

	# 스타일
	head_style = 'padding:6px 8px;color:#111827;font-size:12px;text-align:center;'
	label_head_style = 'padding:0 2px;color:#111827;font-size:12px;text-align:center;vertical-align:middle;overflow:hidden;'
	rowhead_style = 'padding:0 8px;color:#111827;font-size:12px;text-align:left;white-space:nowrap;height:20px;vertical-align:middle;'
	cell_style_base = 'padding:0;text-align:center;white-space:nowrap;font-size:11px;line-height:1.2;height:20px;vertical-align:middle;'

	has_other = any(lb == "기타" for lb in order)
	colgroup = (
		'<col style="width:100px;min-width:100px;max-width:100px;">'
		+ '<col style="width:110px;min-width:110px;max-width:110px;">'
		+ '<col style="width:20px;min-width:20px;max-width:20px;">'
		+ ''.join(['<col style="width:1fr;">' for _ in range(len(order) - (1 if has_other else 0))])
		+ ('<col style="width:20px;min-width:20px;max-width:20px;">' if has_other else '')
		+ ('<col style="width:60px;min-width:60px;max-width:60px;">' if has_other else '')
	)
	head_cells = [
		f'<th style="{head_style}">&nbsp;</th>',
		f'<th style="{head_style}">&nbsp;</th>'
	]
	head_cells.append('<th style="padding:0;line-height:0;font-size:0;">&nbsp;</th>')
	for i, lb in enumerate(order, start=1):
		if lb != "기타":
			prefix = _circled_num(i)
			head_cells.append(
				f'<th style="{label_head_style}"><div style="display:block;width:100%;height:100%;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;line-height:1.2;text-align:center;">{prefix} {html_escape(_display_label(lb, order))}</div></th>'
			)
	if has_other:
		head_cells.append('<th style="padding:0;line-height:0;font-size:0;">&nbsp;</th>')
	if has_other:
		head_cells.append(
			f'<th style="{label_head_style}"><div style="display:block;width:100%;height:100%;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;line-height:1.2;text-align:center;">{html_escape(_display_label("기타", order))}</div></th>'
		)
	head_html = '<thead><tr>' + ''.join(head_cells) + '</tr></thead>'

	# 데이터 준비
	rows_data: List[Dict[str, object]] = []
	for name, rows in seg_bucket_rows:
		cnts = {l: 0 for l in order}
		for r in rows:
			label = label_for_row(r, 'objective') or ''
			if label in cnts:
				cnts[label] += 1
		total = sum(cnts.values()) or 1
		if ' - ' in name:
			seg_name, seg_value = name.split(' - ', 1)
		else:
			seg_name, seg_value = name, ''
		rows_data.append({'seg_name': seg_name,'seg_value': seg_value,'cnts': cnts,'total': total})

	# 임계치 및 색상 스케일 기준
	total_responses = len(question_rows)
	threshold_count = max(int(total_responses * GRAYSCALE_THRESHOLD_PERCENT / 100.0), GRAYSCALE_MIN_COUNT)
	all_pcts: List[float] = []
	for rd in rows_data:
		cnts = rd['cnts']  # type: ignore
		total = int(rd['total'])
		if total >= threshold_count:
			for lb in order:
				if lb != "기타":
					pct = _calculate_percentage(cnts[lb], total)
					all_pcts.append(pct)
	min_pct = min(all_pcts) if all_pcts else 0.0
	max_pct = max(all_pcts) if all_pcts else 100.0

	# 전체 순위(엣지케이스 비교용)
	overall_rank: List[str] = _compute_overall_rank_from_rows_data(rows_data, order)

	# rowspan 및 막대 기준
	first_index: Dict[str, int] = {}
	rowspan_count: Dict[str, int] = {}
	for idx, rd in enumerate(rows_data):
		seg = str(rd['seg_name'])
		if seg not in first_index:
			first_index[seg] = idx
		rowspan_count[seg] = rowspan_count.get(seg, 0) + 1
	max_total = max((int(rd['total']) for rd in rows_data), default=1) or 1

	body_rows: List[str] = []
	for idx, rd in enumerate(rows_data):
		seg_name = str(rd['seg_name'])
		seg_value = str(rd['seg_value'])
		cnts = rd['cnts']  # type: ignore
		total = int(rd['total'])
		cells: List[str] = []
		is_group_start = (idx == first_index.get(seg_name))
		if is_group_start and idx != 0:
			colspan = 3 + (len(order) - (1 if has_other else 0)) + (1 if has_other else 0) + (1 if has_other else 0)
			body_rows.append('<tr><td colspan="' + str(colspan) + '" style="padding:4px 0;height:0;line-height:0;"><div style="height:1px;background:repeating-linear-gradient(to right, #E5E7EB 0 2px, transparent 2px 4px);"></div></td></tr>')
		if is_group_start:
			cells.append(f'<td rowspan="{rowspan_count.get(seg_name,1)}" style="{rowhead_style}">{html_escape(seg_name)}</td>')
		# 엣지케이스 판단 (값 바 강조 전용)
		seg_pct_map: Dict[str, float] = {lb: (cnts[lb] * 100.0 / (total or 1)) for lb in order}
		seg_rank: List[str] = sorted(order, key=lambda lb: (-seg_pct_map.get(lb, 0.0), order.index(lb)))
		orank: List[str] = overall_rank
		is_edgecase = (seg_value != '' and bool(orank) and seg_rank != orank)

		# 값 열
		bar_w = int(round((total / (max_total or 1)) * 100))
		bar_w_css = max(1, bar_w)
		value_td_style = 'padding:0;color:#111827;font-size:12px;text-align:left;white-space:nowrap;height:20px;position:relative;overflow:hidden;vertical-align:middle;'
		bar_html = (
			'<table role="presentation" cellpadding="0" cellspacing="0" border="0" style="border-collapse:collapse;width:100%;height:20px;table-layout:fixed;">'
			'<tr>'
			f'<td width="{bar_w_css}%" style="height:20px;line-height:20px;vertical-align:middle;'
			+ (f"background-color:{CONTRAST_PALETTE[3]};" if is_edgecase else "background-color:#D1D5DB;")
			+ 'padding:0;color:#111827;font-size:11px;white-space:nowrap;overflow:visible;">'
			+ f'<span style="margin-left:4px;">{html_escape(seg_value)}'
			+ f'<span style="color:#6B7280;margin-left:6px;">({total:,})</span></span>'
			+ '</td>'
			f'<td width="{100 - bar_w_css}%" style="height:20px;line-height:20px;vertical-align:middle;padding:0;margin:0;"></td>'
			+ '</tr></table>'
		)
		if seg_value:
			cells.append(f'<td style="{value_td_style}">{bar_html}</td>')
		else:
			bar_html_all = (
				'<table role="presentation" cellpadding="0" cellspacing="0" border="0" style="border-collapse:collapse;width:100%;height:20px;table-layout:fixed;">'
				'<tr>'
				f'<td width="{bar_w_css}%" style="height:20px;line-height:20px;vertical-align:middle;background-color:#D1D5DB;padding:0;color:#111827;font-size:11px;white-space:nowrap;overflow:visible;">'
				+ '<span style="margin-left:4px;">전체'
				+ f'<span style="color:#6B7280;margin-left:6px;">(답변수={total:,})</span></span>'
				+ '</td>'
				f'<td width="{100 - bar_w_css}%" style="height:20px;line-height:20px;vertical-align:middle;padding:0;margin:0;"></td>'
				+ '</tr></table>'
			)
			cells.append(f'<td style="{value_td_style}">{bar_html_all}</td>')
		# 값-히트맵 스페이서
		if is_group_start:
			cells.append(f'<td rowspan="{rowspan_count.get(seg_name,1)}" style="line-height:0;font-size:0;">\n\t<div style="padding:0 4px;">\n\t\t<div style="height:16px;background:transparent;"></div>\n\t</div>\n</td>')
		# 퍼센트 셀들
		use_grayscale = total < threshold_count
		for lb in order:
			if lb == "기타" and has_other:
				if is_group_start:
					cells.append(f'<td rowspan="{rowspan_count.get(seg_name,1)}" style="width:20px;min-width:20px;max-width:20px;line-height:0;font-size:0;">\n\t<div style="padding:0 4px;">\n\t\t<div style="height:16px;background:transparent;"></div>\n\t</div>\n</td>')
			pct = round(100.0 * cnts[lb] / (total or 1), 1)
			if use_grayscale or lb == "기타":
				if lb == "기타":
					bg = _shade_for_other_column(pct)
				else:
					bg = _shade_for_grayscale_dynamic(pct, min_pct, max_pct)
			else:
				bg = _shade_for_pct_dynamic(pct, min_pct, max_pct)
			fg = _auto_text_color(bg)
			if lb == "기타":
				cells.append(f'<td style="{cell_style_base}width:60px;min-width:60px;max-width:60px;padding:0;background:{bg};background-color:{bg};background-image:none;color:{fg};border-radius:12px;overflow:hidden;">{pct:.1f}%</td>')
			else:
				cells.append(f'<td style="{cell_style_base}width:60px;padding:0;background:{bg};background-color:{bg};background-image:none;color:{fg};">{pct:.1f}%</td>')
		body_rows.append('<tr>' + ''.join(cells) + '</tr>')

	return (
		'<table role="presentation" cellpadding="0" cellspacing="0" border="0" '
		'style="width:100%;table-layout:fixed;border-collapse:collapse;padding-left:4px;padding-right:8px;">'
		+ f'<colgroup>{colgroup}</colgroup>'
		+ head_html + '<tbody>' + ''.join(body_rows) + '</tbody>' + '</table>'
	)


	# =========================
	# 평가형: 공통 히트맵 렌더러
	# =========================
def _render_evaluation_heatmap_table(question_rows: List[Dict[str, str]], order: List[str]) -> str:
	# 세그 정의 및 버킷 수집
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
	preferred_orders: Dict[str, List[str]] = {
		"gndr_seg": ["01.남성", "02.여성"],
		"age_seg": ["01.10대","02.20대","03.30대","04.40대","05.50대","06.60대","07.기타"],
	}
	seg_bucket_rows: List[Tuple[str, List[Dict[str, str]]]] = []
	seg_bucket_rows.append(("전체", question_rows))
	for seg_title, seg_key in seg_defs:
		vals = set()
		for r in question_rows:
			v = (r.get(seg_key) or "").strip()
			if v:
				vals.add(v)
		if seg_key in preferred_orders:
			ordered_vals = [v for v in preferred_orders[seg_key] if v in vals]
			remain = sorted([v for v in vals if v not in set(ordered_vals)])
			ordered_vals += remain
		else:
			ordered_vals = sorted(vals)
		for raw_val in ordered_vals:
			if clean_axis_label(raw_val) == '기타':
				continue
			bucket_label = f"{seg_title} - {clean_axis_label(raw_val)}"
			rows_subset = [r for r in question_rows if (r.get(seg_key) or '').strip() == raw_val]
			if not rows_subset:
				continue
			seg_bucket_rows.append((bucket_label, rows_subset))

	# 스타일
	head_style = 'padding:6px 8px;color:#111827;font-size:12px;text-align:center;'
	label_head_style = 'padding:0 2px;color:#111827;font-size:12px;text-align:center;vertical-align:middle;overflow:hidden;'
	rowhead_style = 'padding:0 8px;color:#111827;font-size:12px;text-align:left;white-space:nowrap;height:20px;vertical-align:middle;'
	cell_style_base = 'padding:0;text-align:center;white-space:nowrap;font-size:11px;line-height:1.2;height:20px;vertical-align:middle;'

	# 헤더
	colgroup = (
		'<col style="width:100px;min-width:100px;max-width:100px;">'
		'<col style="width:110px;min-width:110px;max-width:110px;">'
		+ '<col style="width:20px;min-width:20px;max-width:20px;">'
		+ ''.join(['<col style="width:1fr;">' for _ in range(len(order))])
		+ '<col style="width:20px;min-width:20px;max-width:20px;">'
		+ '<col style="width:60px;min-width:60px;max-width:60px;">'
		+ '<col style="width:60px;min-width:60px;max-width:60px;">'
	)
	head_cells = [
		f'<th style="{head_style}">&nbsp;</th>',
		f'<th style="{head_style}">&nbsp;</th>'
	]
	head_cells.append('<th style="padding:0;line-height:0;font-size:0;">&nbsp;</th>')
	for i, lb in enumerate(order, start=1):
		prefix = _circled_num(i)
		label_text = _display_label(lb, order)
		label_with_point = (label_text + '점') if str(label_text).strip().isdigit() else label_text
		head_cells.append(
			f'<th style="{label_head_style}"><div style="display:block;width:100%;height:100%;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;line-height:1.2;text-align:center;">{prefix} {html_escape(label_with_point)}</div></th>'
		)
	head_cells.append('<th style="padding:0;line-height:0;font-size:0;">&nbsp;</th>')
	_, top_text, _ = _calculate_top_satisfaction({l: 1 for l in order}, order)
	head_cells.append(f'<th style="{head_style}padding:0;"><div style="display:block;width:100%;height:100%;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;line-height:1.2;text-align:center;">{top_text}</div></th>')
	head_cells.append(f'<th style="{head_style}padding:0;"><div style="display:block;width:100%;height:100%;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;line-height:1.2;text-align:center;">평균점수</div></th>')
	head_html = '<thead><tr>' + ''.join(head_cells) + '</tr></thead>'

	# 데이터 준비
	rows_data: List[Dict[str, object]] = []
	for name, rows in seg_bucket_rows:
		cnts = {l: 0 for l in order}
		for r in rows:
			content = (r.get('lkng_cntnt') or r.get('answ_cntnt') or '').strip()
			if content in cnts:
				cnts[content] += 1
		total = sum(cnts.values()) or 1
		if ' - ' in name:
			seg_name, seg_value = name.split(' - ', 1)
		else:
			seg_name, seg_value = name, ''
		rows_data.append({'seg_name': seg_name,'seg_value': seg_value,'cnts': cnts,'total': total})

	# 임계치 및 색상 스케일 기준(히트맵/순만족도/평균점수)
	total_responses = len(question_rows)
	threshold_count = max(int(total_responses * GRAYSCALE_THRESHOLD_PERCENT / 100.0), GRAYSCALE_MIN_COUNT)
	heatmap_pcts: List[float] = []
	sun_pcts: List[float] = []
	avg_scores: List[float] = []
	for rd in rows_data:
		cnts = rd['cnts']  # type: ignore
		total = int(rd['total'])
		if total >= threshold_count:
			for lb in order:
				pct = _calculate_percentage(cnts[lb], total)
				heatmap_pcts.append(pct)
			sun_pct, _, _ = _calculate_top_satisfaction(cnts, order)
			sun_pcts.append(sun_pct)
			avg_score = _calculate_average_score(cnts, order)
			avg_scores.append(avg_score)
	min_heatmap_pct = min(heatmap_pcts) if heatmap_pcts else 0.0
	max_heatmap_pct = max(heatmap_pcts) if heatmap_pcts else 100.0
	min_sun_pct = min(sun_pcts) if sun_pcts else 0.0
	max_sun_pct = max(sun_pcts) if sun_pcts else 100.0
	min_avg_score = min(avg_scores) if avg_scores else 1.0
	max_avg_score = max(avg_scores) if avg_scores else 5.0

	# 전체 순위(엣지케이스 비교용)
	overall_rank: List[str] = []
	if rows_data:
		overall_cnts = rows_data[0]['cnts']  # type: ignore
		overall_total = int(rows_data[0]['total'])  # type: ignore
		overall_pct_map: Dict[str, float] = {lb: ((overall_cnts[lb] * 100.0) / (overall_total or 1)) for lb in order}  # type: ignore
		overall_rank = sorted(order, key=lambda lb: (-overall_pct_map.get(lb, 0.0), order.index(lb)))

	# rowspan 및 막대 기준
	first_index: Dict[str, int] = {}
	rowspan_count: Dict[str, int] = {}
	for idx, rd in enumerate(rows_data):
		seg = str(rd['seg_name'])
		if seg not in first_index:
			first_index[seg] = idx
		rowspan_count[seg] = rowspan_count.get(seg, 0) + 1
	max_total = max((int(rd['total']) for rd in rows_data), default=1) or 1

	body_rows: List[str] = []
	for idx, rd in enumerate(rows_data):
		seg_name = str(rd['seg_name'])
		seg_value = str(rd['seg_value'])
		cnts = rd['cnts']  # type: ignore
		total = int(rd['total'])
		cells: List[str] = []
		is_group_start = (idx == first_index.get(seg_name))
		if is_group_start and idx != 0:
			total_cols = 6 + len(order)
			body_rows.append(f'<tr><td colspan="{total_cols}" style="padding:4px 0;height:0;line-height:0;"><div style="height:1px;background:repeating-linear-gradient(to right, #E5E7EB 0 2px, transparent 2px 4px);"></div></td></tr>')
		if is_group_start:
			cells.append(f'<td rowspan="{rowspan_count.get(seg_name,1)}" style="{rowhead_style}">{html_escape(seg_name)}</td>')
		# 엣지케이스 판단(값 바 강조 전용)
		seg_pct_map: Dict[str, float] = {lb: (cnts[lb] * 100.0 / (total or 1)) for lb in order}
		seg_rank: List[str] = sorted(order, key=lambda lb: (-seg_pct_map.get(lb, 0.0), order.index(lb)))
		orank: List[str] = overall_rank
		is_edgecase = (seg_value != '' and bool(orank) and seg_rank != orank)

		# 값 열
		bar_w = int(round((total / (max_total or 1)) * 100))
		bar_w_css = max(1, bar_w)
		value_td_style = 'padding:0;color:#111827;font-size:12px;text-align:left;white-space:nowrap;height:20px;position:relative;overflow:hidden;vertical-align:middle;'
		bar_html = (
			'<table role="presentation" cellpadding="0" cellspacing="0" border="0" style="border-collapse:collapse;width:100%;height:20px;table-layout:fixed;">'
			'<tr>'
			f'<td width="{bar_w_css}%" style="height:20px;line-height:20px;vertical-align:middle;'
			+ (f"background-color:{CONTRAST_PALETTE[3]};" if is_edgecase else "background-color:#D1D5DB;")
			+ 'padding:0;color:#111827;font-size:11px;white-space:nowrap;overflow:visible;">'
			+ f'<span style="margin-left:4px;">{html_escape(seg_value)}'
			+ f'<span style="color:#6B7280;margin-left:6px;">({total:,})</span></span>'
			+ '</td>'
			f'<td width="{100 - bar_w_css}%" style="height:20px;line-height:20px;vertical-align:middle;padding:0;margin:0;"></td>'
			+ '</tr></table>'
		)
		if seg_value:
			cells.append(f'<td style="{value_td_style}">{bar_html}</td>')
		else:
			bar_html_all = (
				'<table role="presentation" cellpadding="0" cellspacing="0" border="0" style="border-collapse:collapse;width:100%;height:20px;table-layout:fixed;">'
				'<tr>'
				f'<td width="{bar_w_css}%" style="height:20px;line-height:20px;vertical-align:middle;background-color:#D1D5DB;padding:0;color:#111827;font-size:11px;white-space:nowrap;overflow:visible;">'
				+ '<span style="margin-left:4px;">전체'
				+ f'<span style="color:#6B7280;margin-left:6px;">(답변수={total:,})</span></span>'
				+ '</td>'
				f'<td width="{100 - bar_w_css}%" style="height:20px;line-height:20px;vertical-align:middle;padding:0;margin:0;"></td>'
				+ '</tr></table>'
			)
			cells.append(f'<td style="{value_td_style}">{bar_html_all}</td>')
		# (값-히트맵) 갭
		if is_group_start:
			cells.append(f'<td rowspan="{rowspan_count.get(seg_name,1)}" style="line-height:0;font-size:0;">\n\t<div style="padding:0 4px;">\n\t\t<div style="height:16px;background:transparent;"></div>\n\t</div>\n</td>')
		# 퍼센트 셀들
		use_grayscale = total < threshold_count
		for lb in order:
			pct = round(100.0 * cnts[lb] / (total or 1), 1)
			if use_grayscale:
				bg = _shade_for_grayscale_dynamic(pct, min_heatmap_pct, max_heatmap_pct)
			else:
				bg = _shade_for_pct_dynamic(pct, min_heatmap_pct, max_heatmap_pct)
			fg = _auto_text_color(bg)
			cells.append(f'<td style="{cell_style_base}width:60px;padding:0;background:{bg};background-color:{bg};background-image:none;color:{fg};">{pct:.1f}%</td>')
		# (히트맵-지표) 갭
		if is_group_start:
			cells.append(f'<td rowspan="{rowspan_count.get(seg_name,1)}" style="line-height:0;font-size:0;">\n\t<div style="padding:0 4px;">\n\t\t<div style="height:16px;background:transparent;"></div>\n\t</div>\n</td>')
		# 순만족도 셀
		sun, _, _ = _calculate_top_satisfaction(cnts, order)
		bg_sun = _shade_for_grayscale_dynamic(sun, min_sun_pct, max_sun_pct) if use_grayscale else _shade_for_pct_dynamic(sun, min_sun_pct, max_sun_pct)
		fg_sun = _auto_text_color(bg_sun)
		cells.append(f'<td style="{cell_style_base}width:60px;min-width:60px;max-width:60px;padding:0;background:{bg_sun};background-color:{bg_sun};background-image:none;color:{fg_sun};border-radius:12px;overflow:hidden;">{sun:.1f}%</td>')
		# 평균점수 셀
		avg_score = _calculate_average_score(cnts, order)
		avg_pct = ((avg_score - min_avg_score) / (max_avg_score - min_avg_score)) * 100.0 if max_avg_score > min_avg_score else 50.0
		bg_avg = _shade_for_grayscale_dynamic(avg_pct, 0.0, 100.0) if use_grayscale else _shade_for_pct_dynamic(avg_pct, 0.0, 100.0)
		fg_avg = _auto_text_color(bg_avg)
		cells.append(f'<td style="{cell_style_base}width:60px;min-width:60px;max-width:60px;padding:0;background:{bg_avg};background-color:{bg_avg};background-image:none;color:{fg_avg};border-radius:12px;overflow:hidden;">{avg_score:.3f}</td>')
		body_rows.append('<tr>' + ''.join(cells) + '</tr>')

	return (
		'<table role="presentation" cellpadding="0" cellspacing="0" border="0" '
		'style="width:100%;table-layout:fixed;border-collapse:collapse;padding-left:4px;padding-right:8px;">'
		+ f'<colgroup>{colgroup}</colgroup>'
		+ head_html + '<tbody>' + ''.join(body_rows) + '</tbody>' + '</table>'
	)


# =========================
# 단일 히트맵 컴포넌트 엔트리
# =========================
def build_heatmap_component(
	question_rows: List[Dict[str, str]],
	order: List[str],
	kind: str = 'general',  # 'general' | 'evaluation'
	include_cross_analysis: bool = False,
	include_other_summary: bool = False,
	question_title: str = '',
	all_data: List[Dict[str, str]] = None,
	question_id: str = None,
	extra_footer_html: str = '',
	remark_base_items: Optional[List[str]] = None,
) -> str:
	"""단일 히트맵 컴포넌트 생성.
	옵션에 따라 일반형/평가형, 교차분석 유무, 기타요약 유무를 제어한다.
	"""
	# 테이블 생성 (kind에 따라 렌더러 선택)
	if kind == 'evaluation':
		table = _render_evaluation_heatmap_table(question_rows, order)
	else:
		table = _render_general_heatmap_table(question_rows, order)
	
	# 교차분석 섹션
	edge_cases_section = ''
	if include_cross_analysis:
		edge_cases: List[Dict[str, object]] = []
		qtype_for_cross = 'evaluation' if kind == 'evaluation' else 'objective'
		for label in order:
			edge_cases.extend(_analyze_cross_segments(question_rows, question_title or ("평가형 문항" if kind=='evaluation' else "객관식 문항"), qtype_for_cross, label))
		edge_cases_section = _build_question_edge_cases_section(edge_cases, order, question_rows, all_data, question_id)

	has_table_edgecase = has_heatmap_edgecase_marker(table)
	has_cross_edgecase = bool(edge_cases) if include_cross_analysis else False

	legend_note_html = build_heatmap_remark(
		base_items=remark_base_items,
		include_edgecase_marker=(has_table_edgecase or has_cross_edgecase),
	)
	
	# 기타 응답 요약 (일반형에서만 의미 있음)
	other_summary_section = ''
	if include_other_summary and kind == 'general':
		other_summary_section = build_other_responses_summary(question_rows)
	
	heading = '<div style="font-weight:700;font-size:14px;color:#111827;margin-bottom:0;">Seg.별 히트맵</div>'
	return '<div style="margin:12px 0;padding:12px;border:1px solid #E5E7EB;border-radius:6px;background:#FFFFFF;">' + heading + table + legend_note_html + (extra_footer_html if extra_footer_html else '') + edge_cases_section + (other_summary_section if other_summary_section else '') + '</div>'

def build_general_heatmap_only(question_rows: List[Dict[str, str]], label_order: List[str], question_title: str = "객관식 문항", all_data: List[Dict[str, str]] = None, question_id: str = None) -> str:
	"""객관식(일반) 문항용 히트맵: 행=세그 버킷, 열=라벨.
	- 만족도 전용 요약/순만족도 없이, 퍼센트 셀만 표시
	- 스타일은 만족도 히트맵과 톤앤매너 일치
	- 교차분석 제외
	"""
	order = list(label_order)
	return build_heatmap_component(
		question_rows,
		order,
		kind='general',
		include_cross_analysis=False,
		include_other_summary=True,
		question_title=question_title,
		all_data=all_data,
		question_id=question_id,
		remark_base_items=[DEFAULT_HEATMAP_REMARK_BASE],
	)

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

	return build_heatmap_component(
		question_rows,
		order,
		kind='evaluation',
		include_cross_analysis=False,
		include_other_summary=False,
		question_title=question_title,
		all_data=all_data,
		question_id=question_id,
		remark_base_items=[DEFAULT_HEATMAP_REMARK_BASE],
	)

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
	# 평가형은 제공된 label_order를 그대로 사용 (패턴 간주 제거)
	order = [lb for lb in label_order]
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
	for i, lb in enumerate(order, start=1):
		# 라벨 줄바꿈 허용을 위해 래퍼 div 사용(폭 기준으로 개행), 어미 제거
		prefix = _circled_num(i)
		label_text = _display_label(lb, order)
		label_with_point = (label_text + '점') if str(label_text).strip().isdigit() else label_text
		head_cells.append(
			f'<th style="{label_head_style}"><div style="display:block;width:100%;height:100%;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;line-height:1.2;text-align:center;">{prefix} {html_escape(label_with_point)}</div></th>'
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
			+ (f"background-color:{CONTRAST_PALETTE[3]};" if is_edgecase else "background-color:#D1D5DB;")
			+ 'padding:0;color:#111827;font-size:11px;white-space:nowrap;overflow:visible;">'
			+ f'<span style="margin-left:4px;">{html_escape(seg_value)}'
			+ f'<span style="color:#6B7280;margin-left:6px;">({total:,})</span></span>'
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
				+ f'<span style="color:#6B7280;margin-left:6px;">(Total={total:,})</span></span>'
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
		# 순만족도: n이 임계치 미만이면 그레이스케일, 아니면 HEATMAP_PALETTE 팔레트
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

	remark_html = build_heatmap_remark(
		base_items=[DEFAULT_HEATMAP_REMARK_BASE],
		include_edgecase_marker=(has_heatmap_edgecase_marker(table) or bool(edge_cases)),
	)

	# 엣지케이스 섹션 생성 (평가형용)
	edge_cases_section = _build_evaluation_edge_cases_section(edge_cases, order, question_rows, all_data, question_id)

	# 요약(카드/랭크) 제거하고 제목 바로 아래 히트맵 표시
	return '<div style="margin:12px 0;padding:12px;border:1px solid #E5E7EB;border-radius:6px;background:#FFFFFF;">' + heading + table + remark_html + edge_cases_section + '</div>'


def detect_encoding(file_path: str) -> str:
	"""CSV 파일 인코딩을 추정하여 반환.

	- 한국어 CSV에서 주로 사용되는 인코딩 순서로 시도: utf-8-sig → cp949 → euc-kr → utf-8
	- 첫 줄을 읽는 데 성공하면 해당 인코딩을 반환, 모두 실패 시 utf-8로 폴백
	"""
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
	"""CSV를 읽어 각 행을 딕셔너리로 반환.

	- 인코딩 자동 감지 후 `csv.DictReader`로 로딩
	- 키/값 문자열은 좌우 공백 제거하여 정규화
	- 반환: [{column: value, ...}, ...]
	"""
	enc = detect_encoding(file_path)
	with open(file_path, "r", encoding=enc, newline="") as f:
		reader = csv.DictReader(f)
		rows: List[Dict[str, str]] = []
		for row in reader:
			# 열 이름 및 값 공백 정규화
			normalized = { (k.strip() if isinstance(k, str) else k): (v.strip() if isinstance(v, str) else v) for k, v in row.items() }
			rows.append(normalized)
	return rows


def get_first_nonempty(rows: List[Dict[str, str]], key: str) -> Optional[str]:
	"""행 리스트에서 주어진 키에 대한 첫 번째 비어있지 않은 값을 반환."""
	for r in rows:
		val = r.get(key)
		if val:
			return val
	return None


def get_report_title(rows: List[Dict[str, str]]) -> str:
    """보고서 제목을 결정.

    - 우선순위: `main_ttl` → 없으면 `surv_id`를 이용한 기본 제목
    """
    title = get_first_nonempty(rows, "main_ttl")
    if title:
        return title
    return f"Survey Report ({get_first_nonempty(rows, 'surv_id') or 'N/A'})"


def group_by_question(rows: List[Dict[str, str]]) -> Dict[str, Dict[str, object]]:
	"""문항 단위로 데이터 그룹핑.

	반환 형태: { 문항키 → { 'title': 표시 제목, 'rows': 해당 문항 행 리스트 } }
	- 문항키: `qsit_sqn` 우선, 없으면 `qsit_ttl` 사용
	- 표시 제목: `qsit_ttl` 우선, 없으면 "문항 {문항키}"
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
	"""한 행에서 그래프/범례용 라벨 후보를 선택.

	우선순위: `answ_cntnt` → `lkng_cntnt` → `answ_sqn`
	공백/점(".")/"0" 값은 제외
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
	"""문항 내 보기(라벨) 분포를 카운트하여 Counter로 반환."""
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
	
	# 다수결로 타입 결정: 같은 문항의 행들에서 가장 많이 등장한 qsit_type_ds_cd를 채택
	from collections import Counter as _Counter
	code_counter = _Counter()
	for r in question_rows:
		val = (r.get("qsit_type_ds_cd") or "").strip()
		if val in mapping:
			code_counter[val] += 1
	# 기본값 objective
	if not code_counter:
		return "objective"
	major_code, _ = max(code_counter.items(), key=lambda kv: kv[1])
	return mapping.get(major_code, "objective")


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


def _expected_evaluation_numeric_labels(question_rows: List[Dict[str, str]]) -> List[str]:
	"""평가형 문항에서 척도 정의(lbl_type_ds_cd)를 기반으로 기대되는 숫자 라벨 목록을 생성."""
	max_scale = 0
	pad_width = 0
	has_numeric_label = False
	for r in question_rows:
		raw_max = (r.get("lbl_type_ds_cd") or "").strip()
		if raw_max.isdigit():
			max_scale = max(max_scale, int(raw_max))
		for key in ("lkng_cntnt", "answ_cntnt"):
			val = (r.get(key) or "").strip()
			if val.isdigit():
				has_numeric_label = True
				pad_width = max(pad_width, len(val))
	if max_scale <= 0 or not has_numeric_label:
		return []
	if pad_width <= 0:
		pad_width = len(str(max_scale))
	if pad_width <= 0:
		pad_width = 1
	return [str(i).zfill(pad_width) for i in range(1, max_scale + 1)]


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

	if qtype == "evaluation":
		expected_labels = _expected_evaluation_numeric_labels(question_rows)
		if expected_labels:
			for label in expected_labels:
				if label not in counts:
					counts[label] = 0
				if label not in sortmap:
					try:
						sortmap[label] = float(label)
					except Exception:
						sortmap[label] = label

	def _mixed_sort_key(v: object):
		if isinstance(v, (int, float)):
			return (0, float(v))
		# try numeric parse from string
		s = str(v)
		try:
			return (0, float(s))
		except Exception:
			return (1, s)

	# 평가형 문항의 경우 특별한 정렬 순서 적용 (패턴 간주 제거)
	if qtype == "evaluation":
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
	external_labels: List[Tuple[str, float]] = []  # (text, start_pct)
	# px 임계값 적용을 위한 차트 가로폭 추정
	approx_chart_width_px = int(REPORT_MAX_WIDTH * GENERAL_STATS_CHART_LEFT_COL_PCT) - GENERAL_STATS_CHART_LEFT_PADDING_PX
	if approx_chart_width_px < 1:
		approx_chart_width_px = int(REPORT_MAX_WIDTH * 0.6)

	cumulative_start_pct = 0.0
	for idx, (label, count) in enumerate(items):
		pct = round(count * 100.0 / total, 2)
		segment_pct = max(pct, 0.0)
		color = color_for_index(idx)
		segment_px = max(0.0, (segment_pct / 100.0) * approx_chart_width_px)
		hide_inner = segment_px < GRAPH_INTERNAL_TEXT_MIN_PX or segment_pct <= 0.0
		inner_text = "" if hide_inner else f"{pct:.1f}%"
		width_style = f"width:{segment_pct}%;"
		if segment_pct <= 0.0:
			width_style += "min-width:1px;max-width:1px;"
		segments_html.append(
			f'<td style="padding:0;height:50px;background:{color};{width_style}text-align:center;overflow:hidden;">'
			f'<div style="display:block;width:100%;color:#FFFFFF;font-size:11px;line-height:50px;white-space:nowrap;overflow:hidden;text-overflow:clip;">{inner_text}</div>'
			'</td>'
		)
		if hide_inner and segment_pct > 0.0:
			text = f"{pct:.1f}%"
			external_labels.append((text, cumulative_start_pct))
		cumulative_start_pct += segment_pct

	captions_row = ""
	if external_labels:
		rows_count = len(external_labels)
		row_h = GRAPH_EXTERNAL_LABEL_ROW_HEIGHT_PX
		row_gap = GRAPH_EXTERNAL_LABEL_ROW_GAP_PX
		total_h = rows_count * row_h + (rows_count - 1) * row_gap if rows_count > 0 else 0
		guidelines = "".join([
			f'<div style="position:absolute;left:{start_pct}%;top:0;width:0;height:{(i+1)*row_h + i*row_gap}px;border-left:{GRAPH_GUIDELINE_STYLE} {GRAPH_GUIDELINE_COLOR};"></div>'
			for i, (_text, start_pct) in enumerate(external_labels)
		])
		label_divs = []
		for i, (text, start_pct) in enumerate(external_labels):
			y_top = i * (row_h + row_gap)
			label_divs.append(
				f'<div style="position:absolute;left:{start_pct}%;top:{y_top}px;height:{row_h}px;text-align:left;color:#111827;font-size:11px;line-height:{row_h}px;white-space:nowrap;">{text}</div>'
			)
		stack = f'<div style="position:relative;height:{total_h}px;">' + guidelines + "".join(label_divs) + '</div>'
		captions_row = f"<tr><td colspan=\"{len(items)}\" style=\"padding:0;\">{stack}</td></tr>"
	mt_top = 2 if external_labels else 6
	return (
		f'<table role="presentation" cellpadding="0" cellspacing="0" border="0" style="width:100%;border-collapse:collapse;margin-top:{mt_top}px;">'
		+ "<tr>" + "".join(segments_html) + "</tr>"
		+ captions_row
		+ "</table>"
	)


def build_stacked_bar_html_ordered_height(items: List[Tuple[str, int]], height_px: int) -> str:
	"""100% 누적막대, 높이를 지정 가능."""
	total = sum(c for _, c in items) or 1
	segments_html: List[str] = []
	external_labels: List[Tuple[str, float]] = []  # (text, start_pct)
	# px 임계값 적용을 위한 차트 가로폭 추정
	approx_chart_width_px = int(REPORT_MAX_WIDTH * GENERAL_STATS_CHART_LEFT_COL_PCT) - GENERAL_STATS_CHART_LEFT_PADDING_PX
	if approx_chart_width_px < 1:
		approx_chart_width_px = int(REPORT_MAX_WIDTH * 0.6)

	cumulative_start_pct = 0.0
	for idx, (label, count) in enumerate(items):
		pct = round(count * 100.0 / total, 2)
		segment_pct = max(pct, 0.0)
		color = color_for_index(idx)
		text_color = _auto_text_color(color)
		segment_px = max(0.0, (segment_pct / 100.0) * approx_chart_width_px)
		hide_inner = segment_px < GRAPH_INTERNAL_TEXT_MIN_PX or segment_pct <= 0.0
		inner_text = "" if hide_inner else f"{pct:.1f}%"
		width_style = f"width:{segment_pct}%;"
		if segment_pct <= 0.0:
			width_style += "min-width:1px;max-width:1px;"
		segments_html.append(
			f'<td style="padding:0;height:{height_px}px;background:{color};{width_style}text-align:center;overflow:hidden;">'
			f'<div style="display:block;width:100%;color:{text_color};font-size:11px;line-height:{height_px}px;white-space:nowrap;overflow:hidden;text-overflow:clip;">{inner_text}</div>'
			'</td>'
		)
		if hide_inner and segment_pct > 0.0:
			text = f"{pct:.1f}%"
			external_labels.append((text, cumulative_start_pct))
		cumulative_start_pct += segment_pct

	captions_row = ""
	if external_labels:
		rows_count = len(external_labels)
		row_h = GRAPH_EXTERNAL_LABEL_ROW_HEIGHT_PX
		row_gap = GRAPH_EXTERNAL_LABEL_ROW_GAP_PX
		total_h = rows_count * row_h + (rows_count - 1) * row_gap if rows_count > 0 else 0
		guidelines = "".join([
			f'<div style="position:absolute;left:{start_pct}%;top:0;width:0;height:{(i+1)*row_h + i*row_gap}px;border-left:{GRAPH_GUIDELINE_STYLE} {GRAPH_GUIDELINE_COLOR};"></div>'
			for i, (_text, start_pct) in enumerate(external_labels)
		])
		label_divs = []
		for i, (text, start_pct) in enumerate(external_labels):
			y_top = i * (row_h + row_gap)
			label_divs.append(
				f'<div style="position:absolute;left:{start_pct}%;top:{y_top}px;height:{row_h}px;text-align:left;color:#111827;font-size:11px;line-height:{row_h}px;white-space:nowrap;">{text}</div>'
			)
		stack = f'<div style="position:relative;height:{total_h}px;">' + guidelines + "".join(label_divs) + '</div>'
		captions_row = f"<tr><td colspan=\"{len(items)}\" style=\"padding:0;\">{stack}</td></tr>"
	return (
		'<table role="presentation" cellpadding="0" cellspacing="0" border="0" style="width:100%;border-collapse:collapse;margin-top:6px;">'
		+ "<tr>" + "".join(segments_html) + "</tr>"
		+ captions_row
		+ "</table>"
	)

def build_stacked_bar_html_ordered_height_evaluation(items: List[Tuple[str, int]], height_px: int) -> str:
	"""평가형 문항 전용 100% 누적막대: 높은 점수에 진한 색 적용"""
	total = sum(c for _, c in items) or 1
	segments_html: List[str] = []
	external_labels: List[Tuple[str, float]] = []  # (text, start_pct)
	# deprecated percent threshold (kept for clarity) removed; px-based threshold used below
	# px 임계값 적용을 위한 차트 가로폭 추정
	approx_chart_width_px = int(REPORT_MAX_WIDTH * GENERAL_STATS_CHART_LEFT_COL_PCT) - GENERAL_STATS_CHART_LEFT_PADDING_PX
	if approx_chart_width_px < 1:
		approx_chart_width_px = int(REPORT_MAX_WIDTH * 0.6)

	cumulative_start_pct = 0.0
	for idx, (label, count) in enumerate(items):
		pct = round(count * 100.0 / total, 2)
		color = color_for_evaluation_index(idx, len(items))
		text_color = _auto_text_color(color)
		segment_pct = max(pct, 0.0)
		segment_px = max(0.0, (segment_pct / 100.0) * approx_chart_width_px)
		hide_inner = segment_px < GRAPH_INTERNAL_TEXT_MIN_PX or segment_pct <= 0.0
		inner_text = "" if hide_inner else f"{pct:.1f}%"
		width_style = f"width:{segment_pct}%;"
		if segment_pct <= 0.0:
			width_style += "min-width:1px;max-width:1px;"
		segments_html.append(
			f'<td style="padding:0;height:{height_px}px;background:{color};{width_style}text-align:center;overflow:hidden;">'
			f'<div style="display:block;width:100%;color:{text_color};font-size:11px;line-height:{height_px}px;white-space:nowrap;overflow:hidden;text-overflow:clip;">{inner_text}</div>'
			'</td>'
		)
		if hide_inner and segment_pct > 0.0:
			text = f"{pct:.1f}%"
			external_labels.append((text, cumulative_start_pct))
		cumulative_start_pct += segment_pct

	# 외부 라벨 스택과 세로 지시선 렌더링
	captions_row = ""
	if external_labels:
		rows_count = len(external_labels)
		row_h = GRAPH_EXTERNAL_LABEL_ROW_HEIGHT_PX
		row_gap = GRAPH_EXTERNAL_LABEL_ROW_GAP_PX
		total_h = rows_count * row_h + (rows_count - 1) * row_gap if rows_count > 0 else 0
		guidelines = "".join([
			f'<div style="position:absolute;left:{start_pct}%;top:0;width:0;height:{(i+1)*row_h + i*row_gap}px;border-left:{GRAPH_GUIDELINE_STYLE} {GRAPH_GUIDELINE_COLOR};"></div>'
			for i, (_text, start_pct) in enumerate(external_labels)
		])
		label_divs = []
		for i, (text, start_pct) in enumerate(external_labels):
			y_end = (i+1)*row_h + i*row_gap
			label_divs.append(
				f'<div style="position:absolute;left:{start_pct}%;top:{y_end}px;height:{row_h}px;text-align:left;color:#111827;font-size:11px;line-height:{row_h}px;white-space:nowrap;">{text}</div>'
			)
		container_h = total_h + row_h
		stack = f'<div style="position:relative;height:{container_h}px;">' + guidelines + "".join(label_divs) + '</div>'
		captions_row = f"<tr><td colspan=\"{len(items)}\" style=\"padding:0;\">{stack}</td></tr>"
	return (
		'<table role="presentation" cellpadding="0" cellspacing="0" border="0" style="width:100%;border-collapse:collapse;margin-top:6px;">'
		+ "<tr>" + "".join(segments_html) + "</tr>"
		+ captions_row
		+ "</table>"
	)

def build_stacked_bar_html_ordered_height_heatmap(items: List[Tuple[str, int]], height_px: int) -> str:
	"""PRIMARY_PALETTE 기반 100% 누적막대: 중간값(60%)을 기준으로 확장된 색상 적용"""
	total = sum(c for _, c in items) or 1
	segments_html: List[str] = []
	external_labels: List[Tuple[str, float]] = []  # (text, start_pct)
	# deprecated percent threshold (kept for clarity) removed; px-based threshold used below
	# px 임계값 적용을 위한 차트 가로폭 추정
	approx_chart_width_px = int(REPORT_MAX_WIDTH * GENERAL_STATS_CHART_LEFT_COL_PCT) - GENERAL_STATS_CHART_LEFT_PADDING_PX
	if approx_chart_width_px < 1:
		approx_chart_width_px = int(REPORT_MAX_WIDTH * 0.6)

	cumulative_start_pct = 0.0
	for idx, (label, count) in enumerate(items):
		pct = round(count * 100.0 / total, 2)
		segment_pct = max(pct, 0.0)
		color = color_for_stats_with_heatmap_shades(idx, len(items))
		text_color = _auto_text_color(color)
		segment_px = max(0.0, (segment_pct / 100.0) * approx_chart_width_px)
		hide_inner = segment_px < GRAPH_INTERNAL_TEXT_MIN_PX or segment_pct <= 0.0
		inner_text = "" if hide_inner else f"{pct:.1f}%"
		width_style = f"width:{segment_pct}%;"
		if segment_pct <= 0.0:
			width_style += "min-width:1px;max-width:1px;"
		segments_html.append(
			f'<td style="padding:0;height:{height_px}px;background:{color};{width_style}text-align:center;overflow:hidden;">'
			f'<div style="display:block;width:100%;color:{text_color};font-size:11px;line-height:{height_px}px;white-space:nowrap;overflow:hidden;text-overflow:clip;">{inner_text}</div>'
			'</td>'
		)
		if hide_inner and segment_pct > 0.0:
			text = f"{pct:.1f}%"
			external_labels.append((text, cumulative_start_pct))
		cumulative_start_pct += segment_pct

	# 외부 라벨 스택과 세로 지시선 렌더링
	captions_row = ""
	if external_labels:
		rows_count = len(external_labels)
		row_h = GRAPH_EXTERNAL_LABEL_ROW_HEIGHT_PX
		row_gap = GRAPH_EXTERNAL_LABEL_ROW_GAP_PX
		total_h = rows_count * row_h + (rows_count - 1) * row_gap if rows_count > 0 else 0
		guidelines = "".join([
			f'<div style="position:absolute;left:{start_pct}%;top:0;width:0;height:{(i+1)*row_h + i*row_gap}px;border-left:{GRAPH_GUIDELINE_STYLE} {GRAPH_GUIDELINE_COLOR};"></div>'
			for i, (_text, start_pct) in enumerate(external_labels)
		])
		label_divs = []
		for i, (text, start_pct) in enumerate(external_labels):
			y_end = (i+1)*row_h + i*row_gap
			label_divs.append(
				f'<div style="position:absolute;left:{start_pct}%;top:{y_end}px;height:{row_h}px;text-align:left;color:#111827;font-size:11px;line-height:{row_h}px;white-space:nowrap;">{text}</div>'
			)
		container_h = total_h + row_h
		stack = f'<div style="position:relative;height:{container_h}px;">' + guidelines + "".join(label_divs) + '</div>'
		captions_row = f"<tr><td colspan=\"{len(items)}\" style=\"padding:0;\">{stack}</td></tr>"
	mt_top = 2 if external_labels else 6
	return (
		f'<table role="presentation" cellpadding="0" cellspacing="0" border="0" style="width:100%;table-layout:fixed;border-collapse:collapse;margin-top:{mt_top}px;">'
		+ "<tr>" + "".join(segments_html) + "</tr>"
		+ captions_row
		+ "</table>"
	)


def build_stacked_bar_with_labels(items: List[Tuple[str, int]]) -> str:
	"""세그 상세용: 각 구간 내부에 "count (pct%)" 라벨을 중앙 정렬로 표기."""
	total = sum(c for _, c in items) or 1
	cells: List[str] = []
	for idx, (label, count) in enumerate(items):
		pct = round(count * 100.0 / total, 1)
		width_pct = round(max(count * 100.0 / total, 0.0), 2)
		color = color_for_index(idx)
		text = f"{count} ({pct}%)"
		label_html = text if width_pct >= 12 else ""
		if width_pct <= 0.0:
			width_style = "width:0;min-width:1px;max-width:1px;"
		else:
			width_style = f"width:{width_pct}%;"
		cells.append(
			(
				'<td style="padding:0;height:12px;vertical-align:middle;text-align:center;'
				f'background:{color};{width_style}color:#FFFFFF;font-size:11px;line-height:12px;white-space:nowrap;">'
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
			.replace("{count}", f"{int(count):,}")
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
		label_str = str(label).strip()
		display_label = f"{_circled_num(idx+1)} {label_str}점" if label_str.isdigit() else f"{_circled_num(idx+1)} {label_str}"
		rows_html.append(
			"""
			<tr>
				<td style=\"padding:2px 6px;white-space:nowrap;vertical-align:top;line-height:1.1;\">\n\t\t\t\t\t<span style=\"display:inline-block;width:10px;height:10px;background:{color};border-radius:2px;margin-right:6px;\"></span>\n\t\t\t\t\t<span style=\"font-size:12px;color:#111827;\">{label}</span>\n\t\t\t\t</td>\n\t\t\t\t<td style=\"padding:2px 0 2px 6px;text-align:right;white-space:nowrap;color:#374151;font-size:12px;line-height:1.1;\">{count} ({pct}%)</td>\n\t\t\t</tr>
			""".replace("{color}", color)
			.replace("{label}", html_escape(str(display_label)))
			.replace("{count}", f"{int(count):,}")
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
			.replace("{count}", f"{int(count):,}")
			.replace("{pct}", f"{pct}")
		)
	return (
		'<table role="presentation" cellpadding="0" cellspacing="0" border="0" style="width:100%;border-collapse:collapse;margin-top:6px;">'
		+ "".join(rows_html) + "</table>"
	)

def build_legend_table_from_items_heatmap_with_numbers(items: List[Tuple[str, int]]) -> str:
	"""PRIMARY_PALETTE 기반 범례: 번호 없이 항목명만 표시"""
	total = sum(c for _, c in items) or 1
	rows_html: List[str] = []
	for idx, (label, count) in enumerate(items):
		pct = round(count * 100.0 / total, 1)
		color = color_for_stats_with_heatmap_shades(idx, len(items))
		numbered_label = f"{_circled_num(idx+1)} {label}"
		rows_html.append(
			"""
			<tr>
				<td style=\"padding:2px 6px;white-space:nowrap;vertical-align:top;line-height:1.1;\">\n\t\t\t\t\t<span style=\"display:inline-block;width:10px;height:10px;background:{color};border-radius:2px;margin-right:6px;\"></span>\n\t\t\t\t\t<span style=\"font-size:12px;color:#111827;\">{numbered_label}</span>\n\t\t\t\t</td>\n\t\t\t\t<td style=\"padding:2px 0 2px 6px;text-align:right;white-space:nowrap;color:#374151;font-size:12px;line-height:1.1;\">{count} ({pct}%)</td>\n\t\t\t</tr>
			""".replace("{color}", color)
			.replace("{numbered_label}", html_escape(str(numbered_label)))
			.replace("{count}", f"{int(count):,}")
			.replace("{pct}", f"{pct}")
		)
	return (
		'<table role="presentation" cellpadding="0" cellspacing="0" border="0" style="width:100%;border-collapse:collapse;margin-top:6px;">'
		+ "".join(rows_html) + "</table>"
	)

def build_legend_table_from_items_heatmap_evaluation_with_numbers(items: List[Tuple[str, int]], question_rows: List[Dict[str, str]] = None) -> str:
	"""평가형 범례에 중간 레이블(LBL_TXT)을 추가하고 극값 색상을 부여한다.
	- answ_cntnt==1 → #E23A32, answ_cntnt==최대척도(lbl_type_ds_cd 또는 추정) → #4262FF, 그 외 #6B7280
	"""
	total = sum(c for _, c in items) or 1
	# label → score 매핑
	label_to_score: Dict[str, int] = {}
	max_scale = 0
	min_label_txt = ""
	mid_label_txt = ""
	max_label_txt = ""
	if question_rows:
		for r in question_rows:
			lb = (r.get("lkng_cntnt") or "").strip()
			ans = (r.get("answ_cntnt") or "").strip()
			if lb and ans.isdigit() and lb not in label_to_score:
				label_to_score[lb] = int(ans)
				if int(ans) > max_scale:
					max_scale = int(ans)
			if not min_label_txt:
				min_label_txt = (r.get("minm_lbl_txt") or "").strip()
			if not mid_label_txt:
				mid_label_txt = (r.get("mddl_lbl_txt") or "").strip()
			if not max_label_txt:
				max_label_txt = (r.get("max_lbl_txt") or "").strip()
		# 최대 척도 후보: lbl_type_ds_cd
		try:
			for r in question_rows:
				v = (r.get("lbl_type_ds_cd") or "").strip()
				if v.isdigit():
					max_scale = max(max_scale, int(v))
		except Exception:
			pass
		# 평가형 예상 라벨 보강 (응답이 없어도 score 매핑 유지)
		for expected_label in _expected_evaluation_numeric_labels(question_rows):
			if expected_label not in label_to_score and expected_label.isdigit():
				try:
					label_to_score[expected_label] = int(expected_label)
				except Exception:
					continue
	if max_scale <= 0:
		# 숫자형 라벨 최대값 또는 항목 수로 추정
		try:
			nums = [int(lb) for lb, _ in items if str(lb).isdigit()]
			max_scale = max(nums) if nums else len(items)
		except Exception:
			max_scale = len(items)

	# 엔트리 사전 구성 (병합 처리를 위해)
	entries: List[Dict[str, object]] = []
	if max_scale > 0:
		_mid = (max_scale + 1) / 2.0
		mid_score = int(_mid) if abs(_mid - int(_mid)) < 1e-9 else None
	else:
		mid_score = None
	for idx, (label, count) in enumerate(items):
		pct = round(count * 100.0 / total, 1)
		color = color_for_stats_with_heatmap_shades(idx, len(items))
		score = label_to_score.get(str(label))
		extra_color = "#6B7280"
		arrow_html = ""
		category = None  # 'lower_mid' | 'upper_mid' | None
		if isinstance(score, int):
			mid_val = (max_scale + 1) / 2.0 if max_scale else 0
			if score == 1:
				extra_color = "#E23A32"
			elif score == max_scale:
				extra_color = "#4262FF"
			elif 1 < score < mid_val:
				arrow_html = '<span style="color:#E23A32;font-size:20px;">↑</span>'
				category = 'lower_mid'
			elif mid_val < score < max_scale:
				arrow_html = '<span style="color:#4262FF;font-size:20px;">↓</span>'
				category = 'upper_mid'
			extra_txt = ""
			if score == 1 and min_label_txt:
				extra_txt = min_label_txt
			elif score == max_scale and max_label_txt:
				extra_txt = max_label_txt
			elif mid_score is not None and score == mid_score and mid_label_txt:
				extra_txt = mid_label_txt
		else:
			extra_txt = ""
		entries.append({
			'label': label,
			'count': count,
			'pct': pct,
			'color': color,
			'extra_txt': extra_txt,
			'extra_color': extra_color,
			'arrow_html': arrow_html,
			'category': category,
		})

	# 연속된 동일 카테고리(lower_mid/upper_mid) 병합(run) 계산
	n = len(entries)
	rowspans: Dict[int, int] = {}
	i = 0
	while i < n:
		cat = entries[i]['category']
		if cat in ('lower_mid', 'upper_mid'):
			j = i + 1
			while j < n and entries[j]['category'] == cat:
				j += 1
			run_len = j - i
			if run_len >= 2:
				rowspans[i] = run_len
				# 나머지 인덱스는 middle 셀 skip
				for k in range(i + 1, j):
					rowspans[k] = 0
				i = j
				continue
		i += 1

	# 렌더링
	rows_html: List[str] = []
	for idx, e in enumerate(entries):
		label = e['label']
		count = e['count']
		pct = e['pct']
		color = e['color']
		extra_txt = e['extra_txt']
		extra_color = e['extra_color']
		arrow_html = e['arrow_html']
		rows_html.append('<tr>')
		# 좌측: 색상 블록 + 라벨
		rows_html.append(
			'<td style="padding:2px 6px;white-space:nowrap;vertical-align:middle;">'
			+ '<div style="display:flex;align-items:center;gap:6px;height:18px;">'
			+ f'<span style="display:inline-block;width:10px;height:10px;background:{color};border-radius:2px;"></span>'
			+ f'<span style="font-size:12px;color:#111827;line-height:1;">{_circled_num(idx+1)} {html_escape(str(label) + ("점" if str(label).strip().isdigit() else ""))}</span>'
			+ '</div>'
			+ '</td>'
		)
		# 중간: 병합 처리
		rs = rowspans.get(idx, None)
		if rs is None:
			# 병합 없음: 일반 셀
			rows_html.append(
				'<td style="padding:2px 6px;white-space:nowrap;vertical-align:middle;text-align:center;">'
				+ f'<div style="display:flex;align-items:center;justify-content:center;gap:4px;height:18px;color:{extra_color};font-size:12px;">{arrow_html}<span style=\"line-height:1;\">{html_escape(extra_txt)}</span></div>'
				+ '</td>'
			)
		elif rs > 0:
			# 병합 시작 셀
			rows_html.append(
				f'<td rowspan="{rs}" style="padding:2px 6px;white-space:nowrap;vertical-align:middle;text-align:center;">'
				+ f'<div style="display:flex;align-items:center;justify-content:center;gap:4px;height:100%;color:{extra_color};font-size:12px;">{arrow_html}<span style=\"line-height:1;\">{html_escape(extra_txt)}</span></div>'
				+ '</td>'
			)
		else:
			# 병합된 행: 중간 셀 생략
			pass
		# 우측: 수치
		rows_html.append(
			'<td style="padding:2px 6px;white-space:nowrap;vertical-align:middle;">'
			+ f'<div style="display:flex;align-items:center;justify-content:flex-end;height:18px;color:#374151;font-size:12px;line-height:1;">{count} ({pct}%)</div>'
			+ '</td>'
		)
		rows_html.append('</tr>')
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


def color_for_fixed_5_by_index(i: int) -> str:
	"""PRIMARY_PALETTE에서 COLOR_CONFIG['pick_5_colors'] 기준 5색을 순환 적용."""
	config = COLOR_CONFIG["pick_5_colors"]
	indices = config["indices"]
	return PRIMARY_PALETTE[indices[i % len(indices)]]

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
	neg_color = HEATMAP_PALETTE[config["indices"][0]]  # 부정: HEATMAP_PALETTE에서 80% 색상
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
			f'<div style="padding:6px;border:1px solid {CONTRAST_PALETTE[3]};background:{CONTRAST_PALETTE[3]}20;border-radius:6px;min-height:60px;">'
			f'<div style="color:{CONTRAST_PALETTE[3]};font-size:12px;font-weight:700;margin-bottom:4px;">부정</div>'
			f'<div style="color:{CONTRAST_PALETTE[3]};font-size:12px;word-break:break-word;">{", ".join(neg_list) if neg_list else "-"}</div>'
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
	"""단일 설문 그룹(동일 `main_ttl`)에 대한 HTML 보고서 생성.

	입력은 동일한 `main_ttl` 그룹의 원천 행이며, 문항 단위로 그룹핑하여
	문항 타입에 맞는 컴포넌트를 동적으로 조립한다.
	상단에는 요약(응답자수, 문항 수, 수집 기간, 문항 타입 구성)을 배치한다.
	"""
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
		
		# 3. 평가형 패턴 간주 제거: qsit_type_ds_cd로만 판단
		effective_qtype = base_qtype
		keywords_ctr = extract_keywords(q_rows)

		section_parts: List[str] = []
		# Header layout - effective_qtype에 따라 문항 타입 표시
		display_type = question_type_label(effective_qtype)
		
		section_parts.append(
			f'<div style="margin:48px 0 4px 0;font-weight:700;color:#111827;font-size:16px;">{q_index}번 문항 <span style="font-weight:400;color:#374151;">| {display_type}</span></div>'
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

def main(argv: List[str]) -> int:
	"""CLI 진입점.

	사용법 예시:
	- python csv_report_generator4.py --csv data/파일.csv --normalize-stats-weights on|off

	동작:
	- CSV 경로가 없으면 기본 경로 또는 data 폴더 최신 CSV를 사용
	- `main_ttl` 별로 데이터를 분리해 개별 HTML 보고서를 생성/저장
	- 종료 시 생성 결과 목록과 정규화 설정 상태를 출력
	"""
	# CLI usage: python csv_report_generator3.py --csv data/20250902_sample_data.csv
	csv_path: Optional[str] = None
	# 옵션: 응답자 단위 정규화 on/off
	global RANKING_NORMALIZE_PER_RESPONDENT
	# 기본값 유지, CLI로 덮어쓰기
	i = 0
	while i < len(argv):
		if argv[i] == "--csv" and i + 1 < len(argv):
			csv_path = argv[i + 1]
			i += 2
			continue
		if argv[i] == "--normalize-stats-weights" and i + 1 < len(argv):
			val = (argv[i + 1] or "").strip().lower()
			if val in ("on", "true", "1", "yes", "y"):
				RANKING_NORMALIZE_PER_RESPONDENT = True
			elif val in ("off", "false", "0", "no", "n"):
				RANKING_NORMALIZE_PER_RESPONDENT = False
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
	print(f"[INFO] normalize-stats-weights={'on' if RANKING_NORMALIZE_PER_RESPONDENT else 'off'}")
	for report_path in generated_reports:
		print(f"  - {report_path}")
	
	return 0


def build_keywords_html(keywords_ctr: Counter) -> str:
	"""키워드 Counter를 태그 리스트 형태의 HTML로 변환."""
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
	"""문항 행들에서 `keywords` 컬럼(콤마 구분)을 파싱하여 빈도 Counter 반환."""
	ctr: Counter = Counter()
	for r in question_rows:
		kw = r.get("keywords")
		if not kw:
			continue
		parts = [p.strip() for p in kw.split(",") if p and p.strip()]
		for p in parts:
			ctr[p] += 1
	return ctr

def _shade_for_pct_dynamic(p: float, min_pct: float, max_pct: float) -> str:
	"""동적 범위에 따른 색상 변환. min_pct~max_pct를 HEATMAP_PALETTE 팔레트에 매핑 (히트맵용)."""
	steps = len(HEATMAP_PALETTE)
	if steps <= 1:
		return HEATMAP_PALETTE[0] if HEATMAP_PALETTE else "#E5E7EB"
	if max_pct <= min_pct:
		return HEATMAP_PALETTE[steps // 2]  # 중간 색상 반환
	
	# min_pct~max_pct를 0~1로 정규화 (단순 선형 변환)
	t = max(0.0, min(1.0, (p - min_pct) / (max_pct - min_pct)))
	
	# 연속적인 색상 보간
	return _interpolate_color(t, HEATMAP_PALETTE)

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
	"""객관식 문항의 '기타' 응답을 주관식 요약과 동일한 스타일로 표시.

	- 대상: 객관식(코드 10)이며 텍스트 입력 허용(`text_yn`=1/Y/y)인 행
	- 카테고리/감정/키워드를 요약하여 표 형태로 구성
	- 상단에는 Base/Total(응답자수/답변수)를 표기
	"""
	# 1) 기타 응답 수집 (객관식 코드 10, text_yn 허용)
	other_responses: List[Dict[str, str]] = []
	_excluded_l2 = {'단순 칭찬/불만', '욕설·무관한 피드백', '개선 의사 없음 (“없습니다”)'}
	for r in question_rows:
		qtype_code = (r.get("qsit_type_ds_cd") or "").strip()
		text_yn = (r.get("text_yn") or "").strip()
		if qtype_code == "10" and text_yn in ("1", "Y", "y"):
			l2 = (r.get("category_level2") or "").strip()
			if l2 in _excluded_l2:
				continue
			other_responses.append(r)
	if not other_responses:
		return ""
	# 2) 헬퍼 (주관식과 동일)
	def _cat(row: Dict[str, str]) -> str:
		c1 = (row.get("category_level1") or "").strip()
		c2 = (row.get("category_level2") or "").strip()
		if c1 or c2:
			sep = " > " if (c1 and c2) else ""
			return c1 + sep + c2
		return ""
	def _sent_raw(row: Dict[str, str]) -> str:
		s = (row.get("sentiment") or "").strip()
		return s
	def _split_kw(s: Optional[str]) -> List[str]:
		if not s:
			return []
		return [p.strip() for p in str(s).split(",") if p and p.strip()][:3]
	# 3) 카테고리별 감정 집계 및 키워드 집계
	from collections import defaultdict, Counter
	cat_sent_counts: Dict[str, Counter] = defaultdict(lambda: Counter())
	cat_total: Counter = Counter()
	for r in other_responses:
		c = _cat(r)
		s = _sent_raw(r)
		cat_sent_counts[c][s] += 1
		cat_total[c] += 1
	# 상위 카테고리 (환경 변수 적용)
	top10_cats: List[str] = [c for c, _ in cat_total.most_common(OBJECTIVE_OTHER_MAX_CATEGORIES)]
	# 키워드 집계 → (cat,sent)별 keyword_anal
	kw_counts: Counter = Counter()
	for r in other_responses:
		c = _cat(r)
		s = _sent_raw(r)
		for kw in _split_kw(r.get("keywords")):
			if kw in SUBJECTIVE_EXCLUDE_KEYWORDS:
				continue
			kw_counts[(c, s, kw)] += 1
	keyword_anal_map: Dict[Tuple[str, str], str] = {}
	for (c, s, kw), cnt in sorted(kw_counts.items(), key=lambda x: (-x[1], x[0][2])):
		key = (c, s)
		existing = keyword_anal_map.get(key, "")
		if existing:
			if existing.count("(") >= 5:
				continue
			keyword_anal_map[key] = existing + ", " + f"{kw}({cnt})"
		else:
			keyword_anal_map[key] = f"{kw}({cnt})"
	# 4) 엔트리 구성 (요약 선택용)
	entries: List[Dict[str, object]] = []
	for r in other_responses:
		c = _cat(r)
		s = _sent_raw(r)
		if c not in top10_cats:
			continue
		kw_anal = keyword_anal_map.get((c, s), "")
		text = (r.get("answ_cntnt") or "").strip()
		summary = (r.get("summary") or "").strip() or text
		def _kw_hits(kw_anal_text: str, body: str) -> int:
			if not kw_anal_text or not body:
				return 0
			kws = [re.sub(r"\(.*\)", "", k).strip() for k in kw_anal_text.split(",")]
			return sum(1 for k in kws if k and k in body)
		hits = _kw_hits(kw_anal, text)
		entries.append({"cat": c, "sent": s, "summary": summary, "hits": hits, "len": len(summary)})
	def _normalize_summary_text(text: str) -> str:
		s = (text or "").strip()
		s = re.sub(r"\s+", " ", s)
		return s
	def _pick_summaries(cat: str, sent: str, limit: int) -> List[str]:
		cand = [e for e in entries if e["cat"] == cat and e["sent"] == sent]
		cand.sort(key=lambda e: (-int(e["hits"]), -int(e["len"])) )
		seen: Set[str] = set()
		result: List[str] = []
		for e in cand:
			s = str(e["summary"])
			sn = _normalize_summary_text(s)
			if sn in seen:
				continue
			seen.add(sn)
			result.append(s)
			if len(result) >= limit:
				break
		return result
	# 5) HTML 렌더 (주관식 요약 스타일 그대로)
	base_n = len({(r.get('cust_id') or '').strip() for r in other_responses if (r.get('cust_id') or '').strip()})
	total_n = len(other_responses)
	base_total_text = (
		f"(응답자수={base_n:,} / 답변수={total_n:,})" if total_n != base_n
		else f"(응답자수={base_n:,})"
	)
	html_parts: List[str] = []
	html_parts.append('<div style="margin-top:24px;">')
	html_parts.append(f'<div style="font-weight:700;font-size:14px;color:#111827;margin-bottom:8px;">기타 응답 요약 <span style="color:#6B7280;font-size:12px;font-weight:400;margin-left:6px;">{base_total_text}</span></div>')
	html_parts.append('<table style="width:100%;border-collapse:collapse;border:1px solid #E5E7EB;">')
	html_parts.append('<thead><tr>'
		"<th style=\"background:#4D596F;color:#FFFFFF;font-size:12px;padding:8px;border:1px solid #E5E7EB;width:40px;\">순번</th>"
		"<th style=\"background:#4D596F;color:#FFFFFF;font-size:12px;padding:8px;border:1px solid #E5E7EB;width:200px;\">카테고리</th>"
		"<th style=\"background:#4D596F;color:#FFFFFF;font-size:12px;padding:8px;border:1px solid #E5E7EB;width:175px;\">감정분석</th>"
		"<th style=\"background:#4D596F;color:#FFFFFF;font-size:12px;padding:8px;border:1px solid #E5E7EB;\">주요 키워드</th>"
		'</tr></thead><tbody>')
	for i, cat in enumerate(top10_cats, start=1):
		resp = int(cat_total[cat])
		pos_cnt = int(cat_sent_counts[cat]["긍정"])
		neg_cnt = int(cat_sent_counts[cat]["부정"])
		neu_cnt = int(cat_sent_counts[cat]["중립"])
		def _pct(a: int, b: int) -> str:
			val = (a * 100.0) / (b or 1)
			return f"{val:.1f}%"
		pos_pct = _pct(pos_cnt, resp)
		neg_pct = _pct(neg_cnt, resp)
		neu_pct = _pct(neu_cnt, resp)
		pos_summary_list = _pick_summaries(cat, "긍정", 3)
		neg_summary_list = _pick_summaries(cat, "부정", 3)
		neu_summary_list = _pick_summaries(cat, "중립", 2)
		cell_idx = (f'<td style="border:1px solid #E5E7EB;padding:8px;color:#374151;font-size:12px;width:40px;text-align:center;">{i}</td>')
		# 카테고리 표기 (부모/자식 2행)
		if " > " in cat:
			parent_cat, child_cat = cat.split(" > ", 1)
			cat_display_html = f'{html_escape(parent_cat)}<br><span style="white-space:nowrap;">└ {html_escape(child_cat)} <span style="color:#6B7280;font-size:11px;">({resp}건)</span></span>'
		else:
			cat_display_html = f'{html_escape(cat)} <span style="color:#6B7280;font-size:11px;">({resp}건)</span>'
		cell_cat = (f'<td style="border:1px solid #E5E7EB;padding:8px;vertical-align:middle;font-size:12px;line-height:1.4;width:200px;">{cat_display_html}</td>')
		# 감정 막대 3줄
		cell_sent = (
			'<td style="border:1px solid #E5E7EB;padding:8px;vertical-align:middle;width:175px;">'
			# 긍정
			f'<div style="display:flex;align-items:center;gap:6px;margin-bottom:4px;">'
			f'<div style="width:120px;height:{SUBJECTIVE_BAR_HEIGHT_PX}px;background:{SUBJECTIVE_BAR_BG_COLOR};overflow:hidden;position:relative;"><div style="position:absolute;left:0;top:0;bottom:0;width:{pos_pct};background:{SUBJECTIVE_POS_BAR_COLOR};"></div></div>'
			f'<div style="color:#111827;font-size:10px;white-space:nowrap;">긍정 {pos_pct}</div>'
			'</div>'
			# 부정
			f'<div style="display:flex;align-items:center;gap:6px;margin-bottom:4px;">'
			f'<div style="width:120px;height:{SUBJECTIVE_BAR_HEIGHT_PX}px;background:{SUBJECTIVE_BAR_BG_COLOR};overflow:hidden;position:relative;"><div style="position:absolute;left:0;top:0;bottom:0;width:{neg_pct};background:{SUBJECTIVE_NEG_BAR_COLOR};"></div></div>'
			f'<div style="color:#111827;font-size:10px;white-space:nowrap;">부정 {neg_pct}</div>'
			'</div>'
			# 중립
			f'<div style="display:flex;align-items:center;gap:6px;">'
			f'<div style="width:120px;height:{SUBJECTIVE_BAR_HEIGHT_PX}px;background:{SUBJECTIVE_BAR_BG_COLOR};overflow:hidden;position:relative;"><div style="position:absolute;left:0;top:0;bottom:0;width:{neu_pct};background:{SUBJECTIVE_NEU_BAR_COLOR};"></div></div>'
			f'<div style="color:#111827;font-size:10px;white-space:nowrap;">중립 {neu_pct}</div>'
			'</div>'
			'</td>'
		)
		# 주요 키워드 영역: 2열(좌 라벨, 우 리스트)
		pos_list_html = ("<ul style='margin:0;padding-left:16px;'>" + "".join(f"<li>{html_escape(x)}</li>" for x in pos_summary_list) + "</ul>") if pos_summary_list else "-"
		neg_list_html = ("<ul style='margin:0;padding-left:16px;'>" + "".join(f"<li>{html_escape(x)}</li>" for x in neg_summary_list) + "</ul>") if neg_summary_list else "-"
		neu_list_html = ("<ul style='margin:0;padding-left:16px;'>" + "".join(f"<li>{html_escape(x)}</li>" for x in neu_summary_list) + "</ul>") if neu_summary_list else "-"
		# 블록별 조건부 표시 (해당 감정 건수가 0이면 블록 생략)
		kw_blocks: List[str] = []
		if pos_cnt > 0 and pos_summary_list:
			kw_blocks.append(f'<div style="margin:0;background:rgba(66,98,255,0.04);padding:6px;"><table role="presentation" cellpadding="0" cellspacing="0" border="0" style="width:100%;table-layout:fixed;"><colgroup><col style="width:60px;"><col></colgroup><tr><td style="padding:0;color:{SUBJECTIVE_POS_BAR_COLOR};font-weight:400;font-size:12px;white-space:nowrap;vertical-align:middle;text-align:center;">긍정 ({pos_cnt})</td><td style="padding:0;color:#111827;font-size:12px;vertical-align:middle;">{pos_list_html}</td></tr></table></div>')
		if neg_cnt > 0 and neg_summary_list:
			kw_blocks.append(f'<div style="margin:0;background:rgba(226,58,50,0.04);padding:6px;"><table role="presentation" cellpadding="0" cellspacing="0" border="0" style="width:100%;table-layout:fixed;"><colgroup><col style="width:60px;"><col></colgroup><tr><td style="padding:0;color:{SUBJECTIVE_NEG_BAR_COLOR};font-weight:400;font-size:12px;white-space:nowrap;vertical-align:middle;text-align:center;">부정 ({neg_cnt})</td><td style="padding:0;color:#111827;font-size:12px;vertical-align:middle;">{neg_list_html}</td></tr></table></div>')
		if neu_cnt > 0 and neu_summary_list:
			kw_blocks.append(f'<div style="margin:0;background:rgba(0,0,0,0.04);padding:6px;"><table role="presentation" cellpadding="0" cellspacing="0" border="0" style="width:100%;table-layout:fixed;"><colgroup><col style="width:60px;"><col></colgroup><tr><td style="padding:0;color:{SUBJECTIVE_NEU_BAR_COLOR};font-weight:400;font-size:12px;white-space:nowrap;vertical-align:middle;text-align:center;">중립 ({neu_cnt})</td><td style="padding:0;color:#111827;font-size:12px;vertical-align:middle;">{neu_list_html}</td></tr></table></div>')
		cell_kw = (
			'<td style="border:1px solid #E5E7EB;padding:0;vertical-align:top;font-size:11px;line-height:1.3;">'
			+ ''.join(kw_blocks) +
			'</td>'
		)
		html_parts.append('<tr>' + cell_idx + cell_cat + cell_sent + cell_kw + '</tr>')
	html_parts.append('</tbody></table>')
	html_parts.append('</div>')
	return ''.join(html_parts)


def build_general_heatmap(question_rows: List[Dict[str, str]], label_order: List[str], question_title: str = "객관식 문항", all_data: List[Dict[str, str]] = None, question_id: str = None) -> str:
	"""객관식(일반) 문항용 히트맵: 행=세그 버킷, 열=라벨.
	- 만족도 전용 요약/순만족도 없이, 퍼센트 셀만 표시
	- 스타일은 만족도 히트맵과 톤앤매너 일치
	"""
	# 만족도 패턴 정렬 유지
	if is_evaluation_pattern(label_order):
		satisfaction_order = ["매우 불만족해요", "불만족해요", "보통이에요", "만족해요", "매우 만족해요"]
		order: List[str] = [l for l in satisfaction_order if l in label_order]
		order.extend(sorted([l for l in label_order if l not in order]))
	else:
		order = list(label_order)
	return build_heatmap_component(
		question_rows,
		order,
		kind='general',
		include_cross_analysis=True,
		include_other_summary=True,
		question_title=question_title,
		all_data=all_data,
		question_id=question_id,
		remark_base_items=[DEFAULT_HEATMAP_REMARK_BASE],
	)

if __name__ == "__main__":
	sys.exit(main())