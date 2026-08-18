"""Activity feed (+ comments/@mention) and in-app notifications."""
from fastapi import APIRouter, Depends, HTTPException

from db import db, ORG_ID
from core_utils import now_iso, serialize_doc, parse_pagination
from rbac import require_permission
from engine import add_activity, create_notification
from models import ActivityCreate, CommentCreate

router = APIRouter(tags=["collaboration"])


@router.get("/activities")
async def list_activities(entity_type: str, entity_id: str, skip: int = 0, limit: int = 50,
                          user: dict = Depends(require_permission("activities", "view"))):
    skip, limit = parse_pagination(skip, limit)
    q = {"org_id": user.get("org_id", ORG_ID), "entity_type": entity_type, "entity_id": entity_id}
    total = await db.activities.count_documents(q)
    rows = await db.activities.find(q, {"_id": 0}).sort("created_at", -1).skip(skip).limit(limit).to_list(limit)
    return {"data": serialize_doc(rows), "total": total}


@router.post("/activities")
async def create_activity(payload: ActivityCreate,
                          user: dict = Depends(require_permission("activities", "create"))):
    doc = await add_activity(
        entity_type=payload.entity_type, entity_id=payload.entity_id, body=payload.body,
        type=payload.type, actor=user.get("email"), mentions=payload.mentions,
        parent_id=payload.parent_id, org_id=user.get("org_id", ORG_ID),
    )
    return {"data": serialize_doc(doc)}


@router.post("/activities/{activity_id}/comment")
async def reply_comment(activity_id: str, payload: CommentCreate,
                        user: dict = Depends(require_permission("activities", "create"))):
    parent = await db.activities.find_one({"id": activity_id}, {"_id": 0})
    if not parent:
        raise HTTPException(status_code=404, detail="Aktivitas tidak ditemukan")
    doc = await add_activity(
        entity_type=parent["entity_type"], entity_id=parent["entity_id"], body=payload.body,
        type="comment", actor=user.get("email"), mentions=payload.mentions,
        parent_id=activity_id, org_id=user.get("org_id", ORG_ID),
    )
    return {"data": serialize_doc(doc)}


@router.get("/notifications")
async def list_notifications(unread_only: bool = False, skip: int = 0, limit: int = 50,
                             user: dict = Depends(require_permission("notifications", "view"))):
    skip, limit = parse_pagination(skip, limit)
    q = {"org_id": user.get("org_id", ORG_ID), "user_email": user.get("email")}
    if unread_only:
        q["read"] = False
    total = await db.notifications.count_documents(q)
    unread = await db.notifications.count_documents({**q, "read": False})
    rows = await db.notifications.find(q, {"_id": 0}).sort("created_at", -1).skip(skip).limit(limit).to_list(limit)
    return {"data": serialize_doc(rows), "total": total, "unread": unread}


@router.post("/notifications/{notif_id}/read")
async def mark_read(notif_id: str, user: dict = Depends(require_permission("notifications", "update"))):
    res = await db.notifications.update_one(
        {"id": notif_id, "user_email": user.get("email")}, {"$set": {"read": True, "read_at": now_iso()}})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Notifikasi tidak ditemukan")
    return {"message": "Ditandai sudah dibaca"}


@router.post("/notifications/read-all")
async def mark_all_read(user: dict = Depends(require_permission("notifications", "update"))):
    await db.notifications.update_many(
        {"user_email": user.get("email"), "read": False}, {"$set": {"read": True, "read_at": now_iso()}})
    return {"message": "Semua notifikasi ditandai dibaca"}
