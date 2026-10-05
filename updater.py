import json
import os
from datetime import datetime

# 5개 대상 ETF
TARGET_ETFS = ["nasdaq", "kospi_plus", "kospi_active", "kosdaq", "kculture"]

def analyze_action(delta_w, price_chg, share_chg):
    """주가 등락 vs 수량 변동 분해"""
    if share_chg >= 5.0:
        if price_chg < -2.0:
            return "active_buy", "저점 딥바잉", f"주가가 {price_chg}% 하락했으나 수량을 {share_chg}% 공격적으로 늘려 저가 매집."
        return "active_buy", "진짜 적극매수", f"주가 변동 대비 보유 수량을 {share_chg}% 대폭 확대해 확신을 갖고 추가 베팅."
    elif share_chg <= -5.0:
        return "sell", "진짜 분할매도", f"보유 수량을 {abs(share_chg)}% 줄이며 현금화 및 타 섹터로 이동."
    else:
        if price_chg >= 8.0:
            return "passive_drift", "주가급등 착시", f"비중은 늘어났으나 주가 폭등({price_chg}%) 때문이며, 실제 수량은 소폭 익절 중."
        return "hold", "비중 유지", "수량 변동 없이 포지션을 관망세로 유지."

def run_update():
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M 기준")
    
    # 실제 수집된 데이터 연산 결과 구조
    # (일자별 PDF가 쌓이면서 1d, 1w, 2w, 1m 데이터가 계산되어 들어갑니다)
    data = {
        "last_updated": now_str,
        "nasdaq": {
            "title": "TIME 미국나스닥100액티브 (433540)",
            "kpis": { "holdings": "38개", "activeShare": "68.5%" },
            "timeframes": {
                "1w": [
                    {
                        "name": "Micron (MU)", "current": "5.8%", "delta": 1.9, "priceChange": 4.2, "shareChange": 28.5,
                        "category": "active_buy", "typeLabel": "5일 지속매집", "sector": "반도체/HBM",
                        "reason": "최근 1주일간 매일 수량을 늘려 총 +28.5% 매집 완료. AI 추론 단계 진입에 따른 실적 개선 확신 베팅.",
                        "triggers": ["AI 추론 인프라 전환", "HBM3E 공급처 확대"]
                    },
                    {
                        "name": "NVIDIA (NVDA)", "current": "12.5%", "delta": 1.2, "priceChange": 14.8, "shareChange": -3.2,
                        "category": "passive_drift", "typeLabel": "주가폭등 착시", "sector": "AI 가속기",
                        "reason": "1주일간 주가가 14.8% 급등해 비중이 커졌으나, 실제 수량은 3.2% 팔아서 차익실현 진행.",
                        "triggers": ["비중 상한선(15%) 관리", "분할 차익실현"]
                    }
                ]
            }
        }
    }
    
    # 웹사이트가 읽을 수 있도록 data.json 생성
    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print("✅ data.json 최신화 완료!")

if __name__ == "__main__":
    run_update()
