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

# Event types for each category
EVENT_TYPES: dict[str, list[str]] = {
    "feeding": ["meal", "water", "treat"],
    "bathroom": ["pee", "poop", "accident"],
    "sleep": ["sleep", "wake", "nap"],
    "training": ["sit", "stay", "come", "down", "heel", "other"],
    "walk": ["walk", "hike", "run"],
    "vet": ["checkup", "vaccination", "medication", "grooming", "other"],
    "spending": ["food", "supplies", "vet", "grooming", "other"],
}


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


@router.get("/form/expand", response_class=HTMLResponse)
async def form_expand(request: Request) -> HTMLResponse:
    """Return the expanded full form."""
    tz = ZoneInfo(settings.timezone)
    now_local = datetime.now(tz).strftime("%Y-%m-%dT%H:%M")
    return templates.TemplateResponse(
        request,
        "_full_form.html",
        {"now_local": now_local},
    )


@router.get("/form/collapse", response_class=HTMLResponse)
async def form_collapse(request: Request) -> HTMLResponse:
    """Return the collapsed form button."""
    return HTMLResponse(
        '<button class="outline" hx-get="/form/expand" '
        'hx-target="#full-form-container" hx-swap="innerHTML">'
        "More options...</button>"
    )


@router.get("/form/event-types", response_class=HTMLResponse)
async def form_event_types(
    request: Request,
    category: Annotated[str, Query()],
) -> HTMLResponse:
    """Return event type options for a category."""
    event_types = EVENT_TYPES.get(category, ["other"])
    return templates.TemplateResponse(
        request,
        "_event_types.html",
        {"event_types": event_types},
    )


@router.get("/form/category-fields", response_class=HTMLResponse)
async def form_category_fields(
    request: Request,
    category: Annotated[str, Query()],
) -> HTMLResponse:
    """Return category-specific form fields."""
    return templates.TemplateResponse(
        request,
        "_category_fields.html",
        {"category": category},
    )


@router.post("/log/full", response_class=HTMLResponse)
async def log_full_entry(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    category: Annotated[str, Form()],
    event_type: Annotated[str, Form()],
    occurred_at: Annotated[str | None, Form()] = None,
    amount: Annotated[str | None, Form()] = None,
    location: Annotated[str | None, Form()] = None,
    command: Annotated[str | None, Form()] = None,
    result: Annotated[str | None, Form()] = None,
    duration_min: Annotated[int | None, Form()] = None,
    distance_km: Annotated[float | None, Form()] = None,
    cost_usd: Annotated[float | None, Form()] = None,
    notes: Annotated[str | None, Form()] = None,
    logged_by: Annotated[str | None, Cookie()] = None,
) -> HTMLResponse:
    """Log a full entry with all fields."""
    user = logged_by or settings.log_users[0]

    # Parse occurred_at from datetime-local format
    parsed_occurred_at = None
    if occurred_at:
        try:
            tz = ZoneInfo(settings.timezone)
            local_dt = datetime.strptime(occurred_at, "%Y-%m-%dT%H:%M")
            local_dt = local_dt.replace(tzinfo=tz)
            parsed_occurred_at = local_dt.astimezone(ZoneInfo("UTC")).replace(tzinfo=None)
        except ValueError:
            pass

    try:
        entry = await create_entry(
            session,
            category=category,
            event_type=event_type,
            logged_by=user,
            occurred_at=parsed_occurred_at,
            amount=amount or None,
            location=location or None,
            command=command or None,
            result=result or None,
            duration_min=duration_min,
            distance_km=distance_km,
            cost_usd=cost_usd,
            notes=notes or None,
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
