#!/usr/bin/env python3
# ruff: noqa: DTZ005
"""모의투자 실시간 자동매매 — 모멘텀 돌파 전략.

스크리닝 통과 종목을 장중 실시간 감시하며 조건 충족 시 매수/매도한다.

사용법:
    python scripts/live_trader.py
    python scripts/live_trader.py --symbols 005930,000660
    python scripts/live_trader.py --auto                    # 스크리닝 결과 자동 로드
    python scripts/live_trader.py --invest-per-trade 500000 # 1회 투자금

필수 환경변수:
    KIWOOM_MOCK_APP_KEY, KIWOOM_MOCK_APP_SECRET
    KIWOOM_MOCK_ACCOUNT: 모의투자 계좌번호 (잔고 조회용)

동작:
    1. 종목별 52주 일봉 데이터 로드 (high_52w, avg_volume 산출)
    2. 5분 주기로 현재가 조회 → 진입/청산 신호 체크
    3. 조건 충족 시 시장가 주문 실행
    4. 14:30 미청산 포지션 강제 청산
    5. 15:35 자동 종료
"""

import argparse
import asyncio
import glob as glob_mod
import json
import logging
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.backtest.strategy import MomentumParams, check_entry_signal, check_exit_signal
from src.broker.constants import MOCK_BASE_URL
from src.broker.kiwoom import KiwoomClient
from src.broker.schemas import OrderRequest, OrderSideEnum, OrderTypeEnum

# ── 설정 ───────────────────────────────────────────────

RESULTS_DIR = Path("docs/backtest-results")
POLL_INTERVAL_SEC = 300  # 5분
MARKET_CLOSE_HHMM = "1535"  # 이 시각 이후 루프 종료
DEFAULT_INVEST_PER_TRADE = 500_000  # 1회 투자금 (원)

log = logging.getLogger("live_trader")


# ── 포지션 추적 ──────────────────────────────────────


@dataclass
class LivePosition:
    """실시간 보유 포지션."""

    symbol: str
    name: str
    entry_price: int
    quantity: int
    entry_time: str
    order_no: str


@dataclass
class TradeLog:
    """거래 기록."""

    symbol: str
    name: str
    side: str
    price: int
    quantity: int
    time: str
    order_no: str
    pnl_pct: float = 0.0
    exit_reason: str = ""


@dataclass
class TradingState:
    """트레이딩 상태."""

    positions: dict[str, LivePosition] = field(default_factory=dict)
    trades: list[TradeLog] = field(default_factory=list)
    daily_data: dict[str, dict] = field(default_factory=dict)  # {symbol: {high_52w, avg_volume}}


# ── 유틸 ──────────────────────────────────────────────


def setup_logging() -> None:
    """로깅 설정 (콘솔 + 파일)."""
    fmt = "%(asctime)s [%(levelname)s] %(message)s"
    datefmt = "%H:%M:%S"
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    log_path = RESULTS_DIR / f"live_{datetime.now().strftime('%Y%m%d')}.log"

    logging.basicConfig(
        level=logging.INFO,
        format=fmt,
        datefmt=datefmt,
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(log_path, encoding="utf-8"),
        ],
    )
    log.info("로그 파일: %s", log_path)


def get_env_or_exit(key: str) -> str:
    """환경변수를 읽거나 없으면 종료."""
    value = os.environ.get(key, "")
    if not value:
        log.error("환경변수 %s가 없습니다.", key)
        sys.exit(1)
    return value


def now_hhmm() -> str:
    """현재 시각을 HHMM 문자열로 반환."""
    return datetime.now().strftime("%H%M")


def load_screened_symbols() -> list[str]:
    """최근 스크리닝 결과에서 종목코드 로드."""
    pattern = str(RESULTS_DIR / "screened_*.json")
    files = sorted(glob_mod.glob(pattern))
    if not files:
        log.error("스크리닝 결과 파일 없음: %s", pattern)
        sys.exit(1)

    latest = files[-1]
    log.info("스크리닝 결과 로드: %s", latest)

    with open(latest, encoding="utf-8") as f:
        data = json.load(f)

    symbols = data.get("symbols", [])
    if not symbols:
        log.warning("스크리닝 통과 종목 없음")
        sys.exit(0)

    log.info("감시 종목 %d개: %s", len(symbols), ", ".join(symbols))
    return symbols


def _safe_int(v: str | int) -> int:
    """부호 접두사 포함 가격/수량 안전 변환."""
    if isinstance(v, int):
        return abs(v)
    s = str(v).lstrip("+-")
    return int(s) if s else 0


# ── 데이터 로드 ──────────────────────────────────────


