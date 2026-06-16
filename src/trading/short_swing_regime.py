"""Short-swing regime overlay (PR B: mock-only safety).

한국장 regime label 을 short_swing 후보 필터/강도 조절에 연결한다.

정책 (mock 한정 1차 정책 — live_trader 가동 데이터 누적 전 안전 우선):

| regime           | allow_new_entry | max_new_entries_override |
|------------------|-----------------|---------------------------|
| risk_off         | False           | 0 (신규 진입 차단)        |
| bull_overheat    | True            | 1 (추격 과열 제한)        |
| volatile_bull    | True            | None (기본)               |
| structural_bull  | True            | None (기본)               |
| neutral / 미상   | True            | None (기본)               |

regime snapshot 은 `outputs/regime/<DATE>/regime_report.json` 에서 로드한다
(daily regime dry-run 산출물, gitignored). 로드 실패/파일 없음이면 None 반환 →
호출자는 regime 미적용 (보수 기본값) 으로 진행.

short_swing 은 daily_candles 미사용이지만 regime overlay 는 거시 시장 상태를
반영해 mock-only 첫 가동에서 위험 노출을 제한한다. boost_sell/review_sell 같은
ai_hedge bias 는 본 모듈이 다루지 않는다 (별도 lab observation 영역).
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import date
from pathlib import Path

log = logging.getLogger(__name__)

_REGIME_OUTPUT_ROOT = Path(__file__).resolve().parents[2] / "outputs" / "regime"


@dataclass(frozen=True)
class RegimeSnapshot:
    """regime_report.json 의 current_regime 발췌."""

    regime: str
    confidence: int


@dataclass(frozen=True)
class RegimeOverlay:
    """short_swing 진입에 적용할 regime 제약."""

    regime: str | None
    allow_new_entry: bool
    max_new_entries_override: int | None
    reason: str

    @classmethod
    def neutral(cls) -> RegimeOverlay:
        return cls(
            regime=None,
            allow_new_entry=True,
            max_new_entries_override=None,
            reason="regime_unknown_default_allow",
        )


def load_current_regime(as_of: date, root: Path | None = None) -> RegimeSnapshot | None:
    """`outputs/regime/<as_of>/regime_report.json` 의 current_regime 발췌.

    daily regime dry-run 이 같은 날 실행됐다면 산출물이 존재한다.
    파일 없음 / 파싱 실패 / 키 누락 시 None 반환 (호출자가 안전 기본값으로).
    """
    base = root if root is not None else _REGIME_OUTPUT_ROOT
    path = base / as_of.isoformat() / "regime_report.json"
    if not path.exists():
        log.info("regime_report.json 미존재 → regime overlay 미적용 (%s)", path)
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        log.warning("regime_report.json 로드 실패 → 미적용: %s", exc)
        return None

    current = payload.get("current_regime") if isinstance(payload, dict) else None
    if not isinstance(current, dict):
        log.warning("regime_report.json 형식 오류 (current_regime 누락) → 미적용")
        return None

    regime = current.get("regime")
    confidence = current.get("confidence")
    if not isinstance(regime, str):
        return None
    return RegimeSnapshot(
        regime=regime,
        confidence=int(confidence) if isinstance(confidence, (int, float)) else 0,
    )


def regime_overlay_decision(snapshot: RegimeSnapshot | None) -> RegimeOverlay:
    """regime label → short_swing 진입 제약 결정.

    snapshot None 이면 기본 허용 (`neutral`). 정책은 모듈 docstring 참조.
    """
    if snapshot is None:
        return RegimeOverlay.neutral()

    regime = snapshot.regime

    if regime == "risk_off":
        return RegimeOverlay(
            regime=regime,
            allow_new_entry=False,
            max_new_entries_override=0,
            reason="regime_block_risk_off",
        )
    if regime == "bull_overheat":
        return RegimeOverlay(
            regime=regime,
            allow_new_entry=True,
            max_new_entries_override=1,
            reason="regime_limit_bull_overheat",
        )
    # volatile_bull / structural_bull / neutral / 기타 → 허용 (override 없음)
    return RegimeOverlay(
        regime=regime,
        allow_new_entry=True,
        max_new_entries_override=None,
        reason=f"regime_allow_{regime}",
    )
