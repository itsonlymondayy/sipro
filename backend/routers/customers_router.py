"""Customers (rich KYC): NIK/NPWP/spouse/heir/income + KYC document uploads.

Adopted from SIPROnext Customer model (Dok 10) and wrapped in the new foundation
(org_id scope + RBAC + phone/NIK normalizers). KYC docs go through the storage
abstraction (Emergent managed or mongo fallback).
"""
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form

import listing as lst
import stage_clock as clock
from denorm import cascade_master_change
from db import db, ORG_ID
from core_utils import new_id, now_iso, serialize_doc, parse_pagination, normalize_phone_e164, normalize_nik
from engine import emit, dispatch_pending
from rbac import require_permission
from models import CustomerCreate, CustomerUpdate
import storage

router = APIRouter(prefix="/customers", tags=["customers"])


def _clean(payload: dict) -> dict:
    if payload.get("phone"):
        payload["phone"] = normalize_phone_e164(payload["phone"])
    if payload.get("nik"):
        payload["nik"] = normalize_nik(payload["nik"])
    return payload


async def _attach_files(cust: dict) -> dict:
    ids = [f["file_id"] for f in (cust.get("kyc_files") or [])]
    if ids:
        metas = await db.files.find({"id": {"$in": ids}, "is_deleted": False},
                                    {"_id": 0, "data_b64": 0}).to_list(100)
        by_id = {m["id"]: m for m in metas}
        for f in cust.get("kyc_files", []):
            m = by_id.get(f["file_id"]) or {}
            f["original_filename"] = m.get("original_filename")
            f["content_type"] = m.get("content_type")
    return cust


CUSTOMER_SORTS = {"name": "name", "nik": "nik", "phone": "phone",
                  "monthly_income": "monthly_income", "kyc_status": "kyc_status",
                  "created_at": "created_at", "updated_at": "updated_at", **clock.SORTS}


@router.get("")
async def list_customers(q: str = None, kyc_status: str = None,
                         created_from: str = None, created_to: str = None,
                         sla: str = None,
                         sort: str = None, direction: str = None,
                         skip: int = 0, limit: int = 50,
                         user: dict = Depends(require_permission("customers", "view"))):
    """Daftar customer: cari + filter multi (KYC) + sort server-side (Fase 40) +
    filter umur/SLA verifikasi berkas dari kebijakan Pusat Konfigurasi (Fase 41)."""
    skip, limit = parse_pagination(skip, limit)
    query = {"org_id": user.get("org_id", ORG_ID)}
    lst.apply_in(query, "kyc_status", kyc_status)
    clock.apply_sla_filter(query, "customer", sla)
    lst.apply_range(query, "created_at", created_from, created_to)
    lst.apply_search(query, q, ("name", "phone", "nik", "email", "npwp"))
    total = await db.customers.count_documents(query)
    rows = await (db.customers.find(query, {"_id": 0})
                  .sort(lst.sort_spec(sort, direction, CUSTOMER_SORTS, ("created_at", -1)))
                  .skip(skip).limit(limit).to_list(limit))
    await clock.attach(rows, "customer", org_id=user.get("org_id", ORG_ID))
    counts = {}
    for st in ("pending", "submitted", "verified"):
        counts[st] = await db.customers.count_documents(
            {"org_id": user.get("org_id", ORG_ID), "kyc_status": st})
    return {"data": serialize_doc(rows), "total": total, "counts": counts}


@router.post("")
async def create_customer(payload: CustomerCreate,
                          user: dict = Depends(require_permission("customers", "create"))):
    org = user.get("org_id", ORG_ID)
    data = _clean(payload.model_dump())
    if data.get("nik"):
        dup = await db.customers.find_one({"org_id": org, "nik": data["nik"]}, {"_id": 0})
        if dup:
            raise HTTPException(status_code=409, detail="NIK sudah terdaftar pada customer lain.")
    ts = now_iso()
    doc = {"id": new_id(), "org_id": org, "kyc_files": [], "kyc_status": "pending",
           "created_by": user.get("email"), "created_at": ts, "updated_at": ts, **data}
    await db.customers.insert_one(doc)
    doc.pop("_id", None)
    # Fase 29: memicu jobdesk SM-07 "Lengkapi KYC pembeli" bila NIK/NPWP belum lengkap.
    if not doc.get("nik"):
        await emit("customer.created", "customer", doc["id"], {"label": doc.get("name")}, org_id=org)
        await dispatch_pending()
    return {"data": serialize_doc(doc)}


async def _get(cid: str, org: str) -> dict:
    c = await db.customers.find_one({"id": cid, "org_id": org}, {"_id": 0})
    if not c:
        raise HTTPException(status_code=404, detail="Customer tidak ditemukan")
    return c


@router.get("/{cid}")
async def get_customer(cid: str, user: dict = Depends(require_permission("customers", "view"))):
    c = await _get(cid, user.get("org_id", ORG_ID))
    return {"data": serialize_doc(await _attach_files(c))}


@router.put("/{cid}")
async def update_customer(cid: str, payload: CustomerUpdate,
                          user: dict = Depends(require_permission("customers", "update"))):
    org = user.get("org_id", ORG_ID)
    await _get(cid, org)
    data = _clean({k: v for k, v in payload.model_dump().items() if v is not None})
    data["updated_at"] = now_iso()
    await db.customers.update_one({"id": cid, "org_id": org}, {"$set": data})
    fresh = await db.customers.find_one({"id": cid, "org_id": org}, {"_id": 0})
    await cascade_master_change("customers", cid, fresh)
    return {"data": serialize_doc(await _attach_files(fresh))}


@router.post("/{cid}/kyc")
async def upload_kyc(cid: str, file: UploadFile = File(...), doc_type: str = Form("ktp"),
                     user: dict = Depends(require_permission("customers", "update"))):
    org = user.get("org_id", ORG_ID)
    await _get(cid, org)
    data = await file.read()
    try:
        rec = await storage.save_file(
            data=data, filename=file.filename or f"{doc_type}.bin",
            content_type=file.content_type or "application/octet-stream", org_id=org,
            owner_type="customer", owner_id=cid, uploaded_by=user.get("email"),
            doc_type=doc_type, tag="kyc",
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    entry = {"file_id": rec["id"], "doc_type": doc_type,
             "original_filename": rec["original_filename"], "uploaded_at": rec["created_at"]}
    await db.customers.update_one({"id": cid, "org_id": org},
                                  {"$push": {"kyc_files": entry},
                                   "$set": {"kyc_status": "submitted", "updated_at": now_iso()}})
    fresh = await db.customers.find_one({"id": cid, "org_id": org}, {"_id": 0})
    return {"data": serialize_doc(await _attach_files(fresh))}