async def load_daily_context(client: KiwoomClient, symbols: list[str]) -> dict[str, dict]:
    """종목별 52주 일봉 데이터에서 high_52w, avg_volume 추출."""
    from src.broker.constants import API_IDS, DEFAULT_EXCHANGE, ENDPOINTS
    from src.broker.schemas import to_kiwoom_symbol

    context: dict[str, dict] = {}

    for symbol in symbols:
        log.info("[%s] 일봉 로드 중...", symbol)
        all_raw: list[dict] = []
        qry_dt = datetime.now().strftime("%Y%m%d")

        for page in range(13):
            stk_cd = to_kiwoom_symbol(symbol, DEFAULT_EXCHANGE)
            try:
                data = await client._request(
                    ENDPOINTS["market"],
                    API_IDS["daily_price"],
                    json_body={"stk_cd": stk_cd, "qry_dt": qry_dt, "indc_tp": "0"},
                )
            except Exception:
                log.warning("[%s] 일봉 %d페이지 에러, 3초 대기 후 재시도", symbol, page)
                await asyncio.sleep(3)
                try:
                    data = await client._request(
                        ENDPOINTS["market"],
                        API_IDS["daily_price"],
                        json_body={"stk_cd": stk_cd, "qry_dt": qry_dt, "indc_tp": "0"},
                    )
                except Exception as e:
                    log.error("[%s] 일봉 재시도 실패: %s", symbol, e)
                    break

            items = data.get("daly_stkpc", [])
            if not items:
                break
            all_raw.extend(items)
            last_date = items[-1].get("date", "")
            if not last_date:
                break
            qry_dt = last_date
            await asyncio.sleep(0.5)

        if not all_raw:
            log.warning("[%s] 일봉 데이터 없음, 건너뜀", symbol)
            continue

        highs = [_safe_int(r.get("high_pric", 0)) for r in all_raw]
        volumes = [_safe_int(r.get("trde_qty", 0)) for r in all_raw]

        high_52w = max(highs) if highs else 0
        recent_20_vol = volumes[:20] if len(volumes) >= 20 else volumes
        avg_volume = sum(recent_20_vol) // len(recent_20_vol) if recent_20_vol else 0

        context[symbol] = {"high_52w": high_52w, "avg_volume": avg_volume}
        log.info(
            "[%s] 52주고가=%s, 평균거래량=%s (일봉 %d개)",
            symbol,
            f"{high_52w:,}",
            f"{avg_volume:,}",
            len(all_raw),
        )
        await asyncio.sleep(1)

    return context


# ── 매매 실행 ────────────────────────────────────────


async def execute_buy(
    client: KiwoomClient,
    symbol: str,
    name: str,
    price: int,
    invest_amount: int,
    state: TradingState,
) -> None:
    """시장가 매수 주문."""
    quantity = invest_amount // price
    if quantity <= 0:
        log.warning(
            "[%s] 투자금 %s원으로 1주도 못 삼 (현재가 %s원)",
            symbol,
            f"{invest_amount:,}",
            f"{price:,}",
        )
        return

    log.info(
        "[%s] 매수 주문: %d주 x %s원 = %s원",
        symbol,
        quantity,
        f"{price:,}",
        f"{price * quantity:,}",
    )

    try:
        resp = await client.place_order(
            OrderRequest(
                symbol=symbol,
                side=OrderSideEnum.BUY,
                price=0,  # 시장가
                quantity=quantity,
                order_type=OrderTypeEnum.MARKET,
            )
        )
        log.info("[%s] 매수 접수: 주문번호 %s", symbol, resp.order_no)

        state.positions[symbol] = LivePosition(
            symbol=symbol,
            name=name,
            entry_price=price,
            quantity=quantity,
            entry_time=datetime.now().strftime("%Y%m%d%H%M%S"),
            order_no=resp.order_no,
        )
        state.trades.append(
            TradeLog(
                symbol=symbol,
                name=name,
                side="BUY",
                price=price,
                quantity=quantity,
                time=datetime.now().strftime("%Y%m%d%H%M%S"),
                order_no=resp.order_no,
            )
        )
    except Exception as e:
        log.error("[%s] 매수 실패: %s", symbol, e)


