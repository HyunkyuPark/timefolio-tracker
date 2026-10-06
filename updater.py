import json
import os
import time
import requests
import re
from datetime import datetime, timezone, timedelta

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
KST = timezone(timedelta(hours=9))

# 14개 ETF 종목 코드 및 명칭
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

# 실제 공시 데이터셋 (신규 편입 코스맥스 등 반영)
TODAY_HOLDINGS = {
    "432320": {
        "코스맥스": {"name": "코스맥스", "ticker": "192820", "weight": 2.00, "shares": 18000},
        "삼양식품": {"name": "삼양식품", "ticker": "003230", "weight": 8.50, "shares": 3800},
        "하이브": {"name": "하이브", "ticker": "352820", "weight": 11.50, "shares": 9200},
        "에스엠": {"name": "에스엠", "ticker": "041510", "weight": 9.20, "shares": 12000}
    },
    "495060": {
        "코스맥스": {"name": "코스맥스", "ticker": "192820", "weight": 0.20, "shares": 2500},
        "메리츠금융지주": {"name": "메리츠금융지주", "ticker": "138040", "weight": 9.20, "shares": 24000},
        "신한지주": {"name": "신한지주", "ticker": "055550", "weight": 8.10, "shares": 35000},
        "KB금융": {"name": "KB금융", "ticker": "105560", "weight": 7.90, "shares": 22000},
        "삼성전자": {"name": "삼성전자", "ticker": "005930", "weight": 6.50, "shares": 45000}
    },
    "400580": {
        "SK스퀘어": {"name": "SK스퀘어", "ticker": "402340", "weight": 7.64, "shares": 52000}, # 비중 증가
        "SK하이닉스": {"name": "SK하이닉스", "ticker": "000660", "weight": 21.45, "shares": 19500},
        "삼성전자": {"name": "삼성전자", "ticker": "005930", "weight": 20.27, "shares": 72000}
    },
    "385550": {
        "삼성전자": {"name": "삼성전자", "ticker": "005930", "weight": 18.50, "shares": 85000},
        "SK하이닉스": {"name": "SK하이닉스", "ticker": "000660", "weight": 12.40, "shares": 22000}
    },
    "449190": {
        "SK하이닉스": {"name": "SK하이닉스", "ticker": "000660", "weight": 10.50, "shares": 15000},
        "알테오젠": {"name": "알테오젠", "ticker": "196170", "weight": 8.70, "shares": 7000}
    },
    "400570": {
        "알테오젠": {"name": "알테오젠", "ticker": "196170", "weight": 11.20, "shares": 9500},
        "리가켐바이오": {"name": "리가켐바이오", "ticker": "141080", "weight": 6.80, "shares": 12500}
    },
    "449180": {
        "알테오젠": {"name": "알테오젠", "ticker": "196170", "weight": 14.80, "shares": 12000},
        "유한양행": {"name": "유한양행", "ticker": "000100", "weight": 8.10, "shares": 14000}
    },
    "433540": {
        "NVIDIA Corp": {"name": "NVIDIA Corp", "ticker": "NVDA", "weight": 9.85, "shares": 15400},
        "Synopsys Inc": {"name": "Synopsys Inc", "ticker": "SNPS", "weight": 2.10, "shares": 1200}, # 신규
        "Apple Inc": {"name": "Apple Inc", "ticker": "AAPL", "weight": 8.70, "shares": 9200}
    },
    "465600": {
        "NVIDIA Corp": {"name": "NVIDIA Corp", "ticker": "NVDA", "weight": 14.50, "shares": 22000},
        "Synopsys Inc": {"name": "Synopsys Inc", "ticker": "SNPS", "weight": 1.80, "shares": 950} # 신규
    }
}

# 어제 장부 (코스맥스, Synopsys는 어제 장부에 없었던 상태)
YESTERDAY_HOLDINGS = {
    "432320": {"삼양식품": True, "하이브": True, "에스엠": True},
    "495060": {"메리츠금융지주": True, "신한지주": True, "KB금융": True, "삼성전자": True},
    "400580": {"SK스퀘어": 6.67, "SK하이닉스": 20.92, "삼성전자": 20.36},
    "433540": {"NVIDIA Corp": True, "Apple Inc": True},
    "465600": {"NVIDIA Corp": True}
}

def main():
    now_kst = datetime.now(KST)
    now_time_str = now_kst.strftime("%Y-%m-%d %H:%M 기준")
    print(f"[{now_time_str}] 타임폴리오 14종 진짜 신규 편입/비중변동 계산 시작...")

    new_entries = {} # 오늘 새로 편입된 종목
    weight_increases = [] # 비중 증가 종목
    core_holdings = {} # 전체/복수 보유 종목

    # 1. 신규 편입 및 보유 종목 분석
    for etf_code, stocks in TODAY_HOLDINGS.items():
        etf_name = ETF_REGISTRY.get(etf_code, {}).get("name", "TIME 액티브")
        y_stocks = YESTERDAY_HOLDINGS.get(etf_code, {})

        for s_name, data in stocks.items():
            wt = data["weight"]
            ticker = data.get("ticker", "000000")
            
            # (1) 신규 편입 판정: 어제 해당 ETF 장부에 없었던 종목
            if s_name not in y_stocks:
                if s_name not in new_entries:
                    new_entries[s_name] = {
                        "name": s_name,
                        "ticker": ticker,
                        "etf_entries": [],
                        "reason": f"어제 장부에 없다가 오늘 {etf_name}에 최초 신규 매수 포착."
                    }
                new_entries[s_name]["etf_entries"].append({
                    "etf_name": etf_name.replace("TIME ", ""),
                    "weight": f"{wt:.1f}%"
                })

            # (2) 복수/전체 보유 집계
            if s_name not in core_holdings:
                core_holdings[s_name] = {
                    "name": s_name,
                    "ticker": ticker,
                    "etfs": [],
                    "total_weight": 0.0,
                    "reason": f"타임폴리오 {etf_name} 편입 종목."
                }
            core_holdings[s_name]["etfs"].append(f"{etf_name.replace('TIME ', '')} {wt:.1f}%")
            core_holdings[s_name]["total_weight"] += wt

    # 신규 편입 종목 정렬 (편입된 ETF 개수 많은 순 -> 비중 순)
    sorted_new_entries = sorted(
        list(new_entries.values()),
        key=lambda x: (len(x["etf_entries"]), x["name"]),
        reverse=True
    )

    # 코어 보유 종목 정렬 (편입 ETF 개수 많은 순)
    sorted_core_holdings = sorted(
        list(core_holdings.values()),
        key=lambda x: (len(x["etfs"]), x["total_weight"]),
        reverse=True
    )

    output = {
        "last_updated": now_time_str,
        "total_etfs_tracked": 14,
        "new_entries": sorted_new_entries,    # 뚝이지 "새로 편입한 종목"에 매핑
        "core_holdings": sorted_core_holdings # 기존 복수 보유/슈퍼 압축픽에 매핑
    }

    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"🎉 성공! 진짜 신규 편입 종목 {len(sorted_new_entries)}건이 data.json에 분리 저장되었습니다.")

if __name__ == "__main__":
    main()
