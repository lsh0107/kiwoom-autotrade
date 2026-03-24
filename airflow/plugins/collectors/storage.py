"""데이터 저장 유틸리티."""

from __future__ import annotations

import json
import logging
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

DATA_DIR = Path(os.environ.get("KIWOOM_DATA_DIR", "data"))


def _get_db_conn() -> Any:
    """DB 연결 반환. AIRFLOW_CONN_KIWOOM_DB 또는 DATABASE_URL 환경변수 사용.

    Returns:
        psycopg2 connection 객체.

    Raises:
        ValueError: DB 연결 정보 미설정 시.
        ImportError: psycopg2 미설치 시.
    """
    # 연결 정보를 먼저 확인 (psycopg2 import 전)
    conn_uri = os.environ.get("AIRFLOW_CONN_KIWOOM_DB")
    if not conn_uri:
        conn_uri = os.environ.get("DATABASE_URL")
    if not conn_uri:
        raise ValueError("AIRFLOW_CONN_KIWOOM_DB 또는 DATABASE_URL 미설정")

    import psycopg2

    # SQLAlchemy 드라이버 접두사 제거: postgresql+XXX://... → postgresql://...
    conn_uri = conn_uri.replace("postgresql+psycopg2://", "postgresql://")
    conn_uri = conn_uri.replace("postgresql+asyncpg://", "postgresql://")
    conn_uri = conn_uri.replace("postgres+psycopg2://", "postgresql://")
    conn_uri = conn_uri.replace("postgres+asyncpg://", "postgresql://")
    conn_uri = conn_uri.replace("postgres://", "postgresql://")

    return psycopg2.connect(conn_uri)


def save_json(category: str, date_str: str, data: Any) -> Path:
    """JSON 데이터 저장.

    Args:
        category: 데이터 카테고리 (예: "premarket", "news").
        date_str: 날짜 문자열 (예: "20250101").
        data: 저장할 데이터.

    Returns:
        저장된 파일 경로.
    """
    path = DATA_DIR / category / f"{date_str}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=str)
    logger.info("저장 완료: %s", path)
    return path


