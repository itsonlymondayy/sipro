"""Deals + Units — atomic booking (anti double-booking). Slice A."""
from fastapi import APIRouter, Depends, HTTPException

import listing as lst
import stage_clock as clock
import sequences as seq
from db import db, ORG_ID, BOOKING_HOLD_DAYS
from core_utils import new_id, now_iso, serialize_doc, parse_pagination, due_in
from rbac import require_permission, scope_query, is_scoped_sales
import lead_lifecycle as lc
from engine import emit, add_activity, auto_create_task, dispatch_pending
from models import DealReserve, DealAction, PpjbSign, AjbSign

router = APIRouter(tags=["deals"])


async def _bind_unit(org: str, unit_id: str):
    """Fase 31: simpan ikatan unit → deal → lead → pembeli pada dokumen unit & jadwalnya."""
    import build_engine as be
    try:
        await be.sync_unit_binding(org, unit_id)
    except Exception:  # noqa: BLE001  (ikatan denormalisasi tidak boleh menggagalkan deal)
        pass


# ----------------------------- Units -----------------------------
UNIT_SORTS = {"code": "code", "type": "type", "status": "status", "price": "price",
              "construction_progress": "construction_progress", "block": "block",
              "cluster_code": "cluster_code", "payment_status": "payment_status",
              "created_at": "created_at", "updated_at": "updated_at"}


@router.get("/units")
async def list_units(project_id: str = None, status: str = None, q: str = None,
                     type: str = None, cluster_id: str = None, block_id: str = None,
                     construction_status: str = None, payment_status: str = None,
                     customer_id: str = None, lead_id: str = None,
                     sort: str = None, direction: str = None,
                     skip: int = 0, limit: int = 200,
                     user: dict = Depends(require_permission("units", "view"))):
    """Daftar unit: cari kode + filter multi (status/tipe/cluster/blok) + sort (Fase 40)."""
    skip, limit = parse_pagination(skip, limit)
    org = user.get("org_id", ORG_ID)
    q_base = {"org_id": org}
    if project_id:
        q_base["project_id"] = project_id
    lst.apply_in(q_base, "status", status)
    lst.apply_in(q_base, "type", type)
    lst.apply_in(q_base, "cluster_id", cluster_id)
    lst.apply_in(q_base, "block_id", block_id)
    lst.apply_in(q_base, "construction_status", construction_status)
    lst.apply_in(q_base, "payment_status", payment_status)
    lst.apply_in(q_base, "customer_id", customer_id)
    lst.apply_in(q_base, "lead_id", lead_id)
    lst.apply_search(q_base, q, ("code", "type", "block", "cluster_code", "lead_name"))
    total = await db.units.count_documents(q_base)
    rows = await (db.units.find(q_base, {"_id": 0})
                  .sort(lst.sort_spec(sort, direction, UNIT_SORTS, ("code", 1)))
                  .skip(skip).limit(limit).to_list(limit))
    projects = await db.projects.find({"org_id": org}, {"_id": 0, "id": 1, "name": 1}).to_list(200)
    pmap = {p["id"]: p["name"] for p in projects}
    for u in rows:
        u["project_name"] = pmap.get(u.get("project_id"))
    lst.attach_aging(rows, history_field="status_history")
    # Hitungan status memakai filter yang sama MINUS filter status sendiri, supaya angka pada
    # chip filter tidak berubah menjadi 0 begitu satu status dipilih (dulu membingungkan).
    base_no_status = {k: v for k, v in q_base.items() if k != "status"}
    counts = {}
    for st in ("available", "reserved", "booked", "sold"):
        counts[st] = await db.units.count_documents({**base_no_status, "status": st})
    return {"data": serialize_doc(rows), "total": total, "counts": counts}


# ----------------------------- Deals -----------------------------
DEAL_SORTS = {"unit_code": "unit_code", "status": "status", "price": "price",
              "booking_fee": "booking_fee", "assigned_to": "assigned_to",
              "reserved_at": "reserved_at", "created_at": "created_at",
              "updated_at": "updated_at", **clock.SORTS}


