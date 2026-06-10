"""
RecoverAI — Contact Enrichment endpoint (Security-Hardened)

Security Fixes Applied:
  1. SSRF Protection: All URLs are resolved to IP before fetching.
     Private/loopback/link-local IP ranges are blocked (RFC 1918, RFC 3927).
     This prevents attackers from probing internal services such as:
       - AWS/GCP metadata endpoints (169.254.169.254)
       - localhost MongoDB/Redis (127.0.0.1, ::1)
       - Internal VPC services (10.x, 172.16.x, 192.168.x)
  2. SSL Verification re-enabled (verify=False removed — was silently accepting
     MITM certificates from compromised intermediate hosts).
  3. Error details no longer leaked to callers (str(exc) removed from detail).
"""
import ipaddress
import logging
import re
import socket
from urllib.parse import urlparse

from bs4 import BeautifulSoup
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, HttpUrl
from starlette.concurrency import run_in_threadpool

# Vercel Serverless compatibility fallback for curl_cffi
try:
    from curl_cffi import requests as web_client
    def get_session(): return web_client.Session(impersonate="chrome110")
    REQ_EXCEPTIONS = (web_client.errors.RequestsError, web_client.errors.CurlError)
    REQ_TIMEOUT = web_client.errors.TimeoutError
except Exception:
    import requests as web_client
    def get_session(): return web_client.Session()
    REQ_EXCEPTIONS = (web_client.exceptions.RequestException,)
    REQ_TIMEOUT = web_client.exceptions.Timeout

from app.api.deps import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/enrich", tags=["Enrichment"])


class EnrichRequest(BaseModel):
    url: HttpUrl


class EnrichResponse(BaseModel):
    email: str | None = None
    phone: str | None = None


# Regex patterns
EMAIL_PATTERN = re.compile(r"([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)")
PHONE_PATTERN = re.compile(r"(\+91[-\s]?(?:\d{10}|\d{5}[-\s]?\d{5})|0\d{2,4}[-\s]?\d{6,8}|\b[6-9]\d{9}\b)")

# Headers that mimic a real Chrome browser — avoids most 403 responses
_CHROME_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/123.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "en-IN,en-US;q=0.9,en;q=0.8,hi;q=0.7",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "DNT": "1",
    "Cache-Control": "max-age=0",
}

# ── SSRF Protection — Private / Reserved IP Ranges ───────────────────────────
# RFC 1918 (private), RFC 3927 (link-local), RFC 5735 (loopback), etc.
_BLOCKED_NETWORKS = [
    ipaddress.ip_network("0.0.0.0/8"),          # "This" network
    ipaddress.ip_network("10.0.0.0/8"),          # RFC 1918 private
    ipaddress.ip_network("100.64.0.0/10"),       # Shared address space (RFC 6598)
    ipaddress.ip_network("127.0.0.0/8"),         # Loopback
    ipaddress.ip_network("169.254.0.0/16"),      # Link-local / AWS metadata
    ipaddress.ip_network("172.16.0.0/12"),       # RFC 1918 private
    ipaddress.ip_network("192.0.0.0/24"),        # IETF Protocol Assignments
    ipaddress.ip_network("192.168.0.0/16"),      # RFC 1918 private
    ipaddress.ip_network("198.18.0.0/15"),       # Benchmarking
    ipaddress.ip_network("198.51.100.0/24"),     # TEST-NET-2
    ipaddress.ip_network("203.0.113.0/24"),      # TEST-NET-3
    ipaddress.ip_network("240.0.0.0/4"),         # Reserved
    ipaddress.ip_network("255.255.255.255/32"),  # Broadcast
    ipaddress.ip_network("::1/128"),             # IPv6 loopback
    ipaddress.ip_network("fc00::/7"),            # IPv6 ULA
    ipaddress.ip_network("fe80::/10"),           # IPv6 link-local
]


def _is_private_ip(ip_str: str) -> bool:
    """Return True if the resolved IP belongs to a private/reserved range."""
    try:
        addr = ipaddress.ip_address(ip_str)
        return any(addr in network for network in _BLOCKED_NETWORKS)
    except ValueError:
        return True  # Fail closed on parse error


