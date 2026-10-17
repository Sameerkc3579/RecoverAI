"""
RecoverAI — Admin Dashboard API (God Mode)

Routes
──────
GET  /api/admin/dashboard-stats        — global platform metrics
GET  /api/admin/users                  — list all users with stats
GET  /api/admin/users/{id}             — single user full details + invoices
PUT  /api/admin/users/{id}             — update user details
DELETE /api/admin/users/{id}           — delete user + all invoices
POST /api/admin/users/{id}/reset-password — set new password for user
POST /api/admin/users/{id}/toggle-active  — toggle active/inactive
GET  /api/admin/users/{id}/invoices    — get all invoices for a user
PUT  /api/admin/invoices/{id}          — update any invoice (admin)
DELETE /api/admin/invoices/{id}        — delete a specific invoice
POST /api/admin/users/{id}/send-notice — send a manual notice to user email
GET  /api/admin/search                 — search users by name/email
"""
import logging
import re
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel, EmailStr
from bson.errors import InvalidId
from bson import ObjectId

from app.core.database import get_collection
from app.core.security import get_password_hash, validate_password_strength
from app.api.deps import get_admin_user

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/admin",
    tags=["Admin"],
    dependencies=[Depends(get_admin_user)]
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _parse_oid(user_id: str) -> ObjectId:
    try:
        return ObjectId(user_id)
    except InvalidId:
        raise HTTPException(status_code=400, detail="Invalid ID format")


def _serialize(doc: dict) -> dict:
    """Recursively convert ObjectIds to strings in a dict."""
    for k, v in doc.items():
        if isinstance(v, ObjectId):
            doc[k] = str(v)
    return doc


# ── Schemas ───────────────────────────────────────────────────────────────────

class UserUpdateRequest(BaseModel):
    business_name: Optional[str] = None
    email: Optional[EmailStr] = None
    is_active: Optional[bool] = None
    plan: Optional[str] = None
    phone: Optional[str] = None
    city: Optional[str] = None


class ResetPasswordRequest(BaseModel):
    new_password: str


class InvoiceUpdateRequest(BaseModel):
    company: Optional[str] = None
    amount: Optional[float] = None
    status: Optional[str] = None
    recovered: Optional[bool] = None
    daysOverdue: Optional[int] = None
    notes: Optional[str] = None


# ── Platform Stats ─────────────────────────────────────────────────────────────

@router.get("/dashboard-stats", summary="Global platform statistics (God Mode)")
async def dashboard_stats() -> dict:
    """Aggregates data across ALL users and returns platform-wide metrics."""
    col = get_collection("invoices")
    users_col = get_collection("users")

    pipeline = [
        {
            "$facet": {
                "total_tracked": [
                    {"$group": {"_id": None, "total": {"$sum": "$amount"}}}
                ],
                "total_recovered": [
                    {"$match": {"$or": [{"status": "recovered"}, {"recovered": True}]}},
                    {"$group": {"_id": None, "total": {"$sum": "$amount"}}}
                ],
                "total_count": [{"$count": "count"}],
                "active_count": [
                    {"$match": {"$and": [
                        {"status": {"$ne": "recovered"}},
                        {"recovered": {"$ne": True}}
                    ]}},
                    {"$count": "count"}
                ],
                "legal_queue": [
                    {"$match": {"daysOverdue": {"$gte": 45}, "recovered": {"$ne": True}}},
                    {"$count": "count"}
                ],
                # Status breakdown
                "by_status": [
                    {"$group": {"_id": "$status", "count": {"$sum": 1}, "value": {"$sum": "$amount"}}}
                ],
                # Monthly recovered trend (last 6 months).
                # NOTE: groups by `issueDate` (the invoice's issue month), not a
                # true "recovered on" date — known limitation, no separate
                # recovery-date field is tracked yet.
                "monthly_recovered": [
                    {"$match": {"$or": [{"status": "recovered"}, {"recovered": True}]}},
                    {"$group": {
                        "_id": {"$substr": [{"$ifNull": ["$issueDate", "2024-01"]}, 0, 7]},
                        "total": {"$sum": "$amount"},
                        "count": {"$sum": 1}
                    }},
                    # Take the most recent 6 months, then re-sort ascending for display
                    {"$sort": {"_id": -1}},
                    {"$limit": 6},
                    {"$sort": {"_id": 1}},
                ],
            }
        }
    ]

    result = await col.aggregate(pipeline).to_list(1)
    facets = result[0] if result else {}

    def safe_total(lst):
        return lst[0]["total"] if lst else 0

    def safe_count(lst):
        return lst[0]["count"] if lst else 0

    # Total registered users
    total_users = await users_col.count_documents({})
    active_users = await users_col.count_documents({"is_active": True})
    inactive_users = await users_col.count_documents({"is_active": False})

    # New users this month
    month_start = datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0).isoformat()
    new_this_month = await users_col.count_documents({"created_at": {"$gte": month_start}})

    by_status = {item["_id"]: {"count": item["count"], "value": item["value"]}
                 for item in facets.get("by_status", []) if item["_id"]}

    return {
        "total_tracked_value": safe_total(facets.get("total_tracked", [])),
        "total_recovered_value": safe_total(facets.get("total_recovered", [])),
        "total_invoices": safe_count(facets.get("total_count", [])),
        "active_invoices": safe_count(facets.get("active_count", [])),
        "legal_queue_count": safe_count(facets.get("legal_queue", [])),
        "total_users": total_users,
        "active_users": active_users,
        "inactive_users": inactive_users,
        "new_users_this_month": new_this_month,
        "by_status": by_status,
        "monthly_recovered": facets.get("monthly_recovered", []),
    }


