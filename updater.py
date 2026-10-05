import json
import os
import requests
from datetime import datetime

# 1. 감시 대상 타임폴리오 공식 ETF 코드
ETF_REGISTRY = {
    "433540": {"name": "TIME 미국나스닥100액티브", "is_broad": True},
    "449170": {"name": "TIME 미국S&P500액티브", "is_broad": True},
    "385550": {"name": "TIME 코스피플러스액티브", "is_broad": True},
    "400580": {"name": "TIME 코스피액티브", "is_broad": True},
    "432320": {"name": "TIME K컬처액티브", "is_broad": False},
    "465600": {"name": "TIME 글로벌인공지능액티브", "is_broad": False},
    "475380": {"name": "TIME 글로벌소부장액티브", "is_broad": False},
    "449180": {"name": "TIME 바이오액티브", "is_broad": False}
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Referer": "https://www.timefolio.co.kr/"
}

def fetch_real_timefolio_pdf(etf_code):
    """
    타임폴리오 자산운용 공식 웹사이트 실시간 PDF 데이터 파서
    """
    items = []
    
    # 1. 타임폴리오 공식 홈페이지 비동기 PDF 조회 엔드포인트
    url = "https://www.timefolio.co.kr/etf/ajax_pdf_list.php"
    params = {"fund_cd": etf_code}
    
    try:
        res = requests.get(url, headers=HEADERS, params=params, timeout=10)
        if res.status_code == 200:
            data = res.json()
            raw_list = data.get("list", []) or data.get("data", [])
            for row in raw_list:
                name = row.get("stk_nm") or row.get("item_name") or ""
                if not name or "원화" in name or "예치금" in name or "현금" in name:
                    continue
                
                weight = float(row.get("weight") or row.get("ratio") or 0.0)
                shares = float(row.get("qty") or row.get("shares") or 0.0)
                price = float(row.get("price") or 0.0)
                
                if weight > 0.05:
                    items.append({
                        "name": name,
                        "ticker": row.get("stk_cd", ""),
                        "weight": weight,
                        "shares": shares,
                        "price": price
                    })
    except Exception as e:
        print(f"[{etf_code}] 타임폴리오 직통 호출 에러: {e}")

    # 2. 만약 공식 홈페이지 응답이 비어있다면, 증권 포털 오픈 API 백업 호출
    if not items:
        backup_url = f"https://api.finance.naver.com/service/itemSummary.nhn?itemcode={etf_code}"
        try:
            # 다음 포털 / KRX 백업 파싱
            sec_url = f"https://finance.daum.net/api/etfs/{etf_code}/portfolio"
            s_headers = {
                "User-Agent": HEADERS["User-Agent"],
                "Referer": "https://finance.daum.net/"
            }
            res = requests.get(sec_url, headers=s_headers, timeout=10)
            if res.status_code == 200:
                data = res.json()
                for row in data.get("data", []):
                    name = row.get("name", "")
                    weight = float(row.get("weight", 0.0))
                    shares = float(row.get("volume", 0.0) or row.get("share", 0.0))
                    if weight > 0.05 and "원화" not in name and "현금" not in name:
                        items.append({
                            "name": name,
                            "ticker": row.get("symbol", ""),
                            "weight": weight,
                            "shares": shares,
                            "price": float(row.get("price", 0.0))
                        })
        except Exception:
            pass

    return items

def evaluate_intensity(share_change, consecutive_days):
    if share_change >= 30.0:
        return {"level": 5, "badge": "초강력 집중 매집 (Lv.5)", "color": "purple"}
    elif share_change >= 15.0:
        return {"level": 4, "badge": "적극 공격 매수 (Lv.4)", "color": "emerald"}
    elif share_change >= 5.0:
        return {"level": 3, "badge": "계단식 분할 매수 (Lv.3)", "color": "blue"}
    elif share_change > 0.0:
        return {"level": 2, "badge": "안정적 비중 확대 (Lv.2)", "color": "slate"}
    elif share_change <= -15.0:
        return {"level": 0, "badge": "대량 엑시트/탈출", "color": "rose"}
    else:
        return {"level": 0, "badge": "분할 차익실현", "color": "amber"}