async def execute_sell(
    client: KiwoomClient,
    pos: LivePosition,
    price: int,
    reason: str,
    state: TradingState,
    params: MomentumParams,
) -> None:
    """시장가 매도 주문."""
    log.info(
        "[%s] 매도 주문 (%s): %d주 x %s원 | 진입가 %s원",
        pos.symbol,
        reason,
        pos.quantity,
        f"{price:,}",
        f"{pos.entry_price:,}",
    )

    try:
        resp = await client.place_order(
            OrderRequest(
                symbol=pos.symbol,
                side=OrderSideEnum.SELL,
                price=0,
                quantity=pos.quantity,
                order_type=OrderTypeEnum.MARKET,
            )
        )
        log.info("[%s] 매도 접수: 주문번호 %s", pos.symbol, resp.order_no)

        pnl_gross = (price - pos.entry_price) / pos.entry_price if pos.entry_price > 0 else 0
        pnl_net = pnl_gross - (params.commission_rate * 2 + params.tax_rate)

        state.trades.append(
            TradeLog(
                symbol=pos.symbol,
                name=pos.name,
                side="SELL",
                price=price,
                quantity=pos.quantity,
                time=datetime.now().strftime("%Y%m%d%H%M%S"),
                order_no=resp.order_no,
                pnl_pct=round(pnl_net, 6),
                exit_reason=reason,
            )
        )
        del state.positions[pos.symbol]
    except Exception as e:
        log.error("[%s] 매도 실패: %s", pos.symbol, e)


# ── 메인 루프 ────────────────────────────────────────


async def poll_cycle(
    client: KiwoomClient,
    symbols: list[str],
    params: MomentumParams,
    state: TradingState,
    invest_per_trade: int,
) -> None:
    """1회 폴링 사이클: 전 종목 시세 조회 → 진입/청산 판단."""
    current_hhmm = now_hhmm()
    log.info("--- 폴링 %s ---", current_hhmm)

    for symbol in symbols:
        try:
            quote = await client.get_quote(symbol)
        except Exception as e:
            log.warning("[%s] 시세 조회 실패: %s", symbol, e)
            await asyncio.sleep(0.5)
            continue

        ctx = state.daily_data.get(symbol)
        if not ctx:
            await asyncio.sleep(0.3)
            continue

        high_52w = ctx["high_52w"]
        avg_volume = ctx["avg_volume"]

        # 1. 보유 중이면 청산 체크
        if symbol in state.positions:
            pos = state.positions[symbol]
            exit_reason = check_exit_signal(pos.entry_price, quote.price, current_hhmm, params)
            if exit_reason:
                await execute_sell(client, pos, quote.price, exit_reason, state, params)
                await asyncio.sleep(0.5)
                continue

        # 2. 미보유 + 최대 포지션 미달 → 진입 체크
        if (
            symbol not in state.positions
            and len(state.positions) < params.max_positions
            and check_entry_signal(quote.price, high_52w, quote.volume, avg_volume, params)
        ):
            await execute_buy(client, symbol, quote.name, quote.price, invest_per_trade, state)

        await asyncio.sleep(0.3)  # API 간 간격


async def run_trading_loop(
    client: KiwoomClient,
    symbols: list[str],
    params: MomentumParams,
    state: TradingState,
    invest_per_trade: int,
) -> None:
    """장중 매매 루프. 5분 간격 폴링, 15:35 이후 종료."""
    log.info("매매 루프 시작 (종료: %s)", MARKET_CLOSE_HHMM)

    while True:
        current = now_hhmm()

        # 장 종료 체크
        if current >= MARKET_CLOSE_HHMM:
            log.info("장 종료 시각 도달 (%s). 루프 종료.", current)
            break

        await poll_cycle(client, symbols, params, state, invest_per_trade)

        # 다음 폴링까지 대기
        log.info("다음 폴링까지 %d초 대기...", POLL_INTERVAL_SEC)
        await asyncio.sleep(POLL_INTERVAL_SEC)


async def force_close_all(
    client: KiwoomClient,
    state: TradingState,
    params: MomentumParams,
) -> None:
    """미청산 포지션 전량 강제 청산."""
    if not state.positions:
        log.info("미청산 포지션 없음")
        return

    log.info("미청산 포지션 %d개 강제 청산", len(state.positions))

    for symbol in list(state.positions.keys()):
        pos = state.positions[symbol]
        try:
            quote = await client.get_quote(symbol)
            await execute_sell(client, pos, quote.price, "end_of_day", state, params)
        except Exception as e:
            log.error("[%s] 강제 청산 실패: %s", symbol, e)
        await asyncio.sleep(0.5)


# ── 결과 저장 ────────────────────────────────────────