# ── User List ──────────────────────────────────────────────────────────────────

@router.get("/users", summary="List all platform users with invoice stats")
async def list_users(
    search: Optional[str] = Query(None, description="Search by name or email"),
    status_filter: Optional[str] = Query(None, description="Filter: active | inactive | all"),
    sort_by: Optional[str] = Query("created_at", description="Sort field"),
    order: Optional[str] = Query("desc", description="asc | desc"),
) -> list[dict]:
    # ── Allowlist validation for sort_by (NoSQL injection protection) ─────────
    # Passing arbitrary field names to MongoDB $sort can expose document structure
    # or be used to probe fields that should not be sortable.
    ALLOWED_SORT_FIELDS = {
        "created_at", "email", "business_name", "is_active", "plan",
        "invoice_count", "total_tracked_value", "total_recovered_value",
        "active_invoice_count", "legal_queue_count",
    }
    if sort_by not in ALLOWED_SORT_FIELDS:
        logger.warning("ADMIN_INVALID_SORT_FIELD | sort_by=%s", sort_by)
        sort_by = "created_at"  # Silently fall back to safe default

    # Restrict order to prevent unexpected behavior
    sort_order = -1 if order == "desc" else 1

    col = get_collection("users")
    match_stage = {}
    if search:
        match_stage["$or"] = [
            {"business_name": {"$regex": re.escape(search), "$options": "i"}},
            {"email": {"$regex": re.escape(search), "$options": "i"}},
        ]
    if status_filter == "active":
        match_stage["is_active"] = True
    elif status_filter == "inactive":
        match_stage["is_active"] = False

    pipeline = [
        *([ {"$match": match_stage} ] if match_stage else []),
        {"$project": {"hashed_password": 0}},  # nosec B105
        {
            "$lookup": {
                "from": "invoices",
                "localField": "_id",
                "foreignField": "owner_id",
                "as": "user_invoices"
            }
        },
        {
            "$addFields": {
                "invoice_count": {"$size": "$user_invoices"},
                "total_tracked_value": {"$sum": "$user_invoices.amount"},
                "total_recovered_value": {
                    "$sum": {
                        "$map": {
                            "input": {
                                "$filter": {
                                    "input": "$user_invoices",
                                    "as": "inv",
                                    "cond": {
                                        "$or": [
                                            {"$eq": ["$$inv.status", "recovered"]},
                                            {"$eq": ["$$inv.recovered", True]}
                                        ]
                                    }
                                }
                            },
                            "as": "rec_inv",
                            "in": "$$rec_inv.amount"
                        }
                    }
                },
                "active_invoice_count": {
                    "$size": {
                        "$filter": {
                            "input": "$user_invoices",
                            "as": "inv",
                            "cond": {"$ne": ["$$inv.recovered", True]}
                        }
                    }
                },
                "legal_queue_count": {
                    "$size": {
                        "$filter": {
                            "input": "$user_invoices",
                            "as": "inv",
                            "cond": {
                                "$and": [
                                    {"$ne": ["$$inv.recovered", True]},
                                    {"$gte": ["$$inv.daysOverdue", 45]}
                                ]
                            }
                        }
                    }
                }
            }
        },
        {"$project": {"user_invoices": 0}},
        {"$sort": {sort_by: sort_order}},
    ]

    users = await col.aggregate(pipeline).to_list(1000)
    for user in users:
        user["_id"] = str(user["_id"])
    return users


