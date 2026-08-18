"""AR (piutang pembeli): jadwal, receipts, aging, BAST->RevRec. Slice Finance."""
from fastapi import APIRouter, Depends, HTTPException

import listing as lst
import stage_clock as clock
import reference as ref
from db import db, ORG_ID
from core_utils import serialize_doc, parse_pagination
from rbac import require_permission
import finance_engine as fe
from models import ArScheduleCreate, ReceiptCreate
from models_finance import DepositApply, DepositReceive, DepositRefund

router = APIRouter(prefix="/finance/ar", tags=["finance-ar"])


AR_SORTS = {"unit_code": "unit_code", "lead_name": "lead_name", "status": "status",
            "total": "total", "paid": "paid", "outstanding": "outstanding",
            "created_at": "created_at", "updated_at": "updated_at", **clock.SORTS}

# SSOT status piutang (satu sumber: reference.py) — dipakai untuk menghitung angka per status
# agar tidak ada lagi daftar status karangan di router.
AR_STATUS_OPTIONS = ref.GROUPS["ar_status"]["options"]


@router.get("")
async def list_ar(status: str = None, q: str = None, sort: str = None, direction: str = None,
                  created_from: str = None, created_to: str = None, sla: str = None,
                  skip: int = 0, limit: int = 50,
                  user: dict = Depends(require_permission("finance", "view"))):
    """Daftar tagihan AR: cari + filter multi status + sort server-side (Fase 40) +
    filter umur status/SLA penagihan dari Pusat Konfigurasi (Fase 41)."""
    org = user.get("org_id", ORG_ID)
    skip, limit = parse_pagination(skip, limit)
    q_base = {"org_id": org}
    lst.apply_in(q_base, "status", status)
    clock.apply_sla_filter(q_base, "ar_invoice", sla)
    lst.apply_range(q_base, "created_at", created_from, created_to)
    lst.apply_search(q_base, q, ("unit_code", "lead_name", "scheme_name"))
    total = await db.ar_invoices.count_documents(q_base)
    rows = await (db.ar_invoices.find(q_base, {"_id": 0})
                  .sort(lst.sort_spec(sort, direction, AR_SORTS, ("created_at", -1)))
                  .skip(skip).limit(limit).to_list(limit))
    await clock.attach(rows, "ar_invoice", org_id=org)
    # Angka per status HARUS memakai kosakata yang benar-benar ditulis mesin keuangan
    # (`finance_engine`: unpaid → partial → paid, sama dengan SSOT `reference.ar_status`).
    # Sebelum ini daftar di sini berisi "draft/open/void" yang TIDAK PERNAH ADA di data,
    # sehingga chip filter selalu 0 dan tagihan `unpaid` tidak punya angka sama sekali —
    # pemakai menyimpulkan "tidak ada piutang belum bayar" padahal ada.
    counts = {}
    for st in [o["value"] for o in AR_STATUS_OPTIONS]:
        counts[st] = await db.ar_invoices.count_documents({"org_id": org, "status": st})
    return {"data": serialize_doc(rows), "total": total, "counts": counts}


@router.get("/aging")
async def ar_aging(user: dict = Depends(require_permission("finance", "view"))):
    return {"data": await fe.ar_aging(user.get("org_id", ORG_ID))}


# --- Fase 26: titipan pelanggan (kelebihan bayar) ---
# CATATAN URUTAN RUTE: harus didaftarkan SEBELUM "/{deal_id}" agar tidak tertelan path param.
@router.get("/deposits")
async def list_deposits(user: dict = Depends(require_permission("finance", "view"))):
    """Daftar saldo titipan pelanggan + totalnya (dipakai KPI & panel Titipan)."""
    org = user.get("org_id", ORG_ID)
    rows = await db.customer_deposits.find({"org_id": org}, {"_id": 0}).sort("updated_at", -1).to_list(500)
    return {"data": serialize_doc(rows), "total": len(rows),
            "balance_total": sum(int(r.get("balance", 0) or 0) for r in rows)}


