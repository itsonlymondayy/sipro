"""Subkontraktor & SPK (Phase 12 — EPIC 2.2).

Subcontractor master + Surat Perintah Kerja (work orders) that bind a subcontractor
to a project with a contract value + retention. SPK are the contractual basis for
subcon Purchase Orders / bills in the procurement pillar. Read is org-scoped;
project-scoped roles (PM/site) only see SPK for their assigned projects.
"""
from fastapi import APIRouter, Depends, HTTPException

import opname as op
import sequences as seq
from denorm import cascade_master_change
from db import db, ORG_ID
from core_utils import new_id, now_iso, serialize_doc
from rbac import require_permission, assert_project_access, project_query
from engine import add_activity
from models import (
    SubcontractorCreate, SubcontractorUpdate,
    SPKCreate, SPKUpdate, SPKStatusUpdate,
)

router = APIRouter(prefix="/subcon", tags=["subcon"])

SPK_STATUS = ("draft", "active", "completed", "cancelled")
PROJECT_SCOPED = ("project_manager", "site_engineer")


async def _accessible_project_ids(user: dict):
    projs = await db.projects.find(project_query(user, {}), {"_id": 0, "id": 1, "name": 1}).to_list(500)
    return {p["id"]: p["name"] for p in projs}


SCOPE_BY_PREFIX = {"SPK": "spk"}


async def _next_number(prefix: str, coll, org_id: str = None) -> str:
    """Nomor atomik per org+tahun. Dulu `count_documents+1`: dua request bersamaan
    menghasilkan nomor identik, dan hitungannya memakai org default (bocor antar tenant)."""
    return await seq.next_number(SCOPE_BY_PREFIX.get(prefix, prefix.lower()),
                                 org_id or ORG_ID, prefix=prefix)


# ----------------------------- Subcontractors -----------------------------
@router.get("/subcontractors")
async def list_subcontractors(q: str = None, active: str = None,
                              user: dict = Depends(require_permission("subcon", "view"))):
    org = user.get("org_id", ORG_ID)
    fq = {"org_id": org}
    if active in ("true", "false"):
        fq["is_active"] = active == "true"
    if q:
        fq["$or"] = [{"name": {"$regex": q, "$options": "i"}},
                     {"code": {"$regex": q, "$options": "i"}},
                     {"specialty": {"$regex": q, "$options": "i"}}]
    rows = await db.subcontractors.find(fq, {"_id": 0}).sort("name", 1).to_list(500)
    for r in rows:
        r["active_spk"] = await db.spk.count_documents(
            {"org_id": org, "subcontractor_id": r["id"], "status": "active"})
    return {"data": serialize_doc(rows), "total": len(rows)}


@router.post("/subcontractors")
async def create_subcontractor(payload: SubcontractorCreate,
                               user: dict = Depends(require_permission("subcon", "create"))):
    org = user.get("org_id", ORG_ID)
    if await db.subcontractors.find_one({"org_id": org, "code": payload.code}):
        raise HTTPException(status_code=400, detail="Kode subkontraktor sudah dipakai.")
    ts = now_iso()
    doc = {
        "id": new_id(), "org_id": org, "code": payload.code, "name": payload.name,
        "specialty": payload.specialty, "phone": payload.phone, "email": payload.email,
        "npwp": payload.npwp, "address": payload.address, "pic_name": payload.pic_name,
        "rating": payload.rating, "is_active": True, "notes": payload.notes,
        "created_by": user.get("email"), "created_at": ts, "updated_at": ts,
    }
    await db.subcontractors.insert_one(dict(doc))
    doc.pop("_id", None)
    return {"data": serialize_doc(doc)}


