import os
import pytz
from datetime import datetime, date, timedelta

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
    """설문 보고서를 HTML 파일로 저장하고 경로를 반환.

    파일명 형식: `survey_report_{SURV_ID}_{TITLE}_{YYYYMMDD}.html`
    - SURV_ID: 설문 ID
    - TITLE: 메인 제목
    - 저장 위치: `out_dir` (기본값은 현재 파일 하위 `reports`)
    """
    os.makedirs(out_dir, exist_ok=True)
    date_str = datetime.now().strftime("%Y%m%d")
    
    # 새로운 파일명 형식: survey_report_(SURV_ID)_(TITLE)_(YYYYMMDD).html
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

##########################################
# sending-cycle utilities

WEEKDAY_MAP = {"MON":0, "TUE":1, "WED":2, "THU":3, "FRI":4, "SAT":5, "SUN":6}

def _parse_to_date(value) -> date | None:
    """
    다양한 입력(YYYY-MM-DD, YYYY-MM-DD HH:MM:SS, datetime/str/None/'-')을 date로 변환.
    실패/공백은 None.
    """
    if value in (None, "-", ""):
        return None
    if isinstance(value, datetime):
        # 이미 타임존이 있든 없든 date만 추출
        return value.date()
    s = str(value).strip()
    if not s:
        return None
    # 공백 또는 'T' 이전까지만 취급해서 date 파싱
    s = s.split("T")[0].split()[0]
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except ValueError:
        return None

def _today_kst_date() -> date:
    return datetime.now(_get_timezone()).date()

def _next_on_or_after(d: date, target_wd: int) -> date:
    """d로부터 target_wd(0=월 ... 6=일)가 되는 '같은 날 또는 이후' 날짜"""
    return d + timedelta(days=(target_wd - d.weekday()) % 7)

def should_send(item: dict, today: date | None = None) -> bool:
    """
    오늘(KST) 발송해야 하는지 True/False 반환.

    규칙:
      - DAILY: 요일/날짜 코드 무시, 기간만 맞으면 True
      - WEEKLY/BIWEEKLY: DTWK_CD 요일 필수 + LAST_CHNG_DTTM을 앵커로 사용
      - MONTHLY: DAY_CD(1~31)와 오늘 날짜가 동일해야 함
      - 공통: SNDG_YN='Y', SNDG_START_DT~SNDG_END_DT(포함, inclusive) 범위 내여야 함
    지원 키:
      - 주기코드: SNDG_CYCL_CD (또는 오타 대비 SNDG_CTCL_CD)
      - 요일코드: DTWK_CD (예: 'MON' 또는 'MON,WED')
      - 날짜코드: DAY_CD (예: '15')
    """
    if today is None:
        today = _today_kst_date()

    # 1) 발송 on/off
    if (item.get("SNDG_YN", "N") or "N").strip().upper() != "Y":
        return False

    # 2) 기간 체크 (inclusive)
    start_dt = _parse_to_date(item.get("SNDG_START_DT"))
    end_dt   = _parse_to_date(item.get("SNDG_END_DT"))
    if (start_dt and today < start_dt) or (end_dt and today > end_dt):
        return False

    # 3) 주기 코드
    cycle = (item.get("SNDG_CTCL_CD") or "").strip().upper()
    if not cycle:
        return False

    # 4) DAILY: 기간만 맞으면 OK
    if cycle == "DAILY":
        return True

    # 5) WEEKLY/BIWEEKLY: 요일 + 앵커(LAST_CHNG_DTTM)
    if cycle in ("WEEKLY", "BIWEEKLY"):
        raw = (item.get("DTWK_CD") or "").strip()
        # 'MON,WED' 형태 지원, '-' 무시
        codes = [c.strip().upper() for c in raw.split(",") if c.strip() and c.strip() != "-"]
        weekdays = [WEEKDAY_MAP[c] for c in codes if c in WEEKDAY_MAP]
        if not weekdays or today.weekday() not in weekdays:
            return False

        last_chg = _parse_to_date(item.get("LAST_CHNG_DTTM"))
        if not last_chg:
            return False  # 앵커 필수

        anchor = _next_on_or_after(last_chg, today.weekday())
        if today < anchor:
            return False

        if cycle == "WEEKLY":
            return True
        # BIWEEKLY: 앵커로부터 14일 간격
        return ((today - anchor).days % 14) == 0

    # 6) MONTHLY: DAY_CD와 오늘 날짜 비교
    if cycle == "MONTHLY":
        raw_day = (item.get("DAY_CD") or "").strip()
        if not raw_day or raw_day == "-":
            return False
        try:
            day_cd = int(raw_day)
        except ValueError:
            return False
        return today.day == day_cd

    # 알 수 없는 주기 코드
    return False

# 별칭(원하시면 기존 이름과 호환)
def should_send_today(item: dict, today: date | None = None) -> bool:
    return should_send(item, today=today)