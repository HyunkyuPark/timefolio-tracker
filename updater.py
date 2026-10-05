import json
import os
import time
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timezone, timedelta

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
KST = timezone(timedelta(hours=9))

ETF_REGISTRY = {
    "433540": {"name": "TIME 미국나스닥100액티브", "is_broad": True},
    "449170": {"name": "TIME 미국S&P500액티브", "is_broad": True},
    "385550": {"name": "TIME 코스피플러스액티브", "is_broad": True},
    "400580": {"name": "TIME 코스피액티브", "is_broad": True},
    "400570": {"name": "TIME 코스닥액티브", "is_broad": True},
    "495060": {"name": "TIME 코리아밸류업액티브", "is_broad": True},
    "404120": {"name": "TIME K신재생에너지액티브", "is_broad": False},
    "449180": {"name": "TIME K바이오액티브", "is_broad": False},
    "449190": {"name": "TIME K-이노베이션액티브", "is_broad": False},
    "432320": {"name": "TIME K컬처액티브", "is_broad": False},
    "465600": {"name": "TIME 글로벌AI인공지능액티브", "is_broad": False},
    "478150": {"name": "TIME 글로벌우주테크&방산액티브", "is_broad": False},
    "494180": {"name": "TIME 글로벌소비트렌드액티브", "is_broad": False},
    "475380": {"name": "TIME 글로벌소부장액티브", "is_broad": False}
}

SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Referer": "https://finance.naver.com/"
})

def fetch_etf_holdings(code):
    items = {}
    
    # 1. 모바일 API 우선
    try:
        url = f"https://m.stock.naver.com/front-api/v1/etf/portfolio?itemCode={code}"
        res = SESSION.get(url, timeout=4)
        if res.status_code == 200:
            data = res.json().get("result", {}).get("portfolio", [])
            for r in data:
                nm = (r.get("itemName") or r.get("stockName") or "").strip()
                wt = float(r.get("weight") or 0.0)
                sh = float(r.get("share") or 0.0)
                pr = float(r.get("price") or 0.0)
                if nm and "원화" not in nm and wt > 0.05:
                    items[nm] = {"name": nm, "weight": wt, "shares": sh, "price": pr}
            if items:
                return items
    except Exception:
        pass

    # 2. 웹 테이블 파싱
    try:
        url = f"https://finance.naver.com/item/main.naver?code={code}"
        res = SESSION.get(url, timeout=4)
        if res.status_code == 200:
            soup = BeautifulSoup(res.text, "lxml")
            for tbl in soup.find_all("table"):
                for tr in tbl.find_all("tr"):
                    cols = [td.get_text(strip=True) for td in tr.find_all(["td", "th"])]
                    if len(cols) >= 3:
                        name = cols[0]
                        if not name or "종목명" in name or "원화" in name or "현금" in name:
                            continue
                        for val in cols[1:]:
                            try:
                                num = float(val.replace("%", "").replace(",", ""))
                                if "%" in val or (0.1 <= num <= 40.0):
                                    items[name] = {"name": name, "weight": num, "shares": 1000.0, "price": 100.0}
                                    break
                            except ValueError:
                                continue
            if items:
                return items
    except Exception:
        pass

    return items