@router.get("/deals")
async def list_deals(status: str = None, q: str = None, assigned_to: str = None,
                     project_id: str = None, lead_id: str = None, unit_id: str = None,
                     sort: str = None, direction: str = None, sla: str = None,
                     created_from: str = None, created_to: str = None,
                     skip: int = 0, limit: int = 50,
                     user: dict = Depends(require_permission("deals", "view"))):
    """Daftar deal: cari + filter multi + sort server-side + umur status (Fase 40) +
    filter umur status/SLA dari Pusat Konfigurasi (Fase 41)."""
    skip, limit = parse_pagination(skip, limit)
    base = {}
    lst.apply_in(base, "status", status)
    lst.apply_in(base, "assigned_to", assigned_to)
    lst.apply_in(base, "project_id", project_id)
    lst.apply_in(base, "lead_id", lead_id)
    lst.apply_in(base, "unit_id", unit_id)
    clock.apply_sla_filter(base, "deal", sla)
    lst.apply_range(base, "created_at", created_from, created_to)
    lst.apply_search(base, q, ("unit_code", "notes"))
    query = scope_query(user, base)
    total = await db.deals.count_documents(query)
    rows = await (db.deals.find(query, {"_id": 0})
                  .sort(lst.sort_spec(sort, direction, DEAL_SORTS, ("created_at", -1)))
                  .skip(skip).limit(limit).to_list(limit))
    await clock.attach(rows, "deal", org_id=user.get("org_id", ORG_ID))
    counts = {}
    for st in ("reserved", "booked", "cancelled", "closed"):
        counts[st] = await db.deals.count_documents({**scope_query(user, {}), "status": st})
    # enrich
    for d in rows:
        unit = await db.units.find_one({"id": d.get("unit_id")}, {"_id": 0, "code": 1, "type": 1})
        lead = await db.leads.find_one({"id": d.get("lead_id")}, {"_id": 0, "name": 1})
        d["unit_code"] = unit.get("code") if unit else None
        d["unit_type"] = unit.get("type") if unit else None
        d["lead_name"] = lead.get("name") if lead else None
    return {"data": serialize_doc(rows), "total": total, "counts": counts}


@router.get("/deals/{deal_id}")
async def get_deal(deal_id: str, user: dict = Depends(require_permission("deals", "view"))):
    d = await db.deals.find_one({"id": deal_id}, {"_id": 0})
    if not d:
        raise HTTPException(status_code=404, detail="Deal tidak ditemukan")
    if is_scoped_sales(user) and d.get("assigned_to") != user.get("email"):
        raise HTTPException(status_code=403, detail="Akses ditolak: bukan deal Anda")
    return {"data": serialize_doc(d)}


