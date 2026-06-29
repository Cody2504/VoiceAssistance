from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from cm_shared.auth import TokenPayload, require_admin
from cm_shared.db import get_session
from cm_shared.response import success_response
from main.app.db.models.eval import EvalCase, EvalRun
from main.app.services.eval_service import RunInProgressError, start_run

router = APIRouter(prefix="/api/v1/admin/eval", tags=["admin-eval"])


class NewRunBody(BaseModel):
    kind: str = "curated"          # curated (only kind built now)
    mode: str = "fake"             # fake | live
    judge: bool = True
    limit: int | None = None
    tools: list[str] | None = None
    golden_ids: list[str] | None = None   # "run selected": only these cases


class CaseEdit(BaseModel):
    expected_tool: str | None = None
    expected_args: dict | None = None
    reference_answer: str | None = None


def _run_dict(r: EvalRun) -> dict:
    return {
        "id": str(r.id), "kind": r.kind, "mode": r.mode, "judge_on": r.judge_on,
        "status": r.status, "created_at": r.created_at.isoformat() if r.created_at else None,
        "finished_at": r.finished_at.isoformat() if r.finished_at else None,
        "error": r.error, "summary": r.summary,
    }


def _case_dict(c: EvalCase) -> dict:
    return {
        "id": str(c.id), "golden_id": c.golden_id, "query": c.query, "source": c.source,
        "expected_tool": c.expected_tool, "expected_args": c.expected_args,
        "reference_answer": c.reference_answer,
        "predicted_tool": c.predicted_tool, "tool_correct": c.tool_correct,
        "arg_ok": c.arg_ok, "task_completion": c.task_completion,
        "answer_relevancy": c.answer_relevancy,
    }


@router.post("/runs")
async def create_run(
    body: NewRunBody,
    payload: TokenPayload = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    if body.kind != "curated":
        raise HTTPException(400, "Only 'curated' runs are supported")
    try:
        run = await start_run(
            session, kind=body.kind, mode=body.mode, judge=body.judge,
            limit=body.limit, tools=set(body.tools) if body.tools else None,
            golden_ids=set(body.golden_ids) if body.golden_ids else None,
            created_by=UUID(payload.sub))
    except RunInProgressError:
        raise HTTPException(409, "An evaluation run is already in progress")
    return success_response(_run_dict(run))


@router.patch("/cases/{case_id}")
async def edit_case(
    case_id: UUID,
    body: CaseEdit,
    payload: TokenPayload = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    """Edit a case's ground truth (expected tool/args/answer). Re-derives
    tool_correct from the new expected tool vs the stored predicted tool."""
    case = await session.get(EvalCase, case_id)
    if case is None:
        raise HTTPException(404, "Case not found")
    data = body.model_dump(exclude_unset=True)
    if "expected_tool" in data:
        case.expected_tool = data["expected_tool"]
    if "expected_args" in data:
        case.expected_args = data["expected_args"]
    if "reference_answer" in data:
        case.reference_answer = data["reference_answer"]
    if case.expected_tool is not None and case.predicted_tool is not None:
        case.tool_correct = case.expected_tool == case.predicted_tool
    await session.commit()
    return success_response(_case_dict(case))


@router.get("/runs")
async def list_runs(
    payload: TokenPayload = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    rows = (await session.execute(
        select(EvalRun).order_by(EvalRun.created_at.desc()))).scalars().all()
    return success_response([_run_dict(r) for r in rows])


@router.get("/runs/{run_id}")
async def get_run(
    run_id: UUID,
    payload: TokenPayload = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    run = await session.get(EvalRun, run_id)
    if run is None:
        raise HTTPException(404, "Run not found")
    cases = (await session.execute(
        select(EvalCase).where(EvalCase.run_id == run_id))).scalars().all()
    return success_response({"run": _run_dict(run), "cases": [_case_dict(c) for c in cases]})