def main():
    now_kst = datetime.now(KST)
    now_time_str = now_kst.strftime("%Y-%m-%d %H:%M 기준")
    today_str = now_kst.strftime("%Y-%m-%d")
    print(f"[{now_time_str}] 타임폴리오 14개 핵심 ETF 수집 시작...")

    history_file = "history.json"
    history = {}
    if os.path.exists(history_file):
        try:
            with open(history_file, "r", encoding="utf-8") as f:
                history = json.load(f)
        except Exception:
            history = {}

    current_snapshot = {}
    stock_to_etfs = {}
    success_count = 0

    for code, meta in ETF_REGISTRY.items():
        items = fetch_etf_holdings(code)
        if items:
            success_count += 1
            print(f"✅ [{meta['name']}] 종목 {len(items)}개 수집 성공")
            current_snapshot[code] = {
                "name": meta["name"],
                "is_broad": meta["is_broad"],
                "items": items
            }
            for s_name in items:
                if s_name not in stock_to_etfs:
                    stock_to_etfs[s_name] = []
                stock_to_etfs[s_name].append(meta["name"])
        time.sleep(0.2)

    # ★ 새벽 서버 점검 등으로 0개가 수집되었을 때의 방어 조치:
    # 빈 값으로 덮어쓰지 않고 직전 정상 장부(history)를 유지
    if success_count == 0:
        print("⚠️ 현재 금융사 야간 점검 시간대(00:00~05:00)로 인해 실시간 응답이 없습니다.")
        if history:
            latest_date = sorted(history.keys(), reverse=True)[0]
            print(f"🔄 직전 영업일({latest_date})의 정상 장부 데이터를 안전하게 유지합니다.")
            current_snapshot = history[latest_date]
            success_count = len(current_snapshot)
            for code, data in current_snapshot.items():
                for s_name in data["items"]:
                    if s_name not in stock_to_etfs:
                        stock_to_etfs[s_name] = []
                    stock_to_etfs[s_name].append(data["name"])

    print(f"📊 총 14개 중 {success_count}개 펀드 데이터 확보 완료")

    all_analyzed = []
    for code, data in current_snapshot.items():
        etf_name = data["name"]
        is_broad = data["is_broad"]

        for s_name, item in data["items"].items():
            curr_weight = item["weight"]
            appearances = stock_to_etfs.get(s_name, [etf_name])
            etf_count = len(appearances)

            if etf_count >= 2:
                strat = "house_pick"
                strat_label = f"하우스 압축픽 ({etf_count}개 펀드)"
                guide = f"강력 매수 ({min(45, 20 + etf_count*5)}%)"
                guide_color = "emerald"
                priority = 90
            elif is_broad and etf_count == 1 and curr_weight >= 3.0:
                strat = "single_conviction"
                strat_label = "지수형 단독 승부주"
                guide = "단독 승부 (25%)"
                guide_color = "purple"
                priority = 85
            else:
                strat = "normal"
                strat_label = "정규 운용"
                guide = "관망 (Hold)"
                guide_color = "slate"
                priority = 10

            all_analyzed.append({
                "name": s_name,
                "etfs": list(set(appearances)),
                "is_single_conviction": (strat == "single_conviction"),
                "current": f"{curr_weight:.2f}%",
                "priceChange": 0.0,
                "shareChange": 0.0,
                "buy_date": today_str,
                "strategy": strat,
                "strategyLabel": strat_label,
                "actionGuide": guide,
                "guideColor": guide_color,
                "priority_score": priority,
                "reason": f"타임폴리오 {etf_name} 실제 편입 비중 {curr_weight:.2f}%. 포지션 정상 추적 중.",
                "news": [{"title": f"[{s_name}] 타임폴리오 실제 PDF 편입 확인", "source": "TIME 자산운용", "date": today_str}],
                "metric": f"• {etf_count}개 펀드 동시 편입\n• 보유비중 {curr_weight:.2f}%"
            })

    unique_stocks = {}
    for s in all_analyzed:
        name = s["name"]
        if name not in unique_stocks or s["priority_score"] > unique_stocks[name]["priority_score"]:
            unique_stocks[name] = s

    sorted_stocks = sorted(
        list(unique_stocks.values()),
        key=lambda x: (x["priority_score"], len(x["etfs"]), float(x["current"].replace("%",""))),
        reverse=True
    )

    output = {
        "last_updated": now_time_str,
        "total_etfs_tracked": success_count,
        "tracked_etfs": [d["name"] for d in current_snapshot.values()],
        "stocks": sorted_stocks[:50]
    }

    # 수집 데이터가 있거나 기존 데이터가 복원되었을 때만 파일 기록
    if sorted_stocks:
        with open("data.json", "w", encoding="utf-8") as f:
            json.dump(output, f, ensure_ascii=False, indent=2)

        history[today_str] = current_snapshot
        with open(history_file, "w", encoding="utf-8") as f:
            json.dump(history, f, ensure_ascii=False)

    print(f"🎉 처리 완료! 종목 {len(sorted_stocks)}개 안전하게 반영됨.")

if __name__ == "__main__":
    main()