@router.post("/{deal_id}/deposit")
async def deposit_receive(deal_id: str, payload: DepositReceive,
                         user: dict = Depends(require_permission("finance", "create"))):
    """Terima titipan di muka (belum dialokasikan ke termin)."""
    try:
        res = await fe.receive_deposit(deal_id, payload.amount, payload.note,
                                      user.get("email"), user.get("org_id", ORG_ID))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"data": serialize_doc(res)}


@router.post("/{deal_id}/deposit/apply")
async def deposit_apply(deal_id: str, payload: DepositApply,
                        user: dict = Depends(require_permission("finance", "update"))):
    try:
        res = await fe.apply_deposit(deal_id, payload.amount, user.get("email"),
                                     user.get("org_id", ORG_ID), payload.note)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"data": serialize_doc(res)}


@router.post("/{deal_id}/deposit/refund")
async def deposit_refund(deal_id: str, payload: DepositRefund,
                         user: dict = Depends(require_permission("finance", "update"))):
    try:
        res = await fe.refund_deposit(deal_id, payload.amount, payload.note,
                                      user.get("email"), user.get("org_id", ORG_ID))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"data": serialize_doc(res)}


@router.get("/{deal_id}")
async def ar_detail(deal_id: str, user: dict = Depends(require_permission("finance", "view"))):
    org = user.get("org_id", ORG_ID)
    inv = await db.ar_invoices.find_one({"org_id": org, "deal_id": deal_id}, {"_id": 0})
    if not inv:
        raise HTTPException(status_code=404, detail="Jadwal AR tidak ditemukan untuk deal ini")
    receipts = await db.receipts.find({"org_id": org, "deal_id": deal_id}, {"_id": 0}).sort("created_at", -1).to_list(200)
    liab = await db.contract_liabilities.find_one({"org_id": org, "deal_id": deal_id}, {"_id": 0})
    rev = await db.revenue_recognitions.find_one({"org_id": org, "deal_id": deal_id}, {"_id": 0})
    dep = await db.customer_deposits.find_one({"org_id": org, "deal_id": deal_id}, {"_id": 0})
    return {"data": serialize_doc(inv), "receipts": serialize_doc(receipts),
            "contract_liability": serialize_doc(liab), "revenue_recognition": serialize_doc(rev),
            "deposit": serialize_doc(dep)}


@router.post("/{deal_id}/schedule")
async def create_schedule(deal_id: str, payload: ArScheduleCreate,
                          user: dict = Depends(require_permission("finance", "create"))):
    org = user.get("org_id", ORG_ID)
    deal = await db.deals.find_one({"id": deal_id, "org_id": org}, {"_id": 0})
    if not deal:
        raise HTTPException(status_code=404, detail="Deal tidak ditemukan")
    try:
        inv = await fe.create_ar_for_deal(deal, scheme_id=payload.scheme_id, org_id=org,
                                          replace=True, actor=user.get("email"))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"data": serialize_doc(inv)}


@router.post("/receipts")
async def create_receipt(payload: ReceiptCreate,
                         user: dict = Depends(require_permission("finance", "create"))):
    if payload.amount <= 0:
        raise HTTPException(status_code=400, detail="Jumlah pembayaran harus lebih dari 0")
    try:
        res = await fe.apply_receipt(payload.deal_id, payload.amount, payload.method,
                                     payload.note, user.get("email"), user.get("org_id", ORG_ID),
                                     allow_overpay=payload.allow_overpay)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"data": serialize_doc(res)}


@router.post("/{deal_id}/bast")
async def bast(deal_id: str, user: dict = Depends(require_permission("finance", "update"))):
    org = user.get("org_id", ORG_ID)
    deal = await db.deals.find_one({"id": deal_id, "org_id": org}, {"_id": 0})
    if not deal:
        raise HTTPException(status_code=404, detail="Deal tidak ditemukan")
    rev = await fe.recognize_revenue(deal, org_id=org, actor=user.get("email"))
    return {"data": serialize_doc(rev)}
