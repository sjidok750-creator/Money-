"""평균회귀(딥 바이) 전략 연구 — Trade 저장소의 backtest/ 에 mr.py 로 복사해 실행:

    cp mr.py ~/Trade/backtest/mr.py
    cd ~/Trade && .venv/bin/python -m backtest.mr          # 딥 깊이 × 익절 스윕
    cd ~/Trade && .venv/bin/python -m backtest.mr combo    # 추세추종 50% + 평균회귀 50% 합성

왜 이 전략인가: 현행 MA30 추세추종은 추세장에 벌고 횡보장에 휩쏘로 잃는다.
평균회귀는 정반대(횡보장에 벌고 추세장에 약함). 둘을 반씩 섞으면 서로의 빈 구간을 메운다.
"봇 여러 마리"의 첫 번째 원칙 = 서로 다른 장세에서 버는 봇을 나란히 둔다.

규칙(일봉, 미래 참조 없음 — 어제 종가까지로 오늘 비중 결정):
  진입: 어제 종가 < MA20 × (1 - dip)         (과매도 딥)
  청산: 어제 종가 ≥ MA20 (평균 복귀)  또는  진입 대비 +tp 익절  또는  -stop 손절  또는 max_hold일 경과
  비중: 진입 코인 균등 (1/n), 나머지 현금
비용은 portfolio.COST(왕복 0.28%)를 그대로 쓴다. 저빈도 원칙: 코인당 한 번 들어가면 평균 복귀까지 며칠 든다.
"""
import sys

import yaml

from .data import load_csv
from .lab import ROW, load_all, ma_trend_factory, series
from .portfolio import run

MA = 20


def mr_factory(markets, px, dip=0.10, tp=0.08, stop=0.15, max_hold=14, ma=MA):
    n = len(markets)
    held = {}   # market -> (entry_price, entry_i)

    def fn(i):
        j = i - 1                       # 어제 인덱스
        if j < ma:
            return {}
        for m in markets:
            p = px[m][j]
            window = px[m][j - ma:j]
            if p is None or None in window:
                held.pop(m, None)
                continue
            mean = sum(window) / ma
            if m in held:
                ep, ei = held[m]
                if (p >= mean or p >= ep * (1 + tp) or p <= ep * (1 - stop)
                        or j - ei >= max_hold):
                    held.pop(m)
            elif p < mean * (1 - dip):
                held[m] = (p, j)
        return {m: 1.0 / n for m in held}

    return fn


def combo_factory(fa, fb, wa=0.5):
    def fn(i):
        a, b = fa(i) or {}, fb(i) or {}
        out = {}
        for m, w in a.items():
            out[m] = out.get(m, 0.0) + w * wa
        for m, w in b.items():
            out[m] = out.get(m, 0.0) + w * (1 - wa)
        return out
    return fn


def main():
    with open("config.yaml") as f:
        markets = yaml.safe_load(f)["universe"]
    dates, closes = load_all(markets)
    px = {m: series(closes, m, dates) for m in markets}
    print(f"기간: {dates[0]} ~ {dates[-1]} ({len(dates)}일)\n")
    header = f"{'전략':>14} | {'총수익':>8} | {'연복리':>7} | {'MDD':>6} | {'샤프':>5} | {'회전':>6} | {'비용':>6} | {'투자일':>5}"
    trend = ma_trend_factory(markets, px, 30, 0.03, 7)

    if len(sys.argv) > 1 and sys.argv[1] == "combo":
        print("합성 검증 — 추세추종(MA30/3%/주1회) + 평균회귀(딥10%/익절8%)\n")
        print(header); print("-" * len(header))
        print(ROW.format(name="추세만", r=run("추세만", dates, closes, trend)))
        mr = mr_factory(markets, px)
        print(ROW.format(name="평균회귀만", r=run("평균회귀만", dates, closes, mr)))
        for wa in (0.7, 0.5, 0.3):
            name = f"추세{int(wa*100)}/MR{int((1-wa)*100)}"
            print(ROW.format(name=name, r=run(name, dates, closes,
                                               combo_factory(trend, mr_factory(markets, px), wa))))
        return

    print("평균회귀 스윕 (딥 깊이 × 익절). 기준선: 추세추종\n")
    print(header); print("-" * len(header))
    print(ROW.format(name="추세(기준)", r=run("추세(기준)", dates, closes, trend)))
    for dip in (0.05, 0.10, 0.15):
        for tp in (0.05, 0.08, 0.12):
            name = f"딥{int(dip*100)}/익{int(tp*100)}"
            r = run(name, dates, closes, mr_factory(markets, px, dip, tp))
            print(ROW.format(name=name, r=r))
        print()


if __name__ == "__main__":
    main()