@router.get("/subcontractors/{sid}")
async def get_subcontractor(sid: str, user: dict = Depends(require_permission("subcon", "view"))):
    org = user.get("org_id", ORG_ID)
    doc = await db.subcontractors.find_one({"id": sid, "org_id": org}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Subkontraktor tidak ditemukan")
    spks = await db.spk.find({"org_id": org, "subcontractor_id": sid}, {"_id": 0}).sort("created_at", -1).to_list(200)
    return {"data": serialize_doc(doc), "spk": serialize_doc(spks)}


@router.put("/subcontractors/{sid}")
async def update_subcontractor(sid: str, payload: SubcontractorUpdate,
                               user: dict = Depends(require_permission("subcon", "update"))):
    org = user.get("org_id", ORG_ID)
    doc = await db.subcontractors.find_one({"id": sid, "org_id": org}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Subkontraktor tidak ditemukan")
    upd = {k: v for k, v in payload.dict(exclude_unset=True).items()}
    upd["updated_at"] = now_iso()
    await db.subcontractors.update_one({"id": sid, "org_id": org}, {"$set": upd})
    fresh = await db.subcontractors.find_one({"id": sid}, {"_id": 0})
    # SSOT: samakan nama yang dikopi ke SPK/termin/CO/PO (dulu jadi basi saat rename).
    await cascade_master_change("subcontractors", sid, fresh)
    return {"data": serialize_doc(fresh)}


# ----------------------------- SPK (work orders) -----------------------------
@router.get("/spk")
async def list_spk(project_id: str = None, subcontractor_id: str = None, status: str = None,
                   user: dict = Depends(require_permission("subcon", "view"))):
    org = user.get("org_id", ORG_ID)
    pmap = await _accessible_project_ids(user)
    fq = {"org_id": org}
    if user.get("role") in PROJECT_SCOPED:
        fq["project_id"] = {"$in": list(pmap.keys())}
    if project_id:
        fq["project_id"] = project_id
    if subcontractor_id:
        fq["subcontractor_id"] = subcontractor_id
    if status:
        fq["status"] = status
    rows = await db.spk.find(fq, {"_id": 0}).sort("created_at", -1).to_list(500)
    rows = await op.enrich_spk_list(org, rows)
    summary = {
        "total": len(rows),
        "active": sum(1 for r in rows if r.get("status") == "active"),
        "completed": sum(1 for r in rows if r.get("status") == "completed"),
        "contract_value": sum(int(r.get("contract_value", 0)) for r in rows),
        "item_based": sum(1 for r in rows if r.get("scope_mode") == "items"),
        "verified_value": sum(int(r.get("scope_verified_value") or 0) for r in rows),
        "billed_value": sum(int(r.get("scope_billed_value") or 0) for r in rows),
        "claimable_value": sum(int(r.get("scope_claimable_value") or 0) for r in rows),
    }
    return {"data": serialize_doc(rows), "total": len(rows), "summary": summary}


@router.post("/spk")
async def create_spk(payload: SPKCreate,
                     user: dict = Depends(require_permission("subcon", "create"))):
    org = user.get("org_id", ORG_ID)
    proj = await assert_project_access(payload.project_id, user)
    sub = await db.subcontractors.find_one({"id": payload.subcontractor_id, "org_id": org}, {"_id": 0})
    if not sub:
        raise HTTPException(status_code=404, detail="Subkontraktor tidak ditemukan")
    ts = now_iso()
    doc = {
        "id": new_id(), "org_id": org, "spk_number": await _next_number("SPK", db.spk, org),
        "subcontractor_id": payload.subcontractor_id, "subcontractor_name": sub.get("name"),
        "project_id": payload.project_id, "project_name": proj.get("name"),
        "title": payload.title, "scope": payload.scope,
        "contract_value": int(payload.contract_value or 0), "retention_pct": float(payload.retention_pct or 0),
        "start_date": payload.start_date, "end_date": payload.end_date,
        "status": "draft", "progress_pct": 0, "notes": payload.notes,
        "created_by": user.get("email"), "created_at": ts, "updated_at": ts,
    }
    await db.spk.insert_one(dict(doc))
    await add_activity(entity_type="project", entity_id=payload.project_id, type="system",
                       body=f"SPK {doc['spk_number']} untuk {sub.get('name')} dibuat (Rp {doc['contract_value']:,}).",
                       actor=user.get("email"), org_id=org)
    doc.pop("_id", None)
    return {"data": serialize_doc(doc)}


async def _get_spk(sid: str, user: dict) -> dict:
    doc = await db.spk.find_one({"id": sid, "org_id": user.get("org_id", ORG_ID)}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="SPK tidak ditemukan")
    await assert_project_access(doc["project_id"], user)
    return doc


@router.get("/spk/{sid}")
async def get_spk(sid: str, user: dict = Depends(require_permission("subcon", "view"))):
    doc = await _get_spk(sid, user)
    pos = await db.purchase_orders.find(
        {"org_id": doc["org_id"], "spk_id": sid}, {"_id": 0}).sort("created_at", -1).to_list(200)
    rows = await op.scope_rows(doc["org_id"], sid)
    return {"data": serialize_doc(doc), "purchase_orders": serialize_doc(pos),
            "scope_summary": op.summarize(rows)}


@router.put("/spk/{sid}")
async def update_spk(sid: str, payload: SPKUpdate,
                     user: dict = Depends(require_permission("subcon", "update"))):
    doc = await _get_spk(sid, user)
    upd = {k: v for k, v in payload.dict(exclude_unset=True).items()}
    scope = await op.scope_rows(doc["org_id"], sid)
    s = op.summarize(scope)
    if scope and upd.get("progress_pct") is not None:
        # INV-33-5: progres SPK berbasis item LAHIR DARI BUKTI, tidak boleh diketik.
        raise HTTPException(status_code=400, detail=(
            "SPK ini dibayar per item pekerjaan, jadi progresnya dihitung otomatis dari "
            f"pekerjaan yang sudah diverifikasi (sekarang {s['progress_pct']}%). "
            "Untuk menaikkan progres: verifikasi pekerjaan di Progres & Mutu Konstruksi."))
    if "contract_value" in upd and upd["contract_value"] is not None:
        upd["contract_value"] = int(upd["contract_value"])
        if scope and upd["contract_value"] < s["scope_value"]:
            raise HTTPException(status_code=400, detail=(
                f"Nilai kontrak {op.rp(upd['contract_value'])} lebih kecil dari total lingkup "
                f"pekerjaan {op.rp(s['scope_value'])}. Kurangi lingkup dulu, atau naikkan "
                "nilai kontrak lewat Change Order."))
    if "progress_pct" in upd and upd["progress_pct"] is not None:
        upd["progress_pct"] = max(0, min(100, int(upd["progress_pct"])))
    upd["updated_at"] = now_iso()
    await db.spk.update_one({"id": sid, "org_id": doc["org_id"]}, {"$set": upd})
    return {"data": serialize_doc(await db.spk.find_one({"id": sid}, {"_id": 0}))}


@router.post("/spk/{sid}/status")
async def spk_status(sid: str, payload: SPKStatusUpdate,
                     user: dict = Depends(require_permission("subcon", "update"))):
    if payload.status not in SPK_STATUS:
        raise HTTPException(status_code=400, detail="Status SPK tidak valid.")
    doc = await _get_spk(sid, user)
    ts = now_iso()
    setter = {"status": payload.status, "updated_at": ts}
    if payload.status == "completed":
        scope = await op.scope_rows(doc["org_id"], sid)
        if scope:
            s = op.summarize(scope)
            pending = [r for r in scope if not r.get("verified")]
            if pending:
                raise HTTPException(status_code=400, detail=(
                    f"{len(pending)} pekerjaan dalam lingkup SPK ini belum diverifikasi "
                    f"(progres terbukti {s['progress_pct']}%). Selesaikan/verifikasi dulu, "
                    "atau keluarkan pekerjaan itu dari lingkup sebelum menutup SPK."))
            setter["progress_pct"] = int(s["progress_pct"])
        else:
            setter["progress_pct"] = 100
        setter["completed_at"] = ts
    if payload.note:
        setter["notes"] = ((doc.get("notes") or "") + f"\n[{ts[:10]}] {payload.note}").strip()
    await db.spk.update_one({"id": sid, "org_id": doc["org_id"]}, {"$set": setter})
    await add_activity(entity_type="project", entity_id=doc["project_id"], type="system",
                       body=f"SPK {doc.get('spk_number')} → status {payload.status}.",
                       actor=user.get("email"), org_id=doc["org_id"])
    return {"data": serialize_doc(await db.spk.find_one({"id": sid}, {"_id": 0}))}
