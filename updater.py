import json
import os
import requests
import pandas as pd
from datetime import datetime, timedelta

# 1. 감시 대상 타임폴리오 ETF 목록
ETF_REGISTRY = {
    # 대표 지수형 액티브 (단독 승부주 감시 대상)
    "433540": {"name": "TIME 미국나스닥100액티브", "is_broad": True},
    "449170": {"name": "TIME 미국S&P500액티브", "is_broad": True},
    "385550": {"name": "TIME 코스피플러스액티브", "is_broad": True},
    "400580": {"name": "TIME 코스피액티브", "is_broad": True},
    
    # 테마 / 섹터형 액티브
    "432320": {"name": "TIME K컬처액티브", "is_broad": False},
    "465600": {"name": "TIME 글로벌인공지능액티브", "is_broad": False},
    "475380": {"name": "TIME 글로벌소부장액티브", "is_broad": False},
    "449180": {"name": "TIME 바이오액티브", "is_broad": False}
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://finance.naver.com/"
}

def fetch_etf_pdf_naver(item_code):
    """
    네이버 증권 ETF 실시간 PDF(구성종목) API 수집
    """
    url = f"https://finance.naver.com/item/main.naver?code={item_code}"
    # 네이버 금융 모바일/내부 PDF 비동기 API 엔드포인트
    api_url = f"https://m.stock.naver.com/api/stock/{item_code}/etf/portfolio"
    
    try:
        res = requests.get(api_url, headers=HEADERS, timeout=10)
        if res.status_code == 200:
            data = res.json()
            items = []
            # portfolio 항목 파싱
            for p in data.get("portfolio", []):
                name = p.get("itemName", "")
                ticker = p.get("itemCode", "")
                weight = float(p.get("weight", 0.0))
                shares = float(p.get("share", 0.0) or p.get("quantity", 0.0))
                price = float(p.get("price", 0.0) or 0.0)
                
                # 원화 현금/단기예치금 등 제외
                if "원화" in name or "예금" in name or "현금" in name or weight <= 0.05:
                    continue
                    
                items.append({
                    "name": name,
                    "ticker": ticker,
                    "weight": weight,
                    "shares": shares,
                    "price": price
                })
            return items
    except Exception as e:
        print(f"[{item_code}] 네이버 API 수집 실패, 대체 수집 시도: {e}")

    # Fallback: 타임폴리오 웹페이지 스크래핑 시도
    return fetch_etf_pdf_timefolio_direct(item_code)

def fetch_etf_pdf_timefolio_direct(item_code):
    """타임폴리오 자산운용 웹사이트 PDF 직접 수집 보조 함수"""
    url = "https://www.timefolio.co.kr/etf/ajax_pdf_list.php"
    params = {"fund_cd": item_code}
    try:
        res = requests.get(url, headers=HEADERS, params=params, timeout=10)
        if res.status_code == 200:
            data = res.json()
            items = []
            for row in data.get("list", []):
                name = row.get("stk_nm", "")
                weight = float(row.get("weight", 0.0))
                shares = float(row.get("qty", 0.0))
                if weight > 0.1:
                    items.append({
                        "name": name,
                        "ticker": row.get("stk_cd", ""),
                        "weight": weight,
                        "shares": shares,
                        "price": float(row.get("eval_amt", 0.0)) / max(1.0, shares)
                    })
            return items
    except Exception as e:
        print(f"[{item_code}] 타임폴리오 직접 수집 오류: {e}")
    return []

def evaluate_intensity(share_change, consecutive_days):
    """매수 강도 및 레벨 판별"""
    if share_change >= 40.0:
        return {"level": 5, "badge": "초강력 집중 매집 (Lv.5)", "color": "purple"}
    elif share_change >= 20.0:
        return {"level": 4, "badge": "적극 공격 매수 (Lv.4)", "color": "emerald"}
    elif share_change >= 10.0:
        return {"level": 3, "badge": "계단식 분할 매수 (Lv.3)", "color": "blue"}
    elif share_change >= 3.0:
        return {"level": 2, "badge": "안정적 비중 확대 (Lv.2)", "color": "slate"}
    elif share_change > 0.0:
        return {"level": 1, "badge": "정찰병 진입 (Lv.1)", "color": "slate"}
    elif share_change <= -15.0:
        return {"level": 0, "badge": "대량 엑시트/탈출", "color": "rose"}
    else:
        return {"level": 0, "badge": "분할 차익실현", "color": "amber"}

