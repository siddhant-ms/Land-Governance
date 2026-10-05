"""SSRF-guarded URL fetch for ingestion: http(s) only, public IPs only, size-capped, no redirects to private hosts."""
import ipaddress
import re
import socket
from urllib.parse import urlparse

import httpx

from app.core.config import get_settings
from app.core.errors import AppError


def assert_public_url(url: str) -> None:
    u = urlparse(url)
    if u.scheme not in ("http", "https") or not u.hostname:
        raise AppError(422, "INVALID_URL", "Only http(s) URLs are allowed.")
    try:
        infos = socket.getaddrinfo(u.hostname, u.port or (443 if u.scheme == "https" else 80), proto=socket.IPPROTO_TCP)
    except socket.gaierror:
        raise AppError(422, "URL_UNRESOLVABLE", "The URL host could not be resolved.")
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
            raise AppError(422, "URL_NOT_ALLOWED", "URLs resolving to private or internal addresses are not allowed.")


def fetch_url(url: str) -> tuple[str, bytes]:
    """Returns (filename, bytes). HTML is reduced to visible text and treated as .txt."""
    assert_public_url(url)
    max_b = get_settings().max_upload_bytes
    with httpx.Client(follow_redirects=False, timeout=20) as c:
        r = c.get(url, headers={"User-Agent": "SIH26019-ingest/1.0"})
    if r.is_redirect:
        raise AppError(422, "URL_REDIRECT", "Redirects are not followed; provide the final URL.")
    if r.status_code != 200:
        raise AppError(422, "URL_FETCH_FAILED", f"Source returned HTTP {r.status_code}.")
    if len(r.content) > max_b:
        raise AppError(413, "FILE_TOO_LARGE", "Remote file exceeds the size limit.")
    ctype = r.headers.get("content-type", "").lower()
    if "pdf" in ctype or r.content.startswith(b"%PDF-"):
        return "remote.pdf", r.content
    if "html" in ctype:
        text = re.sub(r"(?is)<(script|style).*?</\1>", " ", r.text)
        text = re.sub(r"(?s)<[^>]+>", "\n", text)
        text = re.sub(r"\n\s*\n+", "\n\n", text).strip()
        return "remote.txt", text.encode()
    if "text" in ctype:
        return "remote.txt", r.content
    raise AppError(415, "UNSUPPORTED_FILE_TYPE", "Remote content type is not supported.")
