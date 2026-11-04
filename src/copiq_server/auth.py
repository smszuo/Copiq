"""API key auth -- architecture.md section 27.1.

Keys are 32 random bytes, base64url-encoded, prefixed `cw_`. The server
stores only sha256(key) and compares with hmac.compare_digest (constant
time) -- plain `==` on str/bytes short-circuits at the first differing byte
and leaks the shared prefix length through timing.
"""
from __future__ import annotations

import hashlib
import hmac
import secrets

from fastapi import Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from copiq_server.domain.models import ApiKey, utc_now_iso


def generate_key() -> str:
    return "cw_" + secrets.token_urlsafe(32)


def hash_key(key: str) -> str:
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def verify_key(db: Session, presented_key: str) -> ApiKey | None:
    """Constant-time against every stored hash; linear in key count, which is
    fine for a personal installation with a handful of clients."""
    presented_hash = hash_key(presented_key)
    for row in db.execute(select(ApiKey).where(ApiKey.revoked_at.is_(None))).scalars():
        if hmac.compare_digest(row.key_hash, presented_hash):
            row.last_used_at = utc_now_iso()
            db.commit()
            return row
    return None


def require_api_key(db_dep):
    """Returns a FastAPI dependency bound to the given db-session dependency.

    Every client -- CLI, daemon, and the React Web UI -- presents a real
    Bearer token here; there is exactly one auth path. (An earlier
    Jinja2+HTMX Web UI trusted same-origin `HX-Request` calls without a
    token instead, since it had no login form to hold one in. The React
    app has a real settings screen that stores the key, so that carve-out
    no longer applies and has been removed rather than left as dead,
    confusing code.)
    """

    def _dependency(
        db: Session = Depends(db_dep),
        authorization: str | None = Header(default=None),
    ) -> ApiKey:
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="missing bearer API key")
        presented = authorization.removeprefix("Bearer ").strip()
        row = verify_key(db, presented)
        if row is None:
            raise HTTPException(status_code=401, detail="invalid API key")
        return row

    return _dependency
