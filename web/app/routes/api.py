from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.services.summary import get_summary_data

router = APIRouter(prefix="/api", tags=["api"])


@router.get("/summary.json")
async def get_summary_json(
    session: Annotated[AsyncSession, Depends(get_session)],
    date: Annotated[str | None, Query()] = None,
) -> JSONResponse:
    """Get summary data as JSON for a specific date."""
    # Parse date parameter
    target_date = None
    if date:
        try:
            target_date = datetime.strptime(date, "%Y-%m-%d").date()
        except ValueError:
            pass

    data = await get_summary_data(session, target_date)
    return JSONResponse(content=data)
