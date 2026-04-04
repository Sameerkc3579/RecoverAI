"""
RecoverAI — Admin Dashboard API

Routes
──────
GET /api/admin/dashboard-stats — global platform metrics across all users
GET /api/admin/users           — details of all registered users
"""
import logging
from fastapi import APIRouter, Depends

from app.core.database import get_collection
from app.api.deps import get_admin_user

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/admin",
    tags=["Admin"],
    dependencies=[Depends(get_admin_user)]
)


@router.get(
    "/dashboard-stats",
    summary="Global platform statistics (God Mode)",
)
async def dashboard_stats() -> dict:
    """
    Aggregates invoice data across ALL users and returns platform-wide metrics.
    No authentication required — intended for internal admin use.
    """
    col = get_collection("invoices")

    pipeline = [
        {
            "$facet": {
                # Total value of every invoice ever tracked
                "total_tracked": [
                    {"$group": {"_id": None, "total": {"$sum": "$amount"}}}
                ],
                # Total value of recovered invoices
                "total_recovered": [
                    {"$match": {"$or": [{"status": "recovered"}, {"recovered": True}]}},
                    {"$group": {"_id": None, "total": {"$sum": "$amount"}}}
                ],
                # Count all invoices
                "total_count": [
                    {"$count": "count"}
                ],
                # Count non-recovered / active invoices
                "active_count": [
                    {"$match": {"$and": [
                        {"status": {"$ne": "recovered"}},
                        {"recovered": {"$ne": True}}
                    ]}},
                    {"$count": "count"}
                ],
                # Per-user breakdown
                "users": [
                    {"$group": {"_id": "$owner_id", "count": {"$sum": 1}}},
                    {"$count": "count"}
                ],
                # Overdue invoices (45+ days)
                "legal_queue": [
                    {"$match": {
                        "daysOverdue": {"$gte": 45},
                        "recovered": {"$ne": True}
                    }},
                    {"$count": "count"}
                ]
            }
        }
    ]

    result = await col.aggregate(pipeline).to_list(1)
    facets = result[0] if result else {}

    def safe_total(facet_list):
        return facet_list[0]["total"] if facet_list else 0

    def safe_count(facet_list):
        return facet_list[0]["count"] if facet_list else 0

    return {
        "total_tracked_value": safe_total(facets.get("total_tracked", [])),
        "total_recovered_value": safe_total(facets.get("total_recovered", [])),
        "total_invoices": safe_count(facets.get("total_count", [])),
        "active_invoices": safe_count(facets.get("active_count", [])),
        "total_users": safe_count(facets.get("users", [])),
        "legal_queue_count": safe_count(facets.get("legal_queue", [])),
    }


@router.get(
    "/users",
    summary="List all registered platform users",
)
async def list_users() -> list[dict]:
    """
    Returns a list of all businesses/users registered on the platform,
    along with their invoice statistics.
    """
    col = get_collection("users")

    pipeline = [
        # Exclude password hashes
        {"$project": {"hashed_password": 0}},
        # Lookup invoices for each user
        {
            "$lookup": {
                "from": "invoices",
                "localField": "_id",
                "foreignField": "owner_id",
                "as": "user_invoices"
            }
        },
        # Calculate stats per user
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
                }
            }
        },
        # Remove the potentially large invoices array from the final output
        {"$project": {"user_invoices": 0}},
        # Sort newest users first
        {"$sort": {"created_at": -1}}
    ]

    users = await col.aggregate(pipeline).to_list(1000)
    
    # Convert ObjectIds to strings
    for user in users:
        user["_id"] = str(user["_id"])
        
    return users
