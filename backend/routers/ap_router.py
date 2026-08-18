"""AP (utang subcon) tipis: bills manual + retensi + approval + pembayaran + aging."""
from fastapi import APIRouter, Depends, HTTPException

from db import db, ORG_ID
from core_utils import serialize_doc, parse_pagination
from rbac import require_permission
import finance_engine as fe
from models import ApBillCreate, ApPay

router = APIRouter(prefix="/finance/ap", tags=["finance-ap"])


@router.get("/bills")
async def list_bills(status: str = None, skip: int = 0, limit: int = 50,
                     user: dict = Depends(require_permission("finance", "view"))):
    org = user.get("org_id", ORG_ID)
    skip, limit = parse_pagination(skip, limit)
    q = {"org_id": org}
    if status:
        q["status"] = status
    total = await db.ap_invoices.count_documents(q)
    rows = await db.ap_invoices.find(q, {"_id": 0}).sort("created_at", -1).skip(skip).limit(limit).to_list(limit)
    return {"data": serialize_doc(rows), "total": total}


@router.get("/aging")
async def ap_aging(user: dict = Depends(require_permission("finance", "view"))):
    return {"data": await fe.ap_aging(user.get("org_id", ORG_ID))}


@router.post("/bills")
async def create_bill(payload: ApBillCreate,
                      user: dict = Depends(require_permission("finance", "create"))):
    if payload.claimed <= 0:
        raise HTTPException(status_code=400, detail="Nilai klaim harus lebih dari 0")
    bill = await fe.create_ap_bill(payload.vendor, payload.project_id, payload.claimed,
                                   payload.retention_pct, payload.due_date, payload.note,
                                   user.get("email"), user.get("org_id", ORG_ID))
    return {"data": serialize_doc(bill)}


@router.post("/bills/{bill_id}/approve")
async def approve_bill(bill_id: str,
                       user: dict = Depends(require_permission("finance", "approve"))):
    try:
        bill = await fe.approve_ap_bill(bill_id, user.get("email"), user.get("org_id", ORG_ID))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"data": serialize_doc(bill)}


@router.post("/bills/{bill_id}/pay")
async def pay_bill(bill_id: str, payload: ApPay,
                   user: dict = Depends(require_permission("finance", "approve"))):
    if payload.amount <= 0:
        raise HTTPException(status_code=400, detail="Jumlah bayar harus lebih dari 0")
    try:
        bill = await fe.pay_ap_bill(bill_id, payload.amount, payload.note,
                                    user.get("email"), user.get("org_id", ORG_ID))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"data": serialize_doc(bill)}


@router.get("/payments")
async def list_payments(bill_id: str = None, skip: int = 0, limit: int = 50,
                        user: dict = Depends(require_permission("finance", "view"))):
    """Riwayat pembayaran keluar. Sebelum audit koleksi `payments_out` DITULIS tapi tidak
    punya endpoint baca sama sekali, jadi bukti pembayaran tidak bisa ditelusuri."""
    skip, limit = parse_pagination(skip, limit)
    q = {"org_id": user.get("org_id", ORG_ID)}
    if bill_id:
        q["bill_id"] = bill_id
    total = await db.payments_out.count_documents(q)
    rows = await db.payments_out.find(q, {"_id": 0}).sort("created_at", -1).skip(skip).limit(limit).to_list(limit)
    paid_total = 0
    async for r in db.payments_out.aggregate([{"$match": q}, {"$group": {"_id": None, "s": {"$sum": "$amount"}}}]):
        paid_total = int(r.get("s") or 0)
    return {"data": serialize_doc(rows), "total": total, "summary": {"paid_total": paid_total}}