@router.post("/deals/reserve")
async def reserve_unit(payload: DealReserve,
                       user: dict = Depends(require_permission("deals", "create"))):
    org = user.get("org_id", ORG_ID)
    unit = await db.units.find_one({"id": payload.unit_id, "org_id": org}, {"_id": 0})
    if not unit:
        raise HTTPException(status_code=404, detail="Unit tidak ditemukan")
    lead = await db.leads.find_one({"id": payload.lead_id, "org_id": org}, {"_id": 0})
    if not lead:
        raise HTTPException(status_code=404, detail="Lead tidak ditemukan")
    if is_scoped_sales(user) and lead.get("assigned_to") != user.get("email"):
        raise HTTPException(status_code=403, detail="Akses ditolak: bukan lead Anda")
    ts = now_iso()
    deal_id = new_id()
    reserved_until = due_in(days=BOOKING_HOLD_DAYS)
    # ATOMIC hold: only succeeds if unit is currently available.
    res = await db.units.find_one_and_update(
        {"id": payload.unit_id, "org_id": org, "status": "available"},
        {"$set": {"status": "reserved", "reserved_by_deal": deal_id, "updated_at": ts}})
    if res is None:
        raise HTTPException(status_code=409,
                            detail="Unit tidak tersedia — sudah di-reserve atau di-booking oleh transaksi lain.")
    deal = {
        "id": deal_id, "org_id": org, "lead_id": payload.lead_id, "unit_id": payload.unit_id,
        "project_id": unit.get("project_id"), "assigned_to": lead.get("assigned_to") or user.get("email"),
        "status": "reserved", "price": unit.get("price", 0), "booking_fee": payload.booking_fee,
        "reserved_at": ts, "reserved_until": reserved_until, "booked_at": None, "notes": payload.notes,
        "created_by": user.get("email"), "created_at": ts, "updated_at": ts,
    }
    await db.deals.insert_one({**deal, **await clock.patch_for("deal", "reserved",
                                                              org_id=org, at=ts)})
    await _bind_unit(org, payload.unit_id)
    # Fase 29b: tahap "booking" lahir dari BUKTI reservasi unit (bukan pilihan manual).
    await lc.advance_on_deal({"id": deal_id, "lead_id": payload.lead_id, "status": "draft",
                              "org_id": org}, stage="booking", actor=user.get("email"),
                             reason=f"Reservasi unit {unit.get('code')}")
    await emit("deal.reserved", "deal", deal_id, {"unit_id": payload.unit_id}, org_id=org)
    await auto_create_task(
        source_event=f"deal.bookingfee:{deal_id}", jobdesk_code="SM-05",
        title=f"Konfirmasi booking fee: {lead.get('name')} / unit {unit.get('code')}",
        type="follow_up", related_entity_type="deal", related_entity_id=deal_id,
        assigned_to=deal["assigned_to"], due_date=due_in(days=1), priority="high", org_id=org)
    await add_activity(entity_type="lead", entity_id=payload.lead_id, type="system",
                       body=f"Reservasi unit {unit.get('code')} dibuat (hold s/d {reserved_until[:10]}).",
                       actor=user.get("email"), org_id=org)
    deal.pop("_id", None)
    return {"data": serialize_doc(deal)}


async def _get_deal_editable(deal_id: str, user: dict) -> dict:
    d = await db.deals.find_one({"id": deal_id}, {"_id": 0})
    if not d:
        raise HTTPException(status_code=404, detail="Deal tidak ditemukan")
    if is_scoped_sales(user) and d.get("assigned_to") != user.get("email"):
        raise HTTPException(status_code=403, detail="Akses ditolak: bukan deal Anda")
    return d


@router.post("/deals/{deal_id}/book")
async def book_deal(deal_id: str, payload: DealAction,
                    user: dict = Depends(require_permission("deals", "update"))):
    d = await _get_deal_editable(deal_id, user)
    if d.get("status") != "reserved":
        raise HTTPException(status_code=400, detail="Deal harus berstatus 'reserved' untuk di-booking.")
    org = user.get("org_id", ORG_ID)
    ts = now_iso()
    await db.deals.update_one({"id": deal_id}, {"$set": {
        "status": "booked", "booked_at": ts, "updated_at": ts,
        **await clock.patch_for("deal", "booked", org_id=org, at=ts)}})
    await db.units.update_one({"id": d["unit_id"]}, {"$set": {
        "status": "booked", "booked_by_deal": deal_id, "payment_status": "booking_fee", "updated_at": ts}})
    # Fase 31 (perbaikan cacat): ikatan unit → deal → lead → pembeli disimpan pada unit,
    # supaya progres pembangunan, portal pembeli, dan laporan tidak bergantung pencarian
    # berlapis yang mudah putus.
    await _bind_unit(org, d["unit_id"])
    await emit("deal.booked", "deal", deal_id, {"unit_id": d["unit_id"]}, org_id=org)
    await add_activity(entity_type="lead", entity_id=d["lead_id"], type="system",
                       body="Deal dikonfirmasi (booked).", actor=user.get("email"), org_id=org)
    await dispatch_pending()  # process deal.booked now -> generate AR schedule + commission (Finance)
    fresh = await db.deals.find_one({"id": deal_id}, {"_id": 0})
    return {"data": serialize_doc(fresh)}


