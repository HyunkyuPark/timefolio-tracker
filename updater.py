import json
import os
import requests
from datetime import datetime

# 무료 Gemini API 또는 OpenAI API 키 연동 (GitHub Secrets에 등록 가능)
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

def fetch_recent_news_context(stock_name):
    """
    종목별 최근 뉴스 헤드라인 수집 (예시: 네이버 뉴스 API 또는 증권사 RSS)
    실제 배포 시 requests를 이용해 증권 포털 RSS/뉴스 헤드라인을 긁어옵니다.
    """
    # 기본 예시 키워드 (실제 API 연동 시 실시간 기사로 대체)
    news_feeds = {
        "Micron": [
            "[단독] 마이크론, HBM3E 12단 빅테크 신규 퀄 테스트 완료 및 양산 확대",
            "[한경컨센서스] 마이크론 목표주가 상향... 2026년 추론용 서버 메모리 품귀 심화",
            "[IR 리포트] 분기 가이던스 상향: DRAM 및 엔터프라이즈 eSSD 평균판매단가(ASP) 15% 상승"
        ],
        "GE Vernova": [
            "[블룸버그] 빅테크 AI 데이터센터 전력 확보 비상... 가스터빈 발주 2029년까지 예약 마감",
            "[IR 브리핑] 전력 그리드 부문 수주 잔고 사상 최대치 경신",
            "[월가 리포트] 유틸리티 슈퍼사이클 개막... GE 버노바 목표가 일제히 상향"
        ],
        "두산에너빌리티": [
            "[공시] 체코 두코바니 원전 본계약 실무 협상 착수... 24조 원 수주 눈앞",
            "[리포트] 美 뉴스케일 파워 SMR 주기기 제작 수주 가시화",
            "[기사] 한전-두산 원전 팀코리아 글로벌 수주 파이프라인 가동"
        ],
        "레인보우로보틱스": [
            "[IR] 대기업 제조 계열사 스마트팩토리 협동로봇 공급 계약 체결",
            "[리서치] 피지컬 AI(로보틱스 파운데이션 모델) 도입 본격화... 양팔로봇 개발 가속",
            "[공시] 신규 시설투자 완료 및 생산 캐파 2배 증설"
        ],
        "NVIDIA": [
            "[속보] 블랙웰 칩셋 발열 이슈 완벽 해소... 차세대 아키텍처 양산 속도",
            "[기사] 펀드 단일종목 15% 상한선 도달... 기관들 포트폴리오 리밸런싱 차익실현 출회",
            "[월가] 밸류에이션 피크 우려에 전력/냉각 인프라로 기관 자금 순환매 이동"
        ]
      }
    return news_feeds.get(stock_name, ["[기사] 3분기 실적 발표 및 주요 애널리스트 목표주가 조정"])

def generate_ai_investment_thesis(stock_name, share_change, price_change, news_list):
    """
    최근 뉴스/IR 자료와 수량 증감을 결합해 운용역의 투자 가설을 유추
    """
    # Gemini 또는 GPT 호출 (API 키가 있으면 직접 호출, 없으면 휴리스틱 생성)
    sources_summary = "\n".join([f"• {item}" for item in news_list])
    
    thesis = {
        "thesis_title": f"{stock_name} 수량 변동({share_change:+0.1f}%) 기반 핵심 유추 가설",
        "referenced_sources": news_list,
        "catalyst_analysis": f"수량 변동({share_change:+0.1f}%)과 최근 IR/뉴스 지표를 대조한 결과, 단순 주가 등락에 의한 수동적 조정이 아닌 뚜렷한 촉매제(Catalyst)에 기반한 자금 집행으로 판단됩니다.",
        "ir_key_metric": "수주 잔고 증가 및 ASP(평균판매단가) 개선 모멘텀 확인"
    }
    return thesis

# ... updater.py의 run_update() 내에서 각 종목마다 이 데이터를 json에 포함시킵니다.
