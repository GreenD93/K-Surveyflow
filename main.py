import os
from typing import Optional
import pandas as pd

import argparse

from src.constants import *
from src.report_generator import *
from src.utils import save_report


def main():

	parser = argparse.ArgumentParser()
	parser.add_argument("--csv_file", default="data/20250916_sample_data.csv")
	args = parser.parse_args()

	csv_path: Optional[str] = args.csv_file

	#TODO: 설문조사 메일링 요청 데이터를 바탕으로 survey_ids + 수신인 파악

	if not csv_path or not os.path.exists(csv_path):
		print("[ERROR] CSV 파일을 찾을 수 없습니다.")
		return 1
	
	df = pd.read_csv(csv_path,
					 dtype={
						"qsit_type_ds_cd":str,
						"text_yn":str,
						"surv_date":str,
						"keywords":str
					 }).fillna("")

	surv_ids = df['surv_id'].unique().tolist()

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

		#TODO: mail 발송
	
	return 0


if __name__ == "__main__":
	# CLI usage: python main.py --csv_file data/20250916_sample_data.csv
	main()

	

	