@router.post("/deals/{deal_id}/cancel")
async def cancel_deal(deal_id: str, payload: DealAction,
                      user: dict = Depends(require_permission("deals", "update"))):
    d = await _get_deal_editable(deal_id, user)
    if d.get("status") in ("cancelled", "expired", "completed"):
        raise HTTPException(status_code=400, detail="Deal sudah selesai/batal.")
    org = user.get("org_id", ORG_ID)
    ts = now_iso()
    await db.deals.update_one({"id": deal_id}, {"$set": {
        "status": "cancelled", "updated_at": ts,
        **await clock.patch_for("deal", "cancelled", org_id=org, at=ts)}})
    await db.units.update_one({"id": d["unit_id"]}, {"$set": {
        "status": "available", "reserved_by_deal": None, "booked_by_deal": None,
        "payment_status": "none", "updated_at": ts}})
    await _bind_unit(org, d["unit_id"])
    await emit("deal.cancelled", "deal", deal_id, {"unit_id": d["unit_id"]}, org_id=org)
    await add_activity(entity_type="lead", entity_id=d["lead_id"], type="system",
                       body=f"Deal dibatalkan{': ' + payload.note if payload.note else ''}. Unit dilepas.",
                       actor=user.get("email"), org_id=org)
    fresh = await db.deals.find_one({"id": deal_id}, {"_id": 0})
    return {"data": serialize_doc(fresh)}


# ----------------------------- Legal chain (EPIC 1.4): PPJB -> AJB -> sold -----------------------------
async def _deal_payment_summary(deal_id: str, org: str, price: int) -> dict:
    inv = await db.ar_invoices.find_one({"org_id": org, "deal_id": deal_id}, {"_id": 0})
    total = int(inv.get("total", price)) if inv else int(price or 0)
    paid = int(inv.get("paid", 0)) if inv else 0
    outstanding = int(inv.get("outstanding", total - paid)) if inv else total
    pct = round(paid / total * 100) if total > 0 else 0
    return {"price": int(price or 0), "total": total, "paid": paid,
            "outstanding": outstanding, "paid_pct": pct, "ar_status": (inv or {}).get("status")}


async def _legal_number(org: str, prefix: str) -> str:
    field = "ppjb" if prefix == "PPJB" else "ajb"
    return await seq.next_number(f"legal:{field}", org, prefix=prefix)


@router.get("/deals/{deal_id}/legal")
async def deal_legal(deal_id: str, user: dict = Depends(require_permission("deals", "view"))):
    d = await _get_deal_editable(deal_id, user)
    org = user.get("org_id", ORG_ID)
    unit = await db.units.find_one({"id": d.get("unit_id")}, {"_id": 0, "code": 1, "status": 1}) or {}
    lead = await db.leads.find_one({"id": d.get("lead_id")}, {"_id": 0, "name": 1}) or {}
    fin = await db.financing_apps.find_one({"org_id": org, "deal_id": deal_id}, {"_id": 0})
    payment = await _deal_payment_summary(deal_id, org, d.get("price", 0))
    return {"data": {
        "deal_id": deal_id, "status": d.get("status"), "legal_stage": d.get("legal_stage"),
        "unit_code": unit.get("code"), "unit_status": unit.get("status"), "lead_name": lead.get("name"),
        "reserved_at": d.get("reserved_at"), "booked_at": d.get("booked_at"),
        "ppjb": d.get("ppjb"), "ajb": d.get("ajb"), "sold_at": d.get("sold_at"),
        "payment": payment,
        "financing": ({"bank": fin.get("bank_name"), "status": fin.get("status"),
                       "plafon": fin.get("plafon"), "tenor": fin.get("tenor_months")} if fin else None),
    }}


