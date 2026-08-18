"""Marketing Fee agen/broker/referral eksternal (Fase 27).

SoD: sales/marketing mengajukan, finance/owner menyetujui & membayar.
"""
from fastapi import APIRouter, Depends, HTTPException

import marketing_fee as mf
from core_utils import parse_pagination, serialize_doc
from db import db, ORG_ID
from models_p27 import (AgentCreate, AgentUpdate, MarketingFeeCreate, MarketingFeePay,
                        NoteOnly)
from rbac import audit_log, can, require_permission

router = APIRouter(prefix="/marketing", tags=["marketing-fee"])


@router.get("/agents")
async def list_agents(status: str = None, skip: int = 0, limit: int = 100,
                      user: dict = Depends(require_permission("marketing_fee", "view"))):
    skip, limit = parse_pagination(skip, limit)
    q = {"org_id": user.get("org_id", ORG_ID)}
    if status:
        q["status"] = status
    total = await db.agents.count_documents(q)
    rows = await db.agents.find(q, {"_id": 0}).sort("name", 1).skip(skip).limit(limit).to_list(limit)
    return {"data": serialize_doc(rows), "total": total}


@router.post("/agents")
async def create_agent(payload: AgentCreate,
                       user: dict = Depends(require_permission("marketing_fee", "create"))):
    try:
        doc = await mf.create_agent(payload, user.get("email"), user.get("org_id", ORG_ID))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    await audit_log(user, "create", "marketing_fee_agent", doc["id"])
    return {"data": serialize_doc(doc)}


@router.put("/agents/{agent_id}")
async def update_agent(agent_id: str, payload: AgentUpdate,
                       user: dict = Depends(require_permission("marketing_fee", "update"))):
    try:
        doc = await mf.update_agent(agent_id, payload, user.get("email"),
                                    user.get("org_id", ORG_ID))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    await audit_log(user, "update", "marketing_fee_agent", agent_id)
    return {"data": serialize_doc(doc)}


@router.get("/fees")
async def list_fees(status: str = None, agent_id: str = None, skip: int = 0, limit: int = 100,
                    user: dict = Depends(require_permission("marketing_fee", "view"))):
    skip, limit = parse_pagination(skip, limit)
    q = {"org_id": user.get("org_id", ORG_ID)}
    if not await can(user.get("role"), "marketing_fee", "view_all"):
        q["requested_by"] = user.get("email")
    if status:
        q["status"] = status
    if agent_id:
        q["agent_id"] = agent_id
    total = await db.marketing_fees.count_documents(q)
    rows = await db.marketing_fees.find(q, {"_id": 0}).sort("created_at", -1) \
        .skip(skip).limit(limit).to_list(limit)
    return {"data": serialize_doc(rows), "total": total,
            "can_approve": await can(user.get("role"), "marketing_fee", "approve")}


@router.get("/summary")
async def summary(user: dict = Depends(require_permission("marketing_fee", "view"))):
    return {"data": await mf.summary(user.get("org_id", ORG_ID))}


@router.get("/fees/{fee_id}")
async def fee_detail(fee_id: str,
                     user: dict = Depends(require_permission("marketing_fee", "view"))):
    org = user.get("org_id", ORG_ID)
    doc = await db.marketing_fees.find_one({"id": fee_id, "org_id": org}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Pengajuan marketing fee tidak ditemukan.")
    agent = await db.agents.find_one({"id": doc["agent_id"], "org_id": org}, {"_id": 0})
    return {"data": serialize_doc(doc), "agent": serialize_doc(agent)}


@router.post("/fees")
async def create_fee(payload: MarketingFeeCreate,
                     user: dict = Depends(require_permission("marketing_fee", "create"))):
    try:
        doc = await mf.create_fee(payload, user.get("email"), user.get("org_id", ORG_ID))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    await audit_log(user, "create", "marketing_fee", doc["id"], {"gross": doc["amount_gross"]})
    return {"data": serialize_doc(doc)}


@router.post("/fees/{fee_id}/approve")
async def approve_fee(fee_id: str, payload: NoteOnly,
                      user: dict = Depends(require_permission("marketing_fee", "approve"))):
    try:
        doc = await mf.approve_fee(fee_id, user.get("email"), payload.note,
                                   user.get("org_id", ORG_ID))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    await audit_log(user, "approve", "marketing_fee", fee_id, {"net": doc["amount_net"]})
    return {"data": serialize_doc(doc)}


@router.post("/fees/{fee_id}/reject")
async def reject_fee(fee_id: str, payload: NoteOnly,
                     user: dict = Depends(require_permission("marketing_fee", "approve"))):
    try:
        doc = await mf.reject_fee(fee_id, user.get("email"), payload.note,
                                  user.get("org_id", ORG_ID))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    await audit_log(user, "reject", "marketing_fee", fee_id)
    return {"data": serialize_doc(doc)}


@router.post("/fees/{fee_id}/pay")
async def pay_fee(fee_id: str, payload: MarketingFeePay,
                  user: dict = Depends(require_permission("marketing_fee", "approve"))):
    try:
        doc = await mf.pay_fee(fee_id, payload.amount, payload.source, payload.note,
                               user.get("email"), user.get("org_id", ORG_ID))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    await audit_log(user, "pay", "marketing_fee", fee_id, {"amount": doc.get("paid_amount")})
    return {"data": serialize_doc(doc)}
