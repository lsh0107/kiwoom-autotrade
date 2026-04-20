"""UNIVERSE 무결성 테스트.

스크리닝 유니버스(scripts.screen_symbols.UNIVERSE)의 불변 조건을 보호한다:
- 정확히 140개 종목
- 소스 리터럴에 중복 키 없음 (Python dict이 자동 dedupe 해버리기 전에 감지)
"""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

from scripts.screen_symbols import UNIVERSE


def test_universe_has_exactly_140_entries() -> None:
    """UNIVERSE 크기는 정확히 140."""
    assert len(UNIVERSE) == 140, (
        f"UNIVERSE 크기 변경: {len(UNIVERSE)}개 (기대 140). "
        "의도한 변경이면 이 테스트의 기대값을 함께 업데이트하세요."
    )


def test_universe_source_has_no_duplicate_keys() -> None:
    """소스 파일에 중복 종목코드가 리터럴로 나타나지 않아야 한다.

    Python dict은 중복 키를 자동으로 dedupe 하기 때문에 `len(UNIVERSE)`만으로는
    실수로 같은 키를 두 번 적은 경우를 감지할 수 없다. 소스를 직접 파싱해서 검증.
    """
    src_path = Path(__file__).resolve().parents[1] / "scripts" / "screen_symbols.py"
    src = src_path.read_text(encoding="utf-8")

    m = re.search(
        r"UNIVERSE\s*:\s*dict\[str,\s*str\]\s*=\s*(\{.+?\n\})",
        src,
        re.DOTALL,
    )
    assert m is not None, "screen_symbols.py에서 UNIVERSE 리터럴을 찾지 못했습니다."

    body = m.group(1)
    # 6자리 종목코드 키만 추출
    keys = re.findall(r'"(\d{6})"\s*:', body)

    assert len(keys) == 140, (
        f"UNIVERSE 리터럴 키 개수: {len(keys)} (기대 140). "
        "항목을 추가·삭제하면 이 테스트 기대값도 함께 갱신하세요."
    )

    dupes = {k: c for k, c in Counter(keys).items() if c > 1}
    assert not dupes, f"UNIVERSE에 중복된 종목코드 키가 있습니다: {dupes}"


def test_universe_keys_are_six_digit_strings() -> None:
    """모든 키는 6자리 숫자 문자열."""
    bad = [k for k in UNIVERSE if not (isinstance(k, str) and len(k) == 6 and k.isdigit())]
    assert not bad, f"올바르지 않은 종목코드 포맷: {bad}"