def main():
    today_str = datetime.now().strftime("%Y-%m-%d")
    now_time_str = datetime.now().strftime("%Y-%m-%d %H:%M 기준")
    print(f"[{now_time_str}] 타임폴리오 ETF 실시간 PDF 수집 파이프라인 가동...")

    # 이력 데이터 로드 (과거 주식 수와 비교하여 수량 증감률 계산)
    history_file = "history.json"
    history = {}
    if os.path.exists(history_file):
        try:
            with open(history_file, "r", encoding="utf-8") as f:
                history = json.load(f)
        except Exception:
            history = {}

    current_snapshot = {}
    stock_to_etfs = {} # 종목별 편입된 ETF 목록 (교집합 집계)

    # 1. ETF별 실시간 PDF 수집
    for code, meta in ETF_REGISTRY.items():
        items = fetch_etf_pdf_naver(code)
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

    # 2. 이력 비교 및 변동량 연산
    past_dates = sorted([d for d in history.keys() if d < today_str], reverse=True)
    past_snapshot = history.get(past_dates[0], {}) if past_dates else {}

    analyzed_stocks = []

    # 전체 종목 순회
    for code, data in current_snapshot.items():
        etf_name = data["name"]
        is_broad = data["is_broad"]
        past_etf_items = past_snapshot.get(code, {}).get("items", {})

        for s_name, item in data["items"].items():
            curr_weight = item["weight"]
            curr_shares = item["shares"]
            curr_price = item["price"]

            # 과거 데이터 대조
            past_item = past_etf_items.get(s_name)
            if past_item and past_item.get("shares", 0) > 0:
                past_shares = past_item["shares"]
                past_price = past_item.get("price", curr_price)
                share_change = round(((curr_shares - past_shares) / past_shares) * 100, 1)
                price_change = round(((curr_price - past_price) / max(1.0, past_price)) * 100, 1)
                is_new = False
            else:
                # 신규 편입 종목
                share_change = 100.0 if past_snapshot else 0.0
                price_change = 0.0
                is_new = True

            appearances = stock_to_etfs.get(s_name, [etf_name])
            etf_count = len(appearances)

            # 분류 전략 도출
            if etf_count >= 2 and share_change >= 5.0:
                strat = "house_pick"
                strat_label = "하우스 압축픽"
                guide = f"적극 매수 ({min(40, 20 + etf_count*10)}%)"
                guide_color = "emerald"
                is_single = False
            elif is_broad and etf_count == 1 and curr_weight >= 3.0 and share_change >= 10.0:
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
                "buy_date": today_str if share_change > 0 else "보합/매도",
                "consecutive_days": 1 if share_change > 0 else 0,
                "intensity": evaluate_intensity(share_change, 1),
                "strategy": strat,
                "strategyLabel": strat_label,
                "actionGuide": guide,
                "guideColor": guide_color,
                "reason": f"실제 PDF 장부 기준 {etf_name} 내 비중 {curr_weight:.2f}%. 최근 수량 변동률 {share_change:+0.1f}%.",
                "news": [
                    {"title": f"[{s_name}] 최근 공시 및 수급 모니터링", "source": "DART/KRX", "date": today_str}
                ]
            })

    # 중복 종목 제거 (대표 ETF 1개 기준으로 정렬)
    unique_stocks = {}
    for s in analyzed_stocks:
        name = s["name"]
        if name not in unique_stocks or float(s["current"].replace("%","")) > float(unique_stocks[name]["current"].replace("%","")):
            unique_stocks[name] = s

    # 비중 및 수량 변동폭 상위 종목 정렬
    final_list = sorted(list(unique_stocks.values()), key=lambda x: float(x["current"].replace("%","")), reverse=True)

    # 3. 결과 파일 저장
    output = {
        "last_updated": now_time_str,
        "stocks": final_list[:30] # 상위 30개 핵심 종목 추출
    }

    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    # 이력 업데이트 (최근 30일치만 보관)
    history[today_str] = current_snapshot
    if len(history) > 30:
        oldest = sorted(history.keys())[0]
        del history[oldest]

    with open(history_file, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False)

    print(f"✅ 실제 타임폴리오 장부 {len(final_list)}개 종목 파싱 및 data.json 갱신 완료!")

if __name__ == "__main__":
    main()
