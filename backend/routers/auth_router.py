"""Auth routes: login, register, me, logout, refresh."""
from fastapi import APIRouter, Response, HTTPException, Depends

from db import db, ORG_ID, COOKIE_SECURE, COOKIE_SAMESITE
from core_utils import new_id, now_iso, serialize_doc
from security import (
    hash_password, verify_password, create_access_token, create_refresh_token,
    get_current_user,
)
from rbac import ALL_ROLES, effective_permissions
from models import LoginRequest, RegisterRequest

router = APIRouter(prefix="/auth", tags=["auth"])


def _set_cookies(response: Response, access: str, refresh: str = None):
    response.set_cookie("access_token", access, httponly=True, secure=COOKIE_SECURE,
                        samesite=COOKIE_SAMESITE, max_age=86400, path="/")
    if refresh:
        response.set_cookie("refresh_token", refresh, httponly=True, secure=COOKIE_SECURE,
                            samesite=COOKIE_SAMESITE, max_age=604800, path="/")


def _public_user(u: dict) -> dict:
    u = serialize_doc(u)
    u.pop("password_hash", None)
    return u


@router.post("/login")
async def login(payload: LoginRequest, response: Response):
    email = payload.email.lower()
    user = await db.users.find_one({"email": email})
    if not user or not verify_password(payload.password, user.get("password_hash", "")):
        raise HTTPException(status_code=401, detail="Email atau kata sandi salah")
    if not user.get("is_active", True):
        raise HTTPException(status_code=403, detail="Akun nonaktif, hubungi admin")
    # EPIC M4 — block login for users of a suspended tenant (super_admin exempt).
    if user.get("role") != "super_admin":
        org = await db.orgs.find_one({"id": user.get("org_id")}, {"_id": 0, "status": 1})
        if org and org.get("status") == "suspended":
            raise HTTPException(status_code=403, detail="Organisasi dinonaktifkan, hubungi super admin")
    access = create_access_token(user["id"], user["email"], user["role"])
    refresh = create_refresh_token(user["id"])
    _set_cookies(response, access, refresh)
    return {"data": _public_user(user), "access_token": access, "token_type": "bearer"}


@router.post("/register")
async def register(payload: RegisterRequest, response: Response):
    email = payload.email.lower()
    if await db.users.find_one({"email": email}):
        raise HTTPException(status_code=400, detail="Email sudah terdaftar")
    role = payload.role if payload.role in ALL_ROLES else "sales"
    ts = now_iso()
    user = {
        "id": new_id(), "org_id": ORG_ID, "name": payload.name, "email": email,
        "role": role, "password_hash": hash_password(payload.password), "phone": None,
        "is_active": True, "created_at": ts, "updated_at": ts,
    }
    await db.users.insert_one(user)
    access = create_access_token(user["id"], user["email"], user["role"])
    refresh = create_refresh_token(user["id"])
    _set_cookies(response, access, refresh)
    return {"data": _public_user(user), "access_token": access, "token_type": "bearer"}


@router.get("/me")
async def me(user: dict = Depends(get_current_user)):
    u = serialize_doc(user)
    org = await db.orgs.find_one({"id": user.get("org_id")}, {"_id": 0, "id": 1, "name": 1})
    home_id = user.get("home_org_id", user.get("org_id"))
    u["active_org"] = {"id": org.get("id"), "name": org.get("name")} if org else None
    u["is_switched"] = bool(user.get("active_org_id")) and user.get("org_id") != home_id
    # Fase 39b — izin EFEKTIF peran ini dikirim ke klien supaya tampilan tidak menawarkan
    # aksi yang pasti ditolak backend (mis. tombol "Verifikasi" dokumen untuk sales) TANPA
    # menyalin aturan RBAC ke frontend: sumbernya tetap satu, `rbac.py`.
    u["permissions"] = await effective_permissions(user.get("role"))
    return {"data": u}


@router.post("/logout")
async def logout(response: Response):
    response.delete_cookie("access_token", path="/")
    response.delete_cookie("refresh_token", path="/")
    return {"message": "Berhasil keluar"}
