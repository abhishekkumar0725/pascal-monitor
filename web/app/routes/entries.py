from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.services.entries import (
    get_entry_by_id,
    soft_delete_entry,
    undelete_entry,
    update_entry,
)

router = APIRouter(prefix="/entries", tags=["entries"])
templates = Jinja2Templates(directory="app/templates")


@router.get("/{entry_id}/edit", response_class=HTMLResponse)
async def edit_entry_form(
    request: Request,
    entry_id: int,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> HTMLResponse:
    """Return the edit form fragment for an entry."""
    entry = await get_entry_by_id(session, entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="Entry not found")

    return templates.TemplateResponse(
        request,
        "_edit_form.html",
        {"entry": entry},
    )


@router.get("/{entry_id}/row", response_class=HTMLResponse)
async def get_entry_row(
    request: Request,
    entry_id: int,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> HTMLResponse:
    """Return the entry row fragment (for cancel edit)."""
    entry = await get_entry_by_id(session, entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="Entry not found")

    return templates.TemplateResponse(
        request,
        "_entry_row.html",
        {"entry": entry},
    )


@router.post("/{entry_id}", response_class=HTMLResponse)
async def update_entry_route(
    request: Request,
    entry_id: int,
    session: Annotated[AsyncSession, Depends(get_session)],
    event_type: Annotated[str, Form()],
    amount: Annotated[str | None, Form()] = None,
    location: Annotated[str | None, Form()] = None,
    command: Annotated[str | None, Form()] = None,
    result: Annotated[str | None, Form()] = None,
    notes: Annotated[str | None, Form()] = None,
) -> HTMLResponse:
    """Update an entry and return the updated row fragment."""
    entry = await get_entry_by_id(session, entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="Entry not found")

    # Build list of fields to clear (empty strings become None)
    clear_fields = []
    if amount == "":
        amount = None
        clear_fields.append("amount")
    if location == "":
        location = None
        clear_fields.append("location")
    if command == "":
        command = None
        clear_fields.append("command")
    if result == "":
        result = None
        clear_fields.append("result")
    if notes == "":
        notes = None
        clear_fields.append("notes")

    entry = await update_entry(
        session,
        entry,
        event_type=event_type,
        amount=amount,
        location=location,
        command=command,
        result=result,
        notes=notes,
        clear_fields=clear_fields,
    )

    return templates.TemplateResponse(
        request,
        "_entry_row.html",
        {"entry": entry},
    )


@router.delete("/{entry_id}", response_class=HTMLResponse)
async def delete_entry_route(
    request: Request,
    entry_id: int,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> HTMLResponse:
    """Soft-delete an entry and return an undo toast."""
    entry = await get_entry_by_id(session, entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="Entry not found")

    await soft_delete_entry(session, entry)

    return templates.TemplateResponse(
        request,
        "_undo_toast.html",
        {"entry_id": entry_id},
    )


@router.post("/{entry_id}/undelete", response_class=HTMLResponse)
async def undelete_entry_route(
    request: Request,
    entry_id: int,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> HTMLResponse:
    """Restore a soft-deleted entry and return a success toast."""
    entry = await get_entry_by_id(session, entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="Entry not found")

    await undelete_entry(session, entry)

    return templates.TemplateResponse(
        request,
        "_toast.html",
        {"message": "Entry restored", "status": "success"},
    )