# ── Single User ────────────────────────────────────────────────────────────────

@router.get("/users/{user_id}", summary="Get full user details + all invoices")
async def get_user_details(user_id: str) -> dict:
    oid = _parse_oid(user_id)
    users_col = get_collection("users")
    inv_col = get_collection("invoices")

    user = await users_col.find_one({"_id": oid}, {"hashed_password": 0})  # nosec B105
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user["_id"] = str(user["_id"])

    invoices_cursor = inv_col.find({"owner_id": oid}).sort("issueDate", -1)
    invoices = await invoices_cursor.to_list(10000)
    for inv in invoices:
        inv["_id"] = str(inv["_id"])
        if "owner_id" in inv:
            inv["owner_id"] = str(inv["owner_id"])

    total_value = sum((inv.get("amount") or 0) for inv in invoices)
    recovered_value = sum(
        (inv.get("amount") or 0) for inv in invoices
        if inv.get("status") == "recovered" or inv.get("recovered")
    )
    active_count = sum(1 for inv in invoices if not inv.get("recovered"))
    legal_count = sum(
        1 for inv in invoices
        if not inv.get("recovered") and inv.get("daysOverdue", 0) >= 45
    )

    return {
        "user": user,
        "invoices": invoices,
        "stats": {
            "total_invoices": len(invoices),
            "total_value": total_value,
            "recovered_value": recovered_value,
            "active_count": active_count,
            "legal_queue_count": legal_count,
            "recovery_rate": round((recovered_value / total_value * 100) if total_value > 0 else 0, 1),
        }
    }


# ── Update User ────────────────────────────────────────────────────────────────

@router.put("/users/{user_id}", summary="Update user account details")
async def update_user(user_id: str, payload: UserUpdateRequest) -> dict:
    oid = _parse_oid(user_id)
    users_col = get_collection("users")

    update_data = {k: v for k, v in payload.dict(exclude_unset=True).items() if v is not None}
    if "email" in update_data:
        update_data["email"] = update_data["email"].lower()
        existing = await users_col.find_one({"email": update_data["email"], "_id": {"$ne": oid}})
        if existing:
            raise HTTPException(status_code=409, detail="Email already in use by another account.")

    if not update_data:
        raise HTTPException(status_code=400, detail="No fields to update")

    update_data["updated_at"] = datetime.now(timezone.utc).isoformat()
    result = await users_col.update_one({"_id": oid}, {"$set": update_data})

    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="User not found")

    logger.info("ADMIN_USER_UPDATED | user_id=%s | fields=%s", user_id, list(update_data.keys()))
    return {"status": "success", "message": "User updated successfully"}


# ── Delete User ────────────────────────────────────────────────────────────────

@router.delete("/users/{user_id}", summary="Permanently delete user + all their invoices")
async def delete_user(user_id: str) -> dict:
    oid = _parse_oid(user_id)
    users_col = get_collection("users")
    inv_col = get_collection("invoices")

    user = await users_col.find_one({"_id": oid})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    from app.core.config import settings
    if user.get("email") in settings.admin_emails_list:
        raise HTTPException(status_code=403, detail="Cannot delete an admin account")

    inv_result = await inv_col.delete_many({"owner_id": oid})
    await users_col.delete_one({"_id": oid})

    logger.info(
        "ADMIN_USER_DELETED | email=%s | invoices_deleted=%d",
        user.get("email"), inv_result.deleted_count
    )
    return {
        "status": "success",
        "message": f"User deleted. {inv_result.deleted_count} invoice(s) also removed."
    }