def main():
    today_str = datetime.now().strftime("%Y-%m-%d")
    now_time_str = datetime.now().strftime("%Y-%m-%d %H:%M 기준")
    print(f"[{now_time_str}] 타임폴리오 실시간 데이터 수집 시작...")

    # 이력 데이터 로드
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

    for code, meta in ETF_REGISTRY.items():
        items = fetch_real_timefolio_pdf(code)
        print(f"[{meta['name']}] 수집된 실제 종목수: {len(items)}개")
        if not items:
            continue
            
        current_snapshot[code] = {
            "name": meta["name"],
            "is_broad": meta["is_broad"],
            "items": {item["name"]: item for item in items}
        }

        for item in items:
            s_name = item["name"]
            if s_name not in stock_to_etfs:
                stock_to_etfs[s_name] = []
            stock_to_etfs[s_name].append(meta["name"])

    # 변동량 계산
    past_dates = sorted([d for d in history.keys() if d < today_str], reverse=True)
    past_snapshot = history.get(past_dates[0], {}) if past_dates else {}

    analyzed_stocks = []

    for code, data in current_snapshot.items():
        etf_name = data["name"]
        is_broad = data["is_broad"]
        past_etf_items = past_snapshot.get(code, {}).get("items", {})

        for s_name, item in data["items"].items():
            curr_weight = item["weight"]
            curr_shares = item["shares"]
            curr_price = item["price"]

            past_item = past_etf_items.get(s_name)
            if past_item and past_item.get("shares", 0) > 0:
                past_shares = past_item["shares"]
                past_price = past_item.get("price", curr_price)
                share_change = round(((curr_shares - past_shares) / past_shares) * 100, 1)
                price_change = round(((curr_price - past_price) / max(1.0, past_price)) * 100, 1)
            else:
                share_change = 0.0
                price_change = 0.0

            appearances = stock_to_etfs.get(s_name, [etf_name])
            etf_count = len(appearances)

            if etf_count >= 2:
                strat = "house_pick"
                strat_label = "하우스 압축픽"
                guide = f"적극 매수 ({min(40, 20 + etf_count*10)}%)"
                guide_color = "emerald"
                is_single = False
            elif is_broad and etf_count == 1 and curr_weight >= 3.0:
                strat = "single_conviction"
                strat_label = "지수형 단독 승부주"
                guide = "단독 승부 (25~30%)"
                guide_color = "purple"
                is_single = True
            elif share_change <= -15.0:
                strat = "exit_warning"
                strat_label = "엑시트 경보"
                guide = "즉시 동반 매도"
                guide_color = "rose"
                is_single = False
            elif price_change >= 8.0 and share_change <= 0.0:
                strat = "passive_drift"
                strat_label = "고점 착시"
                guide = "매수 금지 / 분할 익절"
                guide_color = "amber"
                is_single = False
            else:
                strat = "normal"
                strat_label = "정규 운용"
                guide = "관망 (Hold)"
                guide_color = "slate"
                is_single = False

            analyzed_stocks.append({
                "name": s_name,
                "etfs": list(set(appearances)),
                "etfKey": code,
                "is_single_conviction": is_single,
                "current": f"{curr_weight:.2f}%",
                "priceChange": price_change,
                "shareChange": share_change,
                "buy_date": today_str if share_change > 0 else "보합/관망",
                "consecutive_days": 1 if share_change > 0 else 0,
                "intensity": evaluate_intensity(share_change, 1),
                "strategy": strat,
                "strategyLabel": strat_label,
                "actionGuide": guide,
                "guideColor": guide_color,
                "reason": f"실제 타임폴리오 {etf_name} 실제 편입 비중 {curr_weight:.2f}%.",
                "news": [
                    {"title": f"[{s_name}] 타임폴리오 실제 PDF 편입 확인", "source": "TIME 자산운용", "date": today_str}
                ]
            })

    # 중복 제거 (가장 비중이 높은 ETF 기준)
    unique_stocks = {}
    for s in analyzed_stocks:
        name = s["name"]
        w = float(s["current"].replace("%",""))
        if name not in unique_stocks or w > float(unique_stocks[name]["current"].replace("%","")):
            unique_stocks[name] = s

    final_list = sorted(list(unique_stocks.values()), key=lambda x: float(x["current"].replace("%","")), reverse=True)

    output = {
        "last_updated": now_time_str,
        "stocks": final_list[:40] # 상위 40개 실제 종목 저장
    }

    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    history[today_str] = current_snapshot
    with open(history_file, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False)

    print(f"🎉 성공! 실제 종목 {len(final_list)}개가 data.json에 기록되었습니다.")

if __name__ == "__main__":
    main()
