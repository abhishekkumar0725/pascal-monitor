from __future__ import annotations

from datetime import datetime, timedelta
from typing import Annotated
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Cookie, Depends, Form, Query, Request, Response
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import get_session
from app.services.entries import create_entry, get_entries_for_date

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

COOKIE_MAX_AGE = 60 * 60 * 24 * 365  # 1 year


@router.get("/", response_class=HTMLResponse)
async def home(
    request: Request,
    logged_by: Annotated[str | None, Cookie()] = None,
) -> HTMLResponse:
    """Render the home page with quick-tap buttons."""
    current_user = logged_by or settings.log_users[0]
    return templates.TemplateResponse(
        request,
        "home.html",
        {
            "log_users": settings.log_users,
            "current_user": current_user,
        },
    )


@router.post("/log", response_class=HTMLResponse)
async def log_entry(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    category: Annotated[str, Form()],
    event_type: Annotated[str, Form()],
    logged_by: Annotated[str | None, Cookie()] = None,
) -> HTMLResponse:
    """Log a quick entry and return a toast fragment."""
    user = logged_by or settings.log_users[0]

    try:
        entry = await create_entry(
            session,
            category=category,
            event_type=event_type,
            logged_by=user,
        )
        time_str = entry.occurred_at.strftime("%-I:%M %p")
        message = f"{entry.event_type.capitalize()} logged {time_str}"
        status = "success"
    except Exception:
        message = "Failed to log entry"
        status = "error"

    return templates.TemplateResponse(
        request,
        "_toast.html",
        {"message": message, "status": status},
    )


@router.post("/set-user")
async def set_user(
    logged_by: Annotated[str, Form()],
) -> Response:
    """Set the logged_by cookie."""
    response = Response(status_code=200)
    response.set_cookie(
        key="logged_by",
        value=logged_by,
        max_age=COOKIE_MAX_AGE,
        httponly=True,
        samesite="lax",
    )
    return response


@router.get("/today", response_class=HTMLResponse)
async def today(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    date: Annotated[str | None, Query()] = None,
) -> HTMLResponse:
    """Show today's entries (or entries for a specific date)."""
    tz = ZoneInfo(settings.timezone)

    # Parse date parameter or default to today
    if date:
        try:
            target_date = datetime.strptime(date, "%Y-%m-%d").date()
        except ValueError:
            target_date = datetime.now(tz).date()
    else:
        target_date = datetime.now(tz).date()

    entries = await get_entries_for_date(session, target_date)

    # Calculate prev/next dates for navigation
    prev_date = (target_date - timedelta(days=1)).isoformat()
    next_date = (target_date + timedelta(days=1)).isoformat()
    display_date = target_date.strftime("%A, %B %-d, %Y")

    return templates.TemplateResponse(
        request,
        "today.html",
        {
            "entries": entries,
            "display_date": display_date,
            "prev_date": prev_date,
            "next_date": next_date,
        },
    )
