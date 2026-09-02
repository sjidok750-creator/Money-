"""빗썸 봇 감사 — 숫자 5개만 뽑는다. ~/Trade 안에서 실행:

    cd ~/Trade && .venv/bin/python /path/to/audit.py

출력: 가동 일수 / 거래 횟수 / 실현손익 합계 / 지불 수수료 추정 / 자산 경로(시작→현재→고점→낙폭)
      + 마지막 추세 판단(어느 코인이 현금 대기인지) + 판정 한 줄.
logs/·state/ 를 읽기만 하고 아무것도 바꾸지 않는다.
"""
import json
import os
import re
import sqlite3
from datetime import datetime

FEE = 0.0004


def load_jsonl(path):
    if not os.path.exists(path):
        return []
    with open(path) as f:
        return [json.loads(l) for l in f if l.strip()]


def main():
    events = load_jsonl("logs/events.jsonl")
    if not events:
        print("logs/events.jsonl 이 없다. ~/Trade 안에서 실행했는지 확인.")
        return
    first = datetime.fromisoformat(events[0]["ts"])
    last = datetime.fromisoformat(events[-1]["ts"])
    days = (last - first).total_seconds() / 86400
    mode = next((e.get("mode") for e in events if e["type"] == "engine_start"), "?")

    trades = [e for e in events if e["type"] == "trade"]
    buys = [t for t in trades if t["side"] == "buy"]
    sells = [t for t in trades if t["side"] == "sell"]
    realized = 0.0
    for t in sells:
        m = re.search(r"손익 ([+-][\d,]+)원", t.get("reason", ""))
        if m:
            realized += float(m.group(1).replace(",", ""))
    fees = sum(t["krw"] for t in trades) * FEE

    eq_rows = []
    if os.path.exists("logs/trades.db"):
        con = sqlite3.connect("logs/trades.db")
        eq_rows = con.execute("select ts, equity_krw from equity order by ts").fetchall()
    start_eq = next((e.get("start") for e in events if e["type"] == "capital_baseline"), None)
    if eq_rows:
        eqs = [r[1] for r in eq_rows]
        start_eq = start_eq or eqs[0]
        cur, peak = eqs[-1], max(eqs)
        dd = (peak - cur) / peak * 100 if peak else 0
    else:
        cur = peak = start_eq or 0
        dd = 0

    trend = {}
    if os.path.exists("state/trend.json"):
        trend = json.load(open("state/trend.json"))
    settle = {}
    if os.path.exists("state/settle.json"):
        settle = json.load(open("state/settle.json"))
    rebal = [e for e in events if e["type"] == "trend_rebalance"]
    blocked = [e for e in events if e["type"] == "buy_blocked"]
    errors = [e for e in events if e["type"] == "error"]

    print(f"모드: {mode} / 가동 {days:.1f}일 ({first.date()} ~ {last.date()})")
    print(f"리밸런싱 판단 {len(rebal)}회 / 매수 {len(buys)}회 / 매도 {len(sells)}회 / 매수 차단 {len(blocked)}회 / 오류 {len(errors)}회")
    print(f"실현손익 합계: {realized:+,.0f}원   지불 수수료 추정: {fees:,.0f}원")
    if start_eq:
        print(f"자산: 시작 {start_eq:,.0f} → 현재 {cur:,.0f} (미실현 포함 {cur - start_eq:+,.0f}원, {(cur / start_eq - 1) * 100:+.2f}%) / 고점 {peak:,.0f} / 낙폭 {dd:.1f}%")
    if settle:
        print(f"확정 대기 {settle.get('reserve', 0):,.0f}원 / 확정 사이클 {settle.get('cycles', 0)}회 / 목표 기준선 {settle.get('baseline', 0):,.0f}원")
    if trend:
        held = [m.replace("KRW-", "") for m, v in trend.items() if not m.startswith("_") and v]
        cash = [m.replace("KRW-", "") for m, v in trend.items() if not m.startswith("_") and not v]
        print(f"추세 판단({trend.get('_last_rebal', '?')}): 보유대상 {held or '없음'} / 현금대기 {cash or '없음'}")
    if rebal:
        for e in rebal[-4:]:
            print(f"  {e['day']}: 대상 {[m.replace('KRW-', '') for m in e['targets']] or '없음'}")

    print()
    # 판정
    if days < 14:
        print("판정: 아직 판정 불가. 주 1회 전략은 최소 4~8회 판단(1~2개월)이 쌓여야 운/실력을 가른다.")
    elif abs(realized) < fees:
        print("판정: 손익이 수수료보다 작다. 전략이 거의 안 움직였거나(현금 대기) 휩쏘로 비용만 냈다.")
    elif realized < 0:
        print("판정: 실현손실. 최근 리밸런싱 대상 변화(휩쏘)와 장세를 대조할 것.")
    else:
        print("판정: 실현이익 발생. 확정 목표(settle.target_krw) 대비 진행률을 확인할 것.")
    if trend and not any(v for m, v in trend.items() if not m.startswith("_")):
        print("보충: 6코인 전부 현금 대기 = 하락장 방어 모드. 이 상태에서 수익 0은 설계대로 동작한 것이다.")


if __name__ == "__main__":
    main()
