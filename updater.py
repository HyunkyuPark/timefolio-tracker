import json
import os
import time
import requests
from datetime import datetime

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

# 타임폴리오 14개 순수 주식형 액티브 ETF 전 라인업
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
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Referer": "https://www.timefolio.co.kr/"
})

def fetch_etf_holdings(code):
    items = {}

    # 1. 타임폴리오 공식 홈페이지 PDF 조회 엔드포인트
    try:
        url = "https://www.timefolio.co.kr/etf/ajax_pdf_list.php"
        data = {"fund_cd": code}
        res = SESSION.post(url, data=data, timeout=6)
        if res.status_code == 200:
            res_json = res.json()
            raw_list = res_json.get("list", []) or res_json.get("data", [])
            for r in raw_list:
                nm = (r.get("stk_nm") or r.get("item_name") or r.get("name") or "").strip()
                if not nm or "원화" in nm or "현금" in nm or "예금" in nm:
                    continue
                try:
                    wt = float(str(r.get("weight", 0)).replace("%", "").replace(",", ""))
                except Exception:
                    wt = 0.0
                try:
                    sh = float(str(r.get("qty", 0) or r.get("quantity", 0)).replace(",", ""))
                except Exception:
                    sh = 0.0
                try:
                    pr = float(str(r.get("price", 0) or r.get("eval_amt", 0)).replace(",", ""))
                except Exception:
                    pr = 0.0

                if wt > 0.05:
                    items[nm] = {"name": nm, "weight": wt, "shares": sh, "price": pr}
            if items:
                return items
    except Exception as e:
        print(f"[{code}] 타임폴리오 직통 수집 시도 중: {e}")

    # 2. KRX 백업 엔드포인트
    try:
        url = f"https://m.stock.naver.com/front-api/v1/etf/portfolio?itemCode={code}"
        h = {"User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X)", "Referer": "https://m.stock.naver.com/"}
        res = SESSION.get(url, headers=h, timeout=4)
        if res.status_code == 200:
            data = res.json().get("result", {}).get("portfolio", [])
            for r in data:
                nm = (r.get("itemName") or r.get("stockName") or "").strip()
                wt = float(r.get("weight") or 0.0)
                sh = float(r.get("share") or r.get("quantity") or 0.0)
                pr = float(r.get("price") or 0.0)
                if nm and "원화" not in nm and wt > 0.05:
                    items[nm] = {"name": nm, "weight": wt, "shares": sh, "price": pr}
            if items:
                return items
    except Exception:
        pass

    return items

def query_gemini_thesis(top_stocks):
    if not GEMINI_API_KEY or not top_stocks:
        return {}

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}"
    summary = [f"- {s['name']} (편입: {','.join(s['etfs'])}, 비중: {s['current']})" for s in top_stocks]
    prompt = f"""
    너는 타임폴리오 액티브 헤지펀드 시니어 주식 리서치 애널리스트다.
    오늘 실제 ETF 장부에서 집중 편입된 핵심 종목들이다:
    {chr(10).join(summary)}

    각 종목의 최근 IR 공시, 실적, 수주 뉴스를 바탕으로 운용역 매수 가설(Thesis)을 추론하라.
    반드시 다음 JSON 형식(키는 종목명 그대로)으로만 한국어로 작성하라:
    {{
      "종목명": {{
        "reason": "핵심 투자 가설 (2~3문장)",
        "news": [
          {{"title": "최근 핵심 뉴스/IR 헤드라인 1", "source": "블룸버그/DART", "date": "최근"}},
          {{"title": "최근 핵심 뉴스/IR 헤드라인 2", "source": "리포트/언론", "date": "최근"}}
        ],
        "metric": "• 핵심 재무/수주 지표 2줄"
      }}
    }}
    """
    try:
        res = requests.post(url, json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=10)
        if res.status_code == 200:
            txt = res.json()["candidates"][0]["content"]["parts"][0]["text"].replace("```json","").replace("```","").strip()
            return json.loads(txt)
    except Exception as e:
        print(f"Gemini API 에러: {e}")
    return {}

