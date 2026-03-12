"""백테스트/매매 결과 조회 라우터."""

import json
from pathlib import Path

from fastapi import APIRouter, HTTPException

from src.api.deps import CurrentUser

router = APIRouter(prefix="/results", tags=["매매결과"])

RESULTS_DIR = Path(__file__).resolve().parents[3] / "docs" / "backtest-results"


@router.get("/list")
async def list_results(
    _current_user: CurrentUser,
) -> list[dict[str, str]]:
    """docs/backtest-results/ 디렉토리의 JSON 파일 목록을 반환한다."""
    if not RESULTS_DIR.exists():
        return []

    files = sorted(RESULTS_DIR.glob("backtest_*.json"), reverse=True)
    return [{"filename": f.name, "modified_at": f.stat().st_mtime.__str__()} for f in files]


@router.get("/{filename}")
async def get_result(
    filename: str,
    _current_user: CurrentUser,
) -> dict:
    """개별 JSON 파일 내용을 반환한다."""
    # 경로 조작 방지
    if "/" in filename or "\\" in filename or ".." in filename:
        raise HTTPException(status_code=400, detail="잘못된 파일명입니다.")

    filepath = RESULTS_DIR / filename
    if not filepath.exists() or not filepath.suffix == ".json":
        raise HTTPException(status_code=404, detail="파일을 찾을 수 없습니다.")

    with filepath.open(encoding="utf-8") as f:
        return json.load(f)
