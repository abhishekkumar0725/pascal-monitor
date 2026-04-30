from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.services.csv_export import (
    export_all_zip,
    export_bathroom_csv,
    export_entries_full_csv,
    export_feeding_csv,
    export_sleep_csv,
    export_training_csv,
)

router = APIRouter(prefix="/export", tags=["export"])


@router.get("/feeding.csv")
async def get_feeding_csv(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Response:
    """Export feeding entries as CSV (legacy format)."""
    content = await export_feeding_csv(session)
    return Response(
        content=content,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=feeding.csv"},
    )


@router.get("/bathroom.csv")
async def get_bathroom_csv(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Response:
    """Export bathroom entries as CSV (legacy format)."""
    content = await export_bathroom_csv(session)
    return Response(
        content=content,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=bathroom.csv"},
    )


@router.get("/sleep.csv")
async def get_sleep_csv(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Response:
    """Export sleep entries as CSV (legacy format)."""
    content = await export_sleep_csv(session)
    return Response(
        content=content,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=sleep.csv"},
    )


@router.get("/training.csv")
async def get_training_csv(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Response:
    """Export training entries as CSV (legacy format)."""
    content = await export_training_csv(session)
    return Response(
        content=content,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=training.csv"},
    )


@router.get("/entries_full.csv")
async def get_entries_full_csv(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Response:
    """Export all entries with full schema including logged_by and category."""
    content = await export_entries_full_csv(session)
    return Response(
        content=content,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=entries_full.csv"},
    )


@router.get("/all.zip")
async def get_all_zip(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Response:
    """Export all four legacy CSVs as a zip file."""
    content = await export_all_zip(session)
    return Response(
        content=content,
        media_type="application/zip",
        headers={"Content-Disposition": "attachment; filename=pascal_export.zip"},
    )
