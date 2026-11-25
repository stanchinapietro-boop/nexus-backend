"""Validate the configured Preview target before SQLAlchemy opens any connection."""
import re
from urllib.parse import parse_qs, unquote, urlsplit


def validate_preview_target(url: str, expected: str, real: str) -> None:
    if not all(re.fullmatch(r"[a-z0-9]{20}", ref) for ref in (expected, real)) or expected == real:
        raise RuntimeError("Configure distinct verified real and Preview Supabase project references.")
    try:
        parsed = urlsplit(url)
        host = parsed.hostname or ""
        user = unquote(parsed.username or "")
        options = parse_qs(parsed.query, keep_blank_values=True)
        direct = host == f"db.{expected}.supabase.co"
        pooler = host.endswith(".pooler.supabase.com") and user.endswith("." + expected)
        # Connection-string parameters can override the parsed host, role or database.
        safe_options = set(options) <= {"sslmode", "connect_timeout", "application_name"}
        tls = options.get("sslmode", []) in (["require"], ["verify-ca"], ["verify-full"])
        valid = (parsed.scheme in {"postgres", "postgresql", "postgresql+psycopg"} and
                 parsed.path == "/postgres" and (direct or pooler) and safe_options and tls)
    except ValueError:
        valid = False
    if not valid:
        raise RuntimeError("Preview connection does not match the approved Supabase target.")
