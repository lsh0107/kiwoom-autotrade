"""scripts/post_merge_rebuild.sh 경로 분류 단위 테스트.

bash 스크립트 자체를 ``--classify <path>`` 모드로 호출해 stdout 결과를
검증한다. docker / git 의존 없음. 메인 재빌드 루프는 호출하지 않는다.

분류 규칙 (스크립트 정책):
    frontend/*                                              → frontend
    scripts/*.py, src/*, alembic/*, pyproject.toml,         → backend
    uv.lock, Dockerfile.backend
    airflow/*                                               → airflow
    그 외 (scripts/*.sh 같은 운영 스크립트)                  → none
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "post_merge_rebuild.sh"


def _classify(path: str) -> str:
    """bash 스크립트 ``--classify`` 모드 호출 후 stdout strip 반환."""
    # subprocess 인자는 모두 신뢰된 테스트 데이터(고정 SCRIPT + parametrize 값).
    result = subprocess.run(  # noqa: S603
        ["bash", str(SCRIPT), "--classify", path],  # noqa: S607
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


# ── backend 트리거 케이스 ───────────────────────────────────────────


@pytest.mark.parametrize(
    "path",
    [
        "scripts/foo.py",
        "scripts/live_trader.py",
        "src/api/v1/decisions.py",
        "src/trading/llm_auto_approval.py",
        "alembic/versions/abc_init.py",
        # alembic.ini 는 backend 트리거 매칭 키워드에 없음 → none (스크립트 정책 의도적)
        "alembic.ini",
        "pyproject.toml",
        "uv.lock",
        "Dockerfile.backend",
    ],
)
def test_backend_paths_classified_as_backend_or_none(path: str) -> None:
    """backend 트리거 대상 + ini 같은 비대상 구분."""
    expected = "backend"
    if path == "alembic.ini":
        # alembic.ini 는 정책상 backend 트리거 매칭 키워드에 없음 → none
        expected = "none"
    assert _classify(path) == expected


# ── 운영 스크립트 (.sh 등) — backend 트리거하지 않음 ────────────────


@pytest.mark.parametrize(
    "path",
    [
        "scripts/post_merge_rebuild.sh",
        "scripts/release.sh",
        "scripts/notes.md",
        "scripts/some-config.yml",
    ],
)
def test_operational_scripts_not_backend(path: str) -> None:
    """scripts/*.py 외의 운영 스크립트는 backend 재빌드 트리거 X."""
    assert _classify(path) == "none"


# ── frontend ─────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "path",
    [
        "frontend/src/app/(authenticated)/decisions/page.tsx",
        "frontend/package.json",
        "frontend/__tests__/smoke/decisions.test.tsx",
    ],
)
def test_frontend_paths(path: str) -> None:
    assert _classify(path) == "frontend"


# ── airflow (감지만, 자동 재빌드 X) ──────────────────────────────────


@pytest.mark.parametrize(
    "path",
    [
        "airflow/dags/screen_universe.py",
        "airflow/plugins/foo.py",
    ],
)
def test_airflow_paths(path: str) -> None:
    assert _classify(path) == "airflow"


# ── 무관 경로 ────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "path",
    [
        ".claude/rules/post-merge-rebuild.md",
        "CLAUDE.md",
        "README.md",
        "docs/foo.md",
        "tests/scripts/test_post_merge_rebuild_sh.py",  # 테스트 자체 변경은 영향 없음
    ],
)
def test_unrelated_paths_none(path: str) -> None:
    assert _classify(path) == "none"


# ── --classify usage 에러 ────────────────────────────────────────────


def test_classify_requires_path_arg() -> None:
    result = subprocess.run(  # noqa: S603
        ["bash", str(SCRIPT), "--classify"],  # noqa: S607
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 2
    assert "usage" in (result.stderr + result.stdout).lower()