def load_json(category: str, date_str: str) -> Any:
    """JSON 데이터 로드.

    Args:
        category: 데이터 카테고리.
        date_str: 날짜 문자열.

    Returns:
        로드된 데이터. 파일이 없으면 None.
    """
    path = DATA_DIR / category / f"{date_str}.json"
    if not path.exists():
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_market_data(category: str, date: str, data: Any) -> None:
    """시장 데이터를 DB market_data 테이블에 upsert.

    JSON 파일 저장 후 DB에 upsert한다. DB 저장 실패 시 예외를 발생시켜
    Airflow 태스크를 실패 처리하고 Asset 발행을 차단한다.

    Args:
        category: 데이터 카테고리 (예: "premarket", "macro").
        date: 날짜 문자열 (YYYYMMDD 형식).
        data: 저장할 데이터 (JSON 직렬화 가능).

    Raises:
        RuntimeError: DB 저장 실패 시.
    """
    # JSON 파일 저장 (로컬 백업)
    save_json(category, date, data)

    # DB 저장 — 실패 시 예외 전파하여 태스크 실패 처리
    try:
        conn = _get_db_conn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO market_data (id, category, date, data, collected_at, updated_at)
                    VALUES (gen_random_uuid(), %s, %s, %s, NOW(), NOW())
                    ON CONFLICT (category, date)
                    DO UPDATE SET data = EXCLUDED.data, updated_at = NOW()
                    """,
                    (category, date, json.dumps(data, ensure_ascii=False, default=str)),
                )
            conn.commit()
            logger.info("DB 저장 완료: market_data category=%s date=%s", category, date)
        finally:
            conn.close()
    except Exception as exc:
        raise RuntimeError(f"시장 데이터 DB 저장 실패: category={category}, date={date}") from exc


def save_news_articles(articles: list[dict]) -> None:
    """뉴스 기사 목록을 DB news_articles 테이블에 bulk insert.

    중복 URL은 ON CONFLICT DO NOTHING으로 스킵한다.
    DB 저장 실패 시 경고 로그 후 계속 진행.

    Args:
        articles: 뉴스 기사 목록. 네이버 API 응답 형식(link/pubDate) 및
                  정규화 형식(url/published_at) 모두 지원.
    """
    if not articles:
        logger.debug("저장할 뉴스 기사 없음")
        return

    try:
        conn = _get_db_conn()
        try:
            with conn.cursor() as cur:
                for article in articles:
                    # 네이버 API: link/pubDate, 정규화: url/published_at 양쪽 지원
                    url = article.get("url") or article.get("link", "")
                    published_at = (
                        article.get("published_at")
                        or article.get("publishedAt")
                        or article.get("pubDate")
                    )
                    cur.execute(
                        """
                        INSERT INTO news_articles
                            (id, keyword, title, url, description,
                             sentiment, published_at, collected_at, created_at, updated_at)
                        VALUES (gen_random_uuid(), %s, %s, %s, %s, %s, %s, NOW(), NOW(), NOW())
                        ON CONFLICT (url) DO NOTHING
                        """,
                        (
                            article.get("keyword", ""),
                            article.get("title", ""),
                            url,
                            article.get("description", ""),
                            article.get("sentiment", "neutral"),
                            published_at,
                        ),
                    )
            conn.commit()
            logger.info("DB 저장 완료: news_articles %d건", len(articles))
        finally:
            conn.close()
    except Exception as exc:
        logger.warning("DB 저장 실패 (news_articles): %s", exc)


def save_briefing(date_str: str, briefing: dict) -> None:
    """브리핑 결과를 JSON 파일 + DB llm_briefings 테이블에 저장.

    date_str 기준으로 유니크하며, 같은 날짜가 존재하면 모든 컬럼을 덮어쓴다.

    Args:
        date_str: 날짜 문자열 (YYYYMMDD 형식).
        briefing: 브리핑 결과 딕셔너리.
            - summary (str): 시장 요약
            - theme_scores (dict): 테마별 점수
            - risk_flags (list): 리스크 플래그 목록
            - weight_adjustments (dict): 비중 조정 제안
            - raw_response (str): LLM 원본 응답
            - provider (str): LLM 공급자
            - model (str): 사용된 모델명

    Raises:
        RuntimeError: DB 저장 실패 시.
    """
    # JSON 파일 저장 (로컬 백업)
    save_json("briefing", date_str, briefing)

    # 날짜 형식 변환 (YYYYMMDD → YYYY-MM-DD)
    date_iso = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]}"

    try:
        conn = _get_db_conn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO llm_briefings
                        (id, date, summary, theme_scores, risk_flags,
                         weight_adjustments, raw_response, provider, model,
                         created_at, updated_at)
                    VALUES (
                        gen_random_uuid(), %s, %s, %s, %s, %s, %s, %s, %s,
                        NOW(), NOW()
                    )
                    ON CONFLICT (date) DO UPDATE SET
                        summary           = EXCLUDED.summary,
                        theme_scores      = EXCLUDED.theme_scores,
                        risk_flags        = EXCLUDED.risk_flags,
                        weight_adjustments = EXCLUDED.weight_adjustments,
                        raw_response      = EXCLUDED.raw_response,
                        provider          = EXCLUDED.provider,
                        model             = EXCLUDED.model,
                        updated_at        = NOW()
                    """,
                    (
                        date_iso,
                        briefing.get("summary", ""),
                        json.dumps(briefing.get("theme_scores", {}), ensure_ascii=False),
                        json.dumps(briefing.get("risk_flags", []), ensure_ascii=False),
                        json.dumps(briefing.get("weight_adjustments", {}), ensure_ascii=False),
                        briefing.get("raw_response", ""),
                        briefing.get("provider", ""),
                        briefing.get("model", ""),
                    ),
                )
            conn.commit()
            logger.info("DB 저장 완료: llm_briefings date=%s", date_iso)
        finally:
            conn.close()
    except Exception as exc:
        raise RuntimeError(f"브리핑 DB 저장 실패: date={date_str}") from exc