def main():
    today_str = datetime.now().strftime("%Y-%m-%d")
    now_time_str = datetime.now().strftime("%Y-%m-%d %H:%M 기준")
    print(f"[{now_time_str}] 타임폴리오 14개 핵심 ETF 수집 시작...")

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
    stock_to_etfs = {}
    success_count = 0

    for code, meta in ETF_REGISTRY.items():
        items = fetch_etf_holdings(code)
        if items:
            success_count += 1
            print(f"✅ [{meta['name']}] {len(items)}개 종목 수집 성공")
            current_snapshot[code] = {
                "name": meta["name"],
                "is_broad": meta["is_broad"],
                "items": items
            }
            for s_name in items:
                if s_name not in stock_to_etfs:
                    stock_to_etfs[s_name] = []
                stock_to_etfs[s_name].append(meta["name"])
        else:
            print(f"❌ [{meta['name']}] 수집 실패")
        
        time.sleep(0.3)

    print(f"📊 총 14개 중 {success_count}개 펀드 실제 장부 추출 완료!")

    all_analyzed = []

    for code, data in current_snapshot.items():
        etf_name = data["name"]
        is_broad = data["is_broad"]
        past_items = past_snapshot.get(code, {}).get("items", {})

        for s_name, item in data["items"].items():
            curr_weight = item["weight"]
            curr_shares = item["shares"]
            curr_price = item["price"]

            past_item = past_items.get(s_name)
            is_new = False

            if past_item and past_item.get("shares", 0) > 0:
                past_shares = past_item["shares"]
                past_price = past_item.get("price", curr_price)
                share_change = round(((curr_shares - past_shares) / past_shares) * 100, 1)
                price_change = round(((curr_price - past_price) / max(1.0, past_price)) * 100, 1)
            else:
                is_new = True
                share_change = 100.0 if past_snapshot else 0.0
                price_change = 0.0

            appearances = stock_to_etfs.get(s_name, [etf_name])
            etf_count = len(appearances)

            if is_new and past_snapshot:
                strat = "new_in"
                strat_label = "신규 매집주"
                guide = "수급 편승 (15~20%)"
                guide_color = "blue"
                priority = 95
            elif etf_count >= 2 and share_change >= 5.0:
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
            elif share_change <= -15.0:
                strat = "exit_warning"
                strat_label = "엑시트 경보"
                guide = "즉시 동반 매도"
                guide_color = "rose"
                priority = 80
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
                "priceChange": price_change,
                "shareChange": share_change,
                "buy_date": today_str if share_change > 0 else "보합/유지",
                "strategy": strat,
                "strategyLabel": strat_label,
                "actionGuide": guide,
                "guideColor": guide_color,
                "priority_score": priority,
                "reason": f"실제 장부 기준 {etf_name} 편입 비중 {curr_weight:.2f}%.",
                "news": [{"title": f"[{s_name}] 타임폴리오 실제 PDF 편입 확인", "source": "TIME 자산운용", "date": today_str}],
                "metric": f"• {etf_count}개 펀드 편입\n• 보유비중 {curr_weight:.2f}%"
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

    priority_candidates = [s for s in sorted_stocks if s["priority_score"] >= 85][:5]
    if priority_candidates:
        ai_res = query_gemini_thesis(priority_candidates)
        for s in sorted_stocks:
            if s["name"] in ai_res:
                info = ai_res[s["name"]]
                s["reason"] = info.get("reason", s["reason"])
                s["news"] = info.get("news", s["news"])
                s["metric"] = info.get("metric", s["metric"])

    output = {
        "last_updated": now_time_str,
        "total_etfs_tracked": success_count,
        "tracked_etfs": [d["name"] for d in current_snapshot.values()],
        "stocks": sorted_stocks[:50]
    }

    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    if current_snapshot:
        history[today_str] = current_snapshot
        with open(history_file, "w", encoding="utf-8") as f:
            json.dump(history, f, ensure_ascii=False)

    print(f"🎉 성공! 실제 종목 {len(sorted_stocks)}개가 data.json에 기록되었습니다.")

if __name__ == "__main__":
    main()
