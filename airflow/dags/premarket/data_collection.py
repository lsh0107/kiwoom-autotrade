"""장전 데이터 수집 DAG.

평일 08:00에 DART 공시, FRED 거시경제, 해외 지수를 병렬 수집한다.
수집 완료 후 Asset("premarket_data")을 발행해 llm_briefing DAG를 트리거한다.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from airflow.sdk import Asset, dag, task

from callbacks.telegram import on_failure_telegram

premarket_dataset = Asset("premarket_data")


@dag(
    dag_id="premarket_data_collection",
    schedule="0 8 * * 1-5",  # 평일 08:00 장전 데이터 수집 (KST)
    start_date=datetime(2026, 1, 1, tzinfo=UTC),
    catchup=False,
    default_args={
        "retries": 2,
        "retry_delay": timedelta(minutes=5),
        "on_failure_callback": on_failure_telegram,
        "execution_timeout": timedelta(minutes=30),
    },
    tags=["premarket", "data", "tier1"],
)
def premarket_data_collection() -> None:
    """장전 데이터 수집 파이프라인."""

    @task()
    def fetch_dart() -> list[dict]:
        """DART 전자공시 수집."""
        from collectors.dart import collect_disclosures

        return collect_disclosures(days=1)

    @task()
    def fetch_fred() -> dict:
        """FRED 거시경제 지표 수집 (VIX, 금리, 환율, WTI)."""
        from collectors.fred import collect_macro

        return collect_macro()

    @task()
    def fetch_overseas() -> dict:
        """해외 주요 지수 수집 (S&P500, 나스닥, 닛케이 등)."""
        from collectors.overseas import collect_indices

        return collect_indices()

    @task()
    def fetch_vkospi() -> dict:
        """VKOSPI(한국 변동성지수) 수집."""
        from collectors.storage import today_str
        from collectors.vkospi import collect_vkospi

        return collect_vkospi(date=today_str())

    @task()
    def fetch_kospi_regime() -> dict:
        """KOSPI MA12 기반 레짐 수집."""
        from collectors.storage import today_str
        from collectors.vkospi import collect_kospi_regime

        return collect_kospi_regime(date=today_str())

    @task()
    def fetch_investor_trading_kospi() -> list[dict]:
        """KOSPI 시장 전체 투자자별 매매 수집."""
        from collectors.krx import collect_investor_trading
        from collectors.storage import today_str

        return collect_investor_trading(date=today_str(), market="KOSPI")

    @task()
    def fetch_investor_trading_kosdaq() -> list[dict]:
        """KOSDAQ 시장 전체 투자자별 매매 수집."""
        from collectors.krx import collect_investor_trading
        from collectors.storage import today_str

        return collect_investor_trading(date=today_str(), market="KOSDAQ")

    @task()
    def fetch_stock_investor_flow() -> dict:
        """종목별 외국인/기관 순매수 수집."""
        from collectors.investor_flow import collect_stock_investor_flow, load_watch_symbols
        from collectors.storage import today_str

        date_str = today_str()
        symbols = load_watch_symbols()
        return collect_stock_investor_flow(date=date_str, symbols=symbols)

    @task(outlets=[premarket_dataset])
    def store(
        dart: list[dict],
        fred: dict,
        overseas: dict,
        vkospi: dict,
        kospi_regime: dict,
        investor_trading_kospi: list[dict],
        investor_trading_kosdaq: list[dict],
        stock_investor_flow: dict,
    ) -> None:
        """수집 결과 통합 저장 (JSON + DB) 및 Dataset 발행."""
        from collectors.storage import save_json, save_market_data, today_str

        date_str = today_str()
        data = {
            "dart": dart,
            "fred": fred,
            "overseas": overseas,
            "vkospi": vkospi,
            "kospi_regime": kospi_regime,
            "investor_trading_kospi": investor_trading_kospi,
            "investor_trading_kosdaq": investor_trading_kosdaq,
            "stock_investor_flow": stock_investor_flow,
        }
        # JSON 파일 저장 (로컬 개발 편의)
        save_json("premarket", date_str, data)
        # DB 저장 (카테고리별 upsert)
        save_market_data("dart_disclosure", date_str, dart)
        save_market_data("fred_macro", date_str, fred)
        save_market_data("overseas_index", date_str, overseas)
        save_market_data("vkospi", date_str, vkospi)
        save_market_data("kospi_regime", date_str, kospi_regime)
        save_market_data("investor_trading", date_str, investor_trading_kospi)
        save_market_data("investor_trading_kosdaq", date_str, investor_trading_kosdaq)
        save_market_data("stock_investor_flow", date_str, stock_investor_flow)

    store(
        dart=fetch_dart(),
        fred=fetch_fred(),
        overseas=fetch_overseas(),
        vkospi=fetch_vkospi(),
        kospi_regime=fetch_kospi_regime(),
        investor_trading_kospi=fetch_investor_trading_kospi(),
        investor_trading_kosdaq=fetch_investor_trading_kosdaq(),
        stock_investor_flow=fetch_stock_investor_flow(),
    )


premarket_data_collection()