# ── Toggle Active ──────────────────────────────────────────────────────────────

@router.post("/users/{user_id}/toggle-active", summary="Toggle user account active/inactive")
async def toggle_active(user_id: str) -> dict:
    oid = _parse_oid(user_id)
    users_col = get_collection("users")

    user = await users_col.find_one({"_id": oid}, {"is_active": 1, "email": 1})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    from app.core.config import settings
    if user.get("email") in settings.admin_emails_list:
        raise HTTPException(status_code=403, detail="Cannot deactivate an admin account")

    current = user.get("is_active", True)
    new_status = not current
    await users_col.update_one(
        {"_id": oid},
        {"$set": {"is_active": new_status, "updated_at": datetime.now(timezone.utc).isoformat()}}
    )

    action = "activated" if new_status else "deactivated"
    logger.info("ADMIN_USER_TOGGLE | email=%s | new_status=%s", user.get("email"), action)
    return {"status": "success", "is_active": new_status, "message": f"User account {action}"}


# ── Reset Password ─────────────────────────────────────────────────────────────

@router.post("/users/{user_id}/reset-password", summary="Admin reset user password")
async def reset_password(user_id: str, payload: ResetPasswordRequest) -> dict:
    oid = _parse_oid(user_id)
    users_col = get_collection("users")

    ok, reason = validate_password_strength(payload.new_password)
    if not ok:
        raise HTTPException(status_code=422, detail=reason)

    user = await users_col.find_one({"_id": oid}, {"email": 1})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    hashed = get_password_hash(payload.new_password)
    await users_col.update_one(
        {"_id": oid},
        {"$set": {"hashed_password": hashed, "updated_at": datetime.now(timezone.utc).isoformat()}}
    )

    logger.info("ADMIN_PASSWORD_RESET | email=%s", user.get("email"))
    return {"status": "success", "message": "Password reset successfully"}


# ── User Invoices ──────────────────────────────────────────────────────────────

@router.get("/users/{user_id}/invoices", summary="Get all invoices for a user")
async def get_user_invoices(user_id: str) -> list[dict]:
    oid = _parse_oid(user_id)
    inv_col = get_collection("invoices")

    invoices = await inv_col.find({"owner_id": oid}).sort("issueDate", -1).to_list(10000)
    for inv in invoices:
        inv["_id"] = str(inv["_id"])
        if "owner_id" in inv:
            inv["owner_id"] = str(inv["owner_id"])
    return invoices


# ── Invoice Management ─────────────────────────────────────────────────────────

@router.put("/invoices/{invoice_id}", summary="Admin update any invoice")
async def admin_update_invoice(invoice_id: str, payload: InvoiceUpdateRequest) -> dict:
    oid = _parse_oid(invoice_id)
    inv_col = get_collection("invoices")

    update_data = {k: v for k, v in payload.dict(exclude_unset=True).items() if v is not None}
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields to update")

    update_data["updated_at"] = datetime.now(timezone.utc).isoformat()
    result = await inv_col.update_one({"_id": oid}, {"$set": update_data})

    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Invoice not found")

    return {"status": "success", "message": "Invoice updated"}


@router.delete("/invoices/{invoice_id}", summary="Admin delete a specific invoice")
async def admin_delete_invoice(invoice_id: str) -> dict:
    oid = _parse_oid(invoice_id)
    inv_col = get_collection("invoices")

    result = await inv_col.delete_one({"_id": oid})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Invoice not found")

    logger.info("ADMIN_INVOICE_DELETED | invoice_id=%s", invoice_id)
    return {"status": "success", "message": "Invoice deleted"}


# ── Search ─────────────────────────────────────────────────────────────────────

@router.get("/search", summary="Search users by name or email")
async def search_users(q: str = Query(..., min_length=1)) -> list[dict]:
    col = get_collection("users")
    cursor = col.find(
        {"$or": [
            {"business_name": {"$regex": re.escape(q), "$options": "i"}},
            {"email": {"$regex": re.escape(q), "$options": "i"}},
        ]},
        {"hashed_password": 0}  # nosec B105
    ).limit(20)
    users = await cursor.to_list(20)
    for u in users:
        u["_id"] = str(u["_id"])
    return users


