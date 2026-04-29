from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict


class Category(StrEnum):
    """Valid entry categories."""

    FEEDING = "feeding"
    BATHROOM = "bathroom"
    SLEEP = "sleep"
    TRAINING = "training"
    WALK = "walk"
    VET = "vet"
    SPENDING = "spending"


class EntryBase(BaseModel):
    """Base schema for entry data."""

    category: Category
    event_type: str
    occurred_at: datetime
    logged_by: str
    amount: str | None = None
    location: str | None = None
    command: str | None = None
    result: str | None = None
    duration_min: int | None = None
    distance_km: float | None = None
    cost_usd: float | None = None
    notes: str | None = None


class EntryCreate(EntryBase):
    """Schema for creating an entry."""

    pass


class EntryUpdate(BaseModel):
    """Schema for updating an entry."""

    event_type: str | None = None
    occurred_at: datetime | None = None
    logged_by: str | None = None
    amount: str | None = None
    location: str | None = None
    command: str | None = None
    result: str | None = None
    duration_min: int | None = None
    distance_km: float | None = None
    cost_usd: float | None = None
    notes: str | None = None


class EntryResponse(EntryBase):
    """Schema for entry response."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    logged_at: datetime
    deleted_at: datetime | None = None
    updated_at: datetime


class HealthResponse(BaseModel):
    """Schema for health check response."""

    status: str
    database: str
