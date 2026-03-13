"""매매 제어 라우터 (KillSwitch: soft-stop, hard-stop, resume, status)."""

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from src.api.deps import CurrentUser
from src.trading.kill_switch import KillSwitchStatus, kill_switch

router = APIRouter(prefix="/trading", tags=["매매 제어"])


# ── Pydantic 스키마 ──────────────────────────────────────


class KillSwitchStatusResponse(BaseModel):
    """KillSwitch 상태 응답."""

    status: KillSwitchStatus
    user_id: str


class HardStopRequest(BaseModel):
    """hard-stop 요청 (confirm 필수)."""

    confirm: bool = Field(
        default=False,
        description="True 필수 — 전량 청산은 되돌릴 수 없습니다",
    )


# ── 엔드포인트 ────────────────────────────────────────────


@router.post(
    "/soft-stop",
    response_model=KillSwitchStatusResponse,
    status_code=status.HTTP_200_OK,
)
async def soft_stop(
    current_user: CurrentUser,
) -> KillSwitchStatusResponse:
    """신규 매수를 중단한다. 보유분은 전략대로 청산 가능."""
    new_status = kill_switch.soft_stop(current_user.id)
    return KillSwitchStatusResponse(
        status=new_status,
        user_id=str(current_user.id),
    )


@router.post(
    "/hard-stop",
    response_model=KillSwitchStatusResponse,
    status_code=status.HTTP_200_OK,
)
async def hard_stop(
    body: HardStopRequest,
    current_user: CurrentUser,
) -> KillSwitchStatusResponse:
    """전량 시장가 청산 + 매매 완전 중단.

    confirm=True 필수. 이 액션은 즉시 적용되며 되돌릴 수 없습니다.
    """
    try:
        new_status = kill_switch.hard_stop(current_user.id, confirm=body.confirm)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e

    return KillSwitchStatusResponse(
        status=new_status,
        user_id=str(current_user.id),
    )


@router.get(
    "/kill-switch-status",
    response_model=KillSwitchStatusResponse,
)
async def get_kill_switch_status(
    current_user: CurrentUser,
) -> KillSwitchStatusResponse:
    """현재 KillSwitch 상태를 조회한다."""
    current_status = kill_switch.get_status(current_user.id)
    return KillSwitchStatusResponse(
        status=current_status,
        user_id=str(current_user.id),
    )


@router.post(
    "/resume",
    response_model=KillSwitchStatusResponse,
    status_code=status.HTTP_200_OK,
)
async def resume(
    current_user: CurrentUser,
) -> KillSwitchStatusResponse:
    """KillSwitch를 해제하고 정상 매매 상태로 복귀한다."""
    new_status = kill_switch.resume(current_user.id)
    return KillSwitchStatusResponse(
        status=new_status,
        user_id=str(current_user.id),
    )
