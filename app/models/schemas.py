"""
RecoveryAgent — Pydantic schemas for invoices and AI prompt requests.
All models follow strict Pydantic v2 conventions (see .agents/rules/pydantic.md).
"""
from __future__ import annotations

from typing import Literal
from pydantic import BaseModel, ConfigDict, EmailStr, Field


# ── Invoice ───────────────────────────────────────────────────────────────────

class InvoiceBase(BaseModel):
    """Core invoice fields shared by create and response models."""
    model_config = ConfigDict(populate_by_name=True)

    company: str = Field(..., min_length=1, max_length=300)
    contact: str = Field(default="")
    phone: str = Field(default="")
    email: str = Field(default="")
    gstin: str | None = None
    amount: float = Field(..., ge=0, description="Outstanding amount in INR")
    invoice_no: str = Field(default="", alias="invoiceNo")
    issue_date: str | None = Field(default=None, alias="issueDate")
    due_date: str = Field(default="", alias="dueDate")
    days_overdue: int = Field(0, alias="daysOverdue")
    status: str = "sent"
    reminders: int = 0
    recovered: bool = False
    channel: str = "WhatsApp"
    industry: str = "Services"
    notes: str | None = None
    city: str | None = None
    proof_url: str | None = Field(default=None)


class InvoiceCreate(InvoiceBase):
    """Request body for POST /api/invoices."""
    pass


class InvoiceResponse(InvoiceBase):
    """Response body — includes the MongoDB-assigned string id."""
    model_config = ConfigDict(populate_by_name=True, from_attributes=True)

    id: str = Field(..., description="MongoDB ObjectId as a string")


class InvoiceUpdate(BaseModel):
    """Request body for PATCH /api/invoices/{id} — all fields optional."""
    model_config = ConfigDict(populate_by_name=True)

    status: str | None = None
    recovered: bool | None = None
    amount: float | None = Field(default=None, ge=0)
    days_overdue: int | None = Field(default=None, alias="daysOverdue")
    notes: str | None = None
    contact: str | None = None
    phone: str | None = None
    email: str | None = None
    channel: str | None = None
    reminders: int | None = None
    proof_url: str | None = None


# ── AI / Chat ─────────────────────────────────────────────────────────────────

class PromptRequest(BaseModel):
    """Request body for POST /api/generate-message."""
    prompt: str = Field(..., description="The contextual prompt to send to the AI")
    invoice_data: dict | None = Field(default=None, description="The invoice details JSON")
    tone: str = Field(default="Firm Warning", description="The tone for the AI generation")

