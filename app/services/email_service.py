"""
RecoverAI — Gmail SMTP Email Service

Sends drip campaign reminder emails to debtors using Gmail's SMTP server.
Requires GMAIL_USER and GMAIL_APP_PASSWORD environment variables.

Setup:
  1. Go to your Google Account → Security → 2-Step Verification → App Passwords
  2. Create an App Password for "Mail"
  3. Add to .env:
     GMAIL_USER=your@gmail.com
     GMAIL_APP_PASSWORD=xxxx xxxx xxxx xxxx
"""
import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.core.config import settings

logger = logging.getLogger(__name__)


def build_html_email(
    debtor_company: str,
    invoice_no: str,
    amount: float,
    days_overdue: int,
    due_date: str,
    tone: str,
    message_body: str,
    sender_business: str = "RecoverAI",
) -> str:
    """Build a clean, professional HTML email body."""
    tone_colors = {
        "Friendly":     ("#1D4ED8", "#DBEAFE"),
        "Firm Warning": ("#D97706", "#FEF3C7"),
        "Final Notice": ("#DC2626", "#FEE2E2"),
        "Legal Threat": ("#7C3AED", "#EDE9FE"),
    }
    accent, bg = tone_colors.get(tone, ("#1D4ED8", "#DBEAFE"))

    return f"""
<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Payment Reminder</title></head>
<body style="margin:0;padding:0;background:#F8FAFC;font-family:Inter,Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#F8FAFC;padding:40px 0;">
    <tr><td align="center">
      <table width="600" cellpadding="0" cellspacing="0" style="background:#fff;border-radius:12px;overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,0.08);">
        <!-- Header -->
        <tr><td style="background:{accent};padding:28px 36px;">
          <div style="font-size:22px;font-weight:800;color:#fff;">{sender_business}</div>
          <div style="font-size:13px;color:rgba(255,255,255,0.8);margin-top:4px;">Payment Reminder Notice</div>
        </td></tr>
        <!-- Alert Banner -->
        <tr><td style="background:{bg};padding:14px 36px;border-bottom:3px solid {accent};">
          <div style="font-size:13px;font-weight:700;color:{accent};">
            ⚠️ Invoice #{invoice_no} is {days_overdue} days overdue — ₹{amount:,.2f} outstanding
          </div>
        </td></tr>
        <!-- Body -->
        <tr><td style="padding:32px 36px;">
          <div style="font-size:15px;color:#1E293B;line-height:1.8;white-space:pre-wrap;">{message_body}</div>
          <hr style="border:none;border-top:1px solid #E2E8F0;margin:28px 0;">
          <table width="100%" style="background:#F8FAFC;border-radius:8px;padding:16px;font-size:13px;color:#475569;">
            <tr>
              <td><strong>Invoice No:</strong> {invoice_no}</td>
              <td><strong>Due Date:</strong> {due_date}</td>
            </tr>
            <tr>
              <td><strong>Days Overdue:</strong> {days_overdue}</td>
              <td><strong>Amount Due:</strong> ₹{amount:,.2f}</td>
            </tr>
          </table>
        </td></tr>
        <!-- Footer -->
        <tr><td style="background:#F1F5F9;padding:18px 36px;text-align:center;">
          <div style="font-size:11px;color:#94A3B8;">Sent by {sender_business} · Powered by RecoverAI</div>
          <div style="font-size:10px;color:#CBD5E1;margin-top:4px;">This is an automated payment reminder.</div>
        </td></tr>
      </table>
    </td></tr>
  </table>
</body>
</html>"""


async def send_reminder_email(
    to_email: str,
    debtor_company: str,
    invoice_no: str,
    amount: float,
    days_overdue: int,
    due_date: str,
    tone: str,
    message_body: str,
    sender_business: str = "RecoverAI",
) -> bool:
    """
    Send a drip campaign reminder email via Gmail SMTP.
    Returns True on success, False on failure.
    Gracefully degrades if credentials are not configured.
    """
    gmail_user = settings.gmail_user
    gmail_password = settings.gmail_app_password

    if not gmail_user or not gmail_password:
        logger.warning(
            "📧 Email drip skipped for %s — GMAIL_USER / GMAIL_APP_PASSWORD "
            "not configured in .env. Add them to enable real email sending.",
            to_email,
        )
        return False

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"[Action Required] Invoice #{invoice_no} — {days_overdue} Days Overdue"
        msg["From"]    = f"{sender_business} <{gmail_user}>"
        msg["To"]      = to_email

        plain = (
            f"Dear {debtor_company},\n\n"
            f"{message_body}\n\n"
            f"Invoice: #{invoice_no} | Due: {due_date} | Amount: ₹{amount:,.2f} | Overdue: {days_overdue}d\n\n"
            f"— {sender_business}"
        )
        html = build_html_email(
            debtor_company, invoice_no, amount, days_overdue, due_date,
            tone, message_body, sender_business
        )

        msg.attach(MIMEText(plain, "plain"))
        msg.attach(MIMEText(html, "html"))

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(gmail_user, gmail_password)
            server.sendmail(gmail_user, to_email, msg.as_string())

        logger.info("📧 Email sent to %s for invoice %s (day %s)", to_email, invoice_no, days_overdue)
        return True

    except smtplib.SMTPAuthenticationError:
        logger.error(
            "📧 Gmail authentication failed for %s. "
            "Check GMAIL_USER and GMAIL_APP_PASSWORD in .env. "
            "Make sure you are using an App Password, not your regular Gmail password.",
            gmail_user,
        )
        return False
    except Exception as exc:
        logger.error("📧 Failed to send email to %s: %s", to_email, exc)
        return False
