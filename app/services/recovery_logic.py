"""
RecoveryAgent — MSMED Act 2006 Interest Calculator.

Under the MSMED Act, delayed payments to MSMEs attract compound interest
with monthly rests at 3× the RBI bank rate.

Reference: Sections 15, 16, and 17 of the Micro, Small and Medium
Enterprises Development (MSMED) Act, 2006.

Usage:
    from app.services.recovery_logic import calculate_msme_interest
    claim = calculate_msme_interest(principal=85000, due_date_str="2024-11-15")
"""
import logging
from datetime import date, datetime

logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────────
RBI_BANK_RATE = 6.5          # Current RBI bank rate (%)
MSME_RATE_MULTIPLIER = 3     # MSMED Act specifies 3× the bank rate
ANNUAL_RATE = RBI_BANK_RATE * MSME_RATE_MULTIPLIER  # 19.5% p.a.
MONTHLY_RATE = ANNUAL_RATE / 100 / 12               # ~0.01625 per month


def calculate_msme_interest(principal: float, due_date_str: str) -> dict:
    """
    Calculate compound interest under MSMED Act 2006, §15–17.

    Parameters
    ----------
    principal : float
        Original invoice amount in INR.
    due_date_str : str
        Due date in ISO format (YYYY-MM-DD).

    Returns
    -------
    dict with keys:
        principal        – original amount
        interest_accrued – compound interest from due date to today
        total_claim      – principal + interest
        days_overdue     – calendar days since due date
        annual_rate_pct  – the applied annual rate (19.5%)
        legal_basis      – statutory reference string
    """
    try:
        due_date = _parse_date(due_date_str)
    except (ValueError, TypeError):
        logger.warning("Invalid due_date_str '%s', returning zero interest.", due_date_str)
        return _zero_result(principal)

    today = date.today()
    days_overdue = (today - due_date).days

    if days_overdue <= 0:
        return _zero_result(principal)

    # Number of full months overdue (fractional months counted as compound periods)
    months_overdue = days_overdue / 30.4375  # average days per month

    # Compound interest with monthly rests:
    #   A = P × (1 + r_monthly) ^ n_months
    #   Interest = A - P
    amount = principal * ((1 + MONTHLY_RATE) ** months_overdue)
    interest_accrued = round(amount - principal, 2)
    total_claim = round(principal + interest_accrued, 2)

    logger.debug(
        "MSME interest: ₹%.2f principal, %d days overdue → ₹%.2f interest (%.1f%% p.a.)",
        principal, days_overdue, interest_accrued, ANNUAL_RATE,
    )

    return {
        "principal": principal,
        "interest_accrued": interest_accrued,
        "total_claim": total_claim,
        "days_overdue": days_overdue,
        "annual_rate_pct": ANNUAL_RATE,
        "legal_basis": "MSMED Act 2006, §15–17 @ 3× RBI Bank Rate",
    }


# ── Helpers ───────────────────────────────────────────────────────────────────

def _parse_date(date_str: str) -> date:
    """Parse various date string formats into a date object."""
    if not date_str or not date_str.strip():
        raise ValueError("Empty date string")
    date_str = date_str.strip()
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(date_str, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Cannot parse date: {date_str}")


def _zero_result(principal: float) -> dict:
    """Return a zero-interest result for invoices that are not overdue."""
    return {
        "principal": principal,
        "interest_accrued": 0.0,
        "total_claim": principal,
        "days_overdue": 0,
        "annual_rate_pct": ANNUAL_RATE,
        "legal_basis": "MSMED Act 2006, §15–17 @ 3× RBI Bank Rate",
    }
