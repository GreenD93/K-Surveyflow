import os
from datetime import datetime

def html_escape(s: str) -> str:
	return (
		s.replace("&", "&amp;")
		.replace("<", "&lt;")
		.replace(">", "&gt;")
		.replace('"', "&quot;")
		.replace("'", "&#39;")
		.replace("\n", "<br>")
	)

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

def save_report(surv_id: str, main_ttl: str, html: str, out_dir: str = os.path.join(os.path.dirname(__file__), "reports")) -> str:

	os.makedirs(out_dir, exist_ok=True)
	date_str = datetime.now().strftime("%Y%m%d")
	
	# 새로운 파일명 형식: survey_report_(N)of(M)_(YYYYMMDD).html
	filename = f"survey_report_{surv_id}_{main_ttl}_{date_str}.html"
	
	path = os.path.join(out_dir, filename)
	with open(path, "w", encoding="utf-8") as f:
		f.write(html)
	return path