@router.post("/deals/{deal_id}/ppjb")
async def sign_ppjb(deal_id: str, payload: PpjbSign,
                    user: dict = Depends(require_permission("deals", "update"))):
    d = await _get_deal_editable(deal_id, user)
    if d.get("status") != "booked":
        raise HTTPException(status_code=400, detail="PPJB hanya untuk deal berstatus 'booked'.")
    if d.get("legal_stage") in ("ppjb", "ajb"):
        raise HTTPException(status_code=400, detail="PPJB sudah ditandatangani untuk deal ini.")
    org = user.get("org_id", ORG_ID)
    ts = now_iso()
    lead = await db.leads.find_one({"id": d.get("lead_id")}, {"_id": 0, "name": 1}) or {}
    unit = await db.units.find_one({"id": d.get("unit_id")}, {"_id": 0, "code": 1}) or {}
    pay = await _deal_payment_summary(deal_id, org, d.get("price", 0))
    ppjb = {"number": payload.number or await _legal_number(org, "PPJB"),
            "signed_date": payload.signed_date or ts[:10], "signed_by": lead.get("name"),
            "dp_paid": pay["paid"], "dp_pct": pay["paid_pct"], "note": payload.note, "created_at": ts}
    await db.deals.update_one({"id": deal_id, "org_id": org},
                              {"$set": {"legal_stage": "ppjb", "ppjb": ppjb, "updated_at": ts}})
    await emit("deal.ppjb", "deal", deal_id, {"unit_id": d["unit_id"], "number": ppjb["number"]}, org_id=org)
    await auto_create_task(
        source_event=f"deal.ajb:{deal_id}",
        title=f"Jadwalkan AJB (notaris): {lead.get('name')} / unit {unit.get('code')}",
        type="follow_up", related_entity_type="deal", related_entity_id=deal_id,
        assigned_to=d.get("assigned_to"), due_date=due_in(days=14), priority="medium", org_id=org)
    await add_activity(entity_type="lead", entity_id=d["lead_id"], type="system",
                       body=f"PPJB {ppjb['number']} ditandatangani untuk unit {unit.get('code')}.",
                       actor=user.get("email"), org_id=org)
    fresh = await db.deals.find_one({"id": deal_id}, {"_id": 0})
    return {"data": serialize_doc(fresh)}


@router.post("/deals/{deal_id}/ajb")
async def sign_ajb(deal_id: str, payload: AjbSign,
                   user: dict = Depends(require_permission("deals", "update"))):
    d = await _get_deal_editable(deal_id, user)
    if d.get("legal_stage") != "ppjb":
        raise HTTPException(status_code=400, detail="AJB memerlukan PPJB yang sudah ditandatangani.")
    org = user.get("org_id", ORG_ID)
    ts = now_iso()
    lead = await db.leads.find_one({"id": d.get("lead_id")}, {"_id": 0, "name": 1}) or {}
    unit = await db.units.find_one({"id": d.get("unit_id")}, {"_id": 0, "code": 1}) or {}
    pay = await _deal_payment_summary(deal_id, org, d.get("price", 0))
    ajb = {"number": payload.number or await _legal_number(org, "AJB"),
           "notary": payload.notary, "signed_date": payload.signed_date or ts[:10],
           "buyer": lead.get("name"), "outstanding_at_ajb": pay["outstanding"],
           "note": payload.note, "created_at": ts}
    await db.deals.update_one({"id": deal_id, "org_id": org}, {"$set": {
        "legal_stage": "ajb", "ajb": ajb, "status": "completed", "sold_at": ts,
        "updated_at": ts, **await clock.patch_for("deal", "completed", org_id=org, at=ts)}})
    await db.units.update_one({"id": d["unit_id"], "org_id": org}, {"$set": {
        "status": "sold", "sold_at": ts, "sold_by_deal": deal_id, "updated_at": ts}})
    await _bind_unit(org, d["unit_id"])
    await emit("deal.ajb", "deal", deal_id, {"unit_id": d["unit_id"], "number": ajb["number"]}, org_id=org)
    await emit("deal.sold", "deal", deal_id, {"unit_id": d["unit_id"]}, org_id=org)
    await add_activity(entity_type="lead", entity_id=d["lead_id"], type="system",
                       body=f"AJB {ajb['number']} ditandatangani — unit {unit.get('code')} SOLD.",
                       actor=user.get("email"), org_id=org)
    fresh = await db.deals.find_one({"id": deal_id}, {"_id": 0})
    return {"data": serialize_doc(fresh)}
