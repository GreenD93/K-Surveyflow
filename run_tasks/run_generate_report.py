import os
from typing import Optional
import pandas as pd

import argparse

from src.constants import *
from src.report_generator import *
from src.utils import save_report

def main(argv: Optional[List[str]] = None) -> int:

	parser = argparse.ArgumentParser(
		description="CSV 기반 HTML 보고서 생성기",
		formatter_class=argparse.ArgumentDefaultsHelpFormatter
	)
	parser.add_argument(
		"--csv",
		dest="csv_path",
		type=str,
		default="data/20251023_sample_data.csv",
		help="CSV 파일 경로 (지정하지 않으면 data 폴더 내 최신 CSV 사용)"
	)
	parser.add_argument(
		"--normalize-stats-weights",
		dest="normalize",
		choices=["on", "off"],
		default="off",
		help="응답자 단위 정규화 설정 (on/off)"
	)

	args = parser.parse_args(argv)

	# 전역 설정 적용
	global RANKING_NORMALIZE_PER_RESPONDENT
	RANKING_NORMALIZE_PER_RESPONDENT = (args.normalize.lower() == "on")

	csv_path: Optional[str] = args.csv_path
	
	if not csv_path or not os.path.exists(csv_path):
		print("[ERROR] CSV 파일을 찾을 수 없습니다.")
		return 1
	
	enc = detect_encoding(csv_path)
	df = pd.read_csv(csv_path, 
					dtype={
						"surv_id": str,
						"qsit_type_ds_cd":str,
						"text_yn":str,
						"surv_date":str,
						"keywords":str
					},
					encoding=enc)
	
	df["main_ttl"] = df["main_ttl"].fillna("기본").astype(str).str.strip()

	# 문자열 컬럼 좌우 공백 제거
	df = df.applymap(lambda x: x.strip() if isinstance(x, str) else x)
	df = df.fillna("")
	
	# main_ttl별 그룹화
	grouped = df.groupby("surv_id")
	generated_reports = []

	for idx, (surv_id, group_df) in enumerate(grouped, 1):

		main_ttl = group_df['main_ttl'].iloc[0]
		print(f"[INFO] '{surv_id}' 보고서 생성 중... (데이터 {len(group_df)}건)")

		# DataFrame을 그대로 HTML 변환하거나 기존 함수 활용
		html = generate_html(group_df.to_dict(orient="records"))
		out_path = save_report(surv_id, main_ttl, html, out_dir=os.path.join(os.path.dirname(__file__), "reports"))
		generated_reports.append(out_path)


	print(f"[COMPLETE] 총 {len(generated_reports)}개 보고서 생성 완료")
	print(f"[INFO] normalize-stats-weights={'on' if RANKING_NORMALIZE_PER_RESPONDENT else 'off'}")
	for report_path in generated_reports:
		print(f"  - {report_path}")

# export PYTHONPATH="$PWD/src:$PYTHONPATH		
if __name__ == "__main__":
	# CLI usage: python main.py --csv_file data/20250916_sample_data.csv --survey_info_file data/isb_surv_rpt_info.csv
	main()