def save_trade_review(date_str: str, review: dict) -> None:
    """리뷰 결과를 JSON 파일 + DB trade_reviews 테이블에 저장.

    date_str 기준으로 유니크하며, 같은 날짜가 존재하면 모든 컬럼을 덮어쓴다.

    Args:
        date_str: 날짜 문자열 (YYYYMMDD 형식).
        review: 리뷰 결과 딕셔너리.
            - summary (str): 매매 리뷰 요약
            - performance_analysis (str): 성과 분석
            - risk_assessment (str): 리스크 평가
            - suggestions (list): 파라미터 개선 제안 목록
            - raw_response (str): LLM 원본 응답
            - provider (str): LLM 공급자
            - model (str): 사용된 모델명

    Raises:
        RuntimeError: DB 저장 실패 시.
    """
    # JSON 파일 저장 (로컬 백업)
    save_json("review", date_str, review)

    # 날짜 형식 변환 (YYYYMMDD → YYYY-MM-DD)
    date_iso = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]}"

    try:
        conn = _get_db_conn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO trade_reviews
                        (id, date, summary, performance_analysis, risk_assessment,
                         suggestions, raw_response, provider, model,
                         created_at, updated_at)
                    VALUES (
                        gen_random_uuid(), %s, %s, %s, %s, %s, %s, %s, %s,
                        NOW(), NOW()
                    )
                    ON CONFLICT (date) DO UPDATE SET
                        summary              = EXCLUDED.summary,
                        performance_analysis = EXCLUDED.performance_analysis,
                        risk_assessment      = EXCLUDED.risk_assessment,
                        suggestions          = EXCLUDED.suggestions,
                        raw_response         = EXCLUDED.raw_response,
                        provider             = EXCLUDED.provider,
                        model                = EXCLUDED.model,
                        updated_at           = NOW()
                    """,
                    (
                        date_iso,
                        review.get("summary", ""),
                        review.get("performance_analysis", ""),
                        review.get("risk_assessment", ""),
                        json.dumps(review.get("suggestions", []), ensure_ascii=False),
                        review.get("raw_response", ""),
                        review.get("provider", ""),
                        review.get("model", ""),
                    ),
                )
            conn.commit()
            logger.info("DB 저장 완료: trade_reviews date=%s", date_iso)
        finally:
            conn.close()
    except Exception as exc:
        raise RuntimeError(f"리뷰 DB 저장 실패: date={date_str}") from exc


def save_decision(date_str: str, decision: dict) -> None:
    """LLM 투자 결정을 DB llm_decisions 테이블에 저장.

    Args:
        date_str: 날짜 문자열 (YYYYMMDD 형식).
        decision: 결정 딕셔너리.
            - decision_type (str): weight_adjust, risk_mode, param_tune, stock_swap
            - context_source (str): overnight, premarket, postmarket
            - content (dict): 결정 내용
            - confidence (float): 신뢰도 0~1
            - raw_response (str): LLM 원본 응답

    Raises:
        RuntimeError: DB 저장 실패 시.
    """
    date_iso = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]}"

    try:
        conn = _get_db_conn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO llm_decisions
                        (id, date, decision_type, context_source, content,
                         confidence, status, raw_response, created_at, updated_at)
                    VALUES (
                        gen_random_uuid(), %s, %s, %s, %s, %s, 'pending', %s,
                        NOW(), NOW()
                    )
                    """,
                    (
                        date_iso,
                        decision.get("decision_type", "weight_adjust"),
                        decision.get("context_source", "premarket"),
                        json.dumps(decision.get("content", {}), ensure_ascii=False),
                        decision.get("confidence"),
                        decision.get("raw_response", ""),
                    ),
                )
            conn.commit()
            logger.info(
                "DB 저장 완료: llm_decisions date=%s type=%s",
                date_iso,
                decision.get("decision_type"),
            )
        finally:
            conn.close()
    except Exception as exc:
        raise RuntimeError(f"결정 DB 저장 실패: date={date_str}") from exc


def today_str() -> str:
    """오늘 날짜 문자열 반환 (YYYYMMDD, KST 기준).

    Returns:
        오늘 날짜 문자열 (예: "20250101").
    """
    kst = datetime.now(tz=UTC) + timedelta(hours=9)
    return kst.strftime("%Y%m%d")