def _assert_url_is_safe(url_str: str) -> tuple[str, str]:
    """
    Resolve the hostname in the URL to an IP address and block any request
    that would hit a private, loopback, or link-local network.

    Returns (resolved_ip, hostname) on success so the caller can connect
    directly to the resolved IP, eliminating the TOCTOU DNS-rebinding window.

    Raises HTTPException 422 if the URL is not safe to fetch.
    """
    parsed = urlparse(url_str)
    hostname = parsed.hostname

    if not hostname:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="URL must have a valid hostname.",
        )

    # Block bare IP addresses that are obviously private
    try:
        addr = ipaddress.ip_address(hostname)
        if _is_private_ip(str(addr)):
            logger.warning("SSRF_BLOCKED | url=%s | reason=private_ip_literal", url_str)
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="The provided URL resolves to a restricted IP address.",
            )
        return str(addr), hostname
    except ValueError:
        pass  # hostname is not a literal IP — resolve it

    # Resolve hostname → IPs and block if any resolve to a private range
    try:
        infos = socket.getaddrinfo(hostname, None)
        first_ip = None
        for info in infos:
            resolved_ip = info[4][0]
            if first_ip is None:
                first_ip = resolved_ip
            if _is_private_ip(resolved_ip):
                logger.warning(
                    "SSRF_BLOCKED | url=%s | hostname=%s | resolved_ip=%s",
                    url_str, hostname, resolved_ip,
                )
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="The provided URL resolves to a restricted IP address.",
                )
        if not first_ip:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Could not resolve the hostname. Please check the URL.",
            )
        return first_ip, hostname
    except HTTPException:
        raise
    except OSError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not resolve the hostname. Please check the URL.",
        )


def _fetch_html(url_str: str, resolved_ip: str, hostname: str) -> str:
    """Fetch HTML over the original hostname URL so TLS/SNI and certificate
    validation work correctly.

    The previous implementation connected to ``https://{ip}:443`` which broke
    certificate validation for essentially every HTTPS site (the cert is issued
    for the hostname, not the IP literal), making enrichment fail in practice.

    SSRF safety is still enforced upstream: _assert_url_is_safe() has resolved
    the hostname and confirmed every resolved IP is public, and we disable
    redirects so a 3xx cannot bounce us onto an internal address. A small
    DNS-rebinding TOCTOU window remains between resolution and connect; closing
    it fully requires pinning the socket to ``resolved_ip`` while preserving SNI
    via a custom transport adapter (tracked separately). SSL verification stays
    ON — re-enabling it was the original MITM fix and must not regress.
    """
    session = get_session()
    session.headers.update(_CHROME_HEADERS)
    session.headers["Referer"] = f"https://www.google.com/search?q={hostname}"

    response = session.get(url_str, timeout=15, allow_redirects=False)
    response.raise_for_status()
    return response.text


def _extract_contacts(html: str) -> tuple[str | None, str | None]:
    """Parse HTML and extract the first email and Indian phone number found."""
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "meta"]):
        tag.extract()

    mailto_email = None
    tel_phone = None
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if href.startswith("mailto:") and not mailto_email:
            mailto_email = href[7:].split("?")[0].strip()
        if href.startswith("tel:") and not tel_phone:
            tel_phone = re.sub(r"[^\d+]", "", href[4:])

    text = soup.get_text(separator=" ")
    email_match = EMAIL_PATTERN.search(text)
    phone_match = PHONE_PATTERN.search(text)

    email = mailto_email or (email_match.group(1) if email_match else None)
    phone = tel_phone or (phone_match.group(1).strip() if phone_match else None)

    if phone:
        phone = re.sub(r"[\s\-]+", " ", phone).strip()

    return email, phone


@router.post("", response_model=EnrichResponse)   # matches /api/enrich
@router.post("/", response_model=EnrichResponse)  # matches /api/enrich/
async def enrich_contact_info(
    request: EnrichRequest,
    current_user: dict = Depends(get_current_user),
):
    url_str = str(request.url)
    logger.info("Enriching contact data from: %s | user=%s", url_str, current_user.get("email"))

    # ── SSRF Guard: resolve hostname and block private IPs ────────────────────
    resolved_ip, hostname = _assert_url_is_safe(url_str)

    try:
        # _fetch_html uses a synchronous HTTP client; run it off the event loop
        # so a slow site cannot block every other request for up to 15 seconds.
        html = await run_in_threadpool(_fetch_html, url_str, resolved_ip, hostname)
    except REQ_TIMEOUT:
        logger.warning("Timeout fetching %s", url_str)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The website took too long to respond. It may be offline or blocking automated access.",
        )
    except REQ_EXCEPTIONS as e:
        logger.warning("Connection error for %s: %s", url_str, e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not connect to the website. The server may be down or rejecting connections.",
        )
    except Exception as e:
        # Log the real error server-side but do NOT expose it to the caller
        logger.error("Scraping failed for %s: %s", url_str, e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not retrieve data from the provided URL.",
        )

    email, phone = _extract_contacts(html)

    # Return ONLY what was actually scraped. Never fabricate contact details —
    # inventing accounts@<domain> / a fake phone and returning them as if they
    # were discovered is dangerous in a debt-collection workflow. Missing fields
    # come back as null so the UI can show "not found".
    logger.info("Enrichment complete — email: %s | phone: %s", email or "—", phone or "—")
    return EnrichResponse(email=email, phone=phone)
