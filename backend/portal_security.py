"""Portal auth: buyer-facing JWT (type='portal') separate from staff access tokens.

Uses the same JWT secret/algorithm but a distinct `type` claim so staff and portal
tokens can never be used interchangeably (staff endpoints require type='access').
"""
import jwt
from datetime import datetime, timezone, timedelta
from fastapi import Request, HTTPException

from db import db, ORG_ID
from security import get_jwt_secret, JWT_ALGORITHM


def create_portal_token(portal_user: dict) -> str:
    payload = {
        "sub": portal_user["id"],
        "cid": portal_user.get("customer_id"),
        "org_id": portal_user.get("org_id", ORG_ID),
        "type": "portal",
        "exp": datetime.now(timezone.utc) + timedelta(hours=12),
    }
    return jwt.encode(payload, get_jwt_secret(), algorithm=JWT_ALGORITHM)


def _extract_token(request: Request):
    token = request.cookies.get("portal_token")
    if not token:
        header = request.headers.get("Authorization", "")
        if header.startswith("Bearer "):
            token = header[7:]
    if not token:
        token = request.query_params.get("auth")  # for <a>/<iframe> pdf links
    return token


async def get_portal_user(request: Request) -> dict:
    token = _extract_token(request)
    if not token:
        raise HTTPException(status_code=401, detail="Tidak terautentikasi (portal)")
    try:
        payload = jwt.decode(token, get_jwt_secret(), algorithms=[JWT_ALGORITHM])
        if payload.get("type") != "portal":
            raise HTTPException(status_code=401, detail="Tipe token tidak valid")
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Sesi berakhir, silakan masuk kembali")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Token tidak valid")
    pu = await db.portal_users.find_one({"id": payload["sub"]}, {"_id": 0})
    if not pu or not pu.get("is_active", True):
        raise HTTPException(status_code=401, detail="Akun portal tidak ditemukan/nonaktif")
    return pu
