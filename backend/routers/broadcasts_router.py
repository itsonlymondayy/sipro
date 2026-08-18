"""EPIC 1.7 — Broadcast / Campaign blast (WhatsApp templates, SIMULATION).

Send a pre-approved WA template to a SEGMENT of leads and/or customers. Because a
broadcast always uses a template it bypasses the 24h session window (that is the
WA purpose of templates). Delivery is simulated (sent -> delivered -> read) and a
per-recipient audit is stored. For lead recipients that already have an inbox
conversation, the outbound template message is appended so the blast is visible in
the Inbox. Go-live later by setting channel_accounts.mode='live' — the contract is
identical.
"""
from fastapi import APIRouter, Depends, HTTPException
from typing import List
from pydantic import BaseModel

from db import db, ORG_ID
from core_utils import new_id, now_iso, serialize_doc, parse_pagination
from rbac import require_permission
from engine import send_template_message

router = APIRouter(prefix="/broadcasts", tags=["broadcasts"])

SAMPLE_SIZE = 8


class BroadcastSegment(BaseModel):
    lead_stages: List[str] = []
    score_bands: List[str] = []
    sources: List[str] = []
    campaigns: List[str] = []
    include_customers: bool = False


class BroadcastPreview(BaseModel):
    segment: BroadcastSegment = BroadcastSegment()


class BroadcastCreate(BaseModel):
    name: str
    template_code: str
    segment: BroadcastSegment = BroadcastSegment()


def _seg_dict(seg) -> dict:
    return {
        "lead_stages": list(seg.lead_stages or []),
        "score_bands": list(seg.score_bands or []),
        "sources": list(seg.sources or []),
        "campaigns": list(seg.campaigns or []),
        "include_customers": bool(seg.include_customers),
    }


async def _resolve_recipients(org: str, seg: dict) -> list:
    """Resolve unique (by phone) recipients from leads (+ customers) matching the segment."""
    q = {"org_id": org, "phone": {"$nin": [None, ""]}}
    if seg["lead_stages"]:
        q["stage"] = {"$in": seg["lead_stages"]}
    if seg["score_bands"]:
        q["score_band"] = {"$in": seg["score_bands"]}
    if seg["sources"]:
        q["source"] = {"$in": seg["sources"]}
    if seg["campaigns"]:
        q["campaign"] = {"$in": seg["campaigns"]}
    leads = await db.leads.find(
        q, {"_id": 0, "id": 1, "name": 1, "phone": 1, "stage": 1, "source": 1, "campaign": 1}
    ).to_list(5000)
    recips = [{"kind": "lead", "ref_id": l["id"], "lead_id": l["id"], "name": l.get("name"),
               "phone": l.get("phone"), "stage": l.get("stage"), "source": l.get("source")}
              for l in leads]
    if seg["include_customers"]:
        cust = await db.customers.find(
            {"org_id": org, "phone": {"$nin": [None, ""]}},
            {"_id": 0, "id": 1, "name": 1, "phone": 1}).to_list(5000)
        recips += [{"kind": "customer", "ref_id": c["id"], "lead_id": None, "name": c.get("name"),
                    "phone": c.get("phone"), "stage": None, "source": "customer"} for c in cust]
    seen, uniq = set(), []
    for r in recips:
        if r["phone"] in seen:
            continue
        seen.add(r["phone"])
        uniq.append(r)
    return uniq


@router.post("/preview")
async def preview_broadcast(p: BroadcastPreview,
                            user: dict = Depends(require_permission("broadcasts", "manage"))):
    org = user.get("org_id", ORG_ID)
    seg = _seg_dict(p.segment)
    recips = await _resolve_recipients(org, seg)
    by_kind = {"lead": 0, "customer": 0}
    for r in recips:
        by_kind[r["kind"]] = by_kind.get(r["kind"], 0) + 1
    return {"data": {"total": len(recips), "by_kind": by_kind,
                     "sample": serialize_doc(recips[:SAMPLE_SIZE])}}


@router.post("")
async def create_broadcast(p: BroadcastCreate,
                           user: dict = Depends(require_permission("broadcasts", "manage"))):
    org = user.get("org_id", ORG_ID)
    tmpl = await db.wa_templates.find_one({"org_id": org, "code": p.template_code}, {"_id": 0})
    if not tmpl:
        raise HTTPException(404, "Template WA tidak ditemukan.")
    seg = _seg_dict(p.segment)
    recips = await _resolve_recipients(org, seg)
    if not recips:
        raise HTTPException(400, "Segmen tidak menghasilkan penerima. Longgarkan filter.")
    ts = now_iso()
    bid = new_id()
    # Deterministic simulation: everyone 'sent' & 'delivered'; ~60% 'read'.
    sent = delivered = len(recips)
    read = 0
    recipient_docs = []
    for idx, r in enumerate(recips):
        is_read = (idx % 5) < 3  # ~60%
        if is_read:
            read += 1
        recipient_docs.append({
            "id": new_id(), "org_id": org, "broadcast_id": bid, "kind": r["kind"],
            "ref_id": r["ref_id"], "lead_id": r.get("lead_id"), "name": r.get("name"),
            "phone": r.get("phone"), "status": "read" if is_read else "delivered",
            "delivered_at": ts, "read_at": ts if is_read else None, "created_at": ts,
        })
        # Mirror into an existing lead conversation so the blast shows in Inbox.
        if r.get("lead_id"):
            conv = await db.conversations.find_one({"org_id": org, "lead_id": r["lead_id"]})
            if conv:
                await send_template_message(conv, tmpl, org, actor="broadcast")
    if recipient_docs:
        await db.broadcast_recipients.insert_many(recipient_docs)
    doc = {
        "id": bid, "org_id": org, "name": p.name, "template_code": tmpl["code"],
        "template_name": tmpl.get("name"), "segment": seg, "channel": "whatsapp",
        "mode": "simulation", "status": "completed",
        "total": len(recips), "sent": sent, "delivered": delivered, "read": read, "failed": 0,
        "created_by": user.get("email"), "created_at": ts, "updated_at": ts,
    }
    await db.broadcasts.insert_one(doc)
    doc.pop("_id", None)
    return {"data": serialize_doc(doc)}


@router.get("")
async def list_broadcasts(skip: int = 0, limit: int = 50,
                          user: dict = Depends(require_permission("broadcasts", "view"))):
    org = user.get("org_id", ORG_ID)
    skip, limit = parse_pagination(skip, limit)
    total = await db.broadcasts.count_documents({"org_id": org})
    rows = await db.broadcasts.find({"org_id": org}, {"_id": 0}).sort(
        "created_at", -1).skip(skip).limit(limit).to_list(limit)
    return {"data": serialize_doc(rows), "total": total}


@router.get("/{broadcast_id}")
async def get_broadcast(broadcast_id: str,
                        user: dict = Depends(require_permission("broadcasts", "view"))):
    org = user.get("org_id", ORG_ID)
    b = await db.broadcasts.find_one({"id": broadcast_id, "org_id": org}, {"_id": 0})
    if not b:
        raise HTTPException(404, "Broadcast tidak ditemukan.")
    recips = await db.broadcast_recipients.find(
        {"org_id": org, "broadcast_id": broadcast_id}, {"_id": 0}).sort("created_at", 1).to_list(2000)
    return {"data": {"broadcast": serialize_doc(b), "recipients": serialize_doc(recips)}}
