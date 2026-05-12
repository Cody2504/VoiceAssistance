from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from cm_shared.auth import TokenPayload, require_user
from cm_shared.db import get_session
from cm_shared.response import success_response
from cm_shared.schemas import UserOut
from main.models.user import User

router = APIRouter(prefix="/api/v1/users", tags=["users"])


@router.get("/me")
async def me(payload: TokenPayload = Depends(require_user), session: AsyncSession = Depends(get_session)):
    user = await session.get(User, payload.sub)
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    return success_response(UserOut.model_validate(user, from_attributes=True).model_dump(mode="json"))
