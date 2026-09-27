from __future__ import annotations

from dataclasses import dataclass

from fastapi import Header, HTTPException
from supabase import create_client

from .config import SUPABASE_ANON_KEY, SUPABASE_URL


@dataclass
class CurrentUser:
    id: str
    email: str | None
    access_token: str


# A plain anon-key client used only to ask Supabase Auth "is this token valid,
# and who is it for" — this delegates verification to Supabase itself, so it
# keeps working regardless of whether the project signs tokens with a legacy
# shared HS256 secret or the newer asymmetric (ECC/RSA) signing keys.
_verify_client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)


def get_current_user(authorization: str | None = Header(default=None)) -> CurrentUser:
    """Verify the Supabase-issued access token sent by the frontend and return
    the caller's identity.

    The token is also handed back so callers can build a per-request, RLS-scoped
    Supabase client (see db.py) — every downstream query is enforced by Postgres
    row-level security keyed on auth.uid(), not just by this check.
    """
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")

    token = authorization.split(" ", 1)[1].strip()
    try:
        response = _verify_client.auth.get_user(token)
    except Exception as exc:
        raise HTTPException(status_code=401, detail="Invalid or expired session") from exc

    user = response.user if response else None
    if not user:
        raise HTTPException(status_code=401, detail="Invalid or expired session")

    return CurrentUser(id=user.id, email=user.email, access_token=token)