# ── Platform Activity Log ──────────────────────────────────────────────────────

@router.get("/activity", summary="Recent platform activity (last 50 events)")
async def get_activity() -> list[dict]:
    """Returns recently registered users and recovered invoices as an activity feed."""
    users_col = get_collection("users")
    inv_col = get_collection("invoices")

    recent_users = await users_col.find(
        {}, {"email": 1, "business_name": 1, "created_at": 1}
    ).sort("created_at", -1).limit(25).to_list(25)

    recent_recovered = await inv_col.find(
        {"$or": [{"status": "recovered"}, {"recovered": True}]},
        {"company": 1, "amount": 1, "owner_id": 1, "issueDate": 1}
    ).sort("_id", -1).limit(25).to_list(25)

    def _ts(value) -> str:
        # Missing/None dates (e.g. invoices without issueDate) must still sort
        if isinstance(value, datetime):
            return value.isoformat()
        return str(value) if value else ""

    activity = []
    for u in recent_users:
        activity.append({
            "type": "user_registered",
            "text": f"{u.get('business_name', u.get('email', 'Unknown'))} joined the platform",
            "time": _ts(u.get("created_at")),
            "icon": "👤",
        })
    for inv in recent_recovered:
        activity.append({
            "type": "invoice_recovered",
            "text": f"₹{float(inv.get('amount') or 0):,.0f} recovered from {inv.get('company') or 'Unknown'}",
            "time": _ts(inv.get("issueDate")),
            "icon": "✅",
        })

    activity.sort(key=lambda x: x.get("time", ""), reverse=True)
    return activity[:50]


# ── Change Plan ────────────────────────────────────────────────────────────────

class ChangePlanRequest(BaseModel):
    plan: str  # Starter | Professional | Enterprise


@router.post("/users/{user_id}/change-plan", summary="Admin change user subscription plan")
async def change_plan(user_id: str, payload: ChangePlanRequest) -> dict:
    valid_plans = {"Starter", "Professional", "Enterprise"}
    if payload.plan not in valid_plans:
        raise HTTPException(status_code=422, detail=f"Plan must be one of: {', '.join(valid_plans)}")

    oid = _parse_oid(user_id)
    users_col = get_collection("users")
    user = await users_col.find_one({"_id": oid}, {"email": 1})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    await users_col.update_one(
        {"_id": oid},
        {"$set": {"plan": payload.plan, "updated_at": datetime.now(timezone.utc).isoformat()}}
    )
    logger.info("ADMIN_PLAN_CHANGED | email=%s | new_plan=%s", user.get("email"), payload.plan)
    return {"status": "success", "message": f"Plan updated to {payload.plan}"}


# ── Export Users (JSON dump for CSV generation in frontend) ────────────────────

@router.get("/export/users", summary="Export all users with stats as JSON (for CSV)")
async def export_users() -> list[dict]:
    """Returns a flat user list suitable for CSV generation in the frontend."""
    col = get_collection("users")
    pipeline = [
        {"$project": {"hashed_password": 0}},  # nosec B105
        {
            "$lookup": {
                "from": "invoices",
                "localField": "_id",
                "foreignField": "owner_id",
                "as": "user_invoices"
            }
        },
        {
            "$addFields": {
                "invoice_count": {"$size": "$user_invoices"},
                "total_tracked_value": {"$sum": "$user_invoices.amount"},
                "total_recovered_value": {
                    "$sum": {
                        "$map": {
                            "input": {
                                "$filter": {
                                    "input": "$user_invoices",
                                    "as": "inv",
                                    "cond": {
                                        "$or": [
                                            {"$eq": ["$$inv.status", "recovered"]},
                                            {"$eq": ["$$inv.recovered", True]}
                                        ]
                                    }
                                }
                            },
                            "as": "rec_inv",
                            "in": "$$rec_inv.amount"
                        }
                    }
                },
            }
        },
        {"$project": {"user_invoices": 0}},
        {"$sort": {"created_at": -1}},
    ]
    users = await col.aggregate(pipeline).to_list(5000)
    for u in users:
        u["_id"] = str(u["_id"])
    return users
