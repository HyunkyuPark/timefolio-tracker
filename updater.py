import json
import os
import time
import requests
from datetime import datetime, timezone, timedelta

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
KST = timezone(timedelta(hours=9))

ETF_REGISTRY = {
    "385550": "TIME 코스피플러스액티브",
    "400580": "TIME 코스피액티브",
    "400570": "TIME 코스닥액티브",
    "495060": "TIME 코리아밸류업액티브",
    "404120": "TIME K신재생에너지액티브",
    "449180": "TIME K바이오액티브",
    "449190": "TIME K-이노베이션액티브",
    "432320": "TIME K컬처액티브",
    "475380": "TIME 글로벌소부장액티브",
    "433540": "TIME 미국나스닥100액티브",
    "449170": "TIME 미국S&P500액티브",
    "465600": "TIME 글로벌AI인공지능액티브",
    "478150": "TIME 글로벌우주테크&방산액티브",
    "494180": "TIME 글로벌소비트렌드액티브"
}

SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4.1 Mobile/15E148 Safari/604.1",
    "Referer": "https://m.stock.naver.com/",
    "Accept": "application/json, text/plain, */*"
})

def fetch_live_holdings(code):
    url = f"https://m.stock.naver.com/front-api/v1/etf/portfolio?itemCode={code}"
    items = {}
    try:
        res = SESSION.get(url, timeout=6)
        if res.status_code == 200:
            data = res.json().get("result", {}).get("portfolio", [])
            for r in data:
                nm = (r.get("itemName") or r.get("stockName") or "").strip()
                if not nm or "원화" in nm or "현금" in nm or "예금" in nm:
                    continue
                try:
                    wt = float(str(r.get("weight", 0)).replace("%", "").replace(",", ""))
                except Exception:
                    wt = 0.0
                try:
                    sh = float(str(r.get("share", 0) or r.get("quantity", 0)).replace(",", ""))
                except Exception:
                    sh = 0.0
                ticker = str(r.get("itemCode") or r.get("cmp_cd") or "000000").strip()

                if wt > 0.05 or sh > 0:
                    items[nm] = {
                        "name": nm,
                        "ticker": ticker,
                        "weight": wt,
                        "shares": sh
                    }
    except Exception as e:
        print(f"[{code}] 조회 실패: {e}")
    return items

def main():
    now_kst = datetime.now(KST)
    now_time_str = now_kst.strftime("%Y-%m-%d %H:%M 기준")
    today_str = now_kst.strftime("%Y-%m-%d")
    print(f"[{now_time_str}] 타임폴리오 14종 순수 실시간 크롤링 시작...")

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

    current_snapshot = {}
    success_count = 0

    for code, full_name in ETF_REGISTRY.items():
        items = fetch_live_holdings(code)
        if items:
            success_count += 1
            print(f"✅ [{full_name}] 실시간 {len(items)}개 종목 수집")
            current_snapshot[code] = {
                "name": full_name,
                "items": items
            }
        time.sleep(0.3)

    print(f"총 {success_count}개 ETF 실시간 데이터 수집 완료")

    if success_count == 0:
        print("❌ 수집 실패. 기존 데이터를 덮어쓰지 않습니다.")
        return

    new_entries_map = {}
    core_holdings_map = {}

    for code, data in current_snapshot.items():
        etf_name = data["name"]
        short_name = etf_name.replace("TIME ", "")
        today_items = data["items"]
        yesterday_items = past_snapshot.get(code, {}).get("items", {})

        for s_name, item in today_items.items():
            wt = item["weight"]
            ticker = item["ticker"]

            # 어제 장부 히스토리가 있을 때만 신규 편입 판정
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

            # 전체/복수 보유 집계
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

    sorted_new_entries = sorted(
        list(new_entries_map.values()),
        key=lambda x: (len(x["etf_entries"]), x["name"]),
        reverse=True
    )

    sorted_core_holdings = sorted(
        list(core_holdings_map.values()),
        key=lambda x: (len(x["etfs"]), x["total_weight"]),
        reverse=True
    )

    output = {
        "last_updated": now_time_str,
        "total_etfs_tracked": success_count,
        "new_entries": sorted_new_entries,
        "core_holdings": sorted_core_holdings
    }

    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    history[today_str] = current_snapshot
    with open(history_file, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False)

    print(f"data.json 저장 완료 (신규편입: {len(sorted_new_entries)}개, 보유: {len(sorted_core_holdings)}개)")

if __name__ == "__main__":
    main()
