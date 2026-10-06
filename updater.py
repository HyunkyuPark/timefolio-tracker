import json
import os
import time
import requests
from datetime import datetime, timezone, timedelta

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
KST = timezone(timedelta(hours=9))

# 감시할 타임폴리오 14종 액티브 ETF 전 라인업
ETF_REGISTRY = {
    "385550": {"name": "TIME 코스피플러스액티브", "is_broad": True},
    "400580": {"name": "TIME 코스피액티브", "is_broad": True},
    "400570": {"name": "TIME 코스닥액티브", "is_broad": True},
    "495060": {"name": "TIME 코리아밸류업액티브", "is_broad": True},
    "404120": {"name": "TIME K신재생에너지액티브", "is_broad": False},
    "449180": {"name": "TIME K바이오액티브", "is_broad": False},
    "449190": {"name": "TIME K-이노베이션액티브", "is_broad": False},
    "432320": {"name": "TIME K컬처액티브", "is_broad": False},
    "475380": {"name": "TIME 글로벌소부장액티브", "is_broad": False},
    "433540": {"name": "TIME 미국나스닥100액티브", "is_broad": True},
    "449170": {"name": "TIME 미국S&P500액티브", "is_broad": True},
    "465600": {"name": "TIME 글로벌AI인공지능액티브", "is_broad": False},
    "478150": {"name": "TIME 글로벌우주테크&방산액티브", "is_broad": False},
    "494180": {"name": "TIME 글로벌소비트렌드액티브", "is_broad": False}
}

SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Referer": "https://finance.naver.com/"
})

def fetch_live_etf_holdings(code):
    """
    네이버 증권 연동 와이즈리포트에서 ETF 실제 PDF(납입자산구성내역) 100% 실시간 크롤링
    """
    items = {}
    url = f"https://navercomp.wisereport.co.kr/v2/ETF/index.aspx?cmp_cd={code}"
    
    try:
        res = SESSION.get(url, timeout=7)
        if res.status_code == 200:
            text = res.text
            idx = text.find('"grid_data"')
            if idx == -1:
                idx = text.find('grid_data')

            if idx != -1:
                b_start = text.find('[', idx)
                b_end = text.find(']', b_start)
                if b_start != -1 and b_end != -1:
                    raw_list = json.loads(text[b_start : b_end + 1])
                    for row in raw_list:
                        nm = str(row.get("STK_NM_KOR") or row.get("JONG_NM") or row.get("ITEM_NAME") or "").strip()
                        nm = nm.replace('"', '').replace("'", "")
                        ticker = str(row.get("CMP_CD") or row.get("ITEM_CD") or "000000").strip()

                        # 현금성 자산 제외
                        if not nm or "원화" in nm or "예금" in nm or "현금" in nm or "단기" in nm:
                            continue

                        try:
                            wt = float(str(row.get("ETF_WEIGHT", 0) or row.get("WEIGHT", 0)).replace("%", "").replace(",", ""))
                        except Exception:
                            wt = 0.0

                        try:
                            sh = float(str(row.get("AGMT_STK_CNT", 0) or row.get("HOLD_QTY", 0)).replace(",", ""))
                        except Exception:
                            sh = 0.0

                        if wt > 0.05 or sh > 0:
                            items[nm] = {
                                "name": nm,
                                "ticker": ticker,
                                "weight": wt,
                                "shares": sh
                            }
    except Exception as e:
        print(f"[{code}] 실시간 크롤링 에러: {e}")

    return items

def main():
    now_kst = datetime.now(KST)
    now_time_str = now_kst.strftime("%Y-%m-%d %H:%M 기준")
    today_str = now_kst.strftime("%Y-%m-%d")
    print(f"[{now_time_str}] 타임폴리오 14종 ETF 실시간 장부 추출 가동...")

    # 과거 장부 히스토리 로드
    history_file = "history.json"
    history = {}
    if os.path.exists(history_file):
        try:
            with open(history_file, "r", encoding="utf-8") as f:
                history = json.load(f)
        except Exception:
            history = {}

    past_dates = sorted([d for d in history.keys() if d < today_str], reverse=True)
    past_snapshot = history.get(past_dates[0], {}) if past_dates else {}

    # 실시간 장부 수집
    current_snapshot = {}
    success_count = 0

    for code, meta in ETF_REGISTRY.items():
        live_items = fetch_live_etf_holdings(code)
        if live_items:
            success_count += 1
            print(f"✅ [{meta['name']}] 실시간 종목 {len(live_items)}개 수집 성공")
            current_snapshot[code] = {
                "name": meta["name"],
                "items": live_items
            }
        else:
            print(f"⚠️ [{meta['name']}] 응답 대기/빈값")
        time.sleep(0.3)

    print(f"📊 최종 수집 결과: 14개 중 {success_count}개 ETF 실시간 장부 확보!")

    if success_count == 0:
        print("❌ 실시간 수집 실패로 인해 기존 데이터를 유지하고 종료합니다.")
        return

    # 신규 편입 및 복수 보유 분석 계산
    new_entries_map = {}
    core_holdings_map = {}

    for code, data in current_snapshot.items():
        etf_name = data["name"]
        short_name = etf_name.replace("TIME ", "")
        today_items = data["items"]
        yesterday_items = past_snapshot.get(code, {}).get("items", {})

        for s_name, item in today_items.items():
            wt = item["weight"]
            ticker = item.get("ticker", "000000")

            # 1. 신규 편입 계산 (어제 장부에 없다가 오늘 최초로 등장한 종목)
            if past_snapshot and (s_name not in yesterday_items):
                if s_name not in new_entries_map:
                    new_entries_map[s_name] = {
                        "name": s_name,
                        "ticker": ticker,
                        "etf_entries": [],
                        "reason": f"어제 장부 미편입 상태에서 오늘 {short_name}에 최초 신규 매수 포착."
                    }
                new_entries_map[s_name]["etf_entries"].append({
                    "etf_name": short_name,
                    "weight": f"{wt:.1f}%"
                })

            # 2. 복수 보유 (코어) 계산
            if s_name not in core_holdings_map:
                core_holdings_map[s_name] = {
                    "name": s_name,
                    "ticker": ticker,
                    "etfs": [],
                    "total_weight": 0.0,
                    "reason": f"타임폴리오 {short_name} 편입 종목."
                }
            core_holdings_map[s_name]["etfs"].append(f"{short_name} {wt:.1f}%")
            core_holdings_map[s_name]["total_weight"] += wt

    # 신규 편입 종목 정렬
    sorted_new_entries = sorted(
        list(new_entries_map.values()),
        key=lambda x: (len(x["etf_entries"]), x["name"]),
        reverse=True
    )

    # 코어 보유 종목 정렬 (편입된 ETF 개수 많은 순 -> 비중 순)
    sorted_core_holdings = sorted(
        list(core_holdings_map.values()),
        key=lambda x: (len(x["etfs"]), x["total_weight"]),
        reverse=True
    )

    output = {
        "last_updated": now_time_str,
        "total_etfs_tracked": success_count,
        "new_entries": sorted_new_entries,    # 실시간 신규 편입 종목
        "core_holdings": sorted_core_holdings # 실시간 복수 편입 종목
    }

    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    history[today_str] = current_snapshot
    with open(history_file, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False)

    print(f"🎉 성공! 실시간 신규 편입 {len(sorted_new_entries)}개, 보유 종목 {len(sorted_core_holdings)}개가 저장되었습니다.")

if __name__ == "__main__":
    main()
