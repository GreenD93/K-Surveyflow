import os
import pytz
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

##########################################
# time utilities

TIME_ZONE = None
TIME_FORMAT = "%Y-%m-%d %H:%M:%S"

def _get_timezone():
    global TIME_ZONE
    if TIME_ZONE is None:
        TIME_ZONE = pytz.timezone('Asia/Seoul')
    return TIME_ZONE

def get_current_time_string(format_string=TIME_FORMAT):
    return datetime.now(_get_timezone()).strftime(format_string)

# 입력 문자열(YYYY-MM-DD 또는 YYYY-MM-DD HH:MM:SS)을 서울 시간대로 파싱
def _parse_input_datetime(dt_str: str) -> datetime:
    tz = _get_timezone()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            naive = datetime.strptime(dt_str, fmt)
            return tz.localize(naive)
        except ValueError:
            continue
    raise ValueError("지원하지 않는 날짜 형식입니다. 예) '2025-10-31' 또는 '2025-10-31 23:59:59'")
##########################################