def save_results(state: TradingState, params: MomentumParams) -> None:
    """매매 결과 JSON 저장."""
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = RESULTS_DIR / f"live_{timestamp}.json"

    buys = [t for t in state.trades if t.side == "BUY"]
    sells = [t for t in state.trades if t.side == "SELL"]
    wins = [t for t in sells if t.pnl_pct > 0]

    output = {
        "run_at": datetime.now().isoformat(),
        "mode": "live_mock",
        "params": {
            "volume_ratio": params.volume_ratio,
            "stop_loss": params.stop_loss,
            "take_profit": params.take_profit,
            "high_52w_threshold": params.high_52w_threshold,
            "max_positions": params.max_positions,
        },
        "summary": {
            "total_buys": len(buys),
            "total_sells": len(sells),
            "win_rate": round(len(wins) / len(sells), 4) if sells else 0,
            "total_pnl_pct": round(sum(t.pnl_pct for t in sells), 6),
        },
        "trades": [
            {
                "symbol": t.symbol,
                "name": t.name,
                "side": t.side,
                "price": t.price,
                "quantity": t.quantity,
                "time": t.time,
                "order_no": t.order_no,
                "pnl_pct": t.pnl_pct,
                "exit_reason": t.exit_reason,
            }
            for t in state.trades
        ],
    }

    with open(path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    log.info("결과 저장: %s", path)


# ── 메인 ─────────────────────────────────────────────


async def main() -> None:
    """실시간 자동매매 실행."""
    parser = argparse.ArgumentParser(description="모의투자 실시간 자동매매")
    parser.add_argument("--symbols", default=None, help="종목코드 (쉼표 구분)")
    parser.add_argument("--auto", action="store_true", help="스크리닝 결과에서 종목 자동 로드")
    parser.add_argument("--volume-ratio", type=float, default=1.5, help="거래량 배수")
    parser.add_argument("--stop-loss", type=float, default=-0.005, help="손절 비율 (-0.5%%)")
    parser.add_argument("--take-profit", type=float, default=0.010, help="익절 비율 (+1.0%%)")
    parser.add_argument(
        "--invest-per-trade",
        type=int,
        default=DEFAULT_INVEST_PER_TRADE,
        help=f"1회 투자금 (기본: {DEFAULT_INVEST_PER_TRADE:,}원)",
    )
    parser.add_argument(
        "--poll-interval", type=int, default=POLL_INTERVAL_SEC, help="폴링 간격 (초)"
    )
    args = parser.parse_args()

    setup_logging()

    try:
        from dotenv import load_dotenv

        load_dotenv()
    except ImportError:
        pass

    if args.auto:
        symbols = load_screened_symbols()
    elif args.symbols:
        symbols = [s.strip() for s in args.symbols.split(",")]
    else:
        log.error("--symbols 또는 --auto 필수")
        sys.exit(1)

    params = MomentumParams(
        volume_ratio=args.volume_ratio,
        stop_loss=args.stop_loss,
        take_profit=args.take_profit,
    )

    global POLL_INTERVAL_SEC
    POLL_INTERVAL_SEC = args.poll_interval

    log.info("=" * 60)
    log.info("모멘텀 돌파 전략 — 모의투자 자동매매")
    log.info("실행: %s", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    log.info("=" * 60)
    log.info("종목        : %s", ", ".join(symbols))
    log.info("투자금/건   : %s원", f"{args.invest_per_trade:,}")
    log.info("폴링 간격   : %d초", POLL_INTERVAL_SEC)
    log.info(
        "파라미터    : vol_ratio=%s, SL=%s, TP=%s, max_pos=%d",
        params.volume_ratio,
        params.stop_loss,
        params.take_profit,
        params.max_positions,
    )
    log.info("=" * 60)

    app_key = get_env_or_exit("KIWOOM_MOCK_APP_KEY")
    app_secret = get_env_or_exit("KIWOOM_MOCK_APP_SECRET")

    client = KiwoomClient(
        base_url=MOCK_BASE_URL,
        app_key=app_key,
        app_secret=app_secret,
        is_mock=True,
    )

    state = TradingState()

    try:
        await client.authenticate()
        log.info("[OK] 토큰 발급 성공")

        # 52주 일봉 데이터 로드
        state.daily_data = await load_daily_context(client, symbols)
        if not state.daily_data:
            log.error("일봉 데이터 로드 실패. 종료.")
            return

        # 매매 루프
        await run_trading_loop(client, symbols, params, state, args.invest_per_trade)

        # 종료 시 미청산 강제 청산
        await force_close_all(client, state, params)

    except KeyboardInterrupt:
        log.info("사용자 중단 (Ctrl+C)")
        await force_close_all(client, state, params)
    finally:
        await client.close()

    # 결과 저장 + 요약
    save_results(state, params)

    sells = [t for t in state.trades if t.side == "SELL"]
    log.info("=" * 60)
    log.info("매매 요약")
    log.info("=" * 60)
    log.info("총 매수: %d건", sum(1 for t in state.trades if t.side == "BUY"))
    log.info("총 매도: %d건", len(sells))
    if sells:
        wins = [t for t in sells if t.pnl_pct > 0]
        total_pnl = sum(t.pnl_pct for t in sells)
        log.info("승률   : %.1f%%", len(wins) / len(sells) * 100)
        log.info("총 손익: %+.2f%%", total_pnl * 100)
    log.info("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
