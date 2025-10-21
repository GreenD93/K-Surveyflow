from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo
from typing import Optional

import pandas as pd
import argparse

WEEKDAY_MAP = {"MON":0, "TUE":1, "WED":2, "THU":3, "FRI":4, "SAT":5, "SUN":6}

def load_data(data_path):

    # "data/isb_surv_rpt_info.csv"
    df = pd.read_csv(data_path)
    df = df.astype(str)

    grouped = df.groupby("SURV_ID").agg({
        'EMPNO': lambda x: list(x),
        'EMAIL': lambda x: list(x),
        'SNDG_YN': 'first',
        'SNDG_START_DT': 'first',
        'SNDG_END_DT': 'first',
        'SNDG_CTCL_CD': 'first',
        'DTWK_CD': 'first',
        'DAY_CD': 'first',
        'DATA_RNG_CD': 'first',
        'FRST_RGST_USER_ID': 'first',
        'FRST_RGST_DTTM': 'first',
        'LAST_CHNG_USER_ID': 'first',
        'LAST_CHNG_DTTM': 'first'
    }).reset_index()

    return grouped

def _parse_date(d):
    if not d or d == "-" or d is None:
        return None
    d = str(d).strip().split("T")[0].split()[0]
    return date.fromisoformat(d)

def _today_kst():
    return datetime.now(ZoneInfo("Asia/Seoul")).date()

def _next_on_or_after(d, target_wd):
    return d + timedelta(days=(target_wd - d.weekday()) % 7)

def should_send(item, today=None):
    """오늘(KST) 발송해야 하면 True, 아니면 False"""
    today = _today_kst() if today is None else today

    # 1) 기본 필터
    if (item.get("SNDG_YN", "N") or "N").upper() != "Y":
        return False
    start_dt = _parse_date(item.get("SNDG_START_DT"))
    end_dt   = _parse_date(item.get("SNDG_END_DT"))
    if (start_dt and today < start_dt) or (end_dt and today > end_dt):
        return False

    # 2) 주기 코드
    cycle = (item.get("SNDG_CYCL_CD") or item.get("SNDG_CTCL_CD") or "").strip().upper()
    if not cycle:
        return False

    # 3) DAILY: 기간만 맞으면 OK
    if cycle == "DAILY":
        return True

    # 4) WEEKLY/BIWEEKLY: 요일 + 앵커
    if cycle in ("WEEKLY", "BIWEEKLY"):
        raw = (item.get("DTWK_CD") or "").strip()
        weekdays = [WEEKDAY_MAP[c] for c in (w.strip().upper() for w in raw.split(",")) if c and c in WEEKDAY_MAP]
        if not weekdays or today.weekday() not in weekdays:
            return False

        last_chg = _parse_date(item.get("LAST_CHNG_DTTM"))
        if not last_chg:
            return False  # 앵커 필수

        anchor = _next_on_or_after(last_chg, today.weekday())
        if today < anchor:
            return False
        if cycle == "WEEKLY":
            return True
        return ((today - anchor).days % 14) == 0  # BIWEEKLY

    # 5) MONTHLY: 날짜코드 일치
    if cycle == "MONTHLY":
        raw_day = (item.get("DAY_CD") or "").strip()
        try:
            day_cd = int(raw_day)
        except:
            return False
        return today.day == day_cd

    return False

if __name__ == "__main__":

    parser = argparse.ArgumentParser()
    parser.add_argument("--csv_file", default="data/isb_surv_rpt_info.csv")
    args = parser.parse_args()

    csv_path: Optional[str] = args.csv_file
    survey_info_df = load_data(csv_path)

    items = survey_info_df.to_dict("records")

    for item in items:

        result = should_send(item)
        
        print(item)
        print(result)

    # item = {
    #     'SURV_ID': '202407006',
    #     'EMPNO': ['20160793', '20161111'],
    #     'EMAIL': ['yonggeol93@gmail.com', 'yonggeol93@naver.com'],
    #     'SNDG_YN': 'Y',
    #     'SNDG_START_DT': '2025-09-26',
    #     'SNDG_END_DT': '2025-10-13',
    #     'SNDG_CTCL_CD': 'WEEKLY',   # 오타/변형 키도 지원
    #     'DTWK_CD': 'WED',            # WEEKLY/BIWEEKLY 때 'MON' 또는 'MON,WED' 형태
    #     'DAY_CD': '-',             # MONTHLY 때 '15' 같은 숫자
    #     'DATA_RNG_CD': '7',
    #     'FRST_RGST_USER_ID': '20160793',
    #     'FRST_RGST_DTTM': '2025-09-26',
    #     'LAST_CHNG_USER_ID': '20160793',
    #     'LAST_CHNG_DTTM': '2025-09-26'
    # }

    # result = should_send(item)
    # print(result)