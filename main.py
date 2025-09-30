import os
from typing import Optional
import pandas as pd

import argparse

from src.load_data import load_data
from src.constants import *
from src.report_generator import *
from src.utils import save_report


# TODO: print -> logging 모듈로 교체

def main():

	parser = argparse.ArgumentParser()
	parser.add_argument("--survey_info_file", default="data/isb_surv_rpt_info.csv")
	parser.add_argument("--raw_data_file", default="data/20250916_raw_data.csv")
	parser.add_argument("--csv_file", default="data/20250916_sample_data.csv")
	args = parser.parse_args()

	survey_info_path: Optional[str] = args.survey_info_file
	raw_data_file: Optional[str] = args.raw_data_file
	csv_path: Optional[str] = args.csv_file

	if not survey_info_path or not os.path.exists(survey_info_path):
		print("[ERROR] SURVEY_INFO 파일을 찾을 수 없습니다.")
		return 1
	
	if not raw_data_file or not os.path.exists(raw_data_file):
		print("[ERROR] raw_data_file 파일을 찾을 수 없습니다.")
		return 1
	
	if not csv_path or not os.path.exists(csv_path):
		print("[ERROR] CSV 파일을 찾을 수 없습니다.")
		return 1
	
	# step1: 통합관리자에 등록된 설문 발송 메일링 정보들 가져오기
	survey_info_df = load_data(survey_info_path)

	# survey_info_df.iloc[0]
	# SURV_ID                                                 202407006
	# EMPNO                                        [20160793, 20161111]
	# EMAIL                [yonggeol93@gmail.com, yonggeol93@naver.com]
	# SNDG_YN                                                         Y
	# SNDG_START_DT                                          2025-09-26
	# SNDG_END_DT                                            2025-10-31
	# SNDG_CTCL_CD                                                DAILY
	# DTWK_CD                                                         -
	# DAY_CD                                                          -
	# DATA_RNG_CD                                                     7
	# FRST_RGST_USER_ID                                        20160793
	# FRST_RGST_DTTM                                         2025-09-26
	# LAST_CHNG_USER_ID                                        20160793
	# LAST_CHNG_DTTM                                         2025-09-26	

	# step2: 해당 설문에 해당하는 원본 데이터 SURV_ID를 키로해서 가져오기
	# TODO: step1에서 불러온 survey list에 해당하는 설문을 Athena 쿼리로 불러와서 데이터 맵핑하는 방향으로 변경해야 함.
	raw_df = pd.read_csv(raw_data_file,
					 dtype={
						"surv_id": str,
						"qsit_type_ds_cd":str,
						"text_yn":str,
						"surv_date":str
					 }).fillna("")

	# step3: 설문 분석(langgraph)을 통해 "llm_level1", "llm_level2", "sentiment" 3개 컬럼 생성
	#        + 주관식 문항 분석 섹션을 위한 summary도 진행
	
	df = pd.read_csv(csv_path,
					 dtype={
						"surv_id": str,
						"qsit_type_ds_cd":str,
						"text_yn":str,
						"surv_date":str,
						"keywords":str
					 }).fillna("")
	
	surv_ids = survey_info_df['SURV_ID'].unique().tolist()

	for idx, surv_id in enumerate(surv_ids):

		surv_df = df[df['surv_id'] == surv_id]
		main_ttl = surv_df['main_ttl'].iloc[0]
		rows = surv_df.to_dict(orient="records")

		if not rows:
			print(f"[ERROR] {main_ttl} 데이터가 없습니다.")
			continue

		print(f"[INFO] {idx+1} of {len(surv_ids)}보고서 생성 중...")
		print(f"[INFO] {surv_id} - '{main_ttl}' - (데이터 {len(rows)}건) ")

		html = generate_html(rows)
		out_path = save_report(surv_id, main_ttl, html, out_dir=os.path.join(os.path.dirname(__file__), "reports"))
		print(f"[OK] '{main_ttl}' 보고서 생성 완료: {out_path}")
		print(f"  - {out_path}")

		# step4: 메일 발송
		# TODO: mail 발송

	print(f"All processes succeeded.")

	return 0


if __name__ == "__main__":
	# CLI usage: python main.py --csv_file data/20250916_sample_data.csv
	main()